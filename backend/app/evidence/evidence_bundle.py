from typing import Any, Optional

from app.evidence.evidence_schema import (
    EvidenceBundle, AccountSummary, FinalDecision, RuleEvidence,
    FeatureEvidence, CycleEvidence, AnomalyDetail, GuardrailLog,
)


def assemble_evidence_bundle(
    statement_id: str,
    observed_start: Optional[str],
    observed_end: Optional[str],
    extraction_confidence: float,
    ood_score: float,
    transaction_count: int,
    tier: str,
    fused_score: float,
    score_formula: str,
    thresholds_applied: dict[str, Any],
    triggered_rules: list[dict[str, Any]],
    features: list[dict[str, Any]],
    cycles: list[dict[str, Any]],
    anomaly_detail: Optional[dict[str, Any]],
    ood_check_passed: bool,
    reconciliation_rate: Optional[float],
    extraction_conf_str: str,
    manual_mapping_used: bool,
    rule_score: Optional[float] = 0.0,
    anomaly_score: Optional[float] = 0.0,
    decision_reason: Optional[str] = "",
) -> EvidenceBundle:
    bundle = EvidenceBundle(
        account_summary=AccountSummary(
            statement_id=statement_id,
            observed_period={"start": observed_start or "", "end": observed_end or ""},
            extraction_confidence=extraction_confidence,
            statement_likelihood_score=ood_score,
            transaction_count=transaction_count,
        ),
        final_decision=FinalDecision(
            tier=tier,
            fused_score=fused_score,
            score_formula_used=score_formula,
            thresholds_applied=thresholds_applied,
            rule_score=rule_score,
            anomaly_score=anomaly_score,
            decision_reason=decision_reason,
        ),
        triggered_rules=[
            RuleEvidence(
                id=r.get("id", ""),
                description=r.get("description", ""),
                condition=r.get("condition", ""),
                computed_value=r.get("computed_value"),
                points=r.get("points", 0),
                contributing_row_ids=r.get("contributing_row_ids", []),
            )
            for r in triggered_rules
        ],
        features=[
            FeatureEvidence(
                name=f.get("name", ""),
                value=f.get("value"),
                formula=f.get("formula", ""),
                explanation=f.get("explanation", ""),
                family=f.get("family", ""),
            )
            for f in features
        ],
        cycles_detected=[
            CycleEvidence(
                cycle_id=c.get("cycle_id", ""),
                nodes=c.get("nodes", []),
                hop_count=c.get("hop_count", 0),
                amount_conservation_ratio=c.get("amount_conservation_ratio"),
                cycle_span_days=c.get("cycle_span_days"),
                cycle_risk_score=c.get("cycle_risk_score"),
                contributing_row_ids=c.get("contributing_row_ids", []),
            )
            for c in cycles
        ],
        anomaly_detail=AnomalyDetail(
            isolation_forest_score=anomaly_detail.get("isolation_forest_score") if anomaly_detail else None,
            top_contributing_features=anomaly_detail.get("top_contributing_features", []) if anomaly_detail else [],
            mad_flagged_features=anomaly_detail.get("mad_flagged_features", {}) if anomaly_detail else {},
        ) if anomaly_detail else None,
        guardrail_log=GuardrailLog(
            ood_check_passed=ood_check_passed,
            ood_score=ood_score,
            reconciliation_rate=reconciliation_rate,
            extraction_confidence=extraction_conf_str,
            manual_mapping_used=manual_mapping_used,
        ),
    )
    return bundle


def _sanitize(obj: Any) -> Any:
    """Recursively convert numpy scalar types to native Python types for JSON serialization."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return obj


def evidence_bundle_to_json(bundle: EvidenceBundle) -> dict[str, Any]:
    return _sanitize(bundle.model_dump())
