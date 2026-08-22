import re
from datetime import datetime

from app.config_loader import load_config


def _try_parse_date(val: str) -> bool:
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
    cleaned = (
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
    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def _has_date_column(
    columns: list[list[str]], min_date_fraction: float = 0.8
) -> tuple[bool, float]:
    for col_idx in range(len(columns[0])):
        col_vals = [row[col_idx] for row in columns if col_idx < len(row)]
        if not col_vals:
            continue
        date_count = sum(1 for v in col_vals if _try_parse_date(v))
        fraction = date_count / len(col_vals) if col_vals else 0
        if fraction >= min_date_fraction:
            return True, fraction
    return False, 0.0


def _has_amount_columns(
    columns: list[list[str]], min_amount_fraction: float = 0.8
) -> tuple[bool, float]:
    numeric_cols = 0
    total_cols = len(columns[0]) if columns else 0
    for col_idx in range(total_cols):
        col_vals = [row[col_idx] for row in columns if col_idx < len(row)]
        if not col_vals:
            continue
        filled_vals = [v for v in col_vals if v.strip()]
        if not filled_vals:
            continue
        num_count = sum(1 for v in filled_vals if _is_numeric(v))
        fraction = num_count / len(filled_vals) if filled_vals else 0
        if fraction >= min_amount_fraction:
            numeric_cols += 1
    return numeric_cols >= 2, numeric_cols / max(total_cols, 1)


def _has_running_balance_column(
    columns: list[list[str]], sample_size: int = 20
) -> tuple[bool, float]:
    for col_idx in range(len(columns[0])):
        col_vals = [row[col_idx] for row in columns if col_idx < len(row)]
        numeric_vals: list[float] = []
        for v in col_vals:
            cleaned = (
                v.strip()
                .replace(",", "")
                .replace("₹", "")
                .replace("$", "")
                .replace(" ", "")
            )
            try:
                numeric_vals.append(float(cleaned))
            except ValueError:
                continue
        if len(numeric_vals) < 3:
            continue
        vals = numeric_vals[: min(len(numeric_vals), sample_size + 1)]
        max_val = max(vals)
        min_val = min(vals)
        if max_val == min_val:
            return True, 1.0
        if min_val > 0 and (max_val / min_val) > 100:
            continue
        consistent = 0
        for i in range(1, len(vals)):
            change = abs(vals[i] - vals[i - 1])
            max_change = 0.5 * max(abs(vals[i]), abs(vals[i - 1]), 1)
            if change <= max_change:
                consistent += 1
        if len(vals) <= 1:
            continue
        rate = consistent / (len(vals) - 1)
        if rate >= 0.3:
            return True, rate
    return False, 0.0


def _has_bank_identity_markers(full_text: str) -> tuple[bool, float]:
    markers = 0
    total = 6
    if re.search(r"^[A-Z]{4}0[A-Z0-9]{6}$", full_text, re.MULTILINE):
        markers += 1
    if re.search(r"\bIFSC\b", full_text, re.IGNORECASE):
        markers += 1
    if re.search(r"\bMICR\b", full_text, re.IGNORECASE):
        markers += 1
    if re.search(
        r"(Statement of Account|Account Statement|Bank Statement)",
        full_text,
        re.IGNORECASE,
    ):
        markers += 1
    if re.search(r"[₹$€]", full_text):
        markers += 1
    if re.search(r"\bBranch\b", full_text, re.IGNORECASE):
        markers += 1
    return markers >= 2, markers / total


def _has_narration_column(columns: list[list[str]]) -> tuple[bool, float]:
    for col_idx in range(len(columns[0])):
        col_vals = [row[col_idx] for row in columns if col_idx < len(row)]
        if not col_vals:
            continue
        non_empty = [v for v in col_vals if len(v.strip()) > 10]
        if len(non_empty) / max(len(col_vals), 1) > 0.3:
            unique = len(set(col_vals))
            if unique / max(len(col_vals), 1) > 0.3:
                return True, unique / max(len(col_vals), 1)
    return False, 0.0


def compute_statement_likelihood(
    raw_rows: list[list[str]], full_text: str, num_rows: int
) -> tuple[float, dict[str, float]]:
    cfg = load_config("thresholds")
    weights = cfg.get("ood_weights", {})
    auto_proceed = cfg.get("ood", {}).get("auto_proceed", 0.70)

    if not raw_rows or len(raw_rows) < 3:
        return 0.0, {
            "has_date_column": 0,
            "has_amount_columns": 0,
            "has_running_balance_column": 0,
            "has_bank_identity_markers": 0,
            "has_narration_column": 0,
            "row_count_plausible": 0,
        }

    columns = list(zip(*raw_rows, strict=False)) if len(raw_rows[0]) > 0 else []
    columns = [list(c) for c in columns]

    signals: dict[str, float] = {}
    has_date, date_score = _has_date_column(raw_rows)
    signals["has_date_column"] = date_score

    has_amount, amt_score = _has_amount_columns(raw_rows)
    signals["has_amount_columns"] = amt_score

    has_balance, bal_score = _has_running_balance_column(raw_rows)
    signals["has_running_balance_column"] = bal_score

    has_bank, bank_score = _has_bank_identity_markers(full_text)
    signals["has_bank_identity_markers"] = bank_score

    has_narr, narr_score = _has_narration_column(raw_rows)
    signals["has_narration_column"] = narr_score

    rc_plausible = 1.0 if 3 <= num_rows <= 200000 else 0.0
    signals["row_count_plausible"] = rc_plausible

    score = sum(signals.get(k, 0) * weights.get(k, 0) for k in weights)
    return min(score, 1.0), signals


def classify_ood_tier(score: float, signals: dict[str, float]) -> str:
    cfg = load_config("thresholds")
    ood = cfg.get("ood", {})
    lower = ood.get("low_confidence_lower", 0.40)
    upper = ood.get("low_confidence_upper", 0.70)

    if score >= upper:
        return "auto_proceed"
    elif score >= lower:
        return "low_confidence"
    else:
        return "hard_reject"


def get_failure_reasons(
    signals: dict[str, float], weights: dict[str, float]
) -> list[str]:
    reasons = []
    for signal_name, weight in weights.items():
        val = signals.get(signal_name, 0)
        if val < 0.5:
            reasons.append(f"{signal_name}: {val:.2f} (below 0.5 threshold)")
    return reasons if reasons else ["All signals passed"]
