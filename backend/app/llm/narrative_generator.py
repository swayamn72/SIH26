import json
import os
from typing import Any, Optional

from app.evidence.evidence_schema import EvidenceBundle
from app.llm.fact_checker import fact_check_output
from app.config_loader import load_prompt


def _get_llm_client():
    """Return Groq client if GROQ_API_KEY is set, otherwise fall back to Ollama."""
    if os.environ.get("GROQ_API_KEY"):
        from app.llm.groq_client import GroqClient
        return GroqClient()
    from app.llm.ollama_client import OllamaClient
    return OllamaClient()

def generate_narrative(evidence_bundle: EvidenceBundle, use_ai: bool = True) -> tuple[str, str]:
    bundle_json = evidence_bundle.model_dump()
    bundle_str = json.dumps(bundle_json, indent=2, default=str)

    template = generate_template_summary(bundle_json)

    if not use_ai:
        return template, "template"

    try:
        system_prompt = load_prompt("system_prompt_summary.txt")
        client = _get_llm_client()

        if not client.is_available():
            return template, "template"

        narrative = client.generate(
            prompt=f"Summarize the following evidence bundle:\n\n{bundle_str}",
            system_prompt=system_prompt,
        )

        if fact_check_output(narrative, bundle_str):
            return narrative, "ai"
        else:
            return template, "template"
    except Exception:
        return template, "template"


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

    rule_list = ", ".join(
        f"{r.get('id', '')} ({r.get('points', 0)} pts)" for r in rules[:3]
    ) or "none triggered"

    cycle_desc = ""
    if cycles:
        cycle_parts = []
        for c in cycles[:3]:
            hops = c.get("hop_count", 0)
            conserv = c.get("amount_conservation_ratio", 0)
            cycle_parts.append(f"{hops}-hop cycle with {conserv:.0%} amount conservation")
        cycle_desc = "Detected cycles: " + "; ".join(cycle_parts) + ". "

    start = period.get("start", "unknown")
    end = period.get("end", "unknown")

    return (
        f"Account {sid} observed over {start} to {end} "
        f"({txn_count} transactions, extracted with {conf:.1%} confidence) "
        f"has been classified as {tier} with a fused score of {score:.1f}. "
        f"The top triggered rules are: {rule_list}. "
        f"{cycle_desc}"
        f"This is a decision-support output, not a final determination, "
        f"and requires human review before any account action."
    )
