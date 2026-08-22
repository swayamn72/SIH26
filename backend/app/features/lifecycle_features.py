from datetime import date, timedelta
from typing import Any

import pandas as pd

from app.config_loader import load_config


def account_age_days_observed(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty or "txn_date" not in df.columns:
        return None, "max(txn_date) - min(txn_date)", "Observed window span"
    start = df["txn_date"].min()
    end = df["txn_date"].max()
    if pd.isna(start) or pd.isna(end):
        return None, "max(txn_date) - min(txn_date)", "Observed window span"
    age = (end - start).days
    return float(age), "max(txn_date) - min(txn_date)", "Observed window span"


def dormancy_breaks(df: pd.DataFrame) -> tuple[float | None, str, str]:
    cfg = load_config("thresholds")
    d = cfg.get("dormancy", {})
    gap_days = d.get("gap_days", 30)
    burst_min = d.get("burst_min_transactions", 3)
    burst_window = d.get("burst_window_days", 3)

    if df.empty or "txn_date" not in df.columns:
        return None, "count of gaps > gap_days followed by burst", "Dormancy-then-burst count"

    sorted_dates = df["txn_date"].dropna().sort_values().unique()
    if len(sorted_dates) < 2:
        return 0.0, "count of gaps > gap_days followed by burst", "Dormancy-then-burst count"

    breaks = 0
    i = 0
    while i < len(sorted_dates) - 1:
        gap = (sorted_dates[i + 1] - sorted_dates[i]).days
        if gap > gap_days:
            burst_start = i + 1
            burst_end = burst_start
            while burst_end < len(sorted_dates) and (sorted_dates[burst_end] - sorted_dates[burst_start]).days <= burst_window:
                burst_end += 1
            burst_count = burst_end - burst_start
            if burst_count >= burst_min:
                breaks += 1
            i = burst_end
        else:
            i += 1

    return float(breaks), "count of gaps > gap_days followed by burst", "Dormancy-then-burst count"


def first_week_activity_ratio(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty or "txn_date" not in df.columns:
        return None, "txn_count(first_7_days) / total_txn_count", "First-week activity ratio"
    sorted_dates = df["txn_date"].dropna().sort_values()
    if len(sorted_dates) < 2:
        return None, "txn_count(first_7_days) / total_txn_count", "First-week activity ratio"
    first_date = sorted_dates.iloc[0]
    week_end = first_date + timedelta(days=7)
    first_week_count = int((sorted_dates <= week_end).sum())
    ratio = first_week_count / len(sorted_dates)
    return float(ratio), "txn_count(first_7_days) / total_txn_count", "First-week activity ratio"


def days_since_last_activity(df: pd.DataFrame, reference_date: date | None = None) -> tuple[float | None, str, str]:
    if df.empty or "txn_date" not in df.columns:
        return None, "reference_date - max(txn_date)", "Days since last activity"
    last = df["txn_date"].max()
    if pd.isna(last):
        return None, "reference_date - max(txn_date)", "Days since last activity"
    ref = reference_date or date.today()
    delta = (ref - last).days
    return float(max(delta, 0)), "reference_date - max(txn_date)", "Days since last activity"
