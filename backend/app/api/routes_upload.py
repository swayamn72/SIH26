import hashlib
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app.db.models import (
    Counterparty,
    Cycle,
    EvidenceBundleRecord,
    InvestigatorLabel,
    Statement,
    Transaction,
)
from app.db.session import get_session
from app.guardrails.ood_detector import (
    classify_ood_tier,
    compute_statement_likelihood,
)
from app.ingestion.file_router import dispatch_extraction
from app.understanding.column_mapper import map_row_to_transaction
from app.understanding.header_classifier import classify_columns
from app.understanding.template_matcher import match_template

logger = logging.getLogger(__name__)

router = APIRouter()

data_dir_env = os.environ.get("DATA_DIR")
if data_dir_env:
    UPLOAD_DIR = Path(data_dir_env) / "uploads"
else:
    UPLOAD_DIR = Path(__file__).parents[3] / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls"}


class DetectedColumnOut(BaseModel):
    index: int
    field: str
    confidence: float


class UploadResultOut(BaseModel):
    statement_id: int
    original_filename: str
    ood_score: float
    ood_tier: str
    ood_signals: dict
    detected_columns: list[DetectedColumnOut]
    transaction_count: int


class BatchUploadOut(BaseModel):
    results: list[UploadResultOut]
    errors: list[dict]


class StatementSummaryOut(BaseModel):
    id: int
    original_filename: str | None = None
    upload_ts: str
    status: str
    ood_score: float | None = None
    ood_tier: str | None = None
    extraction_confidence: float | None = None
    reconciliation_rate: float | None = None
    transaction_count: int | None = None
    observed_start: str | None = None
    observed_end: str | None = None
    tier: str | None = None
    fused_score: float | None = None


@router.get("", response_model=list[StatementSummaryOut])
def list_statements(db: Session = Depends(get_session)):
    statements = db.query(Statement).order_by(Statement.id.desc()).all()
    summaries = []
    for s in statements:
        # Check if there is an evidence bundle record for risk tier / fused score
        ev = (
            db.query(EvidenceBundleRecord)
            .filter(EvidenceBundleRecord.statement_id == s.id)
            .order_by(EvidenceBundleRecord.created_ts.desc())
            .first()
        )
        tier = None
        fused_score = None
        if ev and ev.json_blob and isinstance(ev.json_blob, dict):
            final_dec = ev.json_blob.get("final_decision", {})
            tier = final_dec.get("tier")
            fused_score = final_dec.get("fused_score")

        ood_tier = (
            classify_ood_tier(s.ood_score or 0.0, s.ood_signals or {})
            if s.ood_score is not None
            else None
        )

        summaries.append(
            StatementSummaryOut(
                id=s.id,
                original_filename=s.original_filename,
                upload_ts=s.upload_ts.isoformat() if s.upload_ts else "",
                status=s.status or "uploaded",
                ood_score=s.ood_score,
                ood_tier=ood_tier,
                extraction_confidence=s.extraction_confidence,
                reconciliation_rate=s.reconciliation_rate,
                transaction_count=s.transaction_count,
                observed_start=str(s.observed_start) if s.observed_start else None,
                observed_end=str(s.observed_end) if s.observed_end else None,
                tier=tier,
                fused_score=fused_score,
            )
        )
    return summaries


@router.delete("/{statement_id}")
def delete_statement(statement_id: int, db: Session = Depends(get_session)):
    stmt = db.get(Statement, statement_id)
    if not stmt:
        raise HTTPException(status_code=404, detail="Statement not found")

    # Delete related records
    db.query(Transaction).filter(Transaction.statement_id == statement_id).delete()
    db.query(EvidenceBundleRecord).filter(
        EvidenceBundleRecord.statement_id == statement_id
    ).delete()
    db.query(Cycle).filter(Cycle.statement_id == statement_id).delete()
    db.query(InvestigatorLabel).filter(
        InvestigatorLabel.statement_id == statement_id
    ).delete()
    db.query(Counterparty).filter(
        Counterparty.first_seen_statement_id == statement_id
    ).delete()
    db.delete(stmt)
    db.commit()
    return {"status": "deleted", "statement_id": statement_id}


@router.post("/purge/all")
def purge_all_data(db: Session = Depends(get_session)):
    db.query(Transaction).delete()
    db.query(EvidenceBundleRecord).delete()
    db.query(Cycle).delete()
    db.query(InvestigatorLabel).delete()
    db.query(Counterparty).delete()
    db.query(Statement).delete()
    db.commit()
    return {"status": "purged"}


@router.post("/upload", response_model=BatchUploadOut)
async def upload_statements(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_session),
):
    results: list[UploadResultOut] = []
    errors: list[dict] = []

    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            errors.append(
                {"filename": file.filename, "error": f"Unsupported file type: {ext}"}
            )
            continue

        try:
            content = await file.read()
            file_hash = hashlib.sha256(content).hexdigest()
            safe_name = f"{file_hash}_{file.filename}"
            dest = UPLOAD_DIR / safe_name
            dest.write_bytes(content)

            extracted = dispatch_extraction(dest)
            rows, header, ftype = extracted
            if rows is None or len(rows) == 0:
                errors.append(
                    {"filename": file.filename, "error": f"Extraction failed — {ftype}"}
                )
                continue

            if header is not None:
                detected_headers = header
                data_rows = rows
            else:
                detected_headers = rows[0] if rows else []
                data_rows = rows[1:] if len(rows) > 1 else []

            full_text = "\n".join(
                "\t".join(r) for r in (data_rows[:100] if data_rows else [])
            )
            ood_score, ood_signals = compute_statement_likelihood(
                raw_rows=data_rows,
                full_text=full_text,
                num_rows=len(data_rows),
            )
            ood_tier = classify_ood_tier(ood_score, ood_signals)

            if ood_tier == "hard_reject":
                errors.append(
                    {
                        "filename": file.filename,
                        "error": f"OOD Hard Reject: score {ood_score:.2f} too low. Not a bank statement.",
                    }
                )
                continue

            matched_template, match_score = match_template(detected_headers)
            if matched_template and matched_template.get("column_map"):
                tmpl_map = matched_template["column_map"]
                col_map: dict[int, str] = {}
                for idx, h in enumerate(detected_headers):
                    if h in tmpl_map:
                        col_map[idx] = tmpl_map[h]
            else:
                sample_rows = data_rows[:50] if data_rows else []
                classified = classify_columns(detected_headers, sample_rows)
                col_map = {idx: field for idx, (field, _) in classified.items()}

            statement = Statement(
                filename_hash=file_hash,
                original_filename=file.filename,
                ood_score=ood_score,
                ood_signals=ood_signals,
                status="uploaded",
                raw_headers=detected_headers,
                raw_rows=data_rows[:5000] if len(data_rows) > 5000 else data_rows,
            )
            db.add(statement)
            db.commit()
            db.refresh(statement)

            txn_count = 0
            for row_idx, row in enumerate(data_rows):
                canonical = map_row_to_transaction(row, col_map, statement.id, row_idx)
                if canonical is None:
                    continue
                txn = Transaction(
                    row_id=canonical.row_id,
                    statement_id=statement.id,
                    txn_date=canonical.txn_date,
                    value_date=canonical.value_date,
                    narration=canonical.narration,
                    reference_no=canonical.reference_no,
                    debit_amount=float(canonical.debit_amount)
                    if canonical.debit_amount
                    else None,
                    credit_amount=float(canonical.credit_amount)
                    if canonical.credit_amount
                    else None,
                    balance_after=float(canonical.balance_after)
                    if canonical.balance_after
                    else None,
                    row_confidence=canonical.source_row_confidence,
                )
                db.add(txn)
                txn_count += 1

            statement.transaction_count = txn_count
            if data_rows:
                dates = [
                    t.txn_date
                    for t in db.query(Transaction)
                    .filter(Transaction.statement_id == statement.id)
                    .all()
                    if t.txn_date
                ]
                if dates:
                    statement.observed_start = min(dates)
                    statement.observed_end = max(dates)
            db.commit()

            detected_cols = [
                DetectedColumnOut(index=idx, field=field, confidence=1.0)
                for idx, field in col_map.items()
            ]
            results.append(
                UploadResultOut(
                    statement_id=statement.id,
                    original_filename=file.filename,
                    ood_score=ood_score,
                    ood_tier=ood_tier,
                    ood_signals=ood_signals,
                    detected_columns=detected_cols,
                    transaction_count=txn_count,
                )
            )
        except Exception as exc:
            logger.exception("Failed to process %s", file.filename)
            errors.append({"filename": file.filename, "error": str(exc)})

    return BatchUploadOut(results=results, errors=errors)
