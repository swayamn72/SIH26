from typing import Any, Optional

from app.config_loader import load_config


def decide_tier(
    fused_score: float,
    rule_score: float | None,
    anomaly_score: float | None,
    extraction_confidence: str,
    rules_triggered: bool,
) -> tuple[str, dict[str, Any], str]:
    cfg = load_config("thresholds")
    dec = cfg.get("decision", {})
    t_high = dec.get("confirmed_suspicious_min", 75)
    t_low = dec.get("likely_legitimate_max", 25)

    thresholds_applied = {"T_high": t_high, "T_low": t_low}
    anomaly_val = anomaly_score if anomaly_score is not None else 0.0
    r_score = rule_score if rule_score is not None else 0.0

    if fused_score >= t_high and rules_triggered and extraction_confidence != "low":
        tier = "CONFIRMED_SUSPICIOUS"
        reason = f"Fused risk score ({fused_score:.1f} >= {t_high}) with active regulatory fraud rules triggered."
    elif (
        fused_score <= t_low
        and anomaly_val < 0.3
        and extraction_confidence == "high"
    ):
        tier = "LIKELY_LEGITIMATE"
        reason = f"Fused score ({fused_score:.1f} <= {t_low}) with 0 severe rules triggered and normal anomaly sub-score ({anomaly_val*100:.1f}% < 30%)."
    elif fused_score <= t_low and anomaly_val >= 0.3:
        tier = "REVIEW_REQUIRED"
        reason = f"0 deterministic rules triggered (Rule Score: {r_score:.1f}), but statistical anomaly sub-score ({anomaly_val*100:.1f}%) exceeded the strict auto-clear threshold (< 30.0%)."
    elif extraction_confidence == "low":
        tier = "REVIEW_REQUIRED"
        reason = "Low statement extraction confidence requires human verification before account clearance."
    else:
        tier = "REVIEW_REQUIRED"
        reason = f"Ambiguous risk score ({fused_score:.1f}) between thresholds ({t_low} - {t_high}) requires human auditor sign-off."

    return tier, thresholds_applied, reason

