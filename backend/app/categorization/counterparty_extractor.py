import re

_UPI_PATTERNS = [
    # UPI/DR/410771888258/SAI KRUPA HOTEL/UTIB/... or UPI/CR/431794202708/CHETAN SUDHAKAR POOJARY/...
    re.compile(r"UPI/(?:DR|CR|P2A|P2M|P2P)/\d+/([^/]+)", re.IGNORECASE),
    # UPI/SHREYAS SANJAY UPI-4106... or UPI/Amazon Pay Bala/...
    re.compile(
        r"UPI/([A-Za-z0-9 ._\-]+?)(?:\s+UPI[-:]|\s+/\d|\s*-\d|\s*$)", re.IGNORECASE
    ),
    re.compile(r"UPI/(?:P2A|P2M|P2P|CR|DR)?/?\d*/([A-Za-z0-9.\-@_ ]+)", re.IGNORECASE),
]

_ECOM_PATTERNS = [
    re.compile(
        r"ECOM:(?:\d+:)?([A-Za-z0-9 ]+?)(?:Gurgaon|MUMBAI|GURGOAN|hrIN|MHIN|\d{6,}|\s*$)",
        re.IGNORECASE,
    ),
    re.compile(r"PCD/\d+/([A-Za-z0-9]+)", re.IGNORECASE),
]

_NEFT_IMPS_PATTERNS = [
    re.compile(
        r"(?:NEFT|IMPS|RTGS)[^A-Za-z0-9]+(?:INW|OUT|CR|DR)?[^A-Za-z0-9]+(?:[A-Z0-9]+[^A-Za-z0-9]+)?([A-Za-z0-9 ._\-]+?)(?:\s+S\s+\d|\s+\d{8,}|\s*$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:NEFT|IMPS|RTGS)[-/](?:CR|DR)?[-/]?([A-Z0-9]+)[-/]([A-Za-z0-9 ._\-]+)",
        re.IGNORECASE,
    ),
]

_ATM_PATTERN = re.compile(r"ATM[/-](\w+)", re.IGNORECASE)
_POS_PATTERN = re.compile(r"POS[/-](\w+)", re.IGNORECASE)
_CHEQUE_PATTERN = re.compile(r"(?:CH(?:Q|EQUE)|CHEQUE)\s*[#:/]?\s*(\d+)", re.IGNORECASE)
_VPA_PATTERN = re.compile(r"[\w.\-]+@[\w]+")


def _clean_merchant_name(name: str) -> str:
    cleaned = name.strip().rstrip("/")
    if cleaned.upper().startswith("WWW"):
        cleaned = cleaned[3:]
    if cleaned.upper().endswith("IN") and len(cleaned) > 5:
        cleaned = cleaned[:-2]
    if cleaned.upper().endswith("COM") and len(cleaned) > 6:
        cleaned = cleaned[:-3]
    return cleaned.strip()


def extract_counterparty(narration: str) -> str | None:
    if not narration:
        return None
    narration_clean = narration.replace("\n", " ").strip()
    upper_narration = narration_clean.upper()

    # 1. Bank Infrastructure & Special Operations
    if "SWEEP" in upper_narration:
        return "Sweep Account"
    if "FD PREMAT" in upper_narration or "FD MATURITY" in upper_narration:
        return "Fixed Deposit"
    if "INSTALLMENT" in upper_narration and "RD" in upper_narration:
        return "Recurring Deposit"
    if "POS REFUND" in upper_narration or "ECOM REFUND" in upper_narration:
        return "Merchant Refund"
    if "SMS CHARGES" in upper_narration:
        return "Bank SMS Charges"
    if "ATM CARD" in upper_narration or "ADCCHG" in upper_narration:
        return "ATM Maintenance Charges"
    if "CASH DEPOSIT" in upper_narration or "CSHDEP" in upper_narration:
        return "Cash Deposit"
    if "INTCR" in upper_narration or "INT.PD" in upper_narration:
        return "Bank Interest"

    # 2. UPI
    for pat in _UPI_PATTERNS:
        m = pat.search(narration_clean)
        if m:
            name = m.group(1).strip().rstrip("/")
            if (
                name
                and len(name) > 2
                and not name.isdigit()
                and name.upper() not in ("DR", "CR", "UPI")
            ):
                return _clean_merchant_name(name)

    # 3. E-Commerce / PCD POS
    for pat in _ECOM_PATTERNS:
        m = pat.search(narration_clean)
        if m:
            name = m.group(1).strip()
            if name and len(name) > 2:
                return _clean_merchant_name(name)

    # 4. NEFT / IMPS / RTGS
    for pat in _NEFT_IMPS_PATTERNS:
        m = pat.search(narration_clean)
        if m:
            name = (
                m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)
            ).strip()
            if name and len(name) > 2 and not name.isdigit():
                return name

    # 5. ATM / POS
    m = _ATM_PATTERN.search(narration_clean)
    if m:
        return f"ATM {m.group(1).strip()}"

    m = _POS_PATTERN.search(narration_clean)
    if m:
        return f"POS {m.group(1).strip()}"

    # 6. VPA Pattern
    m = _VPA_PATTERN.search(narration_clean)
    if m:
        return m.group(0)

    # 7. Word Token fallback
    tokens = re.split(r"[/\s\-]+", narration_clean)
    ignore_tokens = {
        "TRANSFER",
        "CREDIT",
        "DEBIT",
        "CHARGES",
        "PAYMENT",
        "TRANSACTION",
        "ONLINE",
    }
    candidates = [
        t
        for t in tokens
        if t.isalpha() and len(t) > 3 and t.upper() not in ignore_tokens
    ]
    if candidates:
        return max(candidates, key=len)

    return None


def is_self_transfer(narration: str, account_holder: str | None) -> bool:
    if not account_holder:
        return False
    self_patterns = [
        "own a/c",
        "self transfer",
        "transfer to own",
        "own account",
        "sweep",
    ]
    if any(p in narration.lower() for p in self_patterns):
        return True
    if account_holder.lower() in narration.lower():
        return True
    return False
