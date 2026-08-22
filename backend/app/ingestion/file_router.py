from pathlib import Path


def _check_magic_bytes(file_path: Path) -> str:
    raw = file_path.read_bytes()[:32]
    if raw.startswith(b"%PDF"):
        return "pdf"
    if raw.startswith(b"\x50\x4b\x03\x04"):
        lower = file_path.suffix.lower()
        if lower == ".xlsx":
            return "xlsx"
        return "zip"
    if raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "xls"
    return "unknown"


def classify_file(file_path: str | Path) -> str | None:
    path = Path(file_path)

    if not path.exists() or path.stat().st_size == 0:
        return None

    size = path.stat().st_size
    max_bytes = 50 * 1024 * 1024
    if size > max_bytes:
        return None

    magic = _check_magic_bytes(path)
    ext = path.suffix.lower()

    if magic == "pdf" and ext == ".pdf":
        return "pdf"
    if ext == ".csv":
        return "csv"
    if ext == ".xlsx":
        return "xlsx"
    if ext == ".xls":
        return "xls"

    if magic == "pdf":
        return "pdf"

    try:
        import pandas as pd

        df = pd.read_csv(path, nrows=3)
        if len(df.columns) >= 2 and len(df) >= 2:
            return "csv"
    except Exception:
        pass

    return None


def dispatch_extraction(
    file_path: str | Path,
) -> tuple[list[list[str]] | None, list[str] | None, str]:
    ftype = classify_file(file_path)
    if ftype is None:
        return None, None, "unsupported"

    if ftype == "pdf":
        from app.ingestion.pdf_extractor import extract_pdf

        rows, header, sub_type = extract_pdf(file_path)
        return rows, header, "pdf"
    elif ftype == "csv":
        from app.ingestion.csv_extractor import extract_csv_rows

        data, header = extract_csv_rows(file_path)
        return data, header, "csv"
    elif ftype in ("xlsx", "xls"):
        from app.ingestion.csv_extractor import extract_xlsx_rows

        data, header = extract_xlsx_rows(file_path)
        return data, header, "xlsx"
    return None, None, ftype
