"""Turning the statement corpus into an interbank transfer ledger.

Bank Intelligence needs rows that name an institution on both sides. A single
statement cannot supply that — it is a star around one account, so every row
touches the same bank and no loop can ever close. The union of many statements
can: if one statement shows A→B, another B→C and a third C→A, the corpus contains
a ring that none of them reveals alone.

So this reads every analysed statement, resolves both institutions per row, and
emits rows in exactly the shape `transfer_ingest.read_transfer_rows` produces, so
the profiling engine, cycle detector and UI all work unchanged.

Two honesty requirements shape the output:

  * Rows whose counterparty bank cannot be resolved are marked UNATTRIBUTED
    rather than guessed at. They still count toward the subject bank's own
    volume — the money did move — but they form no edge and no institution.
  * Every profile carries how much of it was directly observed. A bank seen only
    through someone else's statement is a fragment, and saying so is the
    difference between intelligence and a misleading number.
"""

from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session, select

from app.db.models import Counterparty, Statement, Transaction
from app.institutions.bank_identity import (
    UNATTRIBUTED,
    bank_name,
    resolve_counterparty_bank,
    resolve_subject_bank,
)

# Statements only reach the ledger once they have been analysed — an unconfirmed
# extraction has no reliable amounts to aggregate.
INCLUDED_STATUSES = {"analyzed", "confirmed"}


def _entity_key(bank_code: str, name: Optional[str], fallback: str) -> str:
    """Stable *observation* id, never an identity inferred from a display name.

    A normalized name is not sufficient account-resolution evidence: two unrelated
    people named Rahul at the same bank must not close an invented loop.  The caller
    supplies a statement/row-scoped fallback, which is deliberately always part of
    the returned key.  Case analysis may later resolve subjects only with exact
    mirrored transfer evidence.
    """
    return f"{bank_code}:{fallback}"


def _channel_to_format(channel: Optional[str], narration: str) -> str:
    """Map the Indian payment rails onto the instrument vocabulary the profile uses."""
    text = f"{channel or ''} {narration}".lower()
    if "rtgs" in text:
        return "rtgs"
    if "neft" in text:
        return "neft"
    if "imps" in text:
        return "imps"
    if "upi" in text:
        return "upi"
    if any(t in text for t in ("atm", "cash wdl", "cash deposit", "cshdep", "cash withdrawal")):
        return "cash"
    if any(t in text for t in ("chq", "cheque")):
        return "cheque"
    if "pos" in text or "card" in text:
        return "card"
    return (channel or "unspecified").strip().lower() or "unspecified"


def _subject_bank_for(statement: Statement) -> tuple[str, str]:
    """The statement's own bank, resolved at upload where possible."""
    if statement.bank_code and statement.bank_code != UNATTRIBUTED:
        return statement.bank_code, statement.bank_code_source or "stored"
    # Statements ingested before identity resolution existed still have their
    # preamble, template and filename to fall back on.
    return resolve_subject_bank(
        statement.raw_preamble,
        template_id=statement.template_id_used,
        filename=statement.original_filename,
    )


def build_statement_ledger(db: Session) -> dict[str, Any]:
    """Assemble transfer rows plus attribution coverage from every analysed statement."""
    statements = [
        s
        for s in db.exec(select(Statement)).all()
        if (s.status or "").lower() in INCLUDED_STATUSES
    ]

    counterparties = {
        cp.id: cp.canonical_name for cp in db.exec(select(Counterparty)).all()
    }

    rows: list[dict[str, Any]] = []
    per_statement: list[dict[str, Any]] = []
    subject_banks: dict[str, str] = {}
    attributed = 0
    unattributed = 0
    signal_counts: dict[str, int] = {}
    # A bank is "direct" when we hold a statement issued by it; everything else is
    # only ever seen from the outside.
    direct_banks: set[str] = set()

    for statement in statements:
        subject_code, subject_signal = _subject_bank_for(statement)
        if subject_code == UNATTRIBUTED:
            # Without knowing whose statement this is, its rows cannot be attached
            # to any institution at all.
            per_statement.append({
                "statement_id": statement.id,
                "filename": statement.original_filename,
                "bank_code": UNATTRIBUTED,
                "bank_name": bank_name(UNATTRIBUTED),
                "bank_signal": subject_signal,
                "transactions": 0,
                "attributed": 0,
                "skipped": True,
            })
            continue

        subject_banks[subject_code] = bank_name(subject_code)
        direct_banks.add(subject_code)

        subject_account = _entity_key(
            subject_code, statement.account_holder, f"stmt{statement.id}"
        )

        txns = db.exec(
            select(Transaction).where(Transaction.statement_id == statement.id)
        ).all()

        stmt_attributed = 0
        for txn in txns:
            debit = float(txn.debit_amount or 0.0)
            credit = float(txn.credit_amount or 0.0)
            amount = debit if debit >= credit and debit > 0 else credit
            if amount <= 0:
                continue

            cp_name = counterparties.get(txn.counterparty_id) if txn.counterparty_id else None
            cp_code, signal = resolve_counterparty_bank(
                txn.narration, txn.reference_no, cp_name, subject_code
            )

            if cp_code == UNATTRIBUTED:
                unattributed += 1
            else:
                attributed += 1
                stmt_attributed += 1
                signal_counts[signal or "unknown"] = signal_counts.get(signal or "unknown", 0) + 1

            # Direction follows the statement: a debit leaves the subject's bank.
            cp_account = (
                _entity_key(cp_code, cp_name, f"cp{txn.counterparty_id}")
                if cp_code != UNATTRIBUTED
                else None
            )

            if debit >= credit and debit > 0:
                from_bank, to_bank = subject_code, cp_code
                from_account, to_account = subject_account, cp_account
            else:
                from_bank, to_bank = cp_code, subject_code
                from_account, to_account = cp_account, subject_account

            rows.append({
                "txn_ts": datetime.combine(txn.txn_date, datetime.min.time())
                if txn.txn_date
                else None,
                "from_bank": from_bank,
                "from_account": from_account,
                "to_bank": to_bank,
                "to_account": to_account,
                "amount_paid": round(amount, 2),
                # Statements carry no currency column; leaving these unset keeps the
                # cross-currency component honestly at zero instead of implying INR
                # conversions that were never observed.
                "payment_currency": None,
                "amount_received": round(amount, 2),
                "receiving_currency": None,
                "payment_format": _channel_to_format(txn.channel, txn.narration or ""),
                "is_labelled_laundering": False,
                # Provenance, so a profile can say where its evidence came from.
                "source_statement_id": statement.id,
                "source_row_id": txn.row_id,
                "attribution_signal": signal,
            })

        per_statement.append({
            "statement_id": statement.id,
            "filename": statement.original_filename,
            "bank_code": subject_code,
            "bank_name": bank_name(subject_code),
            "bank_signal": subject_signal,
            "transactions": len(txns),
            "attributed": stmt_attributed,
            "skipped": False,
        })

    # Holding both sides of a transfer means seeing it twice — once as A's debit and
    # once as B's credit. Identical parties, amount and date is one transfer observed
    # twice, and counting it twice would inflate every volume and every recurrence.
    deduped: list[dict[str, Any]] = []
    seen_transfers: set[tuple] = set()
    mirrored = 0
    for row in rows:
        key = (
            row["from_account"],
            row["to_account"],
            round(float(row["amount_paid"]), 2),
            row["txn_ts"].date() if row["txn_ts"] else None,
        )
        if None not in key[:2] and key in seen_transfers:
            mirrored += 1
            continue
        seen_transfers.add(key)
        deduped.append(row)
    rows = deduped

    total = attributed + unattributed
    coverage = {
        "mirrored_transfers_deduplicated": mirrored,
        "statements_total": len(statements),
        "statements_included": sum(1 for s in per_statement if not s["skipped"]),
        "statements_skipped": sum(1 for s in per_statement if s["skipped"]),
        "transactions_used": total,
        "counterparty_attributed": attributed,
        "counterparty_unattributed": unattributed,
        "attribution_rate": round(attributed / total, 4) if total else 0.0,
        "transfer_rows": len(rows),
        "attribution_signals": dict(sorted(signal_counts.items(), key=lambda kv: -kv[1])),
        "subject_banks": [
            {"bank_code": code, "bank_name": name} for code, name in sorted(subject_banks.items())
        ],
        "direct_banks": sorted(direct_banks),
        "per_statement": per_statement,
    }

    display_names = {
        code: bank_name(code)
        for code in {r["from_bank"] for r in rows} | {r["to_bank"] for r in rows}
    }

    return {
        "rows": rows,
        "coverage": coverage,
        "direct_banks": direct_banks,
        "display_names": display_names,
    }


def ledger_fingerprint(db: Session) -> str:
    """Cheap signature of the corpus, so profiles recompute exactly when it changes."""
    statements = db.exec(select(Statement)).all()
    parts = [
        f"{s.id}:{(s.status or '')}:{s.transaction_count or 0}:{s.bank_code or ''}"
        for s in sorted(statements, key=lambda s: s.id or 0)
    ]
    return "|".join(parts)
