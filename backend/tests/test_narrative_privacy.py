from app.evidence.evidence_schema import EvidenceBundle
from app.llm.narrative_generator import (
    compact_redacted_evidence_projection,
    generate_narrative_result,
    generate_template_summary,
)


class _CapturingClient:
    model = "test-local-model"

    def __init__(self):
        self.prompt: str | None = None
        self.system_prompt: str | None = None

    def availability(self):
        return True, None

    def generate(self, prompt, system_prompt=None, **_kwargs):
        self.prompt = prompt
        self.system_prompt = system_prompt
        # Every number appears in the compact projection, allowing fact checking.
        return "Analysis contains 4 transactions with a fused score of 42.0."


def _sensitive_bundle() -> EvidenceBundle:
    return EvidenceBundle.model_validate({
        "account_summary": {
            "statement_id": "stmt-9988776655443322",
            "observed_period": {"start": "2025-02-01", "end": "2025-02-05"},
            "transaction_count": 4,
            "extraction_confidence": 0.99,
        },
        "final_decision": {"tier": "REVIEW_REQUIRED", "fused_score": 42.0},
        "triggered_rules": [{
            "id": "R3_structuring_near_threshold",
            "description": "Raw narration says transfer to Priya Patel",
            "condition": "near_threshold_ratio > 0.3",
            "computed_value": 0.75,
            "points": 20,
            "contributing_row_ids": ["row-raw-sensitive-001"],
        }],
        "features": [{
            "name": "raw_account_number",
            "value": "9988776655443322",
            "formula": "sensitive formula",
            "explanation": "Priya Patel 9876543210",
            "family": "identity",
        }],
        "cycles_detected": [{
            "cycle_id": "cycle-private-123",
            "nodes": ["Alice Example", "Bob Example"],
            "hop_count": 3,
            "amount_conservation_ratio": 0.91,
            "cycle_risk_score": 0.85,
            "contributing_row_ids": ["private-row"],
        }],
        "guardrail_log": {"manual_mapping_used": True},
    })


def test_provider_prompt_uses_compact_redacted_projection(monkeypatch):
    bundle = _sensitive_bundle()
    client = _CapturingClient()
    monkeypatch.setattr("app.llm.ollama_client.OllamaClient", lambda: client)

    result = generate_narrative_result(bundle, mode="ollama")

    assert result.actual_mode == "ollama"
    assert client.prompt is not None
    for sensitive_value in (
        "9988776655443322", "Priya Patel", "9876543210", "row-raw-sensitive-001",
        "cycle-private-123", "Alice Example", "Bob Example", "2025-02-01",
    ):
        assert sensitive_value not in client.prompt
    assert "R3_structuring_near_threshold" in client.prompt
    assert '"transaction_count": 4' in client.prompt
    assert '"fused_score": 42.0' in client.prompt


def test_template_remains_canonical_and_provider_projection_is_separate():
    bundle = _sensitive_bundle()
    bundle_json = bundle.model_dump()

    canonical_template = generate_template_summary(bundle_json)
    template_result = generate_narrative_result(bundle, mode="template")
    projection = compact_redacted_evidence_projection(bundle_json)

    assert template_result.narrative == canonical_template
    assert "stmt-9988776655443322" in canonical_template
    assert projection["analysis"]["fused_score"] == 42.0
    assert "statement_id" not in str(projection)
    assert "Priya Patel" not in str(projection)
    assert "raw_account_number" not in str(projection)
