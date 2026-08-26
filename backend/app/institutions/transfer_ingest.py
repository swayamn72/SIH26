"""Ingestion for interbank transfer ledgers (AML transaction-network exports).

A bank statement is one account's history; this is a multi-party ledger where every
row names both institutions. Column names differ between exports, so headers are
matched by synonym rather than assumed, and the resolved mapping is stored on the
dataset so the UI can show exactly how the file was read.

Files of this shape run to millions of rows, so reading is chunked and capped.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import pandas as pd

from app.config_loader import load_config

# Header synonyms, lower-cased and stripped of punctuation before matching.
COLUMN_SYNONYMS: dict[str, list[str]] = {
    "txn_ts": ["timestamp", "date", "datetime", "txn date", "transaction date", "value date"],
    "from_bank": ["from bank", "sender bank", "originator bank", "payer bank", "source bank", "bank from"],
    "from_account": ["account", "from account", "sender account", "originator account", "payer account"],
    "to_bank": ["to bank", "receiver bank", "beneficiary bank", "payee bank", "target bank", "bank to"],
    "to_account": ["account1", "account 1", "to account", "receiver account", "beneficiary account"],
    "amount_paid": ["amount paid", "amount sent", "paid amount", "debit amount", "amount"],
    "payment_currency": ["payment currency", "sent currency", "currency paid", "currency"],
    "amount_received": ["amount received", "received amount", "credit amount"],
    "receiving_currency": ["receiving currency", "received currency", "currency received"],
    "payment_format": ["payment format", "payment type", "channel", "instrument", "payment method"],
    "is_labelled_laundering": ["is laundering", "islaundering", "label", "is_fraud", "is fraud", "target"],
}

REQUIRED_FIELDS = ("from_bank", "to_bank")


def _normalise(header: str) -> str:
    return " ".join(str(header).strip().lower().replace("_", " ").replace(".", " ").split())


def detect_columns(headers: list[str]) -> dict[str, str]:
    """Map canonical field -> source header. First match wins, each header used once."""
    normalised = {h: _normalise(h) for h in headers}
    taken: set[str] = set()
    mapping: dict[str, str] = {}

    for field, synonyms in COLUMN_SYNONYMS.items():
        for synonym in synonyms:
            for header, norm in normalised.items():
                if header in taken:
                    continue
                if norm == synonym:
                    mapping[field] = header
                    taken.add(header)
                    break
            if field in mapping:
                break

    # Second pass: allow a substring match for anything still unmapped.
    for field, synonyms in COLUMN_SYNONYMS.items():
        if field in mapping:
            continue
        for synonym in synonyms:
            for header, norm in normalised.items():
                if header in taken:
                    continue
                if synonym in norm:
                    mapping[field] = header
                    taken.add(header)
                    break
            if field in mapping:
                break

    return mapping


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("₹", "").replace("$", "").strip()
            if not value:
                return 0.0
        result = float(value)
        return 0.0 if pd.isna(result) else result
    except (TypeError, ValueError):
        return 0.0


def _to_bool(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, (int, float)):
        return float(value) != 0.0
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "laundering", "fraud"}


def _to_ts(value: Any) -> Optional[datetime]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        ts = pd.to_datetime(value, errors="coerce", dayfirst=False)
        if ts is pd.NaT or pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


def _clean_code(value: Any, prefix: str) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    # Numeric bank ids arrive as floats from pandas ("11.0" -> "11").
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return f"{prefix}{text}" if prefix and text.isdigit() else text


def read_transfer_rows(
    file_path: str | Path,
    max_rows: Optional[int] = None,
    chunk_size: int = 50_000,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    """Read a transfer ledger into normalised row dicts.

    Returns (rows, column_mapping, stats). Rows missing either institution are
    skipped and counted rather than silently dropped.
    """
    cfg = load_config("thresholds").get("bank_intelligence", {}) or {}
    cap = int(max_rows if max_rows is not None else cfg.get("max_rows", 250_000))

    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xls"}:
        frames: Iterator[pd.DataFrame] = iter([pd.read_excel(path)])
    else:
        frames = pd.read_csv(path, chunksize=chunk_size, dtype=str, keep_default_na=False)

    rows: list[dict[str, Any]] = []
    mapping: dict[str, str] = {}
    skipped = 0
    total_seen = 0
    truncated = False

    for frame in frames:
        if not mapping:
            mapping = detect_columns(list(frame.columns))
            missing = [f for f in REQUIRED_FIELDS if f not in mapping]
            if missing:
                raise ValueError(
                    "Could not find the institution columns "
                    f"({', '.join(missing)}) in this file. Headers seen: "
                    f"{', '.join(str(c) for c in frame.columns[:12])}"
                )

        for record in frame.to_dict("records"):
            total_seen += 1
            if len(rows) >= cap:
                truncated = True
                break

            from_bank = _clean_code(record.get(mapping["from_bank"]), "BANK_")
            to_bank = _clean_code(record.get(mapping["to_bank"]), "BANK_")
            if not from_bank or not to_bank:
                skipped += 1
                continue

            paid = _to_float(record.get(mapping["amount_paid"])) if "amount_paid" in mapping else 0.0
            received = (
                _to_float(record.get(mapping["amount_received"]))
                if "amount_received" in mapping
                else paid
            )
            if paid == 0.0 and received > 0.0:
                paid = received
            if received == 0.0 and paid > 0.0:
                received = paid

            rows.append({
                "txn_ts": _to_ts(record.get(mapping["txn_ts"])) if "txn_ts" in mapping else None,
                "from_bank": from_bank,
                "from_account": _clean_code(record.get(mapping.get("from_account", "")), ""),
                "to_bank": to_bank,
                "to_account": _clean_code(record.get(mapping.get("to_account", "")), ""),
                "amount_paid": round(paid, 2),
                "payment_currency": (
                    str(record.get(mapping["payment_currency"]) or "").strip()[:16] or None
                    if "payment_currency" in mapping
                    else None
                ),
                "amount_received": round(received, 2),
                "receiving_currency": (
                    str(record.get(mapping["receiving_currency"]) or "").strip()[:16] or None
                    if "receiving_currency" in mapping
                    else None
                ),
                "payment_format": (
                    str(record.get(mapping["payment_format"]) or "").strip()[:32] or None
                    if "payment_format" in mapping
                    else None
                ),
                "is_labelled_laundering": (
                    _to_bool(record.get(mapping["is_labelled_laundering"]))
                    if "is_labelled_laundering" in mapping
                    else False
                ),
            })

        if truncated:
            break

    stats = {
        "rows_ingested": len(rows),
        "rows_skipped": skipped,
        "rows_seen": total_seen,
        "truncated": truncated,
        "row_cap": cap,
        "has_labels": "is_labelled_laundering" in mapping,
    }
    return rows, mapping, stats
