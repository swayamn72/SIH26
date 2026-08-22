from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


class CycleEvidence(BaseModel):
    cycle_id: str
    nodes: list[str]
    hop_count: int
    amount_conservation_ratio: Optional[float] = None
    cycle_span_days: Optional[float] = None
    cycle_risk_score: Optional[float] = None
    contributing_row_ids: list[str] = []


class RuleEvidence(BaseModel):
    id: str
    description: str
    condition: str
    computed_value: Optional[float] = None
    points: int
    contributing_row_ids: list[str] = []


class FeatureEvidence(BaseModel):
    name: str
    value: Any
    formula: str
    explanation: str
    family: str = ""


class AnomalyDetail(BaseModel):
    isolation_forest_score: Optional[float] = None
    top_contributing_features: list[str] = []
    mad_flagged_features: dict[str, float] = {}
    seed: int = 42


class SupervisedDetail(BaseModel):
    calibrated_probability: Optional[float] = None
    model_type: Optional[str] = None
    feature_importance: dict[str, float] = {}


class GuardrailLog(BaseModel):
    ood_check_passed: bool = False
    ood_score: float = 0.0
    reconciliation_rate: Optional[float] = None
    extraction_confidence: str = "unknown"
    manual_mapping_used: bool = False


class AccountSummary(BaseModel):
    statement_id: str = ""
    observed_period: dict[str, str] = {}
    extraction_confidence: float = 0.0
    statement_likelihood_score: float = 0.0
    transaction_count: int = 0


class FinalDecision(BaseModel):
    tier: str = "REVIEW_REQUIRED"
    fused_score: float = 0.0
    score_formula_used: str = ""
    thresholds_applied: dict[str, Any] = {}
    rule_score: Optional[float] = 0.0
    anomaly_score: Optional[float] = 0.0
    decision_reason: Optional[str] = ""


class EvidenceBundle(BaseModel):
    account_summary: AccountSummary = AccountSummary()
    final_decision: FinalDecision = FinalDecision()
    triggered_rules: list[RuleEvidence] = []
    features: list[FeatureEvidence] = []
    cycles_detected: list[CycleEvidence] = []
    anomaly_detail: Optional[AnomalyDetail] = None
    supervised_detail: Optional[SupervisedDetail] = None
    guardrail_log: GuardrailLog = GuardrailLog()
