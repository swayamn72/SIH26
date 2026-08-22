import re
from typing import Optional

from rapidfuzz import fuzz

from app.config_loader import load_config


def infer_channel(narration: str) -> str:
    cfg = load_config("category_rules")
    channels = cfg.get("channels", {})

    for channel_name, channel_cfg in channels.items():
        for pattern in channel_cfg.get("patterns", []):
            if re.search(pattern, narration, re.IGNORECASE):
                return channel_name

    return "UNKNOWN"


def assign_category(narration: str, direction: str) -> str:
    cfg = load_config("category_rules")
    categories = cfg.get("categories", [])
    fuzzy_threshold = cfg.get("fuzzy_match_threshold", 80)

    best_match = "uncategorized"
    best_score = 0

    for cat in categories:
        cat_direction = cat.get("direction", "any")
        if cat_direction not in ("any", direction):
            continue
        for keyword in cat.get("match_any", []):
            if keyword.lower() in narration.lower():
                return cat["name"]
            score = fuzz.partial_ratio(keyword.lower(), narration.lower())
            if score > best_score and score >= fuzzy_threshold:
                best_score = score
                best_match = cat["name"]

    return best_match
