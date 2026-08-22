from datetime import datetime

from rapidfuzz import fuzz

from app.config_loader import load_config

FIELD_HINTS: dict[str, list[str]] = {
    "txn_date": [
        "transaction date",
        "txn date",
        "tran date",
        "date",
        "post date",
        "trans date",
        "posting date",
        "txndate",
        "txn_date",
    ],
    "value_date": ["value date", "value dt", "val dt", "val date", "value_date"],
    "narration": [
        "narration",
        "description",
        "particulars",
        "details",
        "remarks",
        "transaction details",
        "transaction particulars",
        "txn description",
    ],
    "debit_amount": [
        "debit amount (₹)",
        "debit amount",
        "withdrawal amount",
        "debit",
        "withdrawal",
        "dr",
        "dr amount",
        "withdrawal amt",
        "debit (inr)",
        "amount debited",
        "dr.",
    ],
    "credit_amount": [
        "credit amount (₹)",
        "credit amount",
        "deposit amount",
        "credit",
        "deposit",
        "cr",
        "cr amount",
        "deposit amt",
        "credit (inr)",
        "amount credited",
        "cr.",
    ],
    "balance_after": [
        "running balance (₹)",
        "running balance",
        "balance (₹)",
        "balance",
        "closing balance",
        "available balance",
        "balance amt",
        "balance (inr)",
        "net balance",
        "clear balance",
    ],
    "reference_no": [
        "transaction reference",
        "chq / ref no.",
        "chq/ref no",
        "chq no",
        "ref no",
        "reference no",
        "cheque no",
        "utr",
        "ref",
        "reference",
        "chq/ref",
        "txn ref",
        "reference number",
    ],
}


def _try_parse_date(val: str) -> bool:
    if not val or len(val) < 6:
        return False
    fmt_candidates = [
        "%d %b %Y",
        "%d-%b-%Y",
        "%d %B %Y",
        "%d-%B-%Y",
        "%b %d, %Y",
        "%b %d %Y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y%m%d",
        "%d.%m.%Y",
        "%Y/%m/%d",
        "%d %b %y",
    ]
    for fmt in fmt_candidates:
        try:
            datetime.strptime(val.strip(), fmt)
            return True
        except (ValueError, OSError):
            continue
    return False


def _is_numeric(val: str) -> bool:
    try:
        float(
            val.strip()
            .replace(",", "")
            .replace("₹", "")
            .replace("$", "")
            .replace("Rs.", "")
            .replace("INR", "")
            .replace("+", "")
            .replace("-", "")
            .replace(" ", "")
        )
        return True
    except ValueError:
        return False


def _content_heuristic(field: str, sample_values: list[str]) -> float:
    if not sample_values:
        return 0.0
    non_empty = [v for v in sample_values if v.strip()]
    if not non_empty:
        return (
            0.5
            if field in ("credit_amount", "debit_amount", "reference_no", "value_date")
            else 0.0
        )

    if field == "txn_date":
        date_count = sum(1 for v in non_empty if _try_parse_date(v))
        return date_count / len(non_empty)

    if field == "value_date":
        date_count = sum(1 for v in non_empty if _try_parse_date(v))
        return (date_count / len(non_empty)) * 0.9

    if field == "narration":
        long_count = sum(1 for v in non_empty if len(v) > 8)
        unique_ratio = len(set(non_empty)) / max(len(non_empty), 1)
        return (long_count / len(non_empty)) * 0.5 + unique_ratio * 0.5

    if field in ("debit_amount", "credit_amount", "balance_after"):
        num_count = sum(1 for v in non_empty if _is_numeric(v))
        return num_count / len(non_empty)

    if field == "reference_no":
        alnum_count = sum(1 for v in non_empty if any(c.isdigit() for c in v))
        unique_ratio = len(set(non_empty)) / max(len(non_empty), 1)
        return (alnum_count / len(non_empty)) * 0.5 + unique_ratio * 0.5

    return 0.0


def _header_score(field: str, header_raw: str) -> float:
    hints = FIELD_HINTS.get(field, [])
    if not hints:
        return 0.0
    clean_h = (
        header_raw.lower()
        .replace("₹", "")
        .replace("inr", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )
    return max(fuzz.token_sort_ratio(clean_h, h.lower()) / 100.0 for h in hints)


def classify_columns(
    headers: list[str], sample_rows: list[list[str]]
) -> dict[int, tuple[str, float]]:
    cfg = load_config("thresholds")
    h_weight = cfg.get("column_mapping", {}).get("header_score_weight", 0.6)
    c_weight = cfg.get("column_mapping", {}).get("content_score_weight", 0.4)
    min_accept = cfg.get("header_classification", {}).get("field_min_acceptance", 0.50)

    candidates: list[tuple[float, int, str]] = []
    for col_idx, header_raw in enumerate(headers):
        sample_values = [r[col_idx] for r in sample_rows[:50] if col_idx < len(r)]
        for field in FIELD_HINTS:
            hs = _header_score(field, header_raw)
            cs = _content_heuristic(field, sample_values)
            combined = hs * h_weight + cs * c_weight
            if hs >= 0.85:
                combined = max(combined, hs * 0.9)
            if combined >= min_accept:
                candidates.append((combined, col_idx, field))

    # Highest score candidates first
    candidates.sort(key=lambda x: x[0], reverse=True)

    assignments: dict[int, tuple[str, float]] = {}
    assigned_cols: set[int] = set()
    assigned_fields: set[str] = set()

    for score, col_idx, field in candidates:
        if col_idx not in assigned_cols and field not in assigned_fields:
            assignments[col_idx] = (field, score)
            assigned_cols.add(col_idx)
            assigned_fields.add(field)

    return assignments
