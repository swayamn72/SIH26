import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.db.models import Counterparty, Statement, Transaction, EvidenceBundleRecord
from app.evidence.evidence_schema import EvidenceBundle
from app.evidence.evidence_bundle import evidence_bundle_to_json
from app.evidence.pattern_timeline import build_patterns
from app.evidence.why_flagged import build_why_flagged
from app.llm.narrative_generator import generate_narrative

logger = logging.getLogger(__name__)

router = APIRouter()


class TransactionOut(BaseModel):
    row_id: str
    txn_date: str
    value_date: Optional[str] = None
    narration: str
    reference_no: Optional[str] = None
    debit_amount: Optional[float] = None
    credit_amount: Optional[float] = None
    balance_after: Optional[float] = None
    channel: Optional[str] = None
    category: Optional[str] = None
    counterparty_id: Optional[int] = None
    row_confidence: float = 1.0
    is_reconciled: bool = False
    tagged_rules: list[str] = []
    tagged_cycles: list[str] = []


class TransactionPageOut(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[TransactionOut]


class NarrativeOut(BaseModel):
    statement_id: int
    narrative: str
    source: str


class PatternsOut(BaseModel):
    statement_id: int
    subject_node_id: str
    subject_label: str
    patterns: list[dict[str, Any]] = []


def _load_statement_or_404(db: Session, statement_id: int) -> Statement:
    stmt = db.get(Statement, statement_id)
    if stmt is None:
        raise HTTPException(status_code=404, detail=f"Statement {statement_id} not found")
    return stmt


@router.get("/{statement_id}/evidence")
async def get_evidence(statement_id: int, db: Session = Depends(get_session)):
    _load_statement_or_404(db, statement_id)
    rec = db.exec(
        select(EvidenceBundleRecord)
        .where(EvidenceBundleRecord.statement_id == statement_id)
        .order_by(EvidenceBundleRecord.created_ts.desc())
    ).first()
    if rec is None:
        raise HTTPException(status_code=404, detail="No evidence bundle found for this statement")
    return rec.json_blob


@router.get("/{statement_id}/why-flagged")
async def get_why_flagged(statement_id: int, db: Session = Depends(get_session)):
    """Ranked, evidence-backed reasons behind the statement's risk decision."""
    _load_statement_or_404(db, statement_id)

    rec = db.exec(
        select(EvidenceBundleRecord)
        .where(EvidenceBundleRecord.statement_id == statement_id)
        .order_by(EvidenceBundleRecord.created_ts.desc())
    ).first()
    if rec is None or not rec.json_blob:
        raise HTTPException(
            status_code=404,
            detail="No evidence bundle found for this statement - confirm extraction first",
        )

    txns = list(
        db.exec(select(Transaction).where(Transaction.statement_id == statement_id)).all()
    )
    node_labels = {
        str(cp.id): cp.canonical_name for cp in db.exec(select(Counterparty)).all()
    }

    stmt = db.get(Statement, statement_id)
    patterns = build_patterns(
        statement_id=statement_id,
        txns=txns,
        cycles=rec.json_blob.get("cycles_detected", []),
        triggered_rules=rec.json_blob.get("triggered_rules", []),
        node_labels=node_labels,
        subject_label=(stmt.account_holder if stmt else None) or f"Account #{statement_id}",
    )

    return build_why_flagged(
        statement_id=statement_id,
        bundle=rec.json_blob,
        patterns=patterns,
        txns=txns,
        node_labels=node_labels,
    )


@router.get("/{statement_id}/patterns", response_model=PatternsOut)
async def get_patterns(statement_id: int, db: Session = Depends(get_session)):
    """Suspicious patterns as hop-by-hop timelines (A -> B -> C -> A)."""
    stmt = _load_statement_or_404(db, statement_id)
    subject_node_id = f"ACCT_{statement_id}"
    subject_label = stmt.account_holder or f"Account #{statement_id}"

    txns = db.exec(
        select(Transaction).where(Transaction.statement_id == statement_id)
    ).all()
    if not txns:
        return PatternsOut(
            statement_id=statement_id,
            subject_node_id=subject_node_id,
            subject_label=subject_label,
        )

    rec = db.exec(
        select(EvidenceBundleRecord)
        .where(EvidenceBundleRecord.statement_id == statement_id)
        .order_by(EvidenceBundleRecord.created_ts.desc())
    ).first()
    blob = rec.json_blob if rec and rec.json_blob else {}

    node_labels = {
        str(cp.id): cp.canonical_name for cp in db.exec(select(Counterparty)).all()
    }

    patterns = build_patterns(
        statement_id=statement_id,
        txns=list(txns),
        cycles=blob.get("cycles_detected", []),
        triggered_rules=blob.get("triggered_rules", []),
        node_labels=node_labels,
        subject_label=subject_label,
    )

    return PatternsOut(
        statement_id=statement_id,
        subject_node_id=subject_node_id,
        subject_label=subject_label,
        patterns=patterns,
    )


@router.get("/{statement_id}/transactions", response_model=TransactionPageOut)
async def get_transactions(
    statement_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    channel: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    _load_statement_or_404(db, statement_id)

    query = select(Transaction).where(Transaction.statement_id == statement_id)
    if channel:
        query = query.where(Transaction.channel == channel)
    if category:
        query = query.where(Transaction.category == category)
    if min_amount is not None:
        query = query.where(
            (Transaction.debit_amount >= min_amount) | (Transaction.credit_amount >= min_amount)
        )
    if max_amount is not None:
        query = query.where(
            (Transaction.debit_amount <= max_amount) | (Transaction.credit_amount <= max_amount)
        )
    if search:
        query = query.where(Transaction.narration.ilike(f"%{search}%"))

    total = len(db.exec(query).all())
    query = query.offset(offset).limit(limit).order_by(Transaction.txn_date)
    txns = db.exec(query).all()

    return TransactionPageOut(
        total=total,
        offset=offset,
        limit=limit,
        items=[
            TransactionOut(
                row_id=t.row_id,
                txn_date=str(t.txn_date),
                value_date=str(t.value_date) if t.value_date else None,
                narration=t.narration or "",
                reference_no=t.reference_no,
                debit_amount=t.debit_amount,
                credit_amount=t.credit_amount,
                balance_after=t.balance_after,
                channel=t.channel,
                category=t.category,
                counterparty_id=t.counterparty_id,
                row_confidence=t.row_confidence,
                is_reconciled=t.is_reconciled,
                tagged_rules=t.tagged_rules or [],
                tagged_cycles=t.tagged_cycles or [],
            )
            for t in txns
        ],
    )


@router.get("/{statement_id}/narrative", response_model=NarrativeOut)
async def get_narrative(
    statement_id: int,
    use_ai: bool = Query(True),
    db: Session = Depends(get_session),
):
    _load_statement_or_404(db, statement_id)
    rec = db.exec(
        select(EvidenceBundleRecord)
        .where(EvidenceBundleRecord.statement_id == statement_id)
        .order_by(EvidenceBundleRecord.created_ts.desc())
    ).first()
    if rec is None:
        raise HTTPException(status_code=404, detail="No evidence bundle found; run confirm first")

    bundle = EvidenceBundle(**rec.json_blob)
    narrative, source = generate_narrative(bundle, use_ai=use_ai)
    return NarrativeOut(
        statement_id=statement_id,
        narrative=narrative,
        source=source,
    )
