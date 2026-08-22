import csv
import re
from pathlib import Path
from typing import Optional

import pandas as pd
import openpyxl  # noqa: F401

from app.ingestion.encoding_detect import detect_encoding


def _find_header_row(rows: list[list[str]], header_keywords: set[str]) -> int | None:
    for i, row in enumerate(rows):
        text_vals = [str(c).strip().lower() for c in row if isinstance(c, str)]
        keyword_hits = sum(1 for v in text_vals if any(kw in v for kw in header_keywords))
        if keyword_hits >= 2:
            return i
        numeric_count = sum(1 for v in text_vals if _looks_numeric(v))
        if i > 0 and numeric_count >= 2 and len(row) >= 3:
            return i - 1
    return None


def _looks_numeric(s: str) -> bool:
    cleaned = s.replace(",", "").replace(".", "").replace("-", "").strip()
    return cleaned.isdigit()


def _is_footer_row(row: list[str]) -> bool:
    text = " ".join(str(c).strip().lower() for c in row)
    footer_markers = ["total", "closing balance", "opening balance", "disclaimer", "generated on", "page"]
    return any(m in text for m in footer_markers)


def extract_csv_rows(file_path: str | Path) -> tuple[list[list[str]], Optional[list[str]]]:
    path = Path(file_path)
    encoding = detect_encoding(path)

    with open(path, encoding=encoding, errors="replace") as f:
        raw_text = f.read()
        f.seek(0)
        lines = raw_text.splitlines()
        preamble_end = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            comma_count = stripped.count(",")
            if comma_count >= 2 or (comma_count >= 1 and any(kw in stripped.lower() for kw in ["date", "narration", "amount", "balance", "debit", "credit"])):
                preamble_end = i
                break
        sample = "\n".join(lines[preamble_end:]) or raw_text[:8192]
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample[:8192], delimiters=[",", ";", "\t", "|"])
        f.seek(0)
        reader = csv.reader(f, dialect)
        all_rows = [row for row in reader]

    if not all_rows:
        delimiters_to_try = [",", ";", "\t", "|"]
        for delim in delimiters_to_try:
            try:
                with open(path, encoding=encoding, errors="replace") as f:
                    reader = csv.reader(f, delimiter=delim)
                    all_rows = [row for row in reader]
                if len(all_rows) > 1 and len(all_rows[0]) >= 3:
                    break
            except Exception:
                continue

    if not all_rows:
        all_rows = [list(row) for row in pd.read_csv(path, encoding=encoding).fillna("").astype(str).values]

    header_keywords = {"date", "narration", "description", "debit", "credit", "withdrawal",
                       "deposit", "balance", "particulars", "transaction", "amount", "value", "chq", "ref"}
    header_row_idx = _find_header_row(all_rows, header_keywords)

    header: Optional[list[str]] = None
    data: list[list[str]] = []

    if header_row_idx is not None:
        header = all_rows[header_row_idx]
        for row in all_rows[header_row_idx + 1:]:
            if row and any(c.strip() for c in row) and not _is_footer_row(row):
                data.append([str(c).strip() for c in row])
    else:
        data = [[str(c).strip() for c in row] for row in all_rows if any(c.strip() for c in row)]
        data = [row for row in data if not _is_footer_row(row)]

    return data, header


def extract_xlsx_rows(file_path: str | Path) -> tuple[list[list[str]], Optional[list[str]]]:
    df = pd.read_excel(file_path, engine="openpyxl", dtype=str).fillna("")
    rows = [[str(c).strip() for c in row] for row in df.values]
    header = list(df.columns)
    header = [str(h).strip() for h in header]
    data = [row for row in rows if any(c for c in row)]
    return data, header
