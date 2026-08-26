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
from app.institutions.bank_identity import UNATTRIBUTED
from app.institutions.bank_profile import build_bank_intelligence
from app.institutions.statement_ledger import build_statement_ledger, ledger_fingerprint
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


# Profiles for the statement corpus are recomputed on read so newly added
# statements appear immediately, and memoised on a corpus fingerprint so the
# three requests behind one page load do the work once.
_STATEMENT_CACHE: dict[str, Any] = {"fingerprint": None, "intel": None, "coverage": None}

STATEMENT_SOURCE = "statements"


def statement_intelligence(db: Session, force: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    """(intel, coverage) built from every analysed statement in the database."""
    fingerprint = ledger_fingerprint(db)
    if (
        not force
        and _STATEMENT_CACHE["fingerprint"] == fingerprint
        and _STATEMENT_CACHE["intel"] is not None
    ):
        return _STATEMENT_CACHE["intel"], _STATEMENT_CACHE["coverage"]

    ledger = build_statement_ledger(db)
    intel = build_bank_intelligence(
        ledger["rows"],
        skip_banks={UNATTRIBUTED},
        direct_banks=ledger["direct_banks"],
        display_names=ledger["display_names"],
    )
    _STATEMENT_CACHE.update(
        {"fingerprint": fingerprint, "intel": intel, "coverage": ledger["coverage"]}
    )
    return intel, ledger["coverage"]


class SourceOut(BaseModel):
    key: str
    kind: str
    label: str
    description: str
    bank_count: int = 0
    transfer_count: int = 0
    is_live: bool = False
    has_labels: bool = False
    dataset_id: Optional[int] = None


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
    dataset: Optional[DatasetOut] = None
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


def _load_source(
    db: Session, source: str, dataset_id: Optional[int] = None
) -> tuple[list[dict[str, Any]], dict[str, Any], Optional[DatasetOut]]:
    """Resolve a source key to (bank profiles, summary, dataset-or-None).

    'statements' rebuilds from the live corpus; 'ledger:<id>' reads the stored
    profiles for an uploaded ledger. dataset_id is honoured for older callers.
    """
    if dataset_id is not None:
        source = f"ledger:{dataset_id}"

    if source.startswith("ledger:"):
        try:
            ds_id = int(source.split(":", 1)[1])
        except (IndexError, ValueError):
            raise HTTPException(status_code=400, detail=f"Malformed source '{source}'")
        dataset = _load_dataset_or_404(db, ds_id)
        records = db.exec(
            select(BankProfileRecord).where(BankProfileRecord.dataset_id == dataset.id)
        ).all()
        banks = [r.json_blob for r in records if r.json_blob]
        summary = _dataset_summary(db, dataset, records)
        summary["source"] = source
        summary["source_kind"] = "ledger"
        return banks, summary, _dataset_out(dataset)

    if source != STATEMENT_SOURCE:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Use 'statements' or 'ledger:<id>'.",
        )

    intel, coverage = statement_intelligence(db)
    summary = dict(intel.get("summary", {}))
    summary["source"] = STATEMENT_SOURCE
    summary["source_kind"] = "statements"
    summary["coverage"] = coverage
    summary["tier_counts"] = {
        tier: sum(1 for b in intel["banks"] if b.get("risk_tier") == tier)
        for tier in ("HIGH", "MEDIUM", "LOW")
    }
    summary["avg_risk_score"] = (
        round(sum(b["risk_score"] for b in intel["banks"]) / len(intel["banks"]), 1)
        if intel["banks"]
        else 0.0
    )
    summary["cycle_count"] = len(intel.get("cycles", []))
    return list(intel["banks"]), summary, None


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


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_session)):
    """Where institution profiles can be built from, live corpus first."""
    intel, coverage = statement_intelligence(db)
    summary = intel.get("summary", {})

    sources = [
        SourceOut(
            key=STATEMENT_SOURCE,
            kind="statements",
            label="Statement corpus (live)",
            description=(
                f"{coverage['statements_included']} analysed statement(s), "
                f"{coverage['transactions_used']} transactions, "
                f"{coverage['attribution_rate'] * 100:.0f}% of counterparties attributed to a bank"
            ),
            bank_count=summary.get("bank_count", 0),
            transfer_count=summary.get("transfer_count", 0),
            is_live=True,
        )
    ]

    for ds in db.exec(select(TransferDataset).order_by(TransferDataset.upload_ts.desc())).all():
        sources.append(
            SourceOut(
                key=f"ledger:{ds.id}",
                kind="ledger",
                label=f"Ledger #{ds.id} · {ds.original_filename or 'transfer ledger'}",
                description=f"{ds.row_count} transfers across {ds.bank_count} institutions",
                bank_count=ds.bank_count,
                transfer_count=ds.row_count,
                has_labels=ds.has_labels,
                dataset_id=ds.id,
            )
        )

    return sources


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
    source: str = Query(STATEMENT_SOURCE, description="'statements' (live) or 'ledger:<id>'"),
    dataset_id: Optional[int] = Query(None, description="Legacy alias for source='ledger:<id>'"),
    search: Optional[str] = Query(None),
    tier: Optional[str] = Query(None, description="HIGH | MEDIUM | LOW"),
    evidence: Optional[str] = Query(None, description="direct | partial"),
    sort: str = Query("risk_score", description="risk_score|transfer_count|total_received|total_sent|connected_banks|avg_transfer|bank_code"),
    order: str = Query("desc"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_session),
):
    banks, summary, dataset = _load_source(db, source, dataset_id)

    if evidence:
        wanted_evidence = evidence.strip().lower()
        banks = [b for b in banks if b.get("evidence_basis") == wanted_evidence]

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

    return BankListOut(dataset=dataset, summary=summary, banks=page, total=total)


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
    source: str = Query(STATEMENT_SOURCE),
    dataset_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
):
    """One institution's profile, its immediate network and the loops it sits on."""
    if dataset_id is not None:
        source = f"ledger:{dataset_id}"

    if source.startswith("ledger:"):
        ds_id = int(source.split(":", 1)[1])
        dataset = _load_dataset_or_404(db, ds_id)
        record = db.exec(
            select(BankProfileRecord)
            .where(BankProfileRecord.dataset_id == dataset.id)
            .where(BankProfileRecord.bank_code == bank_code)
        ).first()
        if record is None or not record.json_blob:
            raise HTTPException(
                status_code=404, detail=f"No profile for {bank_code} in ledger {dataset.id}"
            )
        profile = record.json_blob
        edges = [
            {
                "from_bank": e.from_bank,
                "to_bank": e.to_bank,
                "transfer_count": e.transfer_count,
                "total_amount": e.total_amount,
                "direction": "outgoing" if e.from_bank == bank_code else "incoming",
            }
            for e in db.exec(
                select(BankEdge)
                .where(BankEdge.dataset_id == dataset.id)
                .where((BankEdge.from_bank == bank_code) | (BankEdge.to_bank == bank_code))
            ).all()
        ]
        cycles = [
            c for c in (dataset.flow_cycles or []) if bank_code in (c.get("banks") or [])
        ]
        return {
            "source": source,
            "dataset": _dataset_out(dataset),
            "coverage": None,
            "profile": profile,
            "neighbourhood": sorted(edges, key=lambda e: -e["total_amount"])[:40],
            "cycles": cycles,
        }

    intel, coverage = statement_intelligence(db)
    profile = next((b for b in intel["banks"] if b["bank_code"] == bank_code), None)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"{bank_code} does not appear in the current statement corpus",
        )

    edges = [
        {
            "from_bank": e["from_bank"],
            "to_bank": e["to_bank"],
            "transfer_count": int(e["transfer_count"]),
            "total_amount": round(float(e["total_amount"]), 2),
            "direction": "outgoing" if e["from_bank"] == bank_code else "incoming",
        }
        for e in intel["edges"]
        if bank_code in (e["from_bank"], e["to_bank"])
        and UNATTRIBUTED not in (e["from_bank"], e["to_bank"])
    ]

    return {
        "source": STATEMENT_SOURCE,
        "dataset": None,
        "coverage": coverage,
        "profile": profile,
        "neighbourhood": sorted(edges, key=lambda e: -e["total_amount"])[:40],
        "cycles": [c for c in intel["cycles"] if bank_code in (c.get("banks") or [])],
    }


@router.get("/graph", response_model=BankGraphOut)
def get_bank_graph(
    source: str = Query(STATEMENT_SOURCE),
    dataset_id: Optional[int] = Query(None),
    top_banks: int = Query(60, ge=2, le=300, description="Keep the N banks by value moved"),
    db: Session = Depends(get_session),
):
    """Bank-to-bank network, trimmed to the busiest institutions so it stays readable."""
    banks, _summary, dataset = _load_source(db, source, dataset_id)

    banks = sorted(banks, key=lambda b: -(b.get("total_sent", 0) + b.get("total_received", 0)))
    keep = {b["bank_code"] for b in banks[:top_banks]}

    nodes = [
        {
            "id": b["bank_code"],
            "label": b.get("display_name") or b["bank_code"],
            "flow": round(b.get("total_sent", 0) + b.get("total_received", 0), 2),
            "risk_score": b.get("risk_score", 0),
            "risk_tier": b.get("risk_tier", "LOW"),
            "transfer_count": b.get("transfer_count", 0),
            "connected_banks": b.get("connected_banks", 0),
            "evidence_basis": b.get("evidence_basis", "direct"),
        }
        for b in banks
        if b["bank_code"] in keep
    ]

    if dataset is not None:
        raw_edges = [
            {
                "source": e.from_bank,
                "target": e.to_bank,
                "amount": e.total_amount,
                "transfer_count": e.transfer_count,
                "row_id": f"{e.from_bank}->{e.to_bank}",
                "labelled_laundering_count": e.labelled_laundering_count,
            }
            for e in db.exec(select(BankEdge).where(BankEdge.dataset_id == dataset.id)).all()
        ]
        cycles = (db.get(TransferDataset, dataset.id).flow_cycles) or []
    else:
        intel, _coverage = statement_intelligence(db)
        raw_edges = [
            {
                "source": e["from_bank"],
                "target": e["to_bank"],
                "amount": round(float(e["total_amount"]), 2),
                "transfer_count": int(e["transfer_count"]),
                "row_id": f"{e['from_bank']}->{e['to_bank']}",
                "labelled_laundering_count": int(e.get("labelled_laundering_count", 0)),
            }
            for e in intel["edges"]
            if UNATTRIBUTED not in (e["from_bank"], e["to_bank"])
        ]
        cycles = intel["cycles"]

    return BankGraphOut(
        dataset_id=dataset.id if dataset else 0,
        nodes=nodes,
        edges=[e for e in raw_edges if e["source"] in keep and e["target"] in keep],
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
