from datetime import date

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes_upload import delete_statement, purge_all_data
from app.db.models import (
    Case,
    CaseAccountNode,
    CaseFinding,
    CaseStatement,
    CaseTransferEdge,
    DemoLoad,
    Statement,
    Transaction,
)
from app.graph.case_graph import analyze_case


def _session() -> Session:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _statement(db: Session, label: str) -> Statement:
    statement = Statement(filename_hash=f"hash-{label}", original_filename=f"{label}.csv", status="confirmed")
    db.add(statement)
    db.flush()
    return statement


def _case_with_materialization(db: Session) -> tuple[Case, Statement, Statement]:
    first, second = _statement(db, "first"), _statement(db, "second")
    case = Case(name="Lifecycle")
    db.add(case)
    db.flush()
    db.add_all([
        CaseStatement(case_id=case.id, statement_id=first.id),
        CaseStatement(case_id=case.id, statement_id=second.id),
        CaseAccountNode(id="lifecycle-node", case_id=case.id, kind="subject_account", label="Subject"),
        CaseTransferEdge(id="lifecycle-edge", case_id=case.id, source_node_id="lifecycle-node", target_node_id="lifecycle-node", amount=1, txn_date=date(2025, 1, 1)),
        CaseFinding(id="lifecycle-finding", case_id=case.id, kind="conserved_flow_cycle", detail={}),
        DemoLoad(tag="lifecycle-demo", case_id=case.id, statement_ids=[first.id]),
    ])
    db.commit()
    return case, first, second


def test_statement_delete_invalidates_case_graph_membership_and_demo_load():
    db = _session()
    case, first, second = _case_with_materialization(db)

    assert delete_statement(first.id, db)["status"] == "deleted"

    assert db.get(Statement, first.id) is None
    assert db.get(CaseStatement, (case.id, first.id)) is None
    assert db.get(CaseStatement, (case.id, second.id)) is not None
    assert db.exec(select(CaseFinding).where(CaseFinding.case_id == case.id)).all() == []
    assert db.exec(select(CaseTransferEdge).where(CaseTransferEdge.case_id == case.id)).all() == []
    assert db.exec(select(CaseAccountNode).where(CaseAccountNode.case_id == case.id)).all() == []
    assert db.get(DemoLoad, "lifecycle-demo") is None


def test_purge_removes_cases_graphs_and_demo_loads():
    db = _session()
    case, first, _ = _case_with_materialization(db)
    first_id, case_id = first.id, case.id

    assert purge_all_data(db)["status"] == "purged"


    assert db.get(Statement, first_id) is None
    assert db.get(Case, case_id) is None
    assert db.exec(select(CaseStatement)).all() == []
    assert db.exec(select(CaseFinding)).all() == []
    assert db.exec(select(CaseTransferEdge)).all() == []
    assert db.exec(select(CaseAccountNode)).all() == []
    assert db.get(DemoLoad, "lifecycle-demo") is None


def _ring(db: Session, reference_ab: str = "AB-000001", duplicate_ab: bool = False) -> Case:
    statements = [_statement(db, label) for label in ("a", "b", "c")]
    case = Case(name="Ring")
    db.add(case)
    db.flush()
    for statement in statements:
        db.add(CaseStatement(case_id=case.id, statement_id=statement.id))
    transfers = [
        (0, "a-ab", reference_ab, 1000, None, 1), (1, "b-ab", reference_ab, None, 1000, 1),
        (1, "b-bc", "BC-000001", 1000, None, 2), (2, "c-bc", "BC-000001", None, 1000, 2),
        (2, "c-ca", "CA-000001", 1000, None, 3), (0, "a-ca", "CA-000001", None, 1000, 3),
    ]
    if duplicate_ab:
        transfers.append((2, "c-ab-collision", reference_ab, None, 1000, 1))
    for index, row_id, reference, debit, credit, day in transfers:
        db.add(Transaction(row_id=row_id, statement_id=statements[index].id, txn_date=date(2025, 1, day),
                           narration="transfer", reference_no=reference, debit_amount=debit, credit_amount=credit))
    db.commit()
    return case


def test_short_or_generic_reference_cannot_resolve_subjects():
    db = _session()
    case = _ring(db, reference_ab="REF")
    result = analyze_case(db, case)

    assert result["findings"] == 0
    edges = db.exec(select(CaseTransferEdge).where(CaseTransferEdge.case_id == case.id)).all()
    assert not any(edge.resolution_method == "mirrored_reference" and "a-ab" in edge.source_row_ids for edge in edges)


def test_ambiguous_mirrored_reference_is_flagged_and_does_not_close_ring():
    db = _session()
    case = _ring(db, duplicate_ab=True)
    result = analyze_case(db, case)

    assert result["findings"] == 0
    edges = db.exec(select(CaseTransferEdge).where(CaseTransferEdge.case_id == case.id)).all()
    assert any(edge.resolution_method == "ambiguous_mirrored_reference" for edge in edges)


def test_repeated_reference_transfers_remain_separate_logical_edges():
    db = _session()
    case = _ring(db)
    memberships = db.exec(select(CaseStatement).where(CaseStatement.case_id == case.id).order_by(CaseStatement.statement_id)).all()
    a_id, b_id = memberships[0].statement_id, memberships[1].statement_id
    db.add_all([
        Transaction(row_id="a-ab-repeat", statement_id=a_id, txn_date=date(2025, 1, 5), narration="transfer", reference_no="AB-000001", debit_amount=1000),
        Transaction(row_id="b-ab-repeat", statement_id=b_id, txn_date=date(2025, 1, 5), narration="transfer", reference_no="AB-000001", credit_amount=1000),
    ])
    db.commit()

    analyze_case(db, case)
    edges = db.exec(select(CaseTransferEdge).where(CaseTransferEdge.case_id == case.id)).all()
    repeated_edges = [edge for edge in edges if {"a-ab", "b-ab"}.issubset(edge.source_row_ids) or {"a-ab-repeat", "b-ab-repeat"}.issubset(edge.source_row_ids)]

    assert len(repeated_edges) == 2
    assert all(len(edge.source_row_ids) == 2 for edge in repeated_edges)


def test_finding_persists_one_ordered_closed_ring():
    db = _session()
    case = _ring(db)
    assert analyze_case(db, case)["findings"] == 1
    finding = db.exec(select(CaseFinding).where(CaseFinding.case_id == case.id)).one()
    edges = [db.get(CaseTransferEdge, edge_id) for edge_id in finding.edge_ids]

    assert finding.hop_count == len(finding.edge_ids) == 3
    assert len(finding.node_sequence) == finding.hop_count + 1
    assert finding.node_sequence[0] == finding.node_sequence[-1]
    assert [edge.source_node_id for edge in edges] + [edges[-1].target_node_id] == finding.node_sequence
    assert [edge.txn_date for edge in edges] == sorted(edge.txn_date for edge in edges)
