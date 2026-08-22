import re
from typing import Optional

from rapidfuzz import fuzz

from app.config_loader import load_config


def normalize_counterparty_name(name: str) -> str:
    name = name.strip().upper()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^\w\s@.\-]", "", name)
    suffixes = [
        r"\bPVT\s*LTD\b", r"\bPRIVATE\s*LIMITED\b", r"\bLIMITED\b", r"\bLTD\b",
        r"\bLLP\b", r"\bINC\b", r"\bCORPORATION\b", r"\bCORP\b",
    ]
    for suffix in suffixes:
        name = re.sub(suffix, "", name, flags=re.IGNORECASE)
    return name.strip()


def merge_counterparty_variants(
    names: list[str],
    threshold: Optional[float] = None,
) -> dict[str, str]:
    if threshold is None:
        cfg = load_config("category_rules") if load_config("category_rules") else {}
        threshold = cfg.get("counterparty_merge_threshold", 92) / 100.0

    normalized = {n: normalize_counterparty_name(n) for n in names}
    merged: dict[str, str] = {}
    assigned: set[str] = set()

    for name, norm in sorted(normalized.items(), key=lambda x: -len(x[1])):
        if name in assigned:
            continue
        cluster_key = norm
        for other_name, other_norm in sorted(normalized.items(), key=lambda x: -len(x[1])):
            if other_name not in assigned and other_name != name:
                ratio = fuzz.token_set_ratio(norm, other_norm) / 100.0
                if ratio >= threshold:
                    merged[other_name] = cluster_key
                    assigned.add(other_name)
        merged[name] = cluster_key
        assigned.add(name)

    return merged
