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
    if token == "critical_value_95":
        return float(load_config("thresholds").get("benford", {}).get("critical_value", 15.507))
    try:
        return float(token)
    except ValueError:
        return 0.0


_CONDITION_OPERATORS = (" >= ", " <= ", " > ", " < ", " == ")


def parse_condition_clauses(
    condition_str: str, feature_values: dict[str, Any]
) -> dict[str, Any]:
    """Break a rule condition into per-clause evidence.

    Returns the joiner plus, for every clause, the feature it reads, the operator,
    the resolved threshold and the account's actual value — so the UI can show
    "net_retention_ratio (0.04) < 0.15" instead of a bare rule name.
    """
    condition_str = (condition_str or "").strip()
    if not condition_str:
        return {"joiner": "AND", "clauses": []}

    joiner = "AND" if " AND " in condition_str else ("OR" if " OR " in condition_str else "AND")
    parts = condition_str.split(f" {joiner} ") if f" {joiner} " in condition_str else [condition_str]

    clauses: list[dict[str, Any]] = []
    for part in parts:
        part = part.strip()
        parsed = False
        for op in _CONDITION_OPERATORS:
            if op in part:
                field, token = part.split(op, 1)
                field = field.strip()
                token = token.strip()
                actual = feature_values.get(field)
                clauses.append({
                    "expression": part,
                    "field": field,
                    "operator": op.strip(),
                    "threshold_expression": token,
                    "threshold_value": _resolve_threshold(token, feature_values),
                    "actual_value": float(actual) if isinstance(actual, (int, float)) else None,
                    "holds": _evaluate_single_condition(part, feature_values),
                })
                parsed = True
                break
        if not parsed:
            clauses.append({
                "expression": part,
                "field": None,
                "operator": None,
                "threshold_expression": None,
                "threshold_value": None,
                "actual_value": None,
                "holds": None,
            })

    return {"joiner": joiner, "clauses": clauses}


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
