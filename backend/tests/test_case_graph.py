from datetime import date

from sqlmodel import Session, SQLModel, create_engine

from app.db.models import Case, CaseStatement, Counterparty, Statement, Transaction
from app.graph.case_graph import analyze_case, case_graph_payload


def _session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _statement(db: Session, name: str) -> Statement:
    statement = Statement(filename_hash=f"hash-{name}", original_filename=f"{name}.csv", status="confirmed")
    db.add(statement)
    db.flush()
    return statement


def _transaction(
    db: Session,
    row_id: str,
    statement_id: int,
    txn_date: date,
    reference: str | None,
    debit: float | None = None,
    credit: float | None = None,
    counterparty_id: int | None = None,
) -> None:
    db.add(Transaction(
        row_id=row_id,
        statement_id=statement_id,
        txn_date=txn_date,
        reference_no=reference,
        narration="transfer",
        debit_amount=debit,
        credit_amount=credit,
        counterparty_id=counterparty_id,
    ))


def test_case_analysis_detects_exact_mirrored_three_hop_ring():
    db = _session()
    a, b, c = (_statement(db, name) for name in ("a", "b", "c"))
    case = Case(name="Trident")
    db.add(case)
    db.flush()
    for statement in (a, b, c):
        db.add(CaseStatement(case_id=case.id, statement_id=statement.id))

    # Each transfer is seen from both account statements with the exact reference.
    _transaction(db, "a-ab", a.id, date(2025, 1, 1), "AB-001", debit=1000)
    _transaction(db, "b-ab", b.id, date(2025, 1, 1), "AB-001", credit=1000)
    _transaction(db, "b-bc", b.id, date(2025, 1, 2), "BC-001", debit=1000)
    _transaction(db, "c-bc", c.id, date(2025, 1, 2), "BC-001", credit=1000)
    _transaction(db, "c-ca", c.id, date(2025, 1, 3), "CA-001", debit=1000)
    _transaction(db, "a-ca", a.id, date(2025, 1, 3), "CA-001", credit=1000)
    db.commit()

    summary = analyze_case(db, case)
    graph = case_graph_payload(db, case.id)

    assert summary == {"nodes": 3, "edges": 3, "findings": 1}
    assert len(graph["findings"]) == 1
    finding = graph["findings"][0]
    assert finding["hop_count"] == 3
    assert len(finding["edge_ids"]) == 3
    assert {row_id for edge in graph["edges"] for row_id in edge["source_row_ids"]} == {
        "a-ab", "b-ab", "b-bc", "c-bc", "c-ca", "a-ca"
    }


def test_same_counterparty_name_does_not_auto_merge_or_create_loop():
    db = _session()
    a, b, c = (_statement(db, name) for name in ("a", "b", "c"))
    case = Case(name="Same name control")
    db.add(case)
    db.flush()
    for statement in (a, b, c):
        db.add(CaseStatement(case_id=case.id, statement_id=statement.id))
    alex_a = Counterparty(canonical_name="ALEX", first_seen_statement_id=a.id)
    alex_b = Counterparty(canonical_name="ALEX", first_seen_statement_id=b.id)
    alex_c = Counterparty(canonical_name="ALEX", first_seen_statement_id=c.id)
    db.add_all([alex_a, alex_b, alex_c])
    db.flush()
    _transaction(db, "a-1", a.id, date(2025, 1, 1), None, debit=1000, counterparty_id=alex_a.id)
    _transaction(db, "b-1", b.id, date(2025, 1, 2), None, debit=1000, counterparty_id=alex_b.id)
    _transaction(db, "c-1", c.id, date(2025, 1, 3), None, debit=1000, counterparty_id=alex_c.id)
    db.commit()

    summary = analyze_case(db, case)
    graph = case_graph_payload(db, case.id)

    assert summary["findings"] == 0
    assert graph["findings"] == []
    assert len({edge["target"] for edge in graph["edges"]}) == 3
    assert {edge["resolution_method"] for edge in graph["edges"]} == {"unresolved_name_not_merged"}
