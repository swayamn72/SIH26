import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.db.models import Statement, Transaction, Cycle, EvidenceBundleRecord, Counterparty
from app.graph.graph_builder import build_transaction_graph, graph_to_json
from app.graph.cycle_detector import detect_cycles
from app.graph.centrality import compute_centrality_metrics


logger = logging.getLogger(__name__)

router = APIRouter()


class BatchMergeIn(BaseModel):
    statement_ids: list[int]


class GraphOut(BaseModel):
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    cycles: list[dict[str, Any]] = []
    centrality: dict[str, dict[str, float]] = {}
    mule_row_ids: list[str] = []
    mule_nodes: list[str] = []


def _load_statement_or_404(db: Session, statement_id: int) -> Statement:
    stmt = db.get(Statement, statement_id)
    if stmt is None:
        raise HTTPException(status_code=404, detail=f"Statement {statement_id} not found")
    return stmt


def _transactions_to_df(txns: list[Transaction]) -> pd.DataFrame:
    records = []
    for t in txns:
        records.append({
            "row_id": t.row_id,
            "txn_date": t.txn_date,
            "value_date": t.value_date,
            "narration": t.narration or "",
            "reference_no": t.reference_no,
            "debit_amount": float(t.debit_amount) if t.debit_amount else 0.0,
            "credit_amount": float(t.credit_amount) if t.credit_amount else 0.0,
            "balance_after": float(t.balance_after) if t.balance_after else None,
            "channel": t.channel or "",
            "counterparty_id": str(t.counterparty_id) if t.counterparty_id else "UNKNOWN",
        })
    return pd.DataFrame(records)


@router.get("/{statement_id}/graph", response_model=GraphOut)
async def get_graph(statement_id: int, db: Session = Depends(get_session)):
    _load_statement_or_404(db, statement_id)
    txns = db.exec(
        select(Transaction).where(Transaction.statement_id == statement_id)
    ).all()
    if not txns:
        return GraphOut()

    all_cps = db.exec(select(Counterparty)).all()
    node_labels = {str(cp.id): cp.canonical_name for cp in all_cps}

    df = _transactions_to_df(txns)
    G = build_transaction_graph(df, subject_account_id=f"ACCT_{statement_id}", node_labels=node_labels)
    graph_data = graph_to_json(G)
    centrality = compute_centrality_metrics(G)

    # Use pre-computed cycles from cache — avoid re-running expensive cycle detection
    ev_rec = db.exec(
        select(EvidenceBundleRecord)
        .where(EvidenceBundleRecord.statement_id == statement_id)
        .order_by(EvidenceBundleRecord.created_ts.desc())
    ).first()

    cycles: list[dict] = []
    mule_row_ids_set: set[str] = set()
    mule_nodes_set: set[str] = set()

    if ev_rec and ev_rec.json_blob:
        cycles = ev_rec.json_blob.get("cycles_detected", [])
        for r in ev_rec.json_blob.get("triggered_rules", []):
            for r_id in r.get("contributing_row_ids", []):
                if r_id:
                    mule_row_ids_set.add(str(r_id))
        for c in cycles:
            for r_id in c.get("contributing_row_ids", []):
                if r_id:
                    mule_row_ids_set.add(str(r_id))
            for n in c.get("nodes", []):
                if n:
                    mule_nodes_set.add(str(n))
    else:
        # Fallback: run detection only if no cache exists yet
        cycles = detect_cycles(G)
        for c in cycles:
            for r_id in c.get("contributing_row_ids", []):
                if r_id:
                    mule_row_ids_set.add(str(r_id))
            for n in c.get("nodes", []):
                if n:
                    mule_nodes_set.add(str(n))

    return GraphOut(
        nodes=graph_data.get("nodes", []),
        edges=graph_data.get("edges", []),
        cycles=cycles,
        centrality=centrality,
        mule_row_ids=list(mule_row_ids_set),
        mule_nodes=list(mule_nodes_set),
    )


@router.post("/batch/merge", response_model=GraphOut)
async def batch_merge(body: BatchMergeIn, db: Session = Depends(get_session)):
    if not body.statement_ids:
        raise HTTPException(status_code=400, detail="statement_ids list is required")
    if len(body.statement_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 statements to merge")

    all_txns: list[Transaction] = []
    for sid in body.statement_ids:
        _load_statement_or_404(db, sid)
        txns = db.exec(
            select(Transaction).where(Transaction.statement_id == sid)
        ).all()
        all_txns.extend(txns)

    if not all_txns:
        return GraphOut()

    all_cps = db.exec(select(Counterparty)).all()
    node_labels = {str(cp.id): cp.canonical_name for cp in all_cps}

    df = _transactions_to_df(all_txns)
    G = build_transaction_graph(df, subject_account_id="ACCT_MERGED", node_labels=node_labels)
    graph_data = graph_to_json(G)
    cycles = detect_cycles(G)
    centrality = compute_centrality_metrics(G)

    mule_row_ids_set = set()
    mule_nodes_set = set()
    for c in cycles:
        for r_id in c.get("contributing_row_ids", []):
            if r_id:
                mule_row_ids_set.add(str(r_id))
        for n in c.get("nodes", []):
            if n:
                mule_nodes_set.add(str(n))

    for c in cycles:
        cycle_rec = Cycle(
            node_sequence=c.get("nodes", []),
            hop_count=c.get("hop_count", 0),
            amount_conservation_ratio=c.get("amount_conservation_ratio"),
            cycle_span_days=c.get("cycle_span_days"),
            cycle_risk_score=c.get("cycle_risk_score"),
            contributing_row_ids=c.get("contributing_row_ids", []),
        )
        db.add(cycle_rec)
    db.commit()

    return GraphOut(
        nodes=graph_data.get("nodes", []),
        edges=graph_data.get("edges", []),
        cycles=cycles,
        centrality=centrality,
        mule_row_ids=list(mule_row_ids_set),
        mule_nodes=list(mule_nodes_set),
    )
