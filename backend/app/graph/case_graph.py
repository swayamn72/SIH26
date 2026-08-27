"""Persisted, conservative multi-statement case graph construction.

A statement always starts as its own subject account.  Counterparty names are
local observations, not identities: they are never merged across statements.
The only automatic subject-to-subject resolution implemented here is an exact
mirrored transfer reference with compatible direction, amount and date.  This
keeps a visually plausible shared name from manufacturing a laundering ring.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.db.models import (
    Case,
    CaseAccountNode,
    CaseFinding,
    CaseStatement,
    CaseTransferEdge,
    Counterparty,
    Statement,
    Transaction,
)
from app.institutions.flow_cycles import find_conserved_cycles


def _stable_id(prefix: str, *parts: object) -> str:
    value = "|".join(str(part or "") for part in parts)
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:20]}"


def _normal_reference(reference: str | None) -> str | None:
    if not reference:
        return None
    compact = "".join(ch for ch in reference.upper() if ch.isalnum())
    return compact or None


def _amount(transaction: Transaction) -> float:
    debit, credit = float(transaction.debit_amount or 0), float(transaction.credit_amount or 0)
    return debit if debit > 0 else credit


def _direction(transaction: Transaction) -> str | None:
    if transaction.debit_amount and float(transaction.debit_amount) > 0:
        return "out"
    if transaction.credit_amount and float(transaction.credit_amount) > 0:
        return "in"
    return None


def _compatible_mirror(left: Transaction, right: Transaction) -> bool:
    """Require exact reference plus observed debit/credit and amount/date agreement."""
    if _direction(left) == _direction(right):
        return False
    if abs(_amount(left) - _amount(right)) > 0.01:
        return False
    if not left.txn_date or not right.txn_date:
        return False
    return abs((left.txn_date - right.txn_date).days) <= 1


def _subject_node_id(case_id: int, statement_id: int) -> str:
    # No account number is embedded in the public graph ID.
    return f"case_{case_id}_subject_{statement_id}"


def _counterparty_node_id(case_id: int, statement_id: int, counterparty_id: int | None, row_id: str) -> str:
    # Counterparties stay statement-scoped unless an evidence-backed resolution
    # maps an observed transfer to another statement subject.
    return _stable_id("node", case_id, statement_id, counterparty_id or "unresolved", row_id)


def analyze_case(db: Session, case: Case) -> dict[str, Any]:
    """Rebuild and persist one case's graph and conserved-flow findings."""
    memberships = db.exec(
        select(CaseStatement).where(CaseStatement.case_id == case.id).order_by(CaseStatement.statement_id)
    ).all()
    statement_ids = [membership.statement_id for membership in memberships]
    statements = {
        statement.id: statement
        for statement in db.exec(select(Statement).where(Statement.id.in_(statement_ids))).all()
    } if statement_ids else {}
    transactions = db.exec(
        select(Transaction).where(Transaction.statement_id.in_(statement_ids)).order_by(Transaction.txn_date, Transaction.row_id)
    ).all() if statement_ids else []
    counterparties = {counterparty.id: counterparty for counterparty in db.exec(select(Counterparty)).all()}

    # Re-analysis is a replacement of the current materialized graph; source
    # statements and source transaction rows remain untouched.
    db.query(CaseFinding).filter(CaseFinding.case_id == case.id).delete()
    db.query(CaseTransferEdge).filter(CaseTransferEdge.case_id == case.id).delete()
    db.query(CaseAccountNode).filter(CaseAccountNode.case_id == case.id).delete()
    db.flush()

    for statement_id in statement_ids:
        statement = statements.get(statement_id)
        if not statement:
            continue
        db.add(CaseAccountNode(
            id=_subject_node_id(case.id, statement_id),
            case_id=case.id,
            kind="subject_account",
            label=f"Statement {statement_id} subject",
            institution=statement.bank_name or statement.bank_code,
            subject_statement_id=statement_id,
            evidence={"statement_id": statement_id, "resolution": "statement_subject"},
        ))

    by_reference: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        reference = _normal_reference(transaction.reference_no)
        if reference:
            by_reference[reference].append(transaction)

    observations: list[dict[str, Any]] = []
    created_local_nodes: set[str] = set()
    for transaction in transactions:
        direction = _direction(transaction)
        amount = _amount(transaction)
        if not direction or amount <= 0:
            continue
        source_statement_id = transaction.statement_id
        subject_id = _subject_node_id(case.id, source_statement_id)
        reference = _normal_reference(transaction.reference_no)
        mirror: Transaction | None = None
        if reference:
            # A reference alone is insufficient: direction, amount, date and a
            # different source statement must agree.  This is exact evidence.
            candidates = [
                candidate for candidate in by_reference[reference]
                if candidate.statement_id != source_statement_id and _compatible_mirror(transaction, candidate)
            ]
            if candidates:
                mirror = sorted(candidates, key=lambda candidate: (candidate.txn_date, candidate.row_id))[0]

        if mirror:
            other_id = _subject_node_id(case.id, mirror.statement_id)
            if direction == "out":
                source_node_id, target_node_id = subject_id, other_id
            else:
                source_node_id, target_node_id = other_id, subject_id
            resolution = "mirrored_reference"
            mirrored_row_id = mirror.row_id
        else:
            local_id = _counterparty_node_id(case.id, source_statement_id, transaction.counterparty_id, transaction.row_id)
            if local_id not in created_local_nodes:
                counterparty = counterparties.get(transaction.counterparty_id)
                db.add(CaseAccountNode(
                    id=local_id,
                    case_id=case.id,
                    kind="counterparty_observation",
                    label=(counterparty.canonical_name if counterparty else "Unresolved counterparty"),
                    institution=None,
                    subject_statement_id=None,
                    evidence={
                        "statement_id": source_statement_id,
                        "counterparty_id": transaction.counterparty_id,
                        "resolution": "unresolved_name_not_merged",
                    },
                ))
                created_local_nodes.add(local_id)
            if direction == "out":
                source_node_id, target_node_id = subject_id, local_id
            else:
                source_node_id, target_node_id = local_id, subject_id
            resolution = "unresolved_name_not_merged"
            mirrored_row_id = None

        observations.append({
            "source_node_id": source_node_id,
            "target_node_id": target_node_id,
            "transaction": transaction,
            "amount": amount,
            "reference": reference,
            "resolution": resolution,
            "mirrored_row_id": mirrored_row_id,
        })

    # References identify a logical transfer.  A mirrored statement observation
    # becomes one edge with both rows as source evidence; reference-less repeats
    # remain distinct because their row ID is part of the logical edge identity.
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        transaction = observation["transaction"]
        identity = observation["reference"] or transaction.row_id
        grouped[(observation["source_node_id"], observation["target_node_id"], identity)].append(observation)

    edge_rows: list[dict[str, Any]] = []
    for (source_node_id, target_node_id, identity), group in sorted(grouped.items()):
        transaction = group[0]["transaction"]
        source_rows = sorted({item["transaction"].row_id for item in group} | {
            item["mirrored_row_id"] for item in group if item["mirrored_row_id"]
        })
        source_statement_ids = sorted({item["transaction"].statement_id for item in group} | {
            db.get(Transaction, item["mirrored_row_id"]).statement_id
            for item in group if item["mirrored_row_id"] and db.get(Transaction, item["mirrored_row_id"])
        })
        edge_id = _stable_id("edge", case.id, source_node_id, target_node_id, identity)
        timestamp = datetime.combine(transaction.txn_date, datetime.min.time())
        edge = CaseTransferEdge(
            id=edge_id,
            case_id=case.id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            amount=group[0]["amount"],
            txn_date=transaction.txn_date,
            reference_fingerprint=_stable_id("ref", identity) if group[0]["reference"] else None,
            source_statement_ids=source_statement_ids,
            source_row_ids=source_rows,
            direction="outgoing_transfer",
            resolution_method=group[0]["resolution"],
            evidence={"timestamp_precision": "date", "source_coverage": len(source_rows)},
        )
        db.add(edge)
        edge_rows.append({
            "edge_id": edge_id,
            "from_account": source_node_id,
            "to_account": target_node_id,
            "from_bank": "case",
            "to_bank": "case",
            "amount": group[0]["amount"],
            "ts_seconds": timestamp.timestamp(),
            "source_row_ids": source_rows,
            "source_statement_ids": source_statement_ids,
        })

    cycles = find_conserved_cycles(edge_rows)
    for cycle in cycles:
        indices = cycle.get("transfer_indices", [])
        hop_edges = [edge_rows[index] for index in indices]
        finding_id = _stable_id("finding", case.id, cycle["cycle_id"])
        db.add(CaseFinding(
            id=finding_id,
            case_id=case.id,
            kind="conserved_flow_cycle",
            risk_score=float(cycle.get("cycle_risk_score") or 0),
            hop_count=int(cycle.get("hop_count") or 0),
            node_sequence=cycle.get("accounts", []),
            edge_ids=[edge["edge_id"] for edge in hop_edges],
            source_row_ids=sorted({row_id for edge in hop_edges for row_id in edge["source_row_ids"]}),
            source_statement_ids=sorted({statement_id for edge in hop_edges for statement_id in edge["source_statement_ids"]}),
            detail={
                **cycle,
                "formula": "amount conservation + velocity compression + recurrence + inverse hop count",
                "limitations": ["Transaction timestamps have date precision.", "Only exact mirrored references resolve statement subjects automatically."],
            },
        ))

    case.analysis_version = (case.analysis_version or 0) + 1
    case.analyzed_ts = datetime.utcnow()
    db.add(case)
    db.commit()
    return {"nodes": len(statement_ids) + len(created_local_nodes), "edges": len(edge_rows), "findings": len(cycles)}


def case_graph_payload(db: Session, case_id: int) -> dict[str, Any]:
    nodes = db.exec(select(CaseAccountNode).where(CaseAccountNode.case_id == case_id)).all()
    edges = db.exec(select(CaseTransferEdge).where(CaseTransferEdge.case_id == case_id)).all()
    findings = db.exec(select(CaseFinding).where(CaseFinding.case_id == case_id)).all()
    finding_edges = {edge_id for finding in findings for edge_id in finding.edge_ids}
    return {
        "case_id": case_id,
        "nodes": [{
            "id": node.id, "kind": node.kind, "label": node.label, "institution": node.institution,
            "risk_tier": "high" if any(node.id in finding.node_sequence for finding in findings) else "normal",
            "evidence": node.evidence or {},
        } for node in nodes],
        "edges": [{
            "id": edge.id, "source": edge.source_node_id, "target": edge.target_node_id,
            "amount": edge.amount, "txn_date": str(edge.txn_date), "source_statement_ids": edge.source_statement_ids,
            "source_row_ids": edge.source_row_ids, "resolution_method": edge.resolution_method,
            "is_finding_edge": edge.id in finding_edges,
        } for edge in edges],
        "findings": [{
            "id": finding.id, "kind": finding.kind, "risk_score": finding.risk_score, "hop_count": finding.hop_count,
            "node_sequence": finding.node_sequence, "edge_ids": finding.edge_ids, "source_row_ids": finding.source_row_ids,
        } for finding in findings],
        "limitations": ["Names are never automatically merged across statements.", "Account numbers are not returned by this API."],
    }
