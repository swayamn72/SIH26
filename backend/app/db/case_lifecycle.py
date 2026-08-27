"""Deletion helpers for derived investigation-case data.

Case graph rows are materialized evidence derived from statements.  Removing a
source statement must remove every affected materialization before the source
row is deleted, so a stale graph or SAR draft cannot expose its data.
"""

from collections.abc import Iterable

from sqlmodel import Session, select

from app.db.models import (
    Case,
    CaseAccountNode,
    CaseFinding,
    CaseStatement,
    CaseTransferEdge,
    DemoLoad,
)


def invalidate_cases_for_statements(db: Session, statement_ids: Iterable[int]) -> set[int]:
    """Remove derived graphs and memberships affected by source-statement deletion."""
    ids = {statement_id for statement_id in statement_ids}
    if not ids:
        return set()

    memberships = db.exec(
        select(CaseStatement).where(CaseStatement.statement_id.in_(ids))
    ).all()
    case_ids = {membership.case_id for membership in memberships}
    if case_ids:
        db.query(CaseFinding).filter(CaseFinding.case_id.in_(case_ids)).delete(
            synchronize_session=False
        )
        db.query(CaseTransferEdge).filter(CaseTransferEdge.case_id.in_(case_ids)).delete(
            synchronize_session=False
        )
        db.query(CaseAccountNode).filter(CaseAccountNode.case_id.in_(case_ids)).delete(
            synchronize_session=False
        )
        for case in db.exec(select(Case).where(Case.id.in_(case_ids))).all():
            case.analyzed_ts = None
            db.add(case)

    db.query(CaseStatement).filter(CaseStatement.statement_id.in_(ids)).delete(
        synchronize_session=False
    )

    # Demo loads contain statement IDs as JSON and can point at a now-invalid
    # case. Remove a matching load rather than retaining a handle to deleted PII.
    for load in db.exec(select(DemoLoad)).all():
        if ids.intersection(load.statement_ids or []) or load.case_id in case_ids:
            db.delete(load)
    return case_ids


def purge_cases(db: Session) -> None:
    """Remove every case-derived record and demo load before purging sources."""
    db.query(CaseFinding).delete(synchronize_session=False)
    db.query(CaseTransferEdge).delete(synchronize_session=False)
    db.query(CaseAccountNode).delete(synchronize_session=False)
    db.query(CaseStatement).delete(synchronize_session=False)
    db.query(DemoLoad).delete(synchronize_session=False)
    db.query(Case).delete(synchronize_session=False)
