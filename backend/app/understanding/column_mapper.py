from datetime import date, datetime
from decimal import Decimal

from app.understanding.canonical_schema import CanonicalTransaction

_DATE_FORMATS = [
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


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    val = val.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).date()
        except (ValueError, OSError):
            continue
    return None


def _parse_amount(val: str | None, force_positive: bool = False) -> Decimal | None:
    if not val:
        return None
    val = (
        str(val)
        .strip()
        .replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("Rs.", "")
        .replace("INR", "")
        .replace(" ", "")
    )
    if not val or val == "-":
        return None

    if val.startswith("(") and val.endswith(")"):
        val = "-" + val[1:-1]

    if val.startswith("-"):
        neg = True
        val = val[1:]
    elif val.startswith("+"):
        neg = False
        val = val[1:]
    else:
        neg = False

    try:
        amt = Decimal(val)
        if force_positive:
            return abs(amt)
        return -amt if neg else amt
    except Exception:
        return None


def map_row_to_transaction(
    row: list[str],
    col_map: dict[int, str],
    statement_id: int,
    row_index: int,
) -> CanonicalTransaction | None:
    if not col_map:
        return None

    fields: dict[str, str | None] = {}
    for col_idx, field_name in col_map.items():
        if col_idx < len(row):
            fields[field_name] = row[col_idx]

    txn_date_s = fields.get("txn_date")
    txn_date = _parse_date(txn_date_s)
    if txn_date is None:
        return None

    value_date_s = fields.get("value_date")
    value_date = _parse_date(value_date_s)

    debit_s = fields.get("debit_amount")
    credit_s = fields.get("credit_amount")

    debit = _parse_amount(debit_s, force_positive=True)
    credit = _parse_amount(credit_s, force_positive=True)

    # Handle single signed amount column if debit/credit not individually populated
    if debit is None and credit is None:
        single_amt_s = fields.get("amount") or fields.get("debit_or_credit")
        if single_amt_s:
            single_val = _parse_amount(single_amt_s)
            if single_val is not None:
                if single_val < 0:
                    debit = abs(single_val)
                    credit = None
                else:
                    credit = single_val
                    debit = None

    balance_s = fields.get("balance_after")
    balance = _parse_amount(balance_s)

    return CanonicalTransaction(
        row_id=f"{statement_id}-{row_index}",
        txn_date=txn_date,
        value_date=value_date,
        narration=fields.get("narration", "") or "",
        reference_no=fields.get("reference_no"),
        debit_amount=debit,
        credit_amount=credit,
        balance_after=balance,
        source_row_confidence=1.0,
    )
