from typing import Optional

from app.understanding.canonical_schema import CanonicalTransaction
from app.config_loader import load_config


def compute_row_confidence(
    txn: CanonicalTransaction,
    is_reconciled: bool = False,
    ocr_confidence: Optional[float] = None,
) -> float:
    scores: list[float] = []

    if ocr_confidence is not None:
        scores.append(ocr_confidence)
    else:
        scores.append(1.0)

    all_fields_present = all([
        txn.txn_date is not None,
        txn.narration is not None and len(txn.narration.strip()) > 0,
        txn.debit_amount is not None or txn.credit_amount is not None,
    ])
    scores.append(1.0 if all_fields_present else 0.5)

    scores.append(1.0 if is_reconciled else 0.5)

    return sum(scores) / len(scores) if scores else 1.0


def classify_extraction_confidence(reconciliation_rate: float) -> str:
    cfg = load_config("thresholds")
    rec = cfg.get("reconciliation", {})
    high_min = rec.get("high_confidence_min", 0.98)
    med_min = rec.get("medium_confidence_min", 0.85)

    if reconciliation_rate >= high_min:
        return "high"
    elif reconciliation_rate >= med_min:
        return "medium"
    else:
        return "low"
