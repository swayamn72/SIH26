import math
from typing import Any

from app.config_loader import load_config


def _evaluate_condition(condition_str: str, feature_values: dict[str, Any]) -> bool:
    condition_str = condition_str.strip()

    if " AND " in condition_str:
        parts = condition_str.split(" AND ")
        return all(_evaluate_single_condition(p.strip(), feature_values) for p in parts)

    if " OR " in condition_str:
        parts = condition_str.split(" OR ")
        return any(_evaluate_single_condition(p.strip(), feature_values) for p in parts)

    return _evaluate_single_condition(condition_str, feature_values)


def _evaluate_single_condition(condition_str: str, feature_values: dict[str, Any]) -> bool:
    # Check multi-character operators BEFORE single-character ones
    # to avoid ">=" being falsely split on ">"
    if " >= " in condition_str:
        field, threshold_str = condition_str.split(" >= ", 1)
        val = feature_values.get(field.strip())
        if val is None:
            return False
        threshold = _resolve_threshold(threshold_str.strip(), feature_values)
        return float(val) >= float(threshold)

    if " <= " in condition_str:
        field, threshold_str = condition_str.split(" <= ", 1)
        val = feature_values.get(field.strip())
        if val is None:
            return False
        threshold = _resolve_threshold(threshold_str.strip(), feature_values)
        return float(val) <= float(threshold)

    if " > " in condition_str:
        field, threshold_str = condition_str.split(" > ", 1)
        val = feature_values.get(field.strip())
        if val is None:
            return False
        threshold = _resolve_threshold(threshold_str.strip(), feature_values)
        return float(val) > float(threshold)

    if " < " in condition_str:
        field, threshold_str = condition_str.split(" < ", 1)
        val = feature_values.get(field.strip())
        if val is None:
            return False
        threshold = _resolve_threshold(threshold_str.strip(), feature_values)
        return float(val) < float(threshold)

    if " == " in condition_str:
        field, threshold_str = condition_str.split(" == ", 1)
        val = feature_values.get(field.strip())
        if val is None:
            return False
        threshold = _resolve_threshold(threshold_str.strip(), feature_values)
        return float(val) == float(threshold)

    return False


def _resolve_threshold(token: str, feature_values: dict[str, Any]) -> float:
    token = token.strip()
    if token in feature_values:
        val = feature_values[token]
        return float(val) if val is not None else 0.0
    if token.startswith("p") and token[1:].isdigit():
        pct = int(token[1:]) / 100.0
        numeric_vals = [float(v) for v in feature_values.values() if isinstance(v, (int, float)) and v is not None]
        if numeric_vals:
            numeric_vals.sort()
            idx = int(len(numeric_vals) * pct)
            return numeric_vals[min(idx, len(numeric_vals) - 1)]
    critical_vals = {"critical_value_95": 15.507}
    if token in critical_vals:
        return critical_vals[token]
    try:
        return float(token)
    except ValueError:
        return 0.0


def evaluate_rules(feature_values: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    cfg = load_config("thresholds")
    rules_cfg = cfg.get("rules", {})
    triggered: list[dict[str, Any]] = []
    total_points = 0

    for rule_id, rule_cfg in rules_cfg.items():
        condition = rule_cfg.get("condition", "")
        points = rule_cfg.get("points", 0)

        try:
            is_triggered = _evaluate_condition(condition, feature_values)
        except Exception:
            is_triggered = False

        if is_triggered:
            total_points += points
            triggered.append({
                "id": rule_id,
                "condition": condition,
                "computed_value": feature_values.get(rule_id.split("_", 1)[0].lower(), None),
                "points": points,
                "description": rule_cfg.get("description", ""),
            })

    rule_score = min(total_points, 100)
    return float(rule_score), triggered
