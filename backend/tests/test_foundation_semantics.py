from datetime import date

import pandas as pd
import pytest

from app.features.behavior_features import (
    median_holding_time_hours,
    net_retention_ratio,
    turnover_ratio,
)
from app.features.velocity_features import inflow_outflow_velocity
from app.scoring.rule_scorer import _resolve_threshold
from app.scoring.supervised_scorer import SupervisedScorer


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestCoreFeatureSemantics:
    def test_turnover_uses_debit_plus_credit_and_requires_positive_balance(self):
        df = _df([
            {"debit_amount": 30.0, "credit_amount": 70.0, "txn_date": date(2024, 1, 1)},
        ])
        assert turnover_ratio(df, 20.0)[0] == 5.0
        assert turnover_ratio(df, None)[0] is None
        assert turnover_ratio(df, 0.0)[0] is None
        assert turnover_ratio(df, -20.0)[0] is None

    def test_turnover_empty_and_zero_flow_boundaries(self):
        assert turnover_ratio(pd.DataFrame(), 100.0)[0] is None
        df = _df([{"debit_amount": 0.0, "credit_amount": 0.0, "txn_date": date(2024, 1, 1)}])
        assert turnover_ratio(df, 0.0)[0] == 0.0

    def test_velocity_uses_inclusive_true_trailing_24h_boundaries(self):
        df = _df([
            {"txn_date": pd.Timestamp("2024-01-01T00:00:00")},
            {"txn_date": pd.Timestamp("2024-01-01T23:59:00")},
            {"txn_date": pd.Timestamp("2024-01-02T00:00:00")},
            {"txn_date": pd.Timestamp("2024-01-02T00:01:00")},
        ])
        value, formula, _ = inflow_outflow_velocity(df)
        assert value == 3  # 00:00 through exactly 24:00 is inclusive
        assert "trailing inclusive 24h" in formula

    def test_velocity_date_only_uses_truthful_peak_daily_label(self):
        df = _df([
            {"txn_date": date(2024, 1, 1)},
            {"txn_date": date(2024, 1, 1)},
            {"txn_date": date(2024, 1, 2)},
        ])
        value, formula, explanation = inflow_outflow_velocity(df)
        assert value == 2
        assert "calendar day" in formula
        assert "date precision" in explanation

    def test_retention_and_holding_do_not_reuse_one_debit(self):
        df = _df([
            {"txn_date": pd.Timestamp("2024-01-01T08:00:00"), "credit_amount": 100.0, "debit_amount": 0.0},
            {"txn_date": pd.Timestamp("2024-01-01T09:00:00"), "credit_amount": 100.0, "debit_amount": 0.0},
            {"txn_date": pd.Timestamp("2024-01-01T10:00:00"), "credit_amount": 0.0, "debit_amount": 100.0},
        ])
        assert net_retention_ratio(df)[0] == pytest.approx(0.5)
        assert median_holding_time_hours(df)[0] == pytest.approx(2.0)

    def test_retention_excludes_same_timestamp_and_24h_plus_one_minute(self):
        df = _df([
            {"txn_date": pd.Timestamp("2024-01-01T08:00:00"), "credit_amount": 100.0, "debit_amount": 0.0},
            {"txn_date": pd.Timestamp("2024-01-01T08:00:00"), "credit_amount": 0.0, "debit_amount": 100.0},
            {"txn_date": pd.Timestamp("2024-01-02T08:01:00"), "credit_amount": 0.0, "debit_amount": 100.0},
        ])
        assert net_retention_ratio(df)[0] == 1.0
        assert median_holding_time_hours(df)[0] is None

    def test_benford_critical_value_is_loaded_from_config(self):
        assert _resolve_threshold("critical_value_95", {}) == pytest.approx(15.507)


class TestGovernedSupervisedFallback:
    def test_checked_in_model_is_disabled_without_explicit_governance(self):
        scorer = SupervisedScorer()
        assert scorer.available is False
        assert scorer.unavailable_reason == "disabled_by_configuration"
