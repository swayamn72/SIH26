"""Persisted, conservative multi-statement case graph construction.

Each statement starts as an independent subject account. Counterparty names are
statement-scoped observations, never identity evidence. Subject accounts are
resolved only through a unique, structurally valid mirrored transfer reference.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.config_loader import load_config
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


def _mirror_settings() -> tuple[int, set[str]]:
    config = load_config("thresholds").get("case_graph", {}).get("mirrored_reference", {})
    return (
        int(config.get("min_alphanumeric_length", 6)),
        {str(token).upper() for token in config.get("generic_tokens", [])},
    )


def _normal_reference(reference: str | None) -> str | None:
    if not reference:
        return None
    compact = "".join(ch for ch in reference.upper() if ch.isalnum())
    min_length, generic_tokens = _mirror_settings()
    if compact in generic_tokens:
        return None
    if len(compact) < min_length:
        return None
    return compact


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
    if _direction(left) == _direction(right) or abs(_amount(left) - _amount(right)) > 0.01:
        return False
    return bool(left.txn_date and right.txn_date and abs((left.txn_date - right.txn_date).days) <= 1)


def _subject_node_id(case_id: int, statement_id: int) -> str:
    return f"case_{case_id}_subject_{statement_id}"


def _counterparty_node_id(case_id: int, statement_id: int, counterparty_id: int | None) -> str:
    """A statement+counterparty node aggregates genuine repeated observations."""
    return _stable_id("node", case_id, statement_id, counterparty_id or "unresolved")


def _clear_materialized_graph(db: Session, case_id: int) -> None:
    db.query(CaseFinding).filter(CaseFinding.case_id == case_id).delete(synchronize_session=False)
    db.query(CaseTransferEdge).filter(CaseTransferEdge.case_id == case_id).delete(synchronize_session=False)
    db.query(CaseAccountNode).filter(CaseAccountNode.case_id == case_id).delete(synchronize_session=False)
    db.flush()


def analyze_case(db: Session, case: Case) -> dict[str, Any]:
    """Rebuild a case graph; each persisted finding contains exactly one ordered round."""
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

    _clear_materialized_graph(db, case.id)
    for statement_id in statement_ids:
        statement = statements.get(statement_id)
        if statement:
            db.add(CaseAccountNode(
                id=_subject_node_id(case.id, statement_id), case_id=case.id,
                kind="subject_account", label=f"Statement {statement_id} subject",
                institution=statement.bank_name or statement.bank_code,
                subject_statement_id=statement_id,
                evidence={"statement_id": statement_id, "resolution": "statement_subject"},
            ))

    by_reference: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        if reference := _normal_reference(transaction.reference_no):
            by_reference[reference].append(transaction)

    # If any row under a reference has competing compatible mirrors, the whole
    # reference is ambiguous. Resolving only a subset could still manufacture a
    # ring from the remaining unique-looking observations.
    ambiguous_references = {
        reference
        for reference, reference_transactions in by_reference.items()
        if any(
            sum(
                candidate.statement_id != transaction.statement_id
                and _compatible_mirror(transaction, candidate)
                for candidate in reference_transactions
            ) != 1
            for transaction in reference_transactions
        )
    }

    observations: list[dict[str, Any]] = []
    created_local_nodes: set[str] = set()
    for transaction in transactions:
        direction, amount = _direction(transaction), _amount(transaction)
        if not direction or amount <= 0:
            continue
        subject_id = _subject_node_id(case.id, transaction.statement_id)
        reference = _normal_reference(transaction.reference_no)
        candidates = [
            candidate for candidate in by_reference.get(reference, [])
            if candidate.statement_id != transaction.statement_id and _compatible_mirror(transaction, candidate)
        ] if reference else []
        # A shared reference can occur in batch metadata. Any competing compatible
        # counterparty is ambiguous and must remain an unresolved observation.
        mirror = candidates[0] if len(candidates) == 1 and reference not in ambiguous_references else None
        ambiguous = reference in ambiguous_references

        if mirror:
            other_id = _subject_node_id(case.id, mirror.statement_id)
            source_node_id, target_node_id = (subject_id, other_id) if direction == "out" else (other_id, subject_id)
            resolution, mirrored_row_id = "mirrored_reference", mirror.row_id
        else:
            local_id = _counterparty_node_id(case.id, transaction.statement_id, transaction.counterparty_id)
            if local_id not in created_local_nodes:
                counterparty = counterparties.get(transaction.counterparty_id)
                db.add(CaseAccountNode(
                    id=local_id, case_id=case.id, kind="counterparty_observation",
                    label=counterparty.canonical_name if counterparty else "Unresolved counterparty",
                    evidence={"statement_id": transaction.statement_id, "counterparty_id": transaction.counterparty_id,
                              "resolution": "unresolved_name_not_merged"},
                ))
                created_local_nodes.add(local_id)
            source_node_id, target_node_id = (subject_id, local_id) if direction == "out" else (local_id, subject_id)
            resolution, mirrored_row_id = ("ambiguous_mirrored_reference", None) if ambiguous else ("unresolved_name_not_merged", None)

        observations.append({
            "source_node_id": source_node_id, "target_node_id": target_node_id,
            "transaction": transaction, "amount": amount, "reference": reference,
            "resolution": resolution, "mirrored_row_id": mirrored_row_id,
        })

    # A mirrored pair is one logical transfer; all other observations, including
    # same-reference repeats, keep their source row in the identity and stay distinct.
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        transaction = observation["transaction"]
        if observation["resolution"] == "mirrored_reference":
            # A reference may legitimately be reused later. The exact mirrored
            # row pair identifies one logical transfer without collapsing repeats.
            identity = _stable_id(
                "mirror", observation["reference"], *sorted((transaction.row_id, observation["mirrored_row_id"]))
            )
        else:
            identity = transaction.row_id
        grouped[(observation["source_node_id"], observation["target_node_id"], identity)].append(observation)

    edge_rows: list[dict[str, Any]] = []
    for (source_node_id, target_node_id, identity), group in sorted(grouped.items()):
        transaction = group[0]["transaction"]
        source_rows = sorted({item["transaction"].row_id for item in group} | {
            item["mirrored_row_id"] for item in group if item["mirrored_row_id"]
        })
        source_statement_ids = sorted({
            db.get(Transaction, row_id).statement_id for row_id in source_rows if db.get(Transaction, row_id)
        })
        edge_id = _stable_id("edge", case.id, source_node_id, target_node_id, identity)
        edge = CaseTransferEdge(
            id=edge_id, case_id=case.id, source_node_id=source_node_id, target_node_id=target_node_id,
            amount=group[0]["amount"], txn_date=transaction.txn_date,
            reference_fingerprint=_stable_id("ref", identity) if group[0]["reference"] else None,
            source_statement_ids=source_statement_ids, source_row_ids=source_rows,
            direction="outgoing_transfer", resolution_method=group[0]["resolution"],
            evidence={"timestamp_precision": "date", "source_coverage": len(source_rows)},
        )
        db.add(edge)
        edge_rows.append({
            "edge_id": edge_id, "from_account": source_node_id, "to_account": target_node_id,
            "from_bank": "case", "to_bank": "case", "amount": group[0]["amount"],
            "ts_seconds": datetime.combine(transaction.txn_date, datetime.min.time()).timestamp(),
            "source_row_ids": source_rows, "source_statement_ids": source_statement_ids,
        })

    cycles = find_conserved_cycles(edge_rows)
    for cycle in cycles:
        indices = cycle.get("transfer_indices", [])
        hop_edges = [edge_rows[index] for index in indices]
        # flow_cycles supplies a single chronological DFS path. Persist it unchanged;
        # do not union repeat episodes into a path whose edges/nodes disagree.
        node_sequence = [hop_edges[0]["from_account"]] + [edge["to_account"] for edge in hop_edges]
        if len(hop_edges) != cycle.get("hop_count") or node_sequence[0] != node_sequence[-1]:
            continue
        finding_id = _stable_id("finding", case.id, *[edge["edge_id"] for edge in hop_edges])
        db.add(CaseFinding(
            id=finding_id, case_id=case.id, kind="conserved_flow_cycle",
            risk_score=float(cycle.get("cycle_risk_score") or 0), hop_count=len(hop_edges),
            node_sequence=node_sequence, edge_ids=[edge["edge_id"] for edge in hop_edges],
            source_row_ids=sorted({row_id for edge in hop_edges for row_id in edge["source_row_ids"]}),
            source_statement_ids=sorted({statement_id for edge in hop_edges for statement_id in edge["source_statement_ids"]}),
            detail={
                **cycle, "accounts": node_sequence[:-1], "transfer_indices": indices,
                "formula": "amount conservation + velocity compression + recurrence + inverse hop count",
                "limitations": ["Transaction timestamps have date precision.", "Only unique, structurally valid mirrored references resolve statement subjects automatically."],
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
        "nodes": [{"id": node.id, "kind": node.kind, "label": node.label, "institution": node.institution,
                   "risk_tier": "high" if any(node.id in finding.node_sequence for finding in findings) else "normal",
                   "evidence": node.evidence or {}} for node in nodes],
        "edges": [{"id": edge.id, "source": edge.source_node_id, "target": edge.target_node_id,
                   "amount": edge.amount, "txn_date": str(edge.txn_date), "source_statement_ids": edge.source_statement_ids,
                   "source_row_ids": edge.source_row_ids, "resolution_method": edge.resolution_method,
                   "is_finding_edge": edge.id in finding_edges} for edge in edges],
        "findings": [{"id": finding.id, "kind": finding.kind, "risk_score": finding.risk_score,
                      "hop_count": finding.hop_count, "node_sequence": finding.node_sequence,
                      "edge_ids": finding.edge_ids, "source_row_ids": finding.source_row_ids} for finding in findings],
        "limitations": ["Names are never automatically merged across statements.", "Account numbers are not returned by this API."],
    }
