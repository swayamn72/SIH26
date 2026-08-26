"""Bank Intelligence API.

Ingests an interbank transfer ledger, then serves institution-level behavioural
profiles, the bank-to-bank network and the detected circular paths between banks.

Profiles are computed once at ingest and stored, so list and detail reads stay
instant on ledgers with hundreds of thousands of rows.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import insert
from sqlmodel import Session, select

from app.db.models import (
    Bank,
    BankEdge,
    BankProfileRecord,
    InterbankTransfer,
    TransferDataset,
)
from app.db.session import get_session
from app.institutions.bank_profile import build_bank_intelligence
from app.institutions.transfer_ingest import read_transfer_rows

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".txt"}

data_dir_env = os.environ.get("DATA_DIR")
if data_dir_env:
    UPLOAD_DIR = Path(data_dir_env) / "uploads"
else:
    UPLOAD_DIR = Path(__file__).parents[3] / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DatasetOut(BaseModel):
    id: int
    original_filename: Optional[str]
    upload_ts: str
    status: str
    row_count: int
    rows_skipped: int
    truncated: bool
    bank_count: int
    account_count: int
    total_value: float
    observed_start: Optional[str]
    observed_end: Optional[str]
    has_labels: bool
    detected_column_mapping: dict[str, Any] = {}
    currencies: list[str] = []
    payment_formats: list[str] = []


class BankListOut(BaseModel):
    dataset: DatasetOut
    summary: dict[str, Any] = {}
    banks: list[dict[str, Any]] = []
    total: int = 0


class BankGraphOut(BaseModel):
    dataset_id: int
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    cycles: list[dict[str, Any]] = []


def _dataset_out(ds: TransferDataset) -> DatasetOut:
    return DatasetOut(
        id=ds.id or 0,
        original_filename=ds.original_filename,
        upload_ts=ds.upload_ts.isoformat(),
        status=ds.status,
        row_count=ds.row_count,
        rows_skipped=ds.rows_skipped,
        truncated=ds.truncated,
        bank_count=ds.bank_count,
        account_count=ds.account_count,
        total_value=ds.total_value,
        observed_start=ds.observed_start.isoformat() if ds.observed_start else None,
        observed_end=ds.observed_end.isoformat() if ds.observed_end else None,
        has_labels=ds.has_labels,
        detected_column_mapping=ds.detected_column_mapping or {},
        currencies=ds.currencies or [],
        payment_formats=ds.payment_formats or [],
    )


def _load_dataset_or_404(db: Session, dataset_id: int) -> TransferDataset:
    ds = db.get(TransferDataset, dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail=f"Transfer dataset {dataset_id} not found")
    return ds


def _resolve_dataset(db: Session, dataset_id: Optional[int]) -> TransferDataset:
    """Named dataset, else the most recent one."""
    if dataset_id is not None:
        return _load_dataset_or_404(db, dataset_id)
    ds = db.exec(select(TransferDataset).order_by(TransferDataset.upload_ts.desc())).first()
    if ds is None:
        raise HTTPException(status_code=404, detail="No transfer dataset has been ingested yet")
    return ds


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_session)):
    datasets = db.exec(select(TransferDataset).order_by(TransferDataset.upload_ts.desc())).all()
    return [_dataset_out(d) for d in datasets]


@router.post("/datasets/upload", response_model=DatasetOut)
async def upload_transfer_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    """Ingest an interbank transfer ledger and profile every institution in it."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or 'unknown'}")

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()[:16]
    dest = UPLOAD_DIR / f"network_{file_hash}_{Path(file.filename or 'ledger.csv').name}"
    dest.write_bytes(content)

    try:
        rows, mapping, stats = read_transfer_rows(dest)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # pragma: no cover - surfaced to the analyst verbatim
        logger.exception("Transfer ledger ingestion failed")
        raise HTTPException(status_code=422, detail=f"Could not read this ledger: {exc}")

    if not rows:
        raise HTTPException(
            status_code=422,
            detail="No usable rows found — every row was missing an institution identifier.",
        )

    intel = build_bank_intelligence(rows)
    summary = intel["summary"]

    dataset = TransferDataset(
        original_filename=file.filename,
        status="ingested",
        row_count=stats["rows_ingested"],
        rows_skipped=stats["rows_skipped"],
        truncated=stats["truncated"],
        bank_count=summary.get("bank_count", 0),
        account_count=summary.get("account_count", 0),
        total_value=summary.get("total_value", 0.0),
        observed_start=_parse_iso(summary.get("observed_start")),
        observed_end=_parse_iso(summary.get("observed_end")),
        has_labels=bool(summary.get("has_labels")),
        detected_column_mapping=mapping,
        currencies=summary.get("currencies", []),
        payment_formats=summary.get("payment_formats", []),
        flow_cycles=intel["cycles"],
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    dataset_id = dataset.id or 0

    # Bulk-insert the ledger, the aggregated edges and one profile per bank.
    if rows:
        db.execute(
            insert(InterbankTransfer.__table__),
            [{**row, "dataset_id": dataset_id} for row in rows],
        )

    bank_codes = {row["from_bank"] for row in rows} | {row["to_bank"] for row in rows}
    if bank_codes:
        db.execute(
            insert(Bank.__table__),
            [
                {
                    "dataset_id": dataset_id,
                    "bank_code": code,
                    "display_name": code.replace("BANK_", "Bank "),
                }
                for code in sorted(bank_codes)
            ],
        )

    if intel["edges"]:
        db.execute(
            insert(BankEdge.__table__),
            [{**edge, "dataset_id": dataset_id} for edge in intel["edges"]],
        )

    if intel["banks"]:
        db.execute(
            insert(BankProfileRecord.__table__),
            [
                {
                    "dataset_id": dataset_id,
                    "bank_code": bank["bank_code"],
                    "risk_score": bank["risk_score"],
                    "risk_tier": bank["risk_tier"],
                    "transfer_count": bank["transfer_count"],
                    "total_received": bank["total_received"],
                    "total_sent": bank["total_sent"],
                    "connected_banks": bank["connected_banks"],
                    "avg_transfer": bank["avg_transfer"],
                    "json_blob": bank,
                }
                for bank in intel["banks"]
            ],
        )

    db.commit()
    db.refresh(dataset)
    return _dataset_out(dataset)


def _parse_iso(value: Optional[str]):
    if not value:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@router.get("/banks", response_model=BankListOut)
def list_banks(
    dataset_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    tier: Optional[str] = Query(None, description="HIGH | MEDIUM | LOW"),
    sort: str = Query("risk_score", description="risk_score|transfer_count|total_received|total_sent|connected_banks|avg_transfer|bank_code"),
    order: str = Query("desc"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
):
    dataset = _resolve_dataset(db, dataset_id)
    records = db.exec(
        select(BankProfileRecord).where(BankProfileRecord.dataset_id == dataset.id)
    ).all()

    banks = [r.json_blob for r in records if r.json_blob]

    if search:
        needle = search.strip().lower()
        banks = [b for b in banks if needle in str(b.get("bank_code", "")).lower()]
    if tier:
        wanted = tier.strip().upper()
        banks = [b for b in banks if b.get("risk_tier") == wanted]

    sort_key = sort if sort in {
        "risk_score",
        "transfer_count",
        "total_received",
        "total_sent",
        "connected_banks",
        "avg_transfer",
        "bank_code",
    } else "risk_score"
    reverse = order.lower() != "asc"
    banks.sort(
        key=lambda b: (b.get(sort_key) if isinstance(b.get(sort_key), (int, float)) else str(b.get(sort_key, ""))),
        reverse=reverse,
    )

    total = len(banks)
    page = banks[offset : offset + limit]

    summary = _dataset_summary(db, dataset, records)
    return BankListOut(dataset=_dataset_out(dataset), summary=summary, banks=page, total=total)


def _dataset_summary(
    db: Session, dataset: TransferDataset, records: list[BankProfileRecord]
) -> dict[str, Any]:
    """Roll the stored profiles back up into a dataset-level view."""
    blobs = [r.json_blob for r in records if r.json_blob]
    tier_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for b in blobs:
        tier_counts[b.get("risk_tier", "LOW")] = tier_counts.get(b.get("risk_tier", "LOW"), 0) + 1

    cycles = dataset.flow_cycles or []
    labelled_banks = [b for b in blobs if b.get("labelled_laundering_transfers", 0) > 0]
    high_banks = [b for b in blobs if b.get("risk_tier") == "HIGH"]

    summary: dict[str, Any] = {
        "bank_count": dataset.bank_count,
        "transfer_count": dataset.row_count,
        "total_value": dataset.total_value,
        "account_count": dataset.account_count,
        "cycle_count": len(cycles),
        "tier_counts": tier_counts,
        "avg_risk_score": round(
            sum(b.get("risk_score", 0.0) for b in blobs) / len(blobs), 1
        )
        if blobs
        else 0.0,
        "top_bank": blobs[0].get("bank_code") if blobs else None,
        "has_labels": dataset.has_labels,
    }

    if dataset.has_labels:
        high_codes = {b["bank_code"] for b in high_banks}
        labelled_codes = {b["bank_code"] for b in labelled_banks}
        summary["label_evaluation"] = {
            "banks_touching_labelled_transfers": len(labelled_codes),
            "banks_scored_high": len(high_codes),
            "high_scored_and_labelled": len(high_codes & labelled_codes),
            "labelled_but_not_high": len(labelled_codes - high_codes),
            "note": "Labels are excluded from the risk score; shown to evaluate it, not to fit it.",
        }

    return summary


@router.get("/banks/{bank_code}")
def get_bank_profile(
    bank_code: str,
    dataset_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
):
    dataset = _resolve_dataset(db, dataset_id)
    record = db.exec(
        select(BankProfileRecord)
        .where(BankProfileRecord.dataset_id == dataset.id)
        .where(BankProfileRecord.bank_code == bank_code)
    ).first()
    if record is None or not record.json_blob:
        raise HTTPException(
            status_code=404, detail=f"No profile for {bank_code} in dataset {dataset.id}"
        )

    edges = db.exec(
        select(BankEdge)
        .where(BankEdge.dataset_id == dataset.id)
        .where((BankEdge.from_bank == bank_code) | (BankEdge.to_bank == bank_code))
    ).all()

    cycles = [c for c in (dataset.flow_cycles or []) if bank_code in (c.get("banks") or [])]

    return {
        "dataset": _dataset_out(dataset),
        "profile": record.json_blob,
        "neighbourhood": [
            {
                "from_bank": e.from_bank,
                "to_bank": e.to_bank,
                "transfer_count": e.transfer_count,
                "total_amount": e.total_amount,
                "direction": "outgoing" if e.from_bank == bank_code else "incoming",
            }
            for e in sorted(edges, key=lambda e: -e.total_amount)[:40]
        ],
        "cycles": cycles,
    }


@router.get("/graph", response_model=BankGraphOut)
def get_bank_graph(
    dataset_id: Optional[int] = Query(None),
    top_banks: int = Query(60, ge=2, le=300, description="Keep the N banks by value moved"),
    db: Session = Depends(get_session),
):
    """Bank-to-bank network, trimmed to the busiest institutions so it stays readable."""
    dataset = _resolve_dataset(db, dataset_id)
    records = db.exec(
        select(BankProfileRecord).where(BankProfileRecord.dataset_id == dataset.id)
    ).all()
    blobs = [r.json_blob for r in records if r.json_blob]
    blobs.sort(key=lambda b: -(b.get("total_sent", 0) + b.get("total_received", 0)))
    keep = {b["bank_code"] for b in blobs[:top_banks]}

    edges = db.exec(select(BankEdge).where(BankEdge.dataset_id == dataset.id)).all()
    nodes = [
        {
            "id": b["bank_code"],
            "label": b["bank_code"].replace("BANK_", "Bank "),
            "flow": round(b.get("total_sent", 0) + b.get("total_received", 0), 2),
            "risk_score": b.get("risk_score", 0),
            "risk_tier": b.get("risk_tier", "LOW"),
            "transfer_count": b.get("transfer_count", 0),
            "connected_banks": b.get("connected_banks", 0),
        }
        for b in blobs
        if b["bank_code"] in keep
    ]

    cycles = dataset.flow_cycles or []

    return BankGraphOut(
        dataset_id=dataset.id or 0,
        nodes=nodes,
        edges=[
            {
                "source": e.from_bank,
                "target": e.to_bank,
                "amount": e.total_amount,
                "transfer_count": e.transfer_count,
                "row_id": f"{e.from_bank}->{e.to_bank}",
                "labelled_laundering_count": e.labelled_laundering_count,
            }
            for e in edges
            if e.from_bank in keep and e.to_bank in keep
        ],
        cycles=cycles,
    )


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: int, db: Session = Depends(get_session)):
    dataset = _load_dataset_or_404(db, dataset_id)
    for model in (BankProfileRecord, BankEdge, Bank, InterbankTransfer):
        for row in db.exec(select(model).where(model.dataset_id == dataset_id)).all():
            db.delete(row)
    db.delete(dataset)
    db.commit()
    return {"status": "deleted", "dataset_id": dataset_id}
