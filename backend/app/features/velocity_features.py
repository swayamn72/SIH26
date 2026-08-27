from datetime import datetime

import pandas as pd

from app.config_loader import load_config


_TRAILING_24H_FORMULA = "max txn count in any trailing inclusive 24h interval"
_PEAK_DAILY_FORMULA = "max txn count on a calendar day (date precision only)"


def _has_timestamp_precision(values: pd.Series) -> bool:
    return any(isinstance(value, (pd.Timestamp, datetime)) for value in values.dropna())


def inflow_outflow_velocity(df: pd.DataFrame) -> tuple[int | None, str, str]:
    """Measure a true trailing 24-hour peak only when statement times are present.

    Canonical statement records currently retain date-only transaction values. For
    those records, returning a rolling-24-hour value would overstate precision, so
    this returns an explicitly labelled peak-calendar-day count instead.
    """
    if df.empty or "txn_date" not in df.columns:
        return None, _TRAILING_24H_FORMULA, "Peak transaction velocity unavailable"

    dates = df["txn_date"].dropna()
    if dates.empty:
        return None, _TRAILING_24H_FORMULA, "Peak transaction velocity unavailable"

    if not _has_timestamp_precision(dates):
        daily_counts = pd.to_datetime(dates).dt.normalize().value_counts()
        return int(daily_counts.max()), _PEAK_DAILY_FORMULA, "Peak daily transaction count (date precision only)"

    timestamps = pd.to_datetime(dates).sort_values().reset_index(drop=True)
    max_count = 0
    start = 0
    for end, window_end in enumerate(timestamps):
        while window_end - timestamps.iloc[start] > pd.Timedelta(hours=24):
            start += 1
        max_count = max(max_count, end - start + 1)

    return max_count, _TRAILING_24H_FORMULA, "Peak transaction count in a trailing 24-hour interval"


def weekend_night_activity_ratio(df: pd.DataFrame) -> tuple[float | None, str, str]:
    cfg = load_config("thresholds")
    b = cfg.get("behavior", {})
    start_hour = b.get("midnight_hour_start", 22)
    end_hour = b.get("midnight_hour_end", 6)

    if df.empty or "txn_date" not in df.columns:
        return None, "fraction of txns outside banking hours/weekends", "Weekend/night ratio"

    total = len(df)
    if total == 0:
        return 0.0, "fraction of txns outside banking hours/weekends", "Weekend/night ratio"

    after_hours = 0
    for _, row in df.iterrows():
        dt = row.get("txn_date")
        is_weekend = dt.weekday() >= 5 if pd.notna(dt) else False
        has_time = False
        if has_time and (dt.hour >= start_hour or dt.hour < end_hour):
            after_hours += 1
        elif is_weekend:
            after_hours += 1

    return float(after_hours / total), "fraction of txns outside banking hours/weekends", "Weekend/night ratio"
