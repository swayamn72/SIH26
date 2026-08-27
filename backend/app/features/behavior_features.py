from typing import Any

import pandas as pd


_RETENTION_FORMULA = "1 - (one_to_one_matched_24h_outflow) / (total_inflow)"
_HOLDING_FORMULA = "median time from credit to one_to_one_matched debit within 24h"
_TURNOVER_FORMULA = "(total_debit + total_credit) / positive_average_daily_balance"


def _one_to_one_24h_matches(df: pd.DataFrame) -> list[tuple[int, int]]:
    """Pair each credit with at most one later debit in its inclusive 24-hour window.

    A debit is consumed once matched, preventing one outflow from being counted
    against several credits. The statement order is used as a stable tie-breaker
    for identical timestamps; transactions at the exact same timestamp are not
    ordered closely enough to infer a credit-to-debit flow.
    """
    if df.empty or "txn_date" not in df.columns:
        return []

    ordered = df.copy()
    ordered["_source_index"] = ordered.index
    ordered = ordered[ordered["txn_date"].notna()].sort_values(
        ["txn_date", "_source_index"], kind="stable"
    )
    used_debits: set[int] = set()
    matches: list[tuple[int, int]] = []

    for credit_index, credit_row in ordered.iterrows():
        credit_amount = credit_row.get("credit_amount")
        credit_time = credit_row.get("txn_date")
        if pd.isna(credit_amount) or credit_amount <= 0 or pd.isna(credit_time):
            continue

        window_end = credit_time + pd.Timedelta(hours=24)
        candidates = ordered[
            (ordered["txn_date"] > credit_time)
            & (ordered["txn_date"] <= window_end)
            & (ordered["debit_amount"].notna())
            & (ordered["debit_amount"] > 0)
        ]
        for debit_index, _ in candidates.iterrows():
            if debit_index not in used_debits:
                used_debits.add(debit_index)
                matches.append((credit_index, debit_index))
                break

    return matches


def net_retention_ratio(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty or "credit_amount" not in df.columns:
        return None, _RETENTION_FORMULA, "Net retention ratio"

    credits = df["credit_amount"].dropna()
    total_credit = float(credits.sum()) if not credits.empty else 0.0
    if total_credit <= 0:
        return 1.0, _RETENTION_FORMULA, "Net retention ratio"

    matched_debit_indexes = [debit_index for _, debit_index in _one_to_one_24h_matches(df)]
    outflow_24h = float(df.loc[matched_debit_indexes, "debit_amount"].sum()) if matched_debit_indexes else 0.0
    retention = 1.0 - (outflow_24h / total_credit)
    return float(max(retention, 0.0)), _RETENTION_FORMULA, "Net retention ratio"


def median_holding_time_hours(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty or "txn_date" not in df.columns:
        return None, _HOLDING_FORMULA, "Median holding time"

    matched_pairs: list[float] = []
    for credit_index, debit_index in _one_to_one_24h_matches(df):
        credit_date = df.at[credit_index, "txn_date"]
        debit_date = df.at[debit_index, "txn_date"]
        hours = (debit_date - credit_date).total_seconds() / 3600
        if hours > 0:
            matched_pairs.append(hours)

    if not matched_pairs:
        return None, _HOLDING_FORMULA, "Median holding time"

    return float(pd.Series(matched_pairs).median()), _HOLDING_FORMULA, "Median holding time"


def turnover_ratio(df: pd.DataFrame, avg_daily_balance: float | None = None) -> tuple[float | None, str, str]:
    """Return debit-plus-credit turnover only when the balance dependency is valid.

    Turnover intentionally counts both positive debit and credit flows. A missing,
    zero, or negative average daily balance makes the ratio unavailable rather than
    inventing a denominator; a statement with no positive flow has turnover zero.
    """
    if df.empty:
        return None, _TURNOVER_FORMULA, "Turnover ratio; debit plus credit over positive average daily balance"
    total_debit = float(df["debit_amount"].dropna().sum())
    total_credit = float(df["credit_amount"].dropna().sum())
    total_flow = total_debit + total_credit
    if total_flow <= 0:
        return 0.0, _TURNOVER_FORMULA, "Turnover ratio; debit plus credit over positive average daily balance"
    if avg_daily_balance is None or avg_daily_balance <= 0:
        return None, _TURNOVER_FORMULA, "Unavailable: average daily balance is missing, zero, or negative"
    ratio = total_flow / avg_daily_balance
    return float(ratio), _TURNOVER_FORMULA, "Turnover ratio; debit plus credit over positive average daily balance"


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
