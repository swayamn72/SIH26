#!/usr/bin/env python3
"""Verify the checked-in Project Trident fixture without invoking application scoring."""

import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "test_data" / "demo" / "project_trident"


def money(value: str) -> Decimal:
    return Decimal(value.replace(",", "").replace("₹", "").strip() or "0")


def rows_by_reference(path: Path) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("Transaction Date,"))
    rows = list(csv.DictReader(lines[header_index:]))
    references: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        references[row["Reference No"]].append(row)
    return rows, references


def reconciles(rows: list[dict[str, str]]) -> bool:
    previous = None
    for row in rows:
        balance = money(row["Balance (₹)"])
        if previous is not None and previous - money(row["Debit Amount (₹)"]) + money(row["Credit Amount (₹)"]) != balance:
            return False
        previous = balance
    return True


def main() -> int:
    manifest = json.loads((DEMO_DIR / "manifest.json").read_text(encoding="utf-8"))
    all_references: dict[str, list[dict[str, str]]] = defaultdict(list)

    for statement in manifest["statements"]:
        rows, references = rows_by_reference(DEMO_DIR / statement["file"])
        if len(rows) != statement["source_transaction_count"]:
            raise AssertionError(f"{statement['id']}: source transaction count changed")
        if not reconciles(rows):
            raise AssertionError(f"{statement['id']}: balances do not reconcile")
        if money(rows[0]["Balance (₹)"]) != money(statement["opening_balance"]):
            raise AssertionError(f"{statement['id']}: opening balance changed")
        if money(rows[-1]["Balance (₹)"]) != money(statement["closing_balance"]):
            raise AssertionError(f"{statement['id']}: closing balance changed")
        for ref, observations in references.items():
            all_references[ref].extend(observations)

    evidence = manifest["expected_evidence"]
    ring_amounts = [money(hop["amount"]) for hop in evidence["ring"]["hops"]]
    for hop in evidence["ring"]["hops"]:
        observations = all_references[hop["reference"]]
        if len(observations) != 2 or any(
            money(row["Debit Amount (₹)"]) + money(row["Credit Amount (₹)"]) != money(hop["amount"])
            or row["Transaction Date"] != hop["date"]
            for row in observations
        ):
            raise AssertionError(f"{hop['reference']}: ring mirror, amount, or date changed")
    if ring_amounts[0] - ring_amounts[-1] != money(evidence["ring"]["amount_loss"]):
        raise AssertionError("ring amount loss changed")
    rapid_refs = evidence["rapid_layering"]["references"]
    if len({row["Transaction Date"] for ref in rapid_refs for row in all_references[ref]}) != 1:
        raise AssertionError("rapid-layering transfers are no longer on the same date")

    for deposit in evidence["structuring"]["deposits"]:
        amount = money(deposit["amount"])
        observations = all_references[deposit["reference"]]
        if len(observations) != 1 or money(observations[0]["Credit Amount (₹)"]) != amount:
            raise AssertionError(f"{deposit['reference']}: deposit evidence changed")
        if not (amount < money(evidence["structuring"]["threshold"]) and amount >= money(evidence["structuring"]["threshold"]) * Decimal("0.90")):
            raise AssertionError(f"{deposit['reference']}: no longer near threshold")

    vasp = evidence["partial_vasp_exit"]
    vasp_observations = all_references[vasp["reference"]]
    if len(vasp_observations) != 1 or money(vasp_observations[0]["Debit Amount (₹)"]) != money(vasp["amount"]) or vasp["counterparty"] not in vasp_observations[0]["Narration"]:
        raise AssertionError("partial VASP exit evidence changed")
    for item in evidence["benign_controls"]:
        if item["reference"] not in all_references:
            raise AssertionError(f"{item['reference']}: expected benign control missing")

    trap = evidence["same_name_false_merge_trap"]
    if len({item["associated_bank"] for item in trap["observations"]}) < 2:
        raise AssertionError("same-name false-merge control no longer has distinct banks")
    for item in trap["observations"]:
        observations = all_references[item["reference"]]
        narration = observations[0]["Narration"].upper() if observations else ""
        if len(observations) != 1 or trap["name"].upper() not in narration or item["associated_bank"] not in narration:
            raise AssertionError(f"{item['reference']}: false-merge observation changed")

    print("Project Trident fixture verified: 3 reconciled statements and A→B→C→A evidence intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
