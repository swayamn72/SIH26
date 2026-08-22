from typing import Any, Callable

import pandas as pd

from app.features import lifecycle_features as lf
from app.features import behavior_features as bf
from app.features import velocity_features as vf
from app.features import structuring_features as sf
from app.features import identity_proxy_features as ipf

FeatureFn = Callable[[pd.DataFrame], tuple[Any, str, str]]


REGISTRY: dict[str, dict[str, Any]] = {
    "account_age_days_observed": {
        "fn": lf.account_age_days_observed,
        "family": "lifecycle",
        "formula": "max(txn_date) - min(txn_date)",
        "description": "Observed window span",
        "source_module": "lifecycle_features",
    },
    "dormancy_breaks": {
        "fn": lf.dormancy_breaks,
        "family": "lifecycle",
        "formula": "count of gaps > 30d followed by burst of >=3 txns within 3d",
        "description": "Dormancy-then-burst count",
        "source_module": "lifecycle_features",
    },
    "first_week_activity_ratio": {
        "fn": lf.first_week_activity_ratio,
        "family": "lifecycle",
        "formula": "txn_count(first_7_days) / total_txn_count",
        "description": "First-week activity ratio",
        "source_module": "lifecycle_features",
    },
    "days_since_last_activity": {
        "fn": lf.days_since_last_activity,
        "family": "lifecycle",
        "formula": "reference_date - max(txn_date)",
        "description": "Days since last activity",
        "source_module": "lifecycle_features",
    },
    "net_retention_ratio": {
        "fn": bf.net_retention_ratio,
        "family": "behavior",
        "formula": "1 - (matched_24h_outflow) / (total_inflow)",
        "description": "Net retention ratio",
        "source_module": "behavior_features",
    },
    "median_holding_time_hours": {
        "fn": bf.median_holding_time_hours,
        "family": "behavior",
        "formula": "median time from credit to matched debit",
        "description": "Median holding time",
        "source_module": "behavior_features",
    },
    # NOTE: average_daily_balance MUST come before turnover_ratio so that
    # compute_all_features() can read the already-computed avg balance value.
    "average_daily_balance": {
        "fn": bf.average_daily_balance,
        "family": "behavior",
        "formula": "area_under_balance_curve / days",
        "description": "Average daily balance",
        "source_module": "behavior_features",
    },
    "turnover_ratio": {
        "fn": bf.turnover_ratio,
        "family": "behavior",
        "formula": "(total_debit + total_credit) / average_daily_balance",
        "description": "Turnover ratio",
        "source_module": "behavior_features",
    },
    "inflow_outflow_velocity": {
        "fn": vf.inflow_outflow_velocity,
        "family": "velocity",
        "formula": "max txn count in any rolling 24h window",
        "description": "Peak 24h velocity",
        "source_module": "velocity_features",
    },
    "weekend_night_activity_ratio": {
        "fn": vf.weekend_night_activity_ratio,
        "family": "velocity",
        "formula": "fraction of txns outside banking hours/weekends",
        "description": "Weekend/night ratio",
        "source_module": "velocity_features",
    },
    "near_threshold_ratio": {
        "fn": sf.near_threshold_ratio,
        "family": "structuring",
        "formula": "fraction of txns within threshold band",
        "description": "Near-threshold ratio",
        "source_module": "structuring_features",
    },
    "round_number_ratio": {
        "fn": sf.round_number_ratio,
        "family": "structuring",
        "formula": "fraction of txns that are round multiples",
        "description": "Round-number ratio",
        "source_module": "structuring_features",
    },
    "benford_deviation_score": {
        "fn": sf.benford_deviation_score,
        "family": "structuring",
        "formula": "chi_sq = sum((observed - expected)^2 / expected)",
        "description": "Benford deviation",
        "source_module": "structuring_features",
    },
    "fan_in_score": {
        "fn": sf.fan_in_score,
        "family": "structuring",
        "formula": "distinct counterparties sending in / txn count",
        "description": "Fan-in score",
        "source_module": "structuring_features",
    },
    "fan_out_score": {
        "fn": sf.fan_out_score,
        "family": "structuring",
        "formula": "distinct counterparties receiving out / txn count",
        "description": "Fan-out score",
        "source_module": "structuring_features",
    },
    "counterparty_concentration_hhi": {
        "fn": ipf.counterparty_concentration_hhi,
        "family": "network",
        "formula": "sum((value_share_i)^2) across counterparties",
        "description": "Counterparty concentration (HHI)",
        "source_module": "identity_proxy_features",
    },
    "name_consistency_flag": {
        "fn": ipf.name_consistency_flag,
        "family": "identity",
        "formula": "1 if name mismatch detected",
        "description": "Name consistency flag",
        "source_module": "identity_proxy_features",
    },
}


def compute_all_features(df: pd.DataFrame) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, entry in REGISTRY.items():
        try:
            fn = entry["fn"]
            if name == "turnover_ratio":
                # average_daily_balance is guaranteed to be computed before this
                # because it appears earlier in the REGISTRY dict (insertion order).
                avg_balance = results.get("average_daily_balance", {}).get("value")
                value, formula, explanation = bf.turnover_ratio(df, avg_balance)
            elif name == "name_consistency_flag":
                value, formula, explanation = fn(None, [])
            else:
                value, formula, explanation = fn(df)
            results[name] = {
                "value": value,
                "formula": entry["formula"],
                "explanation": entry["description"],
                "family": entry["family"],
            }
        except Exception as e:
            results[name] = {"value": None, "formula": entry["formula"], "explanation": str(e), "family": entry["family"]}
    return results
