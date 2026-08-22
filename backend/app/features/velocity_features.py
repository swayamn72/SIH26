from typing import Any

import pandas as pd

from app.config_loader import load_config


def inflow_outflow_velocity(df: pd.DataFrame) -> tuple[int | None, str, str]:
    if df.empty or "txn_date" not in df.columns:
        return None, "max txn count in any rolling 24h window", "Peak 24h velocity"
    sorted_df = df.sort_values("txn_date")
    dates = sorted_df["txn_date"].dropna()
    if len(dates) < 2:
        return 1, "max txn count in any rolling 24h window", "Peak 24h velocity"

    max_count = 0
    for i in range(len(dates)):
        window_end = dates.iloc[i]
        window_start = window_end - pd.Timedelta(hours=24)
        # .sum() on a boolean Series already returns an int scalar.
        # Do NOT wrap with int() — that raises TypeError on multi-element Series.
        count = ((dates >= window_start) & (dates <= window_end)).sum()
        max_count = max(max_count, count)

    return max_count, "max txn count in any rolling 24h window", "Peak 24h velocity"


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
