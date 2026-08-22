from typing import Any

import pandas as pd


def name_consistency_flag(account_holder: str | None, parsed_names: list[str]) -> tuple[int | None, str, str]:
    if not account_holder or not parsed_names:
        return None, "1 if all parsed names match account holder", "Name consistency flag"
    all_match = all(account_holder.strip().lower() == n.strip().lower() for n in parsed_names)
    return 0 if all_match else 1, "1 if all parsed names match account holder", "Name consistency flag"


def counterparty_concentration_hhi(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty or "counterparty_id" not in df.columns:
        return None, "sum((value_share_i)^2) across counterparties", "Counterparty concentration (HHI)"

    flow = df["debit_amount"].fillna(0).abs() + df["credit_amount"].fillna(0).abs()
    if flow.sum() == 0:
        return None, "sum((value_share_i)^2) across counterparties", "Counterparty concentration (HHI)"

    shares = flow.groupby(df["counterparty_id"]).sum()
    total = shares.sum()
    if total == 0:
        return None, "sum((value_share_i)^2) across counterparties", "Counterparty concentration (HHI)"

    hhi = sum((s / total) ** 2 for s in shares)
    return float(hhi), "sum((value_share_i)^2) across counterparties", "Counterparty concentration (HHI)"
