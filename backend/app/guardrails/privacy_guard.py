import logging
import re

PII_PATTERNS = [
    (re.compile(r"\b\d{16}\b"), "[ACCOUNT_NUMBER]"),
    (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), "[IFSC_CODE]"),
    (re.compile(r"\b\d{12}\b"), "[AADHAAR]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]{1}\b"), "[PAN]"),
    (re.compile(r"\b\d{10}\b"), "[MOBILE]"),
]


def redact_pii(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class PIIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_pii(record.msg)
        return True
