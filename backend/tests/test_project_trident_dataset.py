"""Regression checks for the fixed Project Trident synthetic demo package.

These tests assert fixture provenance and accounting only. They deliberately do
not run, configure, or assert scoring outcomes.
"""

import csv
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from app.ingestion.csv_extractor import extract_csv_rows
from app.understanding.column_mapper import map_row_to_transaction
from app.understanding.header_classifier import classify_columns
from app.validation.reconciliation import reconcile_transactions

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "test_data" / "demo" / "project_trident"

EXPECTED_SHA256 = {
    "project_trident_a_hdfc.csv": "598761c775eb202ded014bbc0e069cb78d0ab3f5fc151be9ec9b8b7137138236",
    "project_trident_b_sbi.csv": "95ce357dbacb686daeacc8305ad643633f603b67ce3ebecb6491f525eb4145b6",
    "project_trident_c_icici.csv": "65fec6638718016b2b09f19b119693644c015b5d3d8e8691e1129a2a10253323",
}


def _money(value: str) -> Decimal:
    return Decimal(value.replace(",", "").replace("₹", "").strip() or "0")


def _dict_rows(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("Transaction Date,"))
    return list(csv.DictReader(lines[header_index:]))


def test_project_trident_files_are_byte_stable():
    for filename, expected_digest in EXPECTED_SHA256.items():
        assert hashlib.sha256((DEMO_DIR / filename).read_bytes()).hexdigest() == expected_digest


def test_project_trident_uses_existing_csv_template_and_reconciles():
    manifest = json.loads((DEMO_DIR / "manifest.json").read_text(encoding="utf-8"))

    for statement in manifest["statements"]:
        path = DEMO_DIR / statement["file"]
        rows, headers = extract_csv_rows(path)
        assert headers == [
            "Transaction Date",
            "Value Date",
            "Narration",
            "Reference No",
            "Debit Amount (₹)",
            "Credit Amount (₹)",
            "Balance (₹)",
        ]
        # The shared extractor intentionally filters opening-balance rows as
        # statement metadata, so its output matches the ingestible count.
        assert len(rows) == statement["transaction_count"]

        classified = classify_columns(headers, rows)
        col_map = {index: field for index, (field, _) in classified.items()}
        canonical = [
            map_row_to_transaction(row, col_map, statement_id=1, row_index=index)
            for index, row in enumerate(rows)
        ]
        assert all(canonical)
        reconciliation_rate, flags, error = reconcile_transactions(canonical)
        assert error is None
        assert reconciliation_rate == 1.0
        assert all(flags)

        # Ingestion intentionally omits the opening-balance narrative row.
        ingested = [transaction for transaction in canonical if transaction.narration != "Opening Balance"]
        assert len(ingested) == statement["transaction_count"]


def test_project_trident_manifested_ring_and_controls_are_present():
    manifest = json.loads((DEMO_DIR / "manifest.json").read_text(encoding="utf-8"))
    evidence = manifest["expected_evidence"]
    by_reference: dict[str, list[dict[str, str]]] = defaultdict(list)

    for statement in manifest["statements"]:
        for row in _dict_rows(DEMO_DIR / statement["file"]):
            by_reference[row["Reference No"]].append(row)

    ring = evidence["ring"]
    assert ring["account_order"] == [
        "Asha Verma",
        "Blue Dune Trading LLP",
        "Cobalt Route Solutions Pvt Ltd",
        "Asha Verma",
    ]
    ring_amounts = []
    for hop in ring["hops"]:
        observations = by_reference[hop["reference"]]
        assert len(observations) == 2  # debit and mirrored credit observations
        expected_amount = _money(hop["amount"])
        assert all(
            _money(row["Debit Amount (₹)"]) + _money(row["Credit Amount (₹)"])
            == expected_amount
            for row in observations
        )
        ring_amounts.append(expected_amount)
    assert ring_amounts[0] - ring_amounts[-1] == _money(ring["amount_loss"])
    assert {
        row["Transaction Date"]
        for reference in evidence["rapid_layering"]["references"]
        for row in by_reference[reference]
    } == {"10/06/2024"}

    structuring = evidence["structuring"]
    threshold = _money(structuring["threshold"])
    for deposit in structuring["deposits"]:
        observations = by_reference[deposit["reference"]]
        assert len(observations) == 1
        assert _money(observations[0]["Credit Amount (₹)"]) == _money(deposit["amount"])
        assert threshold * Decimal("0.90") <= _money(deposit["amount"]) < threshold

    vasp = evidence["partial_vasp_exit"]
    vasp_observations = by_reference[vasp["reference"]]
    assert len(vasp_observations) == 1
    assert _money(vasp_observations[0]["Debit Amount (₹)"]) == _money(vasp["amount"])
    assert vasp["counterparty"] in vasp_observations[0]["Narration"]
    for control in evidence["benign_controls"]:
        assert control["reference"] in by_reference

    trap = evidence["same_name_false_merge_trap"]
    assert {observation["associated_bank"] for observation in trap["observations"]} == {"HDFC", "ICIC"}
    for observation in trap["observations"]:
        rows = by_reference[observation["reference"]]
        assert len(rows) == 1
        assert trap["name"].upper() in rows[0]["Narration"].upper()
        assert observation["associated_bank"] in rows[0]["Narration"].upper()
