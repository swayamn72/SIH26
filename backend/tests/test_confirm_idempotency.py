import asyncio
from datetime import date

from sqlmodel import SQLModel, Session, create_engine, select

from app.api.routes_review import confirm_extraction
from app.db.models import Cycle, EvidenceBundleRecord, Statement, Transaction
from app.features.feature_registry import REGISTRY


def _session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _reference_evidence(offset: float) -> dict:
    return {
        "features": [
            {"name": name, "value": float(index + 1) + offset}
            for index, name in enumerate(REGISTRY)
        ]
    }


def test_reconfirm_is_stable_and_excludes_current_statement_from_anomaly_cohort(monkeypatch):
    """Repeated confirmation must not train anomaly scoring on prior self-evidence."""
    monkeypatch.setattr(
        "app.categorization.llm_categorizer.batch_categorize", lambda narrations: {}
    )
    db = _session()

    # The configured minimum reference cohort is three statements. These are
    # deliberately present before the current statement is first confirmed so the
    # test catches the historic 4-row -> 5-row self-duplication behavior.
    for index, offset in enumerate((0.0, 10.0, 20.0), start=1):
        reference = Statement(filename_hash=f"reference-{index}", status="analyzed")
        db.add(reference)
        db.flush()
        db.add(EvidenceBundleRecord(statement_id=reference.id, json_blob=_reference_evidence(offset)))

    statement = Statement(
        filename_hash="current",
        original_filename="current.csv",
        status="uploaded",
        ood_score=1.0,
        transaction_count=3,
        observed_start=date(2024, 1, 1),
        observed_end=date(2024, 1, 3),
    )
    db.add(statement)
    db.flush()
    db.add_all([
        Transaction(
            row_id="current-1", statement_id=statement.id, txn_date=date(2024, 1, 1),
            narration="Salary credit", credit_amount=1000.0, balance_after=1000.0,
        ),
        Transaction(
            row_id="current-2", statement_id=statement.id, txn_date=date(2024, 1, 2),
            narration="ATM withdrawal", debit_amount=500.0, balance_after=500.0,
        ),
        Transaction(
            row_id="current-3", statement_id=statement.id, txn_date=date(2024, 1, 3),
            narration="UPI payment", debit_amount=100.0, balance_after=400.0,
        ),
    ])
    db.commit()

    first = asyncio.run(confirm_extraction(statement.id, db))
    first_bundle = db.exec(
        select(EvidenceBundleRecord).where(EvidenceBundleRecord.statement_id == statement.id)
    ).one()
    first_blob = first_bundle.json_blob
    first_cycles = db.exec(select(Cycle).where(Cycle.statement_id == statement.id)).all()

    second = asyncio.run(confirm_extraction(statement.id, db))
    second_bundle = db.exec(
        select(EvidenceBundleRecord).where(EvidenceBundleRecord.statement_id == statement.id)
    ).one()
    second_cycles = db.exec(select(Cycle).where(Cycle.statement_id == statement.id)).all()

    assert second.model_dump() == first.model_dump()
    assert second_bundle.json_blob == first_blob
    assert len(db.exec(select(EvidenceBundleRecord).where(EvidenceBundleRecord.statement_id == statement.id)).all()) == 1
    assert len(second_cycles) == len(first_cycles)
    assert second_bundle.json_blob["anomaly_detail"]["reference_cohort_size"] == 3
    assert second_bundle.json_blob["anomaly_detail"]["isolation_forest_score"] == first_blob["anomaly_detail"]["isolation_forest_score"]
