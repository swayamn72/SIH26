import json
from pathlib import Path
from typing import Any, Optional

from rapidfuzz import fuzz

from app.config_loader import load_config


def _load_templates() -> list[dict[str, Any]]:
    template_dir = Path(__file__).parents[3] / "config" / "bank_templates"
    templates: list[dict[str, Any]] = []

    if template_dir.is_dir():
        for fpath in sorted(template_dir.glob("*.json")):
            with open(fpath, encoding="utf-8") as f:
                templates.append(json.load(f))

    user_dir = template_dir / "user_learned"
    if user_dir.is_dir():
        for fpath in sorted(user_dir.glob("*.json")):
            with open(fpath, encoding="utf-8") as f:
                templates.append(json.load(f))

    return templates


def match_template(detected_headers: list[str]) -> tuple[Optional[dict[str, Any]], float]:
    templates = _load_templates()
    cfg = load_config("thresholds")
    match_threshold = cfg.get("header_classification", {}).get("template_match_threshold", 0.85)

    best_match = None
    best_score = 0.0

    for tmpl in templates:
        match_headers = tmpl.get("match_headers", [])
        if not match_headers:
            if tmpl.get("is_fallback", False):
                if best_score == 0:
                    best_match = tmpl
                    best_score = 0.0
            continue

        scores: list[float] = []
        for mh in match_headers:
            best_dh_score = max(
                (fuzz.token_sort_ratio(mh.lower(), dh.lower()) / 100.0 for dh in detected_headers),
                default=0.0,
            )
            scores.append(best_dh_score)

        mean_score = sum(scores) / len(scores) if scores else 0.0

        if mean_score > best_score and mean_score >= match_threshold:
            best_score = mean_score
            best_match = tmpl

    return best_match, best_score
