import re
from typing import Optional


_BANNED_TERMS = ["guilty", "money laundering confirmed", "criminal", "arrest", "convicted"]


def _extract_numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?%?", text)


def _numbers_in_json(json_str: str) -> set[str]:
    raw_numbers = _extract_numbers(json_str)
    normalized = set()
    for n in raw_numbers:
        normalized.add(n)
        if n.endswith("%"):
            numeric = n[:-1]
            normalized.add(numeric)
            try:
                as_float = float(numeric) / 100
                normalized.add(f"{as_float:.4f}")
            except ValueError:
                pass
        else:
            try:
                as_float = float(n)
                as_pct = f"{as_float * 100:.0f}%"
                normalized.add(as_pct)
            except ValueError:
                pass
    return normalized


def _check_banned_terms(text: str) -> Optional[str]:
    text_lower = text.lower()
    for term in _BANNED_TERMS:
        if term in text_lower:
            return term
    return None


def fact_check_output(generated_text: str, evidence_json: str) -> bool:
    text_nums = _extract_numbers(generated_text)
    json_nums = _numbers_in_json(evidence_json)

    for num in text_nums:
        if num not in json_nums:
            try:
                if num.endswith("%"):
                    numeric = num[:-1]
                    as_frac = f"{float(numeric) / 100:.4f}"
                    if as_frac in json_nums:
                        continue
                else:
                    as_pct = f"{float(num) * 100:.0f}%"
                    if as_pct in json_nums:
                        continue
                return False
            except ValueError:
                return False

    banned = _check_banned_terms(generated_text)
    if banned:
        return False

    return True
