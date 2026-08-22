import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session, select

from app.db.session import get_session
from app.db.models import Statement, EvidenceBundleRecord

logger = logging.getLogger(__name__)

router = APIRouter()


def _load_statement_or_404(db: Session, statement_id: int) -> Statement:
    stmt = db.get(Statement, statement_id)
    if stmt is None:
        raise HTTPException(status_code=404, detail=f"Statement {statement_id} not found")
    return stmt


def _html_report(bundle: dict) -> str:
    summary = bundle.get("account_summary", {})
    decision = bundle.get("final_decision", {})
    rules = bundle.get("triggered_rules", [])
    features = bundle.get("features", [])
    cycles = bundle.get("cycles_detected", [])
    guardrail = bundle.get("guardrail_log", {})
    anomaly = bundle.get("anomaly_detail")

    sid = summary.get("statement_id", "?")
    period = summary.get("observed_period", {})
    period_str = f"{period.get('start', '?')} to {period.get('end', '?')}"
    txn_count = summary.get("transaction_count", 0)
    conf = summary.get("extraction_confidence", 0)
    likelihood = summary.get("statement_likelihood_score", 0)
    tier = decision.get("tier", "REVIEW_REQUIRED")
    fscore = decision.get("fused_score", 0)
    formula = decision.get("score_formula_used", "")

    rules_rows = "".join(
        f"<tr><td>{r.get('id', '')}</td><td>{r.get('description', '')}</td>"
        f"<td>{r.get('condition', '')}</td><td>{r.get('points', 0)}</td></tr>"
        for r in rules
    ) or "<tr><td colspan='4'>No rules triggered</td></tr>"

    feats_rows = "".join(
        f"<tr><td>{f.get('name', '')}</td><td>{f.get('value', '')}</td>"
        f"<td>{f.get('formula', '')}</td><td>{f.get('family', '')}</td></tr>"
        for f in features
    ) or "<tr><td colspan='4'>No features computed</td></tr>"

    cycles_rows = "".join(
        f"<tr><td>{c.get('cycle_id', '')}</td><td>{c.get('hop_count', 0)}</td>"
        f"<td>{c.get('amount_conservation_ratio', 'N/A')}</td>"
        f"<td>{c.get('cycle_risk_score', 'N/A')}</td></tr>"
        for c in cycles
    ) or "<tr><td colspan='4'>No cycles detected</td></tr>"

    ood_pass = guardrail.get("ood_check_passed", False)
    rec_rate = guardrail.get("reconciliation_rate", "N/A")
    ext_conf = guardrail.get("extraction_confidence", "unknown")
    manual = "Yes" if guardrail.get("manual_mapping_used") else "No"

    anomaly_html = ""
    if anomaly:
        if_score = anomaly.get("isolation_forest_score", "N/A")
        top_feats = ", ".join(anomaly.get("top_contributing_features", [])) or "None"
        mad_feats = json.dumps(anomaly.get("mad_flagged_features", {}))
        anomaly_html = f"""
        <h3>Anomaly Detection</h3>
        <table border='1' cellpadding='4' style='border-collapse:collapse;width:100%'>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Isolation Forest Score</td><td>{if_score}</td></tr>
        <tr><td>Top Contributing Features</td><td>{top_feats}</td></tr>
        <tr><td>MAD Flagged Features</td><td>{mad_feats}</td></tr>
        </table>
        """

    return f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>MuleGuard Report — Statement {sid}</title>
<style>body{{font-family:sans-serif;margin:2em}}h1,h2,h3{{color:#1a365d}}table{{width:100%}}th{{background:#2b6cb0;color:#fff}}</style>
</head><body>
<h1>MuleGuard Local — Analysis Report</h1>
<p>Generated: {datetime.now().isoformat()}</p>

<h2>Account Summary</h2>
<table border='1' cellpadding='4' style='border-collapse:collapse'>
<tr><td>Statement ID</td><td>{sid}</td></tr>
<tr><td>Observed Period</td><td>{period_str}</td></tr>
<tr><td>Transactions</td><td>{txn_count}</td></tr>
<tr><td>Extraction Confidence</td><td>{conf:.2f}</td></tr>
<tr><td>Statement Likelihood Score</td><td>{likelihood:.4f}</td></tr>
</table>

<h2>Final Decision</h2>
<table border='1' cellpadding='4' style='border-collapse:collapse'>
<tr><td>Tier</td><td>{tier}</td></tr>
<tr><td>Fused Score</td><td>{fscore:.1f}</td></tr>
<tr><td>Score Formula</td><td><code>{formula}</code></td></tr>
</table>

<h2>Triggered Rules</h2>
<table border='1' cellpadding='4' style='border-collapse:collapse'>
<tr><th>Rule ID</th><th>Description</th><th>Condition</th><th>Points</th></tr>
{rules_rows}
</table>

<h2>Features</h2>
<table border='1' cellpadding='4' style='border-collapse:collapse'>
<tr><th>Name</th><th>Value</th><th>Formula</th><th>Family</th></tr>
{feats_rows}
</table>

<h2>Cycles Detected</h2>
<table border='1' cellpadding='4' style='border-collapse:collapse'>
<tr><th>Cycle ID</th><th>Hops</th><th>Amount Conservation</th><th>Risk Score</th></tr>
{cycles_rows}
</table>

{anomaly_html}

<h2>Guardrail Log</h2>
<table border='1' cellpadding='4' style='border-collapse:collapse'>
<tr><td>OOD Check Passed</td><td>{ood_pass}</td></tr>
<tr><td>Reconciliation Rate</td><td>{rec_rate}</td></tr>
<tr><td>Extraction Confidence</td><td>{ext_conf}</td></tr>
<tr><td>Manual Mapping Used</td><td>{manual}</td></tr>
</table>

<hr><p><em>MuleGuard Local — decision-support output. Requires human review.</em></p>
</body></html>"""


@router.post("/{statement_id}/export")
async def export_report(statement_id: int, db: Session = Depends(get_session)):
    _load_statement_or_404(db, statement_id)
    rec = db.exec(
        select(EvidenceBundleRecord)
        .where(EvidenceBundleRecord.statement_id == statement_id)
        .order_by(EvidenceBundleRecord.created_ts.desc())
    ).first()
    if rec is None:
        raise HTTPException(status_code=404, detail="No evidence bundle found; run confirm first")

    bundle = rec.json_blob
    html = _html_report(bundle)

    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}_report.pdf"},
        )
    except ImportError:
        logger.info("weasyprint not available; returning JSON download instead")
        return Response(
            content=json.dumps(bundle, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=statement_{statement_id}_evidence.json"},
        )
