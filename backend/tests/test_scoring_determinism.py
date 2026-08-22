import pytest
from app.guardrails.determinism_guard import assert_deterministic
from app.scoring.rule_scorer import evaluate_rules


class TestScoringDeterminism:
    def test_rule_scorer_deterministic(self):
        features = {
            "net_retention_ratio": 0.09,
            "turnover_ratio": 10.0,
            "dormancy_breaks": 0,
            "near_threshold_ratio": 0.1,
            "benford_deviation_score": 5.0,
            "max_cycle_risk_score": 0.0,
            "fan_in_score": 0.5,
        }
        assert assert_deterministic(evaluate_rules, features)

    def test_repeatable_scores(self):
        features = {"net_retention_ratio": 0.5, "turnover_ratio": 3.0, "dormancy_breaks": 0, "near_threshold_ratio": 0.1, "benford_deviation_score": 2.0, "max_cycle_risk_score": 0.0, "fan_in_score": 0.2}
        score1, rules1 = evaluate_rules(features)
        score2, rules2 = evaluate_rules(features)
        assert score1 == score2
        assert len(rules1) == len(rules2)
