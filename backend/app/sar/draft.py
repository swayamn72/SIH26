"""Build jurisdiction-neutral SAR/STR investigator drafts from persisted case evidence."""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.db.models import Case, CaseAccountNode, CaseFinding, CaseTransferEdge, Statement


NON_FILING_NOTICE = (
    "This is an investigator draft only. It is not a filing, does not make a legal "
    "determination, and must be reviewed and confirmed by an authorized investigator before any filing decision."
)


def _finding_or_404(db: Session, case_id: int, finding_id: str) -> tuple[Case, CaseFinding]:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    finding = db.get(CaseFinding, finding_id)
    if not finding or finding.case_id != case_id:
        raise HTTPException(status_code=404, detail="Finding not found")
    return case, finding


def _node_label(nodes: dict[str, CaseAccountNode], node_id: str) -> str:
    node = nodes.get(node_id)
    return node.label if node else node_id


def _date_range(edges: list[CaseTransferEdge]) -> tuple[str | None, str | None]:
    dates = [edge.txn_date for edge in edges if edge.txn_date]
    if not dates:
        return None, None
    return str(min(dates)), str(max(dates))


def build_sar_draft(db: Session, case_id: int, finding_id: str) -> dict[str, Any]:
    """Return the canonical deterministic draft; it never asserts a filing occurred."""
    case, finding = _finding_or_404(db, case_id, finding_id)
    nodes = {
        node.id: node
        for node in db.exec(select(CaseAccountNode).where(CaseAccountNode.case_id == case_id)).all()
    }
    edges = [edge for edge_id in finding.edge_ids if (edge := db.get(CaseTransferEdge, edge_id))]
    statements = {
        statement.id: statement
        for statement in db.exec(
            select(Statement).where(Statement.id.in_(finding.source_statement_ids))
        ).all()
    } if finding.source_statement_ids else {}

    activity_start, activity_end = _date_range(edges)
    ordered_hops = [
        {
            "step": step,
            "edge_id": edge.id,
            "from_node_id": edge.source_node_id,
            "from_label": _node_label(nodes, edge.source_node_id),
            "to_node_id": edge.target_node_id,
            "to_label": _node_label(nodes, edge.target_node_id),
            "amount": edge.amount,
            "txn_date": str(edge.txn_date),
            "evidence_ids": [edge.id, *edge.source_row_ids],
        }
        for step, edge in enumerate(edges, start=1)
    ]
    evidence_ids = [finding.id, *[edge.id for edge in edges], *finding.source_row_ids]
    evidence_ids = list(dict.fromkeys(evidence_ids))
    subject_data = [
        {
            "statement_id": statement_id,
            "account_holder": statements[statement_id].account_holder,
            "institution": statements[statement_id].bank_name or statements[statement_id].bank_code,
            "source_evidence_id": f"statement:{statement_id}",
        }
        for statement_id in finding.source_statement_ids
        if statement_id in statements
    ]
    path_text = " → ".join(
        [_node_label(nodes, node_id) for node_id in finding.node_sequence]
    ) or "No ordered node path was retained."
    total_value = sum(edge.amount for edge in edges)
    date_text = activity_start if activity_start == activity_end else f"{activity_start} to {activity_end}"

    limitations = list((finding.detail or {}).get("limitations") or [])
    limitations.extend([
        "The activity dates are recorded with date precision; transaction times are unavailable.",
        "Names are not automatically merged across statements; only exact mirrored references resolve statement subjects.",
        "This draft relies only on the cited case graph evidence and does not establish intent or a legal conclusion.",
    ])
    limitations = list(dict.fromkeys(limitations))

    return {
        "draft_type": "SAR/STR investigator draft",
        "status": "DRAFT_REQUIRES_REVIEWER_CONFIRMATION",
        "filing_status": "NOT_FILED",
        "non_filing_notice": NON_FILING_NOTICE,
        "case": {"id": case.id, "name": case.name, "description": case.description},
        "finding": {
            "id": finding.id,
            "kind": finding.kind,
            "risk_score": finding.risk_score,
            "hop_count": finding.hop_count,
        },
        "subject_data": subject_data,
        "activity": {
            "categories": ["Conserved flow cycle"],
            "start_date": activity_start,
            "end_date": activity_end,
            "date_precision": "date",
            "transfer_count": len(edges),
            "total_suspicious_value": total_value,
        },
        "five_w_narrative": {
            "who": "The available subjects are the statement holders and statement-scoped entities listed in Subject data. Identity resolution is limited to cited evidence.",
            "what": f"The case analysis identified a {finding.hop_count}-hop {finding.kind.replace('_', ' ')} involving {len(edges)} cited transfer edge(s) totaling {total_value:.2f} in aggregate movement.",
            "when": f"The cited activity occurred {date_text or 'on dates not available in the finding'} (date precision).",
            "where": f"The observed path is {path_text}. Institutions are included only where available in the cited statement metadata.",
            "why": "The activity is included for investigator review because the persisted finding records a conserved, ordered fund-flow path. This is an evidence-based observation, not a conclusion of wrongdoing.",
        },
        "ordered_graph_path": ordered_hops,
        "evidence_ids": evidence_ids,
        "limitations": limitations,
        "missing_required_fields": [
            "Filing jurisdiction and applicable reporting form",
            "Reporting entity and filer contact details",
            "Authorized reviewer identity, review date, and confirmation",
        ],
        "reviewer_confirmation": {
            "required": True,
            "confirmed": False,
            "message": "An authorized investigator must review the cited evidence and explicitly confirm this draft before any filing decision.",
        },
    }


def draft_html(draft: dict[str, Any]) -> str:
    """Render a simple safe HTML export without presenting the draft as a filing."""
    def item(value: Any) -> str:
        return escape(str(value if value is not None else "Not available"))

    hops = "".join(
        "<tr>"
        f"<td>{hop['step']}</td><td>{item(hop['from_label'])}</td><td>{item(hop['to_label'])}</td>"
        f"<td>{hop['amount']:.2f}</td><td>{item(hop['txn_date'])}</td>"
        f"<td>{item(', '.join(hop['evidence_ids']))}</td>"
        "</tr>"
        for hop in draft["ordered_graph_path"]
    ) or "<tr><td colspan='6'>No persisted transfer edges are available.</td></tr>"
    five_w = "".join(
        f"<h3>{escape(label.title())}</h3><p>{item(text)}</p>"
        for label, text in draft["five_w_narrative"].items()
    )
    limitations = "".join(f"<li>{item(value)}</li>" for value in draft["limitations"])
    missing = "".join(f"<li>{item(value)}</li>" for value in draft["missing_required_fields"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>SAR/STR investigator draft</title>
<style>body{{font:14px Arial,sans-serif;color:#0f172a;margin:32px;line-height:1.5}}h1{{margin-bottom:4px}}.notice{{border:1px solid #f59e0b;background:#fffbeb;padding:12px;border-radius:6px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #cbd5e1;padding:7px;text-align:left;vertical-align:top}}th{{background:#f1f5f9}}code{{word-break:break-all}}</style>
</head><body>
<h1>SAR/STR investigator draft</h1><p><strong>Case:</strong> {item(draft['case']['name'])} (#{item(draft['case']['id'])})</p>
<p class="notice"><strong>NOT FILED.</strong> {item(draft['non_filing_notice'])}</p>
<h2>Activity summary</h2><p>{item(draft['activity']['transfer_count'])} transfer edge(s); aggregate movement {item(draft['activity']['total_suspicious_value'])}; dates {item(draft['activity']['start_date'])} to {item(draft['activity']['end_date'])} ({item(draft['activity']['date_precision'])} precision).</p>
<h2>Five-W narrative</h2>{five_w}
<h2>Ordered graph path</h2><table><thead><tr><th>Step</th><th>From</th><th>To</th><th>Amount</th><th>Date</th><th>Evidence IDs</th></tr></thead><tbody>{hops}</tbody></table>
<h2>Evidence IDs</h2><p><code>{item(', '.join(draft['evidence_ids']))}</code></p>
<h2>Limitations</h2><ul>{limitations}</ul>
<h2>Required before any filing decision</h2><ul>{missing}</ul>
<p class="notice"><strong>Reviewer confirmation required.</strong> {item(draft['reviewer_confirmation']['message'])}</p>
</body></html>"""
