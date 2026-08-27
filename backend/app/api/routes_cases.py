"""Investigation case APIs for the multi-statement technical-winner slice."""

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.db.models import (
    Case,
    CaseAccountNode,
    CaseFinding,
    CaseStatement,
    CaseTransferEdge,
    Statement,
    Transaction,
)
from app.db.session import get_session
from app.graph.case_graph import analyze_case, case_graph_payload

router = APIRouter()


class CaseCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2048)
    statement_ids: list[int] = []


class CaseUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CaseOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_ts: str
    analyzed_ts: Optional[str] = None
    analysis_version: int
    statement_ids: list[int]


class StatementMembershipIn(BaseModel):
    statement_id: int


def _case_or_404(db: Session, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case


def _statement_or_404(db: Session, statement_id: int) -> Statement:
    statement = db.get(Statement, statement_id)
    if not statement:
        raise HTTPException(status_code=404, detail=f"Statement {statement_id} not found")
    return statement


def _confirmed_statement_or_422(db: Session, statement_id: int) -> Statement:
    statement = _statement_or_404(db, statement_id)
    if (statement.status or "").lower() not in {"confirmed", "analyzed"}:
        raise HTTPException(
            status_code=422,
            detail="Only confirmed or analyzed statements can be added to a case",
        )
    return statement


def _out(db: Session, case: Case) -> CaseOut:
    statement_ids = [
        membership.statement_id
        for membership in db.exec(
            select(CaseStatement).where(CaseStatement.case_id == case.id).order_by(CaseStatement.statement_id)
        ).all()
    ]
    return CaseOut(
        id=case.id,
        name=case.name,
        description=case.description,
        created_ts=case.created_ts.isoformat(),
        analyzed_ts=case.analyzed_ts.isoformat() if case.analyzed_ts else None,
        analysis_version=case.analysis_version,
        statement_ids=statement_ids,
    )


@router.post("", response_model=CaseOut, status_code=201)
def create_case(body: CaseCreateIn, db: Session = Depends(get_session)):
    # Validate first: a failed request must never create a partial investigation.
    for statement_id in set(body.statement_ids):
        _confirmed_statement_or_422(db, statement_id)
    case = Case(name=body.name.strip(), description=body.description)
    db.add(case)
    db.flush()
    for statement_id in sorted(set(body.statement_ids)):
        db.add(CaseStatement(case_id=case.id, statement_id=statement_id))
    db.commit()
    db.refresh(case)
    return _out(db, case)


@router.get("", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_session)):
    return [_out(db, case) for case in db.exec(select(Case).order_by(Case.id.desc())).all()]


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: int, db: Session = Depends(get_session)):
    return _out(db, _case_or_404(db, case_id))


@router.patch("/{case_id}", response_model=CaseOut)
def rename_case(case_id: int, body: CaseUpdateIn, db: Session = Depends(get_session)):
    case = _case_or_404(db, case_id)
    case.name = body.name.strip()
    db.add(case)
    db.commit()
    db.refresh(case)
    return _out(db, case)


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: int, db: Session = Depends(get_session)):
    _case_or_404(db, case_id)
    db.query(CaseFinding).filter(CaseFinding.case_id == case_id).delete()
    db.query(CaseTransferEdge).filter(CaseTransferEdge.case_id == case_id).delete()
    db.query(CaseAccountNode).filter(CaseAccountNode.case_id == case_id).delete()
    db.query(CaseStatement).filter(CaseStatement.case_id == case_id).delete()
    db.query(Case).filter(Case.id == case_id).delete()
    db.commit()
    return Response(status_code=204)


@router.post("/{case_id}/statements", response_model=CaseOut)
def add_statement(case_id: int, body: StatementMembershipIn, db: Session = Depends(get_session)):
    case = _case_or_404(db, case_id)
    _confirmed_statement_or_422(db, body.statement_id)
    existing = db.get(CaseStatement, (case_id, body.statement_id))
    if not existing:
        db.add(CaseStatement(case_id=case_id, statement_id=body.statement_id))
        db.commit()
    return _out(db, case)


@router.delete("/{case_id}/statements/{statement_id}", response_model=CaseOut)
def remove_statement(case_id: int, statement_id: int, db: Session = Depends(get_session)):
    case = _case_or_404(db, case_id)
    membership = db.get(CaseStatement, (case_id, statement_id))
    if not membership:
        raise HTTPException(status_code=404, detail="Statement is not a member of this case")
    db.delete(membership)
    db.commit()
    return _out(db, case)


@router.post("/{case_id}/analyze")
def analyze(case_id: int, db: Session = Depends(get_session)):
    case = _case_or_404(db, case_id)
    summary = analyze_case(db, case)
    db.refresh(case)
    return {"case": _out(db, case).model_dump(), "summary": summary}


@router.post("/{case_id}/reanalyze")
def reanalyze(case_id: int, db: Session = Depends(get_session)):
    return analyze(case_id, db)


@router.get("/{case_id}/graph")
def get_case_graph(case_id: int, db: Session = Depends(get_session)):
    _case_or_404(db, case_id)
    return case_graph_payload(db, case_id)


@router.get("/{case_id}/findings/{finding_id}")
def get_finding(case_id: int, finding_id: str, db: Session = Depends(get_session)):
    _case_or_404(db, case_id)
    finding = db.get(CaseFinding, finding_id)
    if not finding or finding.case_id != case_id:
        raise HTTPException(status_code=404, detail="Finding not found")
    edges = [db.get(CaseTransferEdge, edge_id) for edge_id in finding.edge_ids]
    return {
        "id": finding.id,
        "case_id": case_id,
        "kind": finding.kind,
        "risk_score": finding.risk_score,
        "hop_count": finding.hop_count,
        "node_sequence": finding.node_sequence,
        "edge_ids": finding.edge_ids,
        "source_row_ids": finding.source_row_ids,
        "source_statement_ids": finding.source_statement_ids,
        "detail": finding.detail,
        "ordered_hops": [
            {
                "edge_id": edge.id,
                "source": edge.source_node_id,
                "target": edge.target_node_id,
                "amount": edge.amount,
                "txn_date": str(edge.txn_date),
                "source_row_ids": edge.source_row_ids,
                "source_statement_ids": edge.source_statement_ids,
            }
            for edge in edges if edge
        ],
    }


@router.get("/{case_id}/nodes/{node_id}/transactions")
def node_transactions(
    case_id: int,
    node_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    direction: Optional[str] = Query(None, pattern="^(in|out)$"),
    statement_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    finding_id: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    _case_or_404(db, case_id)
    if not db.get(CaseAccountNode, node_id):
        raise HTTPException(status_code=404, detail="Node not found")
    edges = db.exec(
        select(CaseTransferEdge).where(
            CaseTransferEdge.case_id == case_id,
            (CaseTransferEdge.source_node_id == node_id) | (CaseTransferEdge.target_node_id == node_id),
        ).order_by(CaseTransferEdge.txn_date, CaseTransferEdge.id)
    ).all()
    if finding_id:
        finding = db.get(CaseFinding, finding_id)
        if not finding or finding.case_id != case_id:
            raise HTTPException(status_code=404, detail="Finding not found")
        edges = [edge for edge in edges if edge.id in finding.edge_ids]
    filtered: list[dict[str, Any]] = []
    for edge in edges:
        edge_direction = "out" if edge.source_node_id == node_id else "in"
        if direction and edge_direction != direction:
            continue
        if statement_id is not None and statement_id not in (edge.source_statement_ids or []):
            continue
        if start_date and edge.txn_date < start_date or end_date and edge.txn_date > end_date:
            continue
        if min_amount is not None and edge.amount < min_amount or max_amount is not None and edge.amount > max_amount:
            continue
        for row_id in edge.source_row_ids or []:
            transaction = db.get(Transaction, row_id)
            if not transaction:
                continue
            statement = db.get(Statement, transaction.statement_id)
            filtered.append({
                "edge_id": edge.id, "direction": edge_direction, "row_id": transaction.row_id,
                "statement_id": transaction.statement_id, "source_filename": statement.original_filename if statement else None,
                "txn_date": str(transaction.txn_date), "amount": edge.amount, "narration": transaction.narration,
                "reference_no": transaction.reference_no, "debit_amount": transaction.debit_amount,
                "credit_amount": transaction.credit_amount,
            })
    return {"total": len(filtered), "offset": offset, "limit": limit, "items": filtered[offset:offset + limit]}
