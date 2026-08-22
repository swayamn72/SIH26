import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.db.models import Statement, Transaction, EvidenceBundleRecord
from app.evidence.evidence_schema import EvidenceBundle
from app.evidence.evidence_bundle import evidence_bundle_to_json
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
