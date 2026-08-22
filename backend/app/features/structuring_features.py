import math
from collections import Counter
from typing import Any

import pandas as pd

from app.config_loader import load_config


def _is_near_threshold(amount: float, thresholds: list[dict]) -> bool:
    for band in thresholds:
        threshold = band.get("threshold", 50000)
        lower_pct = band.get("lower_pct", 0.90)
        lower = threshold * lower_pct
        if lower <= amount <= threshold:
            return True
    return False


def near_threshold_ratio(df: pd.DataFrame) -> tuple[float | None, str, str]:
    cfg = load_config("thresholds")
    bands = cfg.get("structuring", {}).get("near_threshold_bands", [{"threshold": 50000, "lower_pct": 0.90}])

    if df.empty:
        return None, "fraction of txns within threshold band", "Near-threshold ratio"

    amounts = pd.concat([df["debit_amount"].dropna(), df["credit_amount"].dropna()])
    if amounts.empty:
        return 0.0, "fraction of txns within threshold band", "Near-threshold ratio"

    near_count = sum(1 for a in amounts if _is_near_threshold(float(a), bands))
    return float(near_count / len(amounts)), "fraction of txns within threshold band", "Near-threshold ratio"


def round_number_ratio(df: pd.DataFrame) -> tuple[float | None, str, str]:
    cfg = load_config("thresholds")
    moduli = cfg.get("structuring", {}).get("round_number_moduli", [1000, 10000])

    if df.empty:
        return None, "fraction of txns that are round multiples", "Round-number ratio"

    amounts = pd.concat([df["debit_amount"].dropna(), df["credit_amount"].dropna()])
    if amounts.empty:
        return 0.0, "fraction of txns that are round multiples", "Round-number ratio"

    round_count = 0
    nonzero_count = 0
    for a in amounts:
        val = float(a)
        if val > 0:
            nonzero_count += 1
            for m in moduli:
                if abs(val % m) < 0.01:
                    round_count += 1
                    break

    if nonzero_count == 0:
        return 0.0, "fraction of txns that are round multiples", "Round-number ratio"
    return float(round_count / nonzero_count), "fraction of txns that are round multiples", "Round-number ratio"


def benford_deviation_score(df: pd.DataFrame) -> tuple[float | None, str, str]:
    cfg = load_config("thresholds")
    sig_level = cfg.get("benford", {}).get("significance_level", 0.95)

    if df.empty:
        return None, "chi_sq = sum((observed - expected)^2 / expected)", "Benford deviation"

    amounts = pd.concat([df["debit_amount"].dropna(), df["credit_amount"].dropna()])
    amounts = amounts[amounts > 0]
    if len(amounts) < 10:
        return None, "chi_sq = sum((observed - expected)^2 / expected)", "Benford deviation"

    leading_digits = [int(str(abs(int(float(a))))[0]) for a in amounts if abs(int(float(a))) > 0]
    if not leading_digits:
        return None, "chi_sq = sum((observed - expected)^2 / expected)", "Benford deviation"

    observed = Counter(leading_digits)
    n = len(leading_digits)
    chi_sq = 0.0
    for d in range(1, 10):
        expected_p = math.log10(1 + 1 / d)
        expected_n = expected_p * n
        obs_n = observed.get(d, 0)
        chi_sq += (obs_n - expected_n) ** 2 / max(expected_n, 1)

    return float(chi_sq), "chi_sq = sum((observed - expected)^2 / expected)", "Benford deviation"


def fan_in_score(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty or "counterparty_id" not in df.columns:
        return None, "distinct counterparties sending in / txn count", "Fan-in score"
    credits = df[df["credit_amount"].notna() & (df["credit_amount"] > 0)]
    if len(credits) == 0:
        return 0.0, "distinct counterparties sending in / txn count", "Fan-in score"
    distinct = credits["counterparty_id"].nunique()
    return float(distinct / len(credits)), "distinct counterparties sending in / txn count", "Fan-in score"


def fan_out_score(df: pd.DataFrame) -> tuple[float | None, str, str]:
    if df.empty or "counterparty_id" not in df.columns:
        return None, "distinct counterparties receiving out / txn count", "Fan-out score"
    debits = df[df["debit_amount"].notna() & (df["debit_amount"] > 0)]
    if len(debits) == 0:
        return 0.0, "distinct counterparties receiving out / txn count", "Fan-out score"
    distinct = debits["counterparty_id"].nunique()
    return float(distinct / len(debits)), "distinct counterparties receiving out / txn count", "Fan-out score"
