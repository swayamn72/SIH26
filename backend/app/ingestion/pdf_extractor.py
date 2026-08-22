import logging
import re
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

_HEADER_KEYWORDS = [
    "date",
    "narration",
    "particulars",
    "description",
    "details",
    "debit",
    "credit",
    "withdrawal",
    "deposit",
    "balance",
    "transaction",
    "chq",
    "ref",
    "value date",
    "amount",
]


def _is_header_row(row: list[str | None], prev_header: list[str] | None = None) -> bool:
    text = " ".join(str(c or "").strip().lower() for c in row)
    keyword_hits = sum(1 for hint in _HEADER_KEYWORDS if hint in text)
    if keyword_hits >= 2:
        return True
    if prev_header and len(row) == len(prev_header):
        similarity = sum(
            1
            for a, b in zip(row, prev_header)
            if str(a or "").strip().lower() == str(b or "").strip().lower()
        )
        if similarity / max(len(row), 1) > 0.7:
            return True
    return False


def _extract_grid_tables(
    pdf: pdfplumber.PDF,
) -> tuple[list[list[str]], list[str] | None]:
    """Strategy A: Extracts structured grid tables across pages and preserves column headers."""
    all_rows: list[list[str]] = []
    main_header: list[str] | None = None

    for page in pdf.pages:
        tables = page.extract_tables()
        if not tables:
            continue

        # Filter candidate tables with at least 3 columns (ignore 1-2 column metadata tables)
        candidates = [t for t in tables if t and len(t[0]) >= 3]
        if not candidates:
            continue

        # Select the candidate table with the most rows on this page (the main ledger)
        main_table = max(candidates, key=len)
        if not main_table:
            continue

        first_row = [str(c or "").strip() for c in main_table[0]]
        first_row_is_header = _is_header_row(main_table[0], main_header)

        if first_row_is_header:
            if main_header is None:
                main_header = first_row
            data_rows = main_table[1:]
        else:
            data_rows = main_table

        for row in data_rows:
            cleaned_row = [str(c or "").strip().replace("\n", " ") for c in row]
            if not any(cleaned_row):
                continue
            # Skip repeating page headers
            if main_header and [c.lower() for c in cleaned_row] == [
                c.lower() for c in main_header
            ]:
                continue
            if _is_header_row(row, main_header):
                continue
            all_rows.append(cleaned_row)

    return all_rows, main_header


def _extract_borderless_text(
    pdf: pdfplumber.PDF,
) -> tuple[list[list[str]], list[str] | None]:
    """Strategy B: Extracts borderless text-based PDF statements (e.g. Kotak, ICICI, SBI text formats)."""
    date_core = r"(?:\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"

    # Pattern 1: [num] Date ValueDate Narration Amount Balance
    p1 = re.compile(
        rf"^\s*(?:(\d+)\s+)?({date_core})\s+({date_core})\s+(.*?)\s+([+-]?[\d,]+\.\d{{2}})\s+([+-]?[\d,]+\.\d{{2}})\s*$",
        re.IGNORECASE,
    )
    # Pattern 2: [num] Date Narration Debit Credit Balance
    p2 = re.compile(
        rf"^\s*(?:(\d+)\s+)?({date_core})\s+(.*?)\s+([+-]?[\d,]+\.\d{{2}})\s+([+-]?[\d,]+\.\d{{2}})\s+([+-]?[\d,]+\.\d{{2}})\s*$",
        re.IGNORECASE,
    )
    # Pattern 3: [num] Date Narration Amount Balance
    p3 = re.compile(
        rf"^\s*(?:(\d+)\s+)?({date_core})\s+(.*?)\s+([+-]?[\d,]+\.\d{{2}})\s+([+-]?[\d,]+\.\d{{2}})\s*$",
        re.IGNORECASE,
    )

    parsed_txns: list[dict] = []
    current_txn: dict | None = None

    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = text.split("\n")
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Filter boilerplate headers and footers
            lower_line = line_str.lower()
            if any(
                bp in lower_line
                for bp in [
                    "statement generated",
                    "page ",
                    "crn ",
                    "ifsc ",
                    "micr ",
                    "account statement",
                    "branch ",
                ]
            ):
                if not any(
                    k in lower_line
                    for k in [
                        "installment",
                        "sweep",
                        "neft",
                        "upi",
                        "pos",
                        "ecom",
                        "pcd",
                        "transfer",
                    ]
                ):
                    continue
            if "transaction date" in lower_line and "balance" in lower_line:
                continue

            m1 = p1.match(line_str)
            m2 = p2.match(line_str)
            m3 = p3.match(line_str)

            if m1:
                if current_txn:
                    parsed_txns.append(current_txn)
                num, tdate, vdate, details, amt, bal = m1.groups()
                current_txn = {
                    "txn_date": tdate,
                    "value_date": vdate,
                    "narration": details.strip(),
                    "ref": "",
                    "amt": amt,
                    "bal": bal,
                    "mode": "dual_date_single_amt",
                }
            elif m2:
                if current_txn:
                    parsed_txns.append(current_txn)
                num, tdate, details, dr, cr, bal = m2.groups()
                current_txn = {
                    "txn_date": tdate,
                    "value_date": tdate,
                    "narration": details.strip(),
                    "ref": "",
                    "debit": dr,
                    "credit": cr,
                    "bal": bal,
                    "mode": "split_amt",
                }
            elif m3:
                if current_txn:
                    parsed_txns.append(current_txn)
                num, tdate, details, amt, bal = m3.groups()
                current_txn = {
                    "txn_date": tdate,
                    "value_date": tdate,
                    "narration": details.strip(),
                    "ref": "",
                    "amt": amt,
                    "bal": bal,
                    "mode": "single_date_single_amt",
                }
            elif current_txn:
                # Continuation text for the current transaction
                current_txn["narration"] += " " + line_str

    if current_txn:
        parsed_txns.append(current_txn)

    if not parsed_txns:
        return [], None

    has_split = any(t.get("mode") == "split_amt" for t in parsed_txns)
    header = [
        "Transaction Date",
        "Value Date",
        "Description",
        "Reference No",
        "Debit Amount",
        "Credit Amount",
        "Balance",
    ]
    rows: list[list[str]] = []

    for t in parsed_txns:
        if has_split:
            rows.append(
                [
                    t.get("txn_date", ""),
                    t.get("value_date", ""),
                    t.get("narration", ""),
                    t.get("ref", ""),
                    t.get("debit", ""),
                    t.get("credit", ""),
                    t.get("bal", ""),
                ]
            )
        else:
            amt_str = t.get("amt", "").strip()
            debit_val = ""
            credit_val = ""
            if amt_str.startswith("-"):
                debit_val = amt_str.lstrip("-")
            elif amt_str.startswith("+"):
                credit_val = amt_str.lstrip("+")
            else:
                try:
                    v = float(amt_str.replace(",", ""))
                    if v < 0:
                        debit_val = str(abs(v))
                    else:
                        credit_val = str(v)
                except Exception:
                    debit_val = amt_str
            rows.append(
                [
                    t.get("txn_date", ""),
                    t.get("value_date", ""),
                    t.get("narration", ""),
                    t.get("ref", ""),
                    debit_val,
                    credit_val,
                    t.get("bal", ""),
                ]
            )

    return rows, header


def extract_pdf(file_path: str | Path) -> tuple[list[list[str]], list[str] | None, str]:
    """
    Extracts transaction records from a PDF statement using multi-strategy fallback:
    1. Grid Table Extraction (preserves header & eliminates metadata tables)
    2. Borderless Text Layout Parser (handles un-gridded text formats like Kotak/SBI)
    3. OCR Fallback for scanned image-only PDFs
    """
    path = Path(file_path)

    try:
        with pdfplumber.open(path) as pdf:
            # 1. Try Strategy A: Grid Table Extraction
            rows, header = _extract_grid_tables(pdf)
            if len(rows) >= 2 and header is not None and len(header) >= 3:
                logger.info(
                    "PDF extraction succeeded via Strategy A (Grid Tables): %d rows",
                    len(rows),
                )
                return rows, header, "pdf_table"

            # 2. Try Strategy B: Borderless Text Parser
            rows, header = _extract_borderless_text(pdf)
            if len(rows) >= 2 and header is not None:
                logger.info(
                    "PDF extraction succeeded via Strategy B (Borderless Text): %d rows",
                    len(rows),
                )
                return rows, header, "pdf_text"
    except Exception as exc:
        logger.warning("PDF extraction encountered error: %s", exc)

    # 3. Try Strategy C: OCR Fallback
    try:
        from app.ingestion.ocr_fallback import ocr_pdf

        ocr_rows = ocr_pdf(file_path)
        if len(ocr_rows) >= 2:
            return ocr_rows, None, "pdf_ocr"
    except Exception as exc:
        logger.warning("OCR fallback skipped: %s", exc)

    return [], None, "pdf_failed"


