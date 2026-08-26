"""Resolving which institution sits on each side of a statement transaction.

A statement names its own bank in the preamble, but the counterparty's bank is
only ever implied by the narration. Three signals carry it, in descending order
of certainty:

  1. A full IFSC — `IMPS/CR/1098234/DIGITAL_PAY_SERVICES/SBIN0001122/…`
  2. A bank code prefixing a reference token — `RTGS/CR/SBIN20240201/…`
  3. A UPI handle or a bank name in the text — `…@okhdfcbank`, `NEFT FROM HDFC`

Everything else stays unresolved. Attributing a `BHIM_UPI` collection to a bank
would invent an institution, so those tokens are rejected explicitly rather than
guessed at, and the caller is told what share of rows went unattributed.

Only the four-character bank code is ever kept. Branch digits are discarded: the
profile is per institution, and dropping them keeps branch-level location — which
`privacy_guard` treats as PII — out of the analysis entirely.
"""

import re
from typing import Any, Optional

from app.config_loader import load_config

# IFSC: 4-letter bank code, a literal 0, then 6 alphanumerics.
IFSC_RE = re.compile(r"\b([A-Z]{4})0[A-Z0-9]{6}\b")
# Truncated or malformed IFSC-ish tokens still carry the bank code (e.g. HDFC0012).
IFSC_LOOSE_RE = re.compile(r"\b([A-Z]{4})0[A-Z0-9]{3,9}\b")
# A reference token prefixed with a bank code: SBIN20240201, HDFC20240201.
CODE_PREFIX_RE = re.compile(r"\b([A-Z]{4})[0-9]{6,}\b")
UPI_HANDLE_RE = re.compile(r"@([a-zA-Z]+)")

UNATTRIBUTED = "UNATTRIBUTED"


def _registry() -> dict[str, Any]:
    try:
        cfg = load_config("bank_registry")
    except FileNotFoundError:
        cfg = {}
    return {
        "ifsc_codes": {k.upper(): v for k, v in (cfg.get("ifsc_codes") or {}).items()},
        "upi_handles": {k.lower(): v.upper() for k, v in (cfg.get("upi_handles") or {}).items()},
        "name_aliases": {k.lower(): v.upper() for k, v in (cfg.get("name_aliases") or {}).items()},
        "non_institution": {str(t).lower() for t in (cfg.get("non_institution_tokens") or [])},
    }


_CACHE: Optional[dict[str, Any]] = None


def registry() -> dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _registry()
    return _CACHE


def bank_name(code: Optional[str]) -> str:
    if not code:
        return "Unattributed"
    if code == UNATTRIBUTED:
        return "Unattributed"
    known = registry()["ifsc_codes"].get(code.upper())
    return known or code.upper()


def _known(code: Optional[str]) -> Optional[str]:
    """Accept a code only if the registry knows it — avoids treating any random
    four letters (NEFT, IMPS, CASH) as an institution."""
    if not code:
        return None
    code = code.upper()
    if code in registry()["ifsc_codes"]:
        return code
    return None


def resolve_from_text(*fields: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Best institution code found across the given text fields.

    Returns (bank_code, signal) where signal names which rule matched, so the UI
    can show how an attribution was made.
    """
    text = " ".join(f for f in fields if f)
    if not text:
        return None, None
    upper = text.upper()

    for match in IFSC_RE.finditer(upper):
        code = _known(match.group(1))
        if code:
            return code, "ifsc"

    for match in IFSC_LOOSE_RE.finditer(upper):
        code = _known(match.group(1))
        if code:
            return code, "ifsc_partial"

    for match in CODE_PREFIX_RE.finditer(upper):
        code = _known(match.group(1))
        if code:
            return code, "reference_prefix"

    handles = registry()["upi_handles"]
    for match in UPI_HANDLE_RE.finditer(text):
        handle = match.group(1).lower()
        if handle in handles:
            return handles[handle], "upi_handle"

    # Name match last, and only on tokens that are not platform names.
    lowered = text.lower()
    non_institution = registry()["non_institution"]
    for alias, code in sorted(registry()["name_aliases"].items(), key=lambda kv: -len(kv[0])):
        if alias in non_institution:
            continue
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", lowered):
            return code, "name"

    return None, None


def resolve_subject_bank(
    preamble: Optional[list[str]],
    template_id: Optional[str] = None,
    filename: Optional[str] = None,
) -> tuple[str, str]:
    """Identify the bank whose statement this is.

    Preamble first (it carries the bank name and the account's own IFSC), then the
    matched template id, then the filename. Returns (code, source_signal).
    """
    if preamble:
        code, signal = resolve_from_text(*preamble)
        if code:
            return code, f"preamble_{signal}"

    if template_id:
        code, _ = resolve_from_text(template_id.replace("_", " "))
        if code:
            return code, "template"

    if filename:
        code, _ = resolve_from_text(filename.replace("_", " ").replace("-", " "))
        if code:
            return code, "filename"

    return UNATTRIBUTED, "unresolved"


def resolve_counterparty_bank(
    narration: Optional[str],
    reference_no: Optional[str] = None,
    counterparty_name: Optional[str] = None,
    subject_bank: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Identify the institution on the other side of a transaction.

    Falls back to UNATTRIBUTED rather than guessing. A resolved code identical to
    the subject's bank is kept — same-bank transfers are real and common.
    """
    code, signal = resolve_from_text(narration, reference_no, counterparty_name)
    if code:
        return code, signal
    return UNATTRIBUTED, None


def extract_preamble(path: Any, max_lines: int = 20) -> list[str]:
    """Read the lines above the transaction header, which the extractor drops.

    The bank name, account holder and the account's own IFSC live there, so it is
    the only reliable place to learn whose statement this is.
    """
    from pathlib import Path

    p = Path(path)
    suffix = p.suffix.lower()

    try:
        if suffix in {".xlsx", ".xls"}:
            import pandas as pd

            frame = pd.read_excel(p, header=None, nrows=max_lines, dtype=str)
            lines = [
                " ".join(str(c) for c in row if str(c) not in ("nan", "None", ""))
                for row in frame.values.tolist()
            ]
        elif suffix == ".pdf":
            # PDFs go through their own extractor; the text layer is not read here.
            return []
        else:
            # Encoding detection is a nice-to-have here — a preamble that fails to
            # decode must not cost us the bank identity, so fall back to utf-8.
            encoding = "utf-8"
            try:
                from app.ingestion.encoding_detect import detect_encoding

                encoding = detect_encoding(p) or "utf-8"
            except Exception:
                pass
            with open(p, encoding=encoding, errors="replace") as fh:
                lines = [next(fh, "").rstrip("\n") for _ in range(max_lines)]
    except Exception:
        return []

    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        # Stop once the transaction header begins — everything after is data.
        if sum(kw in lowered for kw in ("date", "narration", "particulars", "debit", "credit", "balance")) >= 2:
            break
        kept.append(stripped)

    return kept
