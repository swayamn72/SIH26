from datetime import date

from fastapi.testclient import TestClient

from sqlmodel import Session, SQLModel, create_engine

from app.api.routes_sar import export_sar_draft
from app.db.models import Case, CaseAccountNode, CaseFinding, CaseTransferEdge, Statement
from app.sar.draft import build_sar_draft


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _finding(db: Session) -> tuple[Case, CaseFinding]:
    statement = Statement(filename_hash="hash", status="confirmed", account_holder="A. Analyst", bank_name="Example Bank")
    case = Case(name="Evidence case")
    db.add_all([statement, case])
    db.flush()
    source, target = "node-a", "node-b"
    db.add_all([
        CaseAccountNode(id=source, case_id=case.id, kind="subject_account", label="A. Analyst"),
        CaseAccountNode(id=target, case_id=case.id, kind="subject_account", label="B. Counterparty"),
        CaseTransferEdge(id="edge-1", case_id=case.id, source_node_id=source, target_node_id=target, amount=1250.0, txn_date=date(2026, 8, 20), source_row_ids=["row-1"], source_statement_ids=[statement.id]),
    ])
    finding = CaseFinding(
        id="finding-1", case_id=case.id, kind="conserved_flow_cycle", risk_score=0.9,
        hop_count=1, node_sequence=[source, target], edge_ids=["edge-1"], source_row_ids=["row-1"],
        source_statement_ids=[statement.id], detail={"limitations": ["Source data is date precision."]},
    )
    db.add(finding)
    db.commit()
    return case, finding


def test_draft_is_deterministic_evidence_cited_and_non_filing():
    db = _session()
    case, finding = _finding(db)

    first = build_sar_draft(db, case.id, finding.id)
    second = build_sar_draft(db, case.id, finding.id)

    assert first == second
    assert first["filing_status"] == "NOT_FILED"
    assert first["reviewer_confirmation"]["required"] is True
    assert first["reviewer_confirmation"]["confirmed"] is False
    assert first["activity"]["total_suspicious_value"] == 1250.0
    assert first["ordered_graph_path"][0]["evidence_ids"] == ["edge-1", "row-1"]
    assert "finding-1" in first["evidence_ids"]
    assert "jurisdiction" in " ".join(first["missing_required_fields"]).lower()


def test_json_and_html_exports_set_attachment_filename():
    db = _session()
    case, finding = _finding(db)

    json_response = export_sar_draft(case.id, finding.id, "json", db)
    html_response = export_sar_draft(case.id, finding.id, "html", db)

    assert json_response.media_type == "application/json"
    assert json_response.headers["content-disposition"] == 'attachment; filename="case_1_finding_finding-1_sar_str_draft.json"'
    assert html_response.media_type == "text/html"
    assert html_response.headers["content-disposition"] == 'attachment; filename="case_1_finding_finding-1_sar_str_draft.html"'
    assert "NOT FILED" in html_response.body.decode()


def test_draft_api_returns_canonical_json_and_html_export(monkeypatch):
    from app.db.session import get_session
    from app.main import app

    db = _session()
    case, finding = _finding(db)

    def override_session():
        yield db

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            draft = client.get(f"/api/cases/{case.id}/findings/{finding.id}/sar-draft")
            html = client.get(f"/api/cases/{case.id}/findings/{finding.id}/sar-draft/export?format=html")
        assert draft.status_code == 200
        assert draft.json()["filing_status"] == "NOT_FILED"
        assert html.status_code == 200
        assert html.headers["content-disposition"].endswith('sar_str_draft.html"')
    finally:
        app.dependency_overrides.clear()
        db.close()
