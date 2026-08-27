"""Idempotent Project Trident demo loading through the normal statement pipeline.

The manifest is used only after analysis to verify the checked-in synthetic
fixture. It is never supplied to extraction, scoring, or graph detection.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlmodel import Session, select

from app.api.routes_cases import CaseCreateIn, create_case
from app.api.routes_review import confirm_extraction
from app.api.routes_upload import UPLOAD_DIR, upload_statements
from app.db.models import (
    Case,
    CaseAccountNode,
    CaseFinding,
    CaseStatement,
    CaseTransferEdge,
    Counterparty,
    Cycle,
    DemoLoad,
    EvidenceBundleRecord,
    InvestigatorLabel,
    Statement,
    Transaction,
)
from app.graph.case_graph import analyze_case

PROJECT_TRIDENT_TAG = "project-trident"
PROJECT_TRIDENT_CASE_NAME = "Project Trident"
DEMO_DIR = Path(__file__).resolve().parents[3] / "test_data" / "demo" / "project_trident"


def _manifest(demo_dir: Path = DEMO_DIR) -> dict[str, Any]:
    return json.loads((demo_dir / "manifest.json").read_text(encoding="utf-8"))


def _remove_uploaded_file(db: Session, statement: Statement) -> None:
    """Remove the managed fixture only when no non-demo statement shares it."""
    if not statement.original_filename:
        return
    shared = db.exec(
        select(Statement).where(
            Statement.filename_hash == statement.filename_hash,
            Statement.original_filename == statement.original_filename,
        )
    ).first()
    if shared:
        return
    path = UPLOAD_DIR / f"{statement.filename_hash}_{statement.original_filename}"
    path.unlink(missing_ok=True)


def reset_project_trident(db: Session) -> dict[str, int]:
    """Delete only records listed in the Project Trident demo tag."""
    load = db.get(DemoLoad, PROJECT_TRIDENT_TAG)
    if not load:
        return {"cases": 0, "statements": 0}

    statement_ids = list(load.statement_ids or [])
    case_id = load.case_id
    statements = [db.get(Statement, statement_id) for statement_id in statement_ids]

    if case_id is not None:
        db.query(CaseFinding).filter(CaseFinding.case_id == case_id).delete()
        db.query(CaseTransferEdge).filter(CaseTransferEdge.case_id == case_id).delete()
        db.query(CaseAccountNode).filter(CaseAccountNode.case_id == case_id).delete()
        db.query(CaseStatement).filter(CaseStatement.case_id == case_id).delete()
        db.query(Case).filter(Case.id == case_id).delete()

    for statement_id in statement_ids:
        db.query(Transaction).filter(Transaction.statement_id == statement_id).delete()
        db.query(EvidenceBundleRecord).filter(
            EvidenceBundleRecord.statement_id == statement_id
        ).delete()
        db.query(Cycle).filter(Cycle.statement_id == statement_id).delete()
        db.query(InvestigatorLabel).filter(
            InvestigatorLabel.statement_id == statement_id
        ).delete()
        # Counterparties are statement-scoped by the confirmation service.
        db.query(Counterparty).filter(
            Counterparty.first_seen_statement_id == statement_id
        ).delete()
        db.query(Statement).filter(Statement.id == statement_id).delete()

    db.delete(load)
    db.commit()
    for statement in statements:
        if statement:
            _remove_uploaded_file(db, statement)
    return {"cases": 1 if case_id is not None else 0, "statements": len(statement_ids)}


def _verification(
    db: Session,
    case_id: int,
    statement_ids: list[int],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    expected_hops = manifest["expected_evidence"]["ring"]["hops"]
    if len(statement_ids) != 3:
        raise RuntimeError("Project Trident did not produce three statement records")

    subject_nodes = [f"case_{case_id}_subject_{statement_id}" for statement_id in statement_ids]
    expected_routes = {
        expected_hops[0]["reference"]: (subject_nodes[0], subject_nodes[1]),
        expected_hops[1]["reference"]: (subject_nodes[1], subject_nodes[2]),
        expected_hops[2]["reference"]: (subject_nodes[2], subject_nodes[0]),
    }
    expected_amounts = {hop["reference"]: float(hop["amount"]) for hop in expected_hops}

    findings = db.exec(
        select(CaseFinding).where(
            CaseFinding.case_id == case_id,
            CaseFinding.kind == "conserved_flow_cycle",
            CaseFinding.hop_count == 3,
        )
    ).all()
    for finding in findings:
        edges = [db.get(CaseTransferEdge, edge_id) for edge_id in finding.edge_ids]
        by_reference: dict[str, CaseTransferEdge] = {}
        for edge in edges:
            if not edge:
                continue
            references = {
                transaction.reference_no
                for row_id in edge.source_row_ids
                if (transaction := db.get(Transaction, row_id)) and transaction.reference_no
            }
            for reference in references:
                by_reference[reference] = edge
        if set(by_reference) != set(expected_routes):
            continue
        if all(
            (edge := by_reference[reference]).source_node_id == route[0]
            and edge.target_node_id == route[1]
            and abs(edge.amount - expected_amounts[reference]) < 0.01
            for reference, route in expected_routes.items()
        ):
            return {
                "verified": True,
                "finding_id": finding.id,
                "hop_references": [hop["reference"] for hop in expected_hops],
                "node_sequence": subject_nodes + [subject_nodes[0]],
            }

    raise RuntimeError("Project Trident analysis did not persist the expected A→B→C→A finding")


async def load_project_trident(
    db: Session,
    demo_dir: Path = DEMO_DIR,
) -> dict[str, Any]:
    """Reset and load the fixed demo fixture using normal upload/confirm services."""
    manifest = _manifest(demo_dir)
    reset_project_trident(db)
    load = DemoLoad(tag=PROJECT_TRIDENT_TAG, status="loading", statement_ids=[])
    db.add(load)
    db.commit()

    try:
        statement_ids: list[int] = []
        for statement_data in manifest["statements"]:
            path = demo_dir / statement_data["file"]
            # Calling the existing upload route keeps fixture parsing identical to
            # investigator uploads rather than creating synthetic source rows.
            upload = UploadFile(filename=path.name, file=BytesIO(path.read_bytes()))
            result = await upload_statements(files=[upload], db=db)
            if result.errors or len(result.results) != 1:
                raise RuntimeError(f"Unable to upload {path.name}: {result.errors}")
            statement_id = result.results[0].statement_id
            statement_ids.append(statement_id)
            load.statement_ids = list(statement_ids)
            db.add(load)
            db.commit()

        for statement_id in statement_ids:
            await confirm_extraction(statement_id, db)

        case = create_case(
            CaseCreateIn(
                name=PROJECT_TRIDENT_CASE_NAME,
                description="Synthetic Project Trident demo; reset/load affects only this demo tag.",
                statement_ids=statement_ids,
            ),
            db,
        )
        load.case_id = case.id
        load.status = "analyzing"
        db.add(load)
        db.commit()

        analyze_case(db, db.get(Case, case.id))
        verification = _verification(db, case.id, statement_ids, manifest)
        load.status = "ready"
        db.add(load)
        db.commit()
        return {
            "tag": PROJECT_TRIDENT_TAG,
            "case_id": case.id,
            "statement_ids": statement_ids,
            "verification": verification,
        }
    except Exception:
        reset_project_trident(db)
        raise
