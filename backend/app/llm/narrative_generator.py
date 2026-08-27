import json
import os
from dataclasses import dataclass
from typing import Any, Literal

from app.config_loader import load_prompt
from app.evidence.evidence_schema import EvidenceBundle
from app.llm.fact_checker import fact_check_output

NarrativeMode = Literal["template", "ollama", "groq", "auto"]
_VALID_MODES = {"template", "ollama", "groq", "auto"}


@dataclass(frozen=True)
class NarrativeResult:
    narrative: str
    requested_mode: NarrativeMode
    actual_mode: Literal["template", "ollama", "groq"]
    model: str | None
    fallback_reason: str | None
    fact_check_passed: bool | None


def _configured_mode() -> NarrativeMode:
    mode = os.environ.get("NARRATIVE_MODE", "template").lower()
    return mode if mode in _VALID_MODES else "template"


def compact_redacted_evidence_projection(bundle_json: dict[str, Any]) -> dict[str, Any]:
    """Return the small, non-identifying fact set allowed in provider prompts.

    Raw transaction rows, counterparty/account-holder names, statement identifiers,
    dates, source locators, feature-level values, and free-text evidence never leave
    the deterministic backend through narrative providers.
    """
    summary = bundle_json.get("account_summary", {})
    decision = bundle_json.get("final_decision", {})
    projection: dict[str, Any] = {
        "analysis": {
            "transaction_count": summary.get("transaction_count", 0),
            "extraction_confidence": summary.get("extraction_confidence", 0),
            "risk_tier": decision.get("tier", "REVIEW_REQUIRED"),
            "fused_score": decision.get("fused_score", 0),
        },
        "triggered_rules": [
            {"id": rule.get("id", ""), "points": rule.get("points", 0)}
            for rule in bundle_json.get("triggered_rules", [])[:3]
        ],
        "cycles": [
            {
                "hop_count": cycle.get("hop_count", 0),
                "amount_conservation_ratio": cycle.get("amount_conservation_ratio"),
                "cycle_risk_score": cycle.get("cycle_risk_score"),
            }
            for cycle in bundle_json.get("cycles_detected", [])[:3]
        ],
        "limitations": {
            "anomaly_availability": (bundle_json.get("anomaly_detail") or {}).get("availability_reason"),
            "manual_mapping_used": (bundle_json.get("guardrail_log") or {}).get("manual_mapping_used", False),
        },
    }
    return projection


def _generate_with_client(
    client: Any,
    mode: Literal["ollama", "groq"],
    provider_evidence_json: str,
    template: str,
) -> NarrativeResult:
    try:
        available, reason = client.availability()
        if not available:
            return NarrativeResult(template, mode, "template", None, reason, None)
        narrative = client.generate(
            prompt=f"Summarize the following redacted evidence projection:\n\n{provider_evidence_json}",
            system_prompt=load_prompt("system_prompt_summary.txt"),
        )
        if fact_check_output(narrative, provider_evidence_json):
            return NarrativeResult(narrative, mode, mode, client.model, None, True)
        return NarrativeResult(template, mode, "template", None, "fact_check_failed", False)
    except Exception as exc:
        return NarrativeResult(
            template,
            mode,
            "template",
            None,
            f"{mode}_generation_failed: {exc.__class__.__name__}",
            None,
        )


def generate_narrative_result(
    evidence_bundle: EvidenceBundle, mode: NarrativeMode | None = None, use_ai: bool = True
) -> NarrativeResult:
    """Generate narrative only through the explicitly selected provider.

    Template output remains canonical and uses the complete internal bundle. Any
    Ollama/Groq request receives only a compact redacted evidence projection. The
    default is deterministic template mode; cloud fallback happens only for an
    explicitly requested `auto` mode.
    """
    requested_mode = mode or _configured_mode()
    if not use_ai:
        requested_mode = "template"
    bundle_json = evidence_bundle.model_dump()
    template = generate_template_summary(bundle_json)

    if requested_mode == "template":
        return NarrativeResult(template, "template", "template", None, None, None)

    provider_evidence_json = json.dumps(
        compact_redacted_evidence_projection(bundle_json), indent=2, default=str
    )
    if requested_mode == "ollama":
        from app.llm.ollama_client import OllamaClient
        return _generate_with_client(OllamaClient(), "ollama", provider_evidence_json, template)

    if requested_mode == "groq":
        from app.llm.groq_client import GroqClient
        try:
            return _generate_with_client(GroqClient(), "groq", provider_evidence_json, template)
        except Exception as exc:
            return NarrativeResult(template, "groq", "template", None, f"groq_unavailable: {exc.__class__.__name__}", None)

    # Auto is opt-in. Prefer the local provider, and disclose a cloud fallback.
    from app.llm.ollama_client import OllamaClient
    local_result = _generate_with_client(OllamaClient(), "ollama", provider_evidence_json, template)
    if local_result.actual_mode == "ollama":
        return NarrativeResult(local_result.narrative, "auto", "ollama", local_result.model, None, local_result.fact_check_passed)
    from app.llm.groq_client import GroqClient
    try:
        cloud_result = _generate_with_client(GroqClient(), "groq", provider_evidence_json, template)
    except Exception as exc:
        cloud_result = NarrativeResult(template, "groq", "template", None, f"groq_unavailable: {exc.__class__.__name__}", None)
    if cloud_result.actual_mode == "groq":
        return NarrativeResult(cloud_result.narrative, "auto", "groq", cloud_result.model, "ollama_unavailable", cloud_result.fact_check_passed)
    return NarrativeResult(template, "auto", "template", None, local_result.fallback_reason or cloud_result.fallback_reason, None)


def generate_narrative(evidence_bundle: EvidenceBundle, use_ai: bool = True) -> tuple[str, str]:
    """Compatibility wrapper for callers expecting `(narrative, source)`."""
    result = generate_narrative_result(evidence_bundle, use_ai=use_ai)
    return result.narrative, result.actual_mode


def generate_template_summary(bundle_json: dict[str, Any]) -> str:
    summary = bundle_json.get("account_summary", {})
    decision = bundle_json.get("final_decision", {})
    rules = bundle_json.get("triggered_rules", [])
    cycles = bundle_json.get("cycles_detected", [])

    sid = summary.get("statement_id", "unknown")
    period = summary.get("observed_period", {})
    txn_count = summary.get("transaction_count", 0)
    conf = summary.get("extraction_confidence", 0)
    tier = decision.get("tier", "REVIEW_REQUIRED")
    score = decision.get("fused_score", 0)
    rule_list = ", ".join(f"{r.get('id', '')} ({r.get('points', 0)} pts)" for r in rules[:3]) or "none triggered"

    cycle_desc = ""
    if cycles:
        cycle_desc = "Detected cycles: " + "; ".join(
            f"{c.get('hop_count', 0)}-hop cycle with {c.get('amount_conservation_ratio', 0):.0%} amount conservation"
            for c in cycles[:3]
        ) + ". "

    return (
        f"Account {sid} observed over {period.get('start', 'unknown')} to {period.get('end', 'unknown')} "
        f"({txn_count} transactions, extracted with {conf:.1%} confidence) has been classified as {tier} "
        f"with a fused score of {score:.1f}. The top triggered rules are: {rule_list}. {cycle_desc}"
        "This is a decision-support output, not a final determination, and requires human review before any account action."
    )
