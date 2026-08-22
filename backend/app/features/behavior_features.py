from decimal import Decimal
from typing import Any

import pandas as pd


def net_retention_ratio(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty:
        return None, "1 - (matched_24h_outflow) / (total_inflow)", "Net retention ratio"
    credits = df["credit_amount"].dropna()
    total_credit = float(credits.sum()) if not credits.empty else 0.0
    if total_credit <= 0:
        return 1.0, "1 - (matched_24h_outflow) / (total_inflow)", "Net retention ratio"

    outflow_24h = 0.0
    for _, credit_row in df.iterrows():
        if pd.notna(credit_row.get("credit_amount")) and credit_row["credit_amount"] > 0:
            txn_time = credit_row.get("txn_date")
            if pd.notna(txn_time):
                window = df[
                    (df["txn_date"] > txn_time)
                    & (df["debit_amount"].notna())
                    & (df["debit_amount"] > 0)
                ]
                if not window.empty:
                    outflow_24h += float(window["debit_amount"].iloc[0])

    retention = 1.0 - (outflow_24h / total_credit)
    return float(max(retention, 0)), "1 - (matched_24h_outflow) / (total_inflow)", "Net retention ratio"


def median_holding_time_hours(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty or "txn_date" not in df.columns:
        return None, "median time from credit to matched debit", "Median holding time"
    matched_pairs: list[float] = []
    sorted_df = df.sort_values("txn_date")
    for _, credit_row in sorted_df.iterrows():
        if pd.notna(credit_row.get("credit_amount")) and credit_row["credit_amount"] > 0:
            credit_date = credit_row["txn_date"]
            follow_debits = sorted_df[
                (sorted_df["txn_date"] > credit_date)
                & (sorted_df["debit_amount"].notna())
                & (sorted_df["debit_amount"] > 0)
            ]
            if not follow_debits.empty:
                next_debit_date = follow_debits.iloc[0]["txn_date"]
                hours = (next_debit_date - credit_date).total_seconds() / 3600
                if hours > 0:
                    matched_pairs.append(hours)

    if not matched_pairs:
        return None, "median time from credit to matched debit", "Median holding time"

    matched_pairs.sort()
    median = matched_pairs[len(matched_pairs) // 2]
    return float(median), "median time from credit to matched debit", "Median holding time"


def turnover_ratio(df: pd.DataFrame, avg_daily_balance: float | None = None) -> tuple[float | None, str, str]:
    if df.empty:
        return None, "(total_debit + total_credit) / average_daily_balance", "Turnover ratio"
    total_debit = float(df["debit_amount"].dropna().sum())
    total_credit = float(df["credit_amount"].dropna().sum())
    total_flow = total_debit + total_credit
    if total_flow <= 0:
        return 0.0, "(total_debit + total_credit) / average_daily_balance", "Turnover ratio"
    if avg_daily_balance is None or avg_daily_balance <= 0:
        return None, "(total_debit + total_credit) / average_daily_balance", "Turnover ratio"
    ratio = total_flow / avg_daily_balance
    return float(ratio), "(total_debit + total_credit) / average_daily_balance", "Turnover ratio"


def average_daily_balance(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty or "balance_after" not in df.columns:
        return None, "area_under_balance_curve / days", "Average daily balance"
    balance_col = df["balance_after"].dropna()
    if balance_col.empty:
        return None, "area_under_balance_curve / days", "Average daily balance"
    date_col = df.loc[balance_col.index, "txn_date"].dropna()
    if date_col.empty:
        return float(balance_col.mean()), "area_under_balance_curve / days", "Average daily balance"

    data = pd.DataFrame({"date": date_col, "balance": balance_col}).sort_values("date")
    if len(data) < 2:
        return float(data["balance"].iloc[0]), "area_under_balance_curve / days", "Average daily balance"

    total_area = 0.0
    total_days = 0.0
    for i in range(len(data) - 1):
        d1, b1 = data.iloc[i]["date"], float(data.iloc[i]["balance"])
        d2, b2 = data.iloc[i + 1]["date"], float(data.iloc[i + 1]["balance"])
        days = (d2 - d1).days
        if days > 0:
            area = (b1 + b2) / 2 * days
            total_area += area
            total_days += days

    if total_days <= 0:
        return float(data["balance"].iloc[0]), "area_under_balance_curve / days", "Average daily balance"
    return float(total_area / total_days), "area_under_balance_curve / days", "Average daily balance"
