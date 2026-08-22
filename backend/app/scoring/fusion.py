from typing import Any, Optional

from app.config_loader import load_config


def _normalize(value: float | None, max_val: float = 100.0) -> float:
    if value is None:
        return 0.0
    return min(max(float(value) / max_val, 0.0), 1.0)


def fuse_scores(
    rule_score: float | None,
    anomaly_score: float | None,
    supervised_probability: float | None = None,
) -> tuple[float, str]:
    cfg = load_config("thresholds")
    fusion = cfg.get("fusion", {})
    supervised_available = supervised_probability is not None

    rule_norm = _normalize(rule_score, 100.0)
    anomaly_norm = _normalize(anomaly_score, 1.0)

    if supervised_available:
        weights = fusion.get("supervised_available", {})
        w_rule = weights.get("rule_score", 0.40)
        w_anomaly = weights.get("anomaly_score", 0.25)
        w_supervised = weights.get("supervised_probability", 0.35)
        fused = w_rule * rule_norm + w_anomaly * anomaly_norm + w_supervised * _normalize(supervised_probability, 1.0)
        formula = f"{w_rule}*rule_score + {w_anomaly}*anomaly_score + {w_supervised}*supervised_probability"
    else:
        weights = fusion.get("supervised_unavailable", {})
        w_rule = weights.get("rule_score", 0.65)
        w_anomaly = weights.get("anomaly_score", 0.35)
        fused = w_rule * rule_norm + w_anomaly * anomaly_norm
        formula = f"{w_rule}*rule_score + {w_anomaly}*anomaly_score (no supervised model active)"

    return round(fused * 100, 1), formula
