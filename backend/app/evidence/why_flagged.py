"""The "Why Flagged?" evidence summary.

Answers the only question an investigator actually asks: why did this account get
this score? Every reason returned here is assembled from the stored evidence
bundle, the detected pattern timelines and the real transaction rows - the rule
clause that fired with its actual-vs-threshold numbers, the features behind it,
and the transactions that produced those numbers. Nothing is narrated by a model.
"""

from datetime import date, datetime, time
from typing import Any, Optional

from app.config_loader import load_config
from app.scoring.rule_scorer import parse_condition_clauses

SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

MAX_SAMPLE_TRANSACTIONS = 5

CONFIDENCE_FORMULA = (
    "confidence = 100 * (0.35*extraction_quality + 0.25*statement_fit "
    "+ 0.25*decision_margin + 0.15*signal_corroboration)"
)

# Rules that a named reason already explains; anything else becomes its own reason.
RULE_TO_REASON = {
    "R5_circular_flow_detected": "circular_flow",
    "R1_low_retention_high_turnover": "high_velocity",
    "R3_structuring_near_threshold": "abnormal_amounts",
    "R4_benford_anomaly": "abnormal_amounts",
    "R2_dormancy_then_burst": "dormancy_burst",
    "R6_fan_in_fan_out": "high_risk_connections",
}

REASON_TITLES = {
    "circular_flow": "Circular transaction pattern",
    "high_velocity": "Unusually high transaction velocity",
    "abnormal_amounts": "Abnormal transaction amounts",
    "high_risk_connections": "Connection to high-risk accounts",
    "dormancy_burst": "Dormant account reactivated in a burst",
    "statistical_outlier": "Statistical outlier vs. peer baseline",
}

REASON_CATEGORIES = {
    "circular_flow": "graph",
    "high_velocity": "velocity",
    "abnormal_amounts": "structuring",
    "high_risk_connections": "network",
    "dormancy_burst": "lifecycle",
    "statistical_outlier": "statistical",
}


def _as_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _amount_of(txn: Any) -> tuple[float, str]:
    debit = float(txn.debit_amount or 0.0)
    credit = float(txn.credit_amount or 0.0)
    if debit >= credit and debit > 0:
        return debit, "debit"
    if credit > 0:
        return credit, "credit"
    return 0.0, "debit"


def _severity_from_points(points: float) -> str:
    if points >= 25:
        return "CRITICAL"
    if points >= 20:
        return "HIGH"
    if points >= 15:
        return "MEDIUM"
    return "LOW"


def _txn_evidence(txn: Any, labels: dict[str, str]) -> dict[str, Any]:
    amount, direction = _amount_of(txn)
    cp_id = str(txn.counterparty_id) if txn.counterparty_id is not None else "UNKNOWN"
    dt = _as_datetime(txn.txn_date)
    return {
        "row_id": txn.row_id,
        "txn_id": txn.reference_no or txn.row_id,
        "timestamp": dt.isoformat() if dt else None,
        "counterparty": labels.get(cp_id, "Unknown counterparty"),
        "counterparty_id": cp_id,
        "amount": round(amount, 2),
        "direction": direction,
        "channel": txn.channel or "",
        "narration": txn.narration or "",
    }


def _sample(
    rows: list[Any], labels: dict[str, str], key=None
) -> tuple[list[dict[str, Any]], int]:
    """Return up to MAX_SAMPLE_TRANSACTIONS evidence rows plus the count withheld."""
    ordered = sorted(rows, key=key) if key else rows
    shown = [_txn_evidence(t, labels) for t in ordered[:MAX_SAMPLE_TRANSACTIONS]]
    return shown, max(0, len(ordered) - MAX_SAMPLE_TRANSACTIONS)


def _feature_evidence(
    features_by_name: dict[str, dict[str, Any]],
    names: list[str],
    thresholds: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in names:
        f = features_by_name.get(name)
        if not f or f.get("value") is None:
            continue
        entry = {
            "name": name,
            "value": f.get("value"),
            "formula": f.get("formula", ""),
            "explanation": f.get("explanation", ""),
            "family": f.get("family", ""),
        }
        t = thresholds.get(name)
        if t:
            entry["threshold_value"] = t.get("threshold_value")
            entry["operator"] = t.get("operator")
            entry["rule_id"] = t.get("rule_id")
        out.append(entry)
    return out


def _peak_velocity_rows(txns: list[Any], window_hours: float = 24.0) -> list[Any]:
    """The densest rolling window of activity - what inflow_outflow_velocity measures."""
    dated = [t for t in txns if _as_datetime(t.txn_date)]
    dated.sort(key=lambda t: (_as_datetime(t.txn_date), t.row_id))
    best: list[Any] = []
    start = 0
    for end in range(len(dated)):
        end_dt = _as_datetime(dated[end].txn_date)
        while start < end:
            span = (end_dt - _as_datetime(dated[start].txn_date)).total_seconds() / 3600.0
            if span <= window_hours:
                break
            start += 1
        if end - start + 1 > len(best):
            best = dated[start : end + 1]
    return best


def _money(value: float) -> str:
    return f"₹{value:,.2f}"


def _build_circular_reason(patterns, cycles, labels, txn_by_row) -> Optional[dict[str, Any]]:
    cycle_patterns = [p for p in patterns if p.get("kind") == "cycle"]
    if not cycle_patterns and not cycles:
        return None

    if cycle_patterns:
        top = cycle_patterns[0]
        rows = [txn_by_row[r] for r in top.get("row_ids", []) if r in txn_by_row]
        shown, withheld = _sample(rows, labels)
        path = " → ".join(n["label"] for n in top.get("node_path", []))
        return {
            "id": "circular_flow",
            "severity": top.get("severity", "HIGH"),
            "headline": (
                f"{_money(top.get('total_amount', 0.0))} moved along {path} and returned to the "
                f"account within {top.get('span_days', 0)} days."
            ),
            "detail": top.get("summary", ""),
            "how_computed": top.get("formula", ""),
            "metrics": [
                {"label": "Cycle risk", "value": f"{top.get('risk_score', 0) * 100:.0f}%"},
                {"label": "Hops in path", "value": len(top.get("node_path", [])) - 1},
                {"label": "Transfers", "value": len(top.get("row_ids", []))},
                {"label": "Amount conservation",
                 "value": f"{float((top.get('metrics') or {}).get('amount_conservation_ratio') or 0) * 100:.0f}%"},
            ],
            "transactions": shown,
            "transactions_withheld": withheld,
            "pattern_ids": [p["pattern_id"] for p in cycle_patterns],
            "graph_pattern_id": top["pattern_id"],
        }

    top_cycle = max(cycles, key=lambda c: c.get("cycle_risk_score") or 0)
    return {
        "id": "circular_flow",
        "severity": "HIGH",
        "headline": (
            f"A {top_cycle.get('hop_count', 0)}-hop circular flow was detected in the "
            "transaction graph."
        ),
        "detail": "Contributing transaction rows are no longer resolvable for this cycle.",
        "how_computed": "cycle_risk = 0.35*amount_conservation + 0.30*velocity_compression "
                        "+ 0.20*cycle_recurrence + 0.15*inverse_hop_count",
        "metrics": [
            {"label": "Cycle risk", "value": f"{float(top_cycle.get('cycle_risk_score') or 0) * 100:.0f}%"},
            {"label": "Hops", "value": top_cycle.get("hop_count", 0)},
        ],
        "transactions": [],
        "transactions_withheld": 0,
        "pattern_ids": [],
        "graph_pattern_id": None,
    }


def _build_velocity_reason(
    patterns, txns, labels, features_by_name, txn_by_row
) -> Optional[dict[str, Any]]:
    layering = [p for p in patterns if p.get("kind") == "layering"]
    peak = float(features_by_name.get("inflow_outflow_velocity", {}).get("value") or 0)
    hold = features_by_name.get("median_holding_time_hours", {}).get("value")
    retention = features_by_name.get("net_retention_ratio", {}).get("value")
    turnover = features_by_name.get("turnover_ratio", {}).get("value")

    retains_little = retention is not None and float(retention) < 0.5
    if not layering and peak < 5 and not retains_little:
        return None

    if layering:
        top = layering[0]
        rows = [txn_by_row[r] for r in top.get("row_ids", []) if r in txn_by_row]
        shown, withheld = _sample(rows, labels)
        m = top.get("metrics") or {}
        headline = (
            f"{_money(float(m.get('inflow') or 0))} arrived and "
            f"{_money(float(m.get('outflow') or 0))} left within "
            f"{float(m.get('hold_days') or 0):.2f} days "
            f"({float(m.get('amount_match') or 0) * 100:.0f}% amount match)."
        )
        graph_pattern_id = top["pattern_id"]
    else:
        rows = _peak_velocity_rows(txns)
        shown, withheld = _sample(rows, labels)
        headline = f"{len(rows)} transactions cleared inside a single 24-hour window."
        graph_pattern_id = None

    metrics = [{"label": "Peak 24h transactions", "value": int(peak)}]
    if hold is not None:
        metrics.append({"label": "Median holding time", "value": f"{float(hold):.2f} h"})
    if retention is not None:
        metrics.append({"label": "Net retention", "value": f"{float(retention) * 100:.1f}%"})
    if turnover is not None:
        metrics.append({"label": "Turnover ratio", "value": f"{float(turnover):.2f}x"})

    return {
        "id": "high_velocity",
        "severity": "HIGH" if layering else "MEDIUM",
        "headline": headline,
        "detail": (
            "Money is passing through rather than being held: inflows are matched by "
            "near-equal outflows inside the holding window."
        ),
        "how_computed": (top.get("formula", "") if layering else
                         "peak_velocity = max txn count in any rolling 24h window"),
        "metrics": metrics,
        "transactions": shown,
        "transactions_withheld": withheld,
        "pattern_ids": [p["pattern_id"] for p in layering],
        "graph_pattern_id": graph_pattern_id,
    }


def _build_amount_reason(
    patterns, txns, labels, features_by_name, txn_by_row
) -> Optional[dict[str, Any]]:
    structuring = [p for p in patterns if p.get("kind") == "structuring"]
    near_ratio = features_by_name.get("near_threshold_ratio", {}).get("value")
    round_ratio = features_by_name.get("round_number_ratio", {}).get("value")
    benford = features_by_name.get("benford_deviation_score", {}).get("value")

    has_signal = (
        bool(structuring) or float(near_ratio or 0) >= 0.10 or float(round_ratio or 0) >= 0.30
    )
    if not has_signal:
        return None

    if structuring:
        top = structuring[0]
        rows = [txn_by_row[r] for r in top.get("row_ids", []) if r in txn_by_row]
        shown, withheld = _sample(rows, labels, key=lambda t: -_amount_of(t)[0])
        m = top.get("metrics") or {}
        threshold = float(m.get("threshold") or 0)
        headline = (
            f"{int(m.get('transaction_count') or len(rows))} transfers sit just under the "
            f"{_money(threshold)} reporting threshold "
            f"(mean {float(m.get('mean_proximity') or 0) * 100:.1f}% of it)."
        )
        graph_pattern_id = top["pattern_id"]
    else:
        rows = sorted(txns, key=lambda t: -_amount_of(t)[0])
        shown, withheld = _sample(rows, labels, key=lambda t: -_amount_of(t)[0])
        headline = (
            f"{float(round_ratio or 0) * 100:.1f}% of transfers are round-number amounts - "
            "atypical for organic spending."
        )
        graph_pattern_id = None

    metrics = []
    if near_ratio is not None:
        metrics.append({"label": "Near-threshold share", "value": f"{float(near_ratio) * 100:.1f}%"})
    if round_ratio is not None:
        metrics.append({"label": "Round-number share", "value": f"{float(round_ratio) * 100:.1f}%"})
    if benford is not None:
        metrics.append({"label": "Benford chi-square", "value": f"{float(benford):.2f}"})

    return {
        "id": "abnormal_amounts",
        "severity": "HIGH" if structuring else "MEDIUM",
        "headline": headline,
        "detail": (
            "Amounts cluster where they attract least attention rather than following the "
            "natural digit distribution of genuine spending."
        ),
        "how_computed": (top.get("formula", "") if structuring else
                         "round_number_ratio = round-multiple txns / non-zero txns"),
        "metrics": metrics,
        "transactions": shown,
        "transactions_withheld": withheld,
        "pattern_ids": [p["pattern_id"] for p in structuring],
        "graph_pattern_id": graph_pattern_id,
    }


def _build_connections_reason(
    patterns, txns, labels, features_by_name
) -> Optional[dict[str, Any]]:
    """Counterparties that sit on a detected pattern, ranked by value moved."""
    flagged_ids: set[str] = set()
    pattern_by_cp: dict[str, set[str]] = {}
    for p in patterns:
        for node in p.get("node_path", []):
            if node.get("is_subject"):
                continue
            flagged_ids.add(str(node["id"]))
            pattern_by_cp.setdefault(str(node["id"]), set()).add(p["pattern_id"])

    if not flagged_ids:
        return None

    stats: dict[str, dict[str, Any]] = {}
    for txn in txns:
        cp_id = str(txn.counterparty_id) if txn.counterparty_id is not None else "UNKNOWN"
        if cp_id not in flagged_ids:
            continue
        amount, direction = _amount_of(txn)
        s = stats.setdefault(
            cp_id,
            {"counterparty_id": cp_id, "counterparty": labels.get(cp_id, "Unknown counterparty"),
             "transaction_count": 0, "total_amount": 0.0, "inflow": 0.0, "outflow": 0.0},
        )
        s["transaction_count"] += 1
        s["total_amount"] += amount
        s["inflow" if direction == "credit" else "outflow"] += amount

    if not stats:
        return None

    ranked = sorted(stats.values(), key=lambda s: -s["total_amount"])
    for s in ranked:
        s["total_amount"] = round(s["total_amount"], 2)
        s["inflow"] = round(s["inflow"], 2)
        s["outflow"] = round(s["outflow"], 2)
        s["patterns"] = sorted(pattern_by_cp.get(s["counterparty_id"], set()))

    fan_in = features_by_name.get("fan_in_score", {}).get("value")
    fan_out = features_by_name.get("fan_out_score", {}).get("value")
    hhi = features_by_name.get("counterparty_concentration_hhi", {}).get("value")

    metrics = [{"label": "Flagged counterparties", "value": len(ranked)}]
    if fan_in is not None:
        metrics.append({"label": "Fan-in score", "value": f"{float(fan_in):.2f}"})
    if fan_out is not None:
        metrics.append({"label": "Fan-out score", "value": f"{float(fan_out):.2f}"})
    if hhi is not None:
        metrics.append({"label": "Counterparty HHI", "value": f"{float(hhi):.3f}"})

    top = ranked[0]
    return {
        "id": "high_risk_connections",
        "severity": "HIGH" if len(ranked) >= 3 else "MEDIUM",
        "headline": (
            f"{len(ranked)} counterparties sit on a detected pattern path; "
            f"{top['counterparty']} alone moved {_money(top['total_amount'])} across "
            f"{top['transaction_count']} transfers."
        ),
        "detail": (
            "These accounts are not flagged by name or by any external list - they are "
            "flagged because they appear on this statement's own detected patterns."
        ),
        "how_computed": "counterparties on detected pattern paths, ranked by total value moved",
        "metrics": metrics,
        "counterparties": ranked[:MAX_SAMPLE_TRANSACTIONS],
        "counterparties_withheld": max(0, len(ranked) - MAX_SAMPLE_TRANSACTIONS),
        "transactions": [],
        "transactions_withheld": 0,
        "pattern_ids": sorted({pid for s in ranked for pid in s["patterns"]}),
        "graph_pattern_id": top["patterns"][0] if top["patterns"] else None,
    }


def _build_dormancy_reason(patterns, labels, txn_by_row) -> Optional[dict[str, Any]]:
    bursts = [p for p in patterns if p.get("kind") == "dormancy_burst"]
    if not bursts:
        return None
    top = bursts[0]
    rows = [txn_by_row[r] for r in top.get("row_ids", []) if r in txn_by_row]
    shown, withheld = _sample(rows, labels)
    m = top.get("metrics") or {}
    return {
        "id": "dormancy_burst",
        "severity": top.get("severity", "MEDIUM"),
        "headline": (
            f"The account sat idle for {float(m.get('dormant_days') or 0):.0f} days, then ran "
            f"{int(m.get('burst_transaction_count') or len(rows))} transactions in "
            f"{float(m.get('burst_span_days') or 0):.1f} days."
        ),
        "detail": "Sudden reactivation after dormancy is a common mule-account onboarding signature.",
        "how_computed": top.get("formula", ""),
        "metrics": [
            {"label": "Dormant days", "value": f"{float(m.get('dormant_days') or 0):.0f}"},
            {"label": "Burst transactions", "value": int(m.get("burst_transaction_count") or len(rows))},
            {"label": "Burst window", "value": f"{float(m.get('burst_span_days') or 0):.1f} days"},
        ],
        "transactions": shown,
        "transactions_withheld": withheld,
        "pattern_ids": [p["pattern_id"] for p in bursts],
        "graph_pattern_id": top["pattern_id"],
    }


def _build_statistical_reason(
    anomaly_detail: Optional[dict[str, Any]], features_by_name: dict[str, dict[str, Any]]
) -> Optional[dict[str, Any]]:
    if not anomaly_detail:
        return None
    mad = anomaly_detail.get("mad_flagged_features") or {}
    iso = float(anomaly_detail.get("isolation_forest_score") or 0.0)
    # Nothing deviated and the account is not isolated: this is not a reason for anything.
    # 0.30 is the same auto-clear bar the decision policy applies to the anomaly sub-score.
    if not mad and iso < 0.30:
        return None

    deviations = [
        {
            "name": name,
            "value": value,
            "formula": features_by_name.get(name, {}).get("formula", ""),
            "explanation": features_by_name.get(name, {}).get("explanation", ""),
        }
        for name, value in mad.items()
    ]

    return {
        "id": "statistical_outlier",
        "severity": "HIGH" if len(mad) >= 3 else "MEDIUM",
        "headline": (
            f"{len(mad)} feature(s) fall outside the robust (median absolute deviation) "
            f"baseline; isolation forest places this account in the top "
            f"{iso * 100:.1f}% most isolated."
        ),
        "detail": (
            "Unsupervised check - it does not know the rules, so agreement with the rule "
            "engine is independent corroboration."
        ),
        "how_computed": "robust z = |x - median| / (1.4826 * MAD); flagged when z > 3.5",
        "metrics": [
            {"label": "Flagged features", "value": len(mad)},
            {"label": "Isolation forest", "value": f"{iso * 100:.1f}%"},
        ],
        "deviations": deviations,
        "transactions": [],
        "transactions_withheld": 0,
        "pattern_ids": [],
        "graph_pattern_id": None,
    }


def _confidence(
    bundle: dict[str, Any],
    tier: str,
    fused_score: float,
    rules_fired: bool,
    cycles_found: bool,
    anomaly_flagged: bool,
    supervised: Optional[dict[str, Any]],
) -> dict[str, Any]:
    cfg = load_config("thresholds")
    dec = cfg.get("decision", {})
    t_high = float(dec.get("confirmed_suspicious_min", 75))
    t_low = float(dec.get("likely_legitimate_max", 25))

    guardrail = bundle.get("guardrail_log", {}) or {}
    summary = bundle.get("account_summary", {}) or {}

    extraction_numeric = summary.get("extraction_confidence")
    if not isinstance(extraction_numeric, (int, float)):
        extraction_numeric = guardrail.get("reconciliation_rate")
    if not isinstance(extraction_numeric, (int, float)):
        extraction_numeric = {"high": 0.98, "medium": 0.90, "low": 0.60}.get(
            str(guardrail.get("extraction_confidence", "")).lower(), 0.75
        )
    extraction_quality = min(max(float(extraction_numeric), 0.0), 1.0)

    statement_fit = min(max(float(guardrail.get("ood_score") or 0.0), 0.0), 1.0)

    # How far the score sits from the nearest tier boundary, as a share of the review band.
    if tier == "CONFIRMED_SUSPICIOUS":
        margin = (fused_score - t_high) / max(100.0 - t_high, 1.0)
    elif tier == "LIKELY_LEGITIMATE":
        margin = (t_low - fused_score) / max(t_low, 1.0)
    else:
        nearest = min(abs(fused_score - t_high), abs(fused_score - t_low))
        margin = nearest / max((t_high - t_low) / 2.0, 1.0)
    decision_margin = min(max(margin, 0.0), 1.0)

    suspicious = tier != "LIKELY_LEGITIMATE"
    families = {
        "Deterministic rules": rules_fired,
        "Graph cycle detection": cycles_found,
        "Statistical anomaly": anomaly_flagged,
    }
    if supervised:
        prob = supervised.get("calibrated_probability")
        families["Supervised model"] = bool(prob is not None and float(prob) >= 0.5)
    agreeing = sum(1 for fired in families.values() if fired == suspicious)
    corroboration = agreeing / len(families)

    score = 100 * (
        0.35 * extraction_quality
        + 0.25 * statement_fit
        + 0.25 * decision_margin
        + 0.15 * corroboration
    )

    return {
        "score": round(score, 1),
        "formula": CONFIDENCE_FORMULA,
        "components": [
            {
                "name": "Extraction quality",
                "value": round(extraction_quality, 4),
                "weight": 0.35,
                "description": "Share of rows that reconciled against the running balance.",
            },
            {
                "name": "Statement fit",
                "value": round(statement_fit, 4),
                "weight": 0.25,
                "description": "How closely the upload matches a known bank-statement shape.",
            },
            {
                "name": "Decision margin",
                "value": round(decision_margin, 4),
                "weight": 0.25,
                "description": f"Distance of {fused_score:.1f} from the nearest tier boundary "
                               f"({t_low:.0f} / {t_high:.0f}).",
            },
            {
                "name": "Signal corroboration",
                "value": round(corroboration, 4),
                "weight": 0.15,
                "description": f"{agreeing} of {len(families)} independent detectors agree with "
                               f"the {tier.replace('_', ' ').lower()} call.",
            },
        ],
        "detector_agreement": [
            {"detector": name, "flagged": fired, "agrees": fired == suspicious}
            for name, fired in families.items()
        ],
    }


def build_why_flagged(
    statement_id: int,
    bundle: dict[str, Any],
    patterns: list[dict[str, Any]],
    txns: list[Any],
    node_labels: dict[str, str],
) -> dict[str, Any]:
    """Assemble the ranked, evidence-backed answer to "why was this flagged?"."""
    cfg = load_config("thresholds")
    rules_cfg = cfg.get("rules", {}) or {}
    fusion_cfg = cfg.get("fusion", {}) or {}
    dec = cfg.get("decision", {}) or {}

    decision = bundle.get("final_decision", {}) or {}
    features = bundle.get("features", []) or []
    triggered = bundle.get("triggered_rules", []) or []
    cycles = bundle.get("cycles_detected", []) or []
    anomaly_detail = bundle.get("anomaly_detail")
    supervised = bundle.get("supervised_detail")

    features_by_name = {f.get("name"): f for f in features if f.get("name")}
    feature_values = {
        name: float(f["value"])
        for name, f in features_by_name.items()
        if isinstance(f.get("value"), (int, float))
    }
    # Injected at scoring time, so it is absent from the stored feature list.
    if cycles:
        feature_values["max_cycle_risk_score"] = max(
            float(c.get("cycle_risk_score") or 0.0) for c in cycles
        )

    txn_by_row = {t.row_id: t for t in txns}

    fused_score = float(decision.get("fused_score") or 0.0)
    rule_score = float(decision.get("rule_score") or 0.0)
    anomaly_score = float(decision.get("anomaly_score") or 0.0)
    tier = decision.get("tier") or "REVIEW_REQUIRED"

    # Score composition, using the same weights the fusion step applied.
    if supervised and supervised.get("calibrated_probability") is not None:
        weights = fusion_cfg.get("supervised_available", {})
        w_rule = float(weights.get("rule_score", 0.40))
        w_anomaly = float(weights.get("anomaly_score", 0.25))
        w_sup = float(weights.get("supervised_probability", 0.35))
    else:
        weights = fusion_cfg.get("supervised_unavailable", {})
        w_rule = float(weights.get("rule_score", 0.65))
        w_anomaly = float(weights.get("anomaly_score", 0.35))
        w_sup = 0.0

    rule_component = w_rule * min(rule_score / 100.0, 1.0) * 100
    anomaly_component = w_anomaly * min(anomaly_score, 1.0) * 100
    supervised_component = (
        w_sup * min(float(supervised.get("calibrated_probability") or 0.0), 1.0) * 100
        if w_sup else 0.0
    )
    total_component = rule_component + anomaly_component + supervised_component or 1.0

    score_breakdown = [
        {"component": "Deterministic rules", "weight": w_rule, "raw_value": rule_score,
         "points_of_fused": round(rule_component, 1)},
        {"component": "Statistical anomaly", "weight": w_anomaly, "raw_value": round(anomaly_score, 4),
         "points_of_fused": round(anomaly_component, 1)},
    ]
    if w_sup:
        score_breakdown.append({
            "component": "Supervised model", "weight": w_sup,
            "raw_value": supervised.get("calibrated_probability"),
            "points_of_fused": round(supervised_component, 1),
        })

    # Rule evidence, keyed by the reason it belongs to.
    total_points = sum(float(r.get("points") or 0) for r in triggered) or 1.0
    rule_evidence: dict[str, list[dict[str, Any]]] = {}
    feature_thresholds: dict[str, dict[str, Any]] = {}
    for rule in triggered:
        rule_id = rule.get("id", "")
        condition = rule.get("condition") or rules_cfg.get(rule_id, {}).get("condition", "")
        points = float(rule.get("points") or 0)
        parsed = parse_condition_clauses(condition, feature_values)
        for clause in parsed["clauses"]:
            if clause.get("field"):
                feature_thresholds[clause["field"]] = {
                    "threshold_value": clause.get("threshold_value"),
                    "operator": clause.get("operator"),
                    "rule_id": rule_id,
                }
        entry = {
            "id": rule_id,
            "description": rule.get("description", "") or rules_cfg.get(rule_id, {}).get("description", ""),
            "condition": condition,
            "points": points,
            "joiner": parsed["joiner"],
            "clauses": parsed["clauses"],
            "contribution_pct": round(
                (points / total_points) * rule_component / total_component * 100, 1
            ),
        }
        rule_evidence.setdefault(RULE_TO_REASON.get(rule_id, rule_id), []).append(entry)

    # Candidate reasons, each built only when real evidence exists for it.
    candidates = [
        _build_circular_reason(patterns, cycles, node_labels, txn_by_row),
        _build_velocity_reason(patterns, txns, node_labels, features_by_name, txn_by_row),
        _build_amount_reason(patterns, txns, node_labels, features_by_name, txn_by_row),
        _build_connections_reason(patterns, txns, node_labels, features_by_name),
        _build_dormancy_reason(patterns, node_labels, txn_by_row),
        _build_statistical_reason(anomaly_detail, features_by_name),
    ]

    reason_feature_map = {
        # max_cycle_risk_score is injected at scoring time and added explicitly below.
        "circular_flow": [],
        "high_velocity": ["inflow_outflow_velocity", "net_retention_ratio", "turnover_ratio",
                          "median_holding_time_hours"],
        "abnormal_amounts": ["near_threshold_ratio", "round_number_ratio", "benford_deviation_score"],
        "high_risk_connections": ["fan_in_score", "fan_out_score", "counterparty_concentration_hhi"],
        "dormancy_burst": ["dormancy_breaks", "first_week_activity_ratio"],
        "statistical_outlier": [],
    }

    reasons: list[dict[str, Any]] = []
    for reason in candidates:
        if reason is None:
            continue
        rid = reason["id"]
        rules_for_reason = rule_evidence.pop(rid, [])
        contribution = round(sum(r["contribution_pct"] for r in rules_for_reason), 1)
        if rid == "statistical_outlier":
            contribution = round(anomaly_component / total_component * 100, 1)

        reason.update({
            "title": REASON_TITLES.get(rid, rid),
            "category": REASON_CATEGORIES.get(rid, "other"),
            "rules": rules_for_reason,
            "rule_points": sum(r["points"] for r in rules_for_reason),
            "contribution_pct": contribution,
            "is_score_driver": contribution > 0,
            "features": _feature_evidence(
                features_by_name, reason_feature_map.get(rid, []), feature_thresholds
            ),
        })
        if rid == "circular_flow" and "max_cycle_risk_score" in feature_values:
            reason["features"].insert(0, {
                "name": "max_cycle_risk_score",
                "value": round(feature_values["max_cycle_risk_score"], 4),
                "formula": "max(cycle_risk_score) across detected cycles",
                "explanation": "Highest-risk circular flow found",
                "family": "graph",
                **({k: v for k, v in feature_thresholds.get("max_cycle_risk_score", {}).items()}),
            })
        if rules_for_reason:
            reason["severity"] = max(
                [reason["severity"]] + [_severity_from_points(r["points"]) for r in rules_for_reason],
                key=lambda s: SEVERITY_RANK.get(s, 0),
            )
        reasons.append(reason)

    # Any triggered rule without a named reason still gets its own entry.
    for rid, entries in rule_evidence.items():
        top_rule = max(entries, key=lambda r: r["points"])
        clause_text = f" {entries[0]['joiner']} ".join(
            c["expression"] for c in top_rule["clauses"]
        )
        reasons.append({
            "id": rid,
            "title": top_rule["description"] or rid.replace("_", " ").capitalize(),
            "category": "rule",
            "severity": _severity_from_points(top_rule["points"]),
            "headline": f"Rule {rid} fired: {clause_text}.",
            "detail": top_rule["description"],
            "how_computed": top_rule["condition"],
            "metrics": [{"label": "Rule points", "value": f"+{top_rule['points']:.0f}"}],
            "rules": entries,
            "rule_points": sum(r["points"] for r in entries),
            "contribution_pct": round(sum(r["contribution_pct"] for r in entries), 1),
            "is_score_driver": True,
            "features": [],
            "transactions": [],
            "transactions_withheld": 0,
            "pattern_ids": [],
            "graph_pattern_id": None,
        })

    reasons.sort(
        key=lambda r: (r["contribution_pct"], SEVERITY_RANK.get(r["severity"], 0)), reverse=True
    )

    confidence = _confidence(
        bundle=bundle,
        tier=tier,
        fused_score=fused_score,
        rules_fired=bool(triggered),
        cycles_found=bool(cycles),
        anomaly_flagged=bool((anomaly_detail or {}).get("mad_flagged_features")),
        supervised=supervised,
    )

    t_high = float(dec.get("confirmed_suspicious_min", 75))
    t_low = float(dec.get("likely_legitimate_max", 25))
    if tier == "CONFIRMED_SUSPICIOUS":
        risk_level, emoji = "HIGH", "🔴"
    elif tier == "LIKELY_LEGITIMATE":
        risk_level, emoji = "LOW", "🟢"
    else:
        risk_level, emoji = "MEDIUM", "🟠"

    return {
        "statement_id": statement_id,
        "tier": tier,
        "risk_score": round(fused_score, 1),
        "risk_level": risk_level,
        "risk_level_emoji": emoji,
        "thresholds": {"likely_legitimate_max": t_low, "confirmed_suspicious_min": t_high},
        "decision_reason": decision.get("decision_reason", ""),
        "score_formula": decision.get("score_formula_used", ""),
        "score_breakdown": score_breakdown,
        "confidence": confidence,
        "reasons": reasons,
        "evidence_coverage": {
            "transactions_examined": len(txns),
            "counterparties_seen": len({t.counterparty_id for t in txns if t.counterparty_id}),
            "patterns_detected": len(patterns),
            "rules_evaluated": len(rules_cfg),
            "rules_triggered": len(triggered),
            "features_computed": len(features),
        },
    }
