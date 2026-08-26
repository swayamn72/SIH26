"""Suspicious-pattern timelines.

Converts deterministic detector output (cycles, near-threshold structuring,
rapid pass-through layering, dormancy bursts) into ordered hop-by-hop
timelines - ACCOUNT A -> ACCOUNT B -> ACCOUNT C -> ACCOUNT A - that the UI
renders as an evidence timeline and deep-links into the proof graph.

Every pattern carries the formula used to derive its risk score so the
timeline stays as auditable as the rest of the evidence bundle.
"""

from datetime import date, datetime, time
from typing import Any, Optional

from app.config_loader import load_config

SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

HOP_RISK_FORMULA = (
    "hop_risk = min(1, pattern_risk + 0.10*near_threshold + 0.05*rapid_hop)"
)


def _defaults() -> dict[str, Any]:
    cfg = load_config("thresholds")
    pt = cfg.get("pattern_timeline", {}) or {}
    return {
        "layering_max_hold_days": pt.get("layering_max_hold_days", 1),
        "layering_min_amount_match": pt.get("layering_min_amount_match", 0.6),
        "max_layering_chains": pt.get("max_layering_chains", 10),
        "structuring_min_transactions": pt.get("structuring_min_transactions", 2),
        "min_pattern_risk": pt.get("min_pattern_risk", 0.5),
        "max_patterns": pt.get("max_patterns", 25),
        "rapid_hop_hours": pt.get("rapid_hop_hours", 24),
        "near_threshold_bands": (cfg.get("structuring", {}) or {}).get(
            "near_threshold_bands", [{"threshold": 50000, "lower_pct": 0.90}]
        ),
        "dormancy": cfg.get("dormancy", {}) or {},
    }


def severity_from_risk(risk: float) -> str:
    if risk >= 0.85:
        return "CRITICAL"
    if risk >= 0.70:
        return "HIGH"
    if risk >= 0.50:
        return "MEDIUM"
    return "LOW"


def severity_from_points(points: float) -> str:
    if points >= 25:
        return "CRITICAL"
    if points >= 20:
        return "HIGH"
    if points >= 15:
        return "MEDIUM"
    return "LOW"


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


def _iso(value: Any) -> Optional[str]:
    dt = _as_datetime(value)
    return dt.isoformat() if dt else None


def _band_for(amount: float, bands: list[dict]) -> Optional[dict]:
    """Return the near-threshold band an amount falls inside, if any."""
    for band in bands:
        threshold = float(band.get("threshold", 50000))
        lower_pct = float(band.get("lower_pct", 0.90))
        if threshold * lower_pct <= amount <= threshold:
            return {"threshold": threshold, "lower_pct": lower_pct}
    return None


def _amount_of(txn: Any) -> tuple[float, str]:
    """Return (amount, direction) for a transaction row."""
    debit = float(txn.debit_amount or 0.0)
    credit = float(txn.credit_amount or 0.0)
    if debit >= credit and debit > 0:
        return debit, "debit"
    if credit > 0:
        return credit, "credit"
    return 0.0, "debit" if debit > 0 else "credit"


def _counterparty_node(txn: Any, labels: dict[str, str]) -> tuple[str, str]:
    cp_id = str(txn.counterparty_id) if txn.counterparty_id is not None else "UNKNOWN"
    fallback = "Unknown counterparty" if cp_id == "UNKNOWN" else cp_id
    return cp_id, labels.get(cp_id, fallback)


def _build_hop(
    txn: Any,
    step: int,
    subject_id: str,
    subject_label: str,
    labels: dict[str, str],
    bands: list[dict],
    prev_dt: Optional[datetime],
    rapid_hop_hours: float,
    pattern_risk: float,
) -> dict[str, Any]:
    amount, direction = _amount_of(txn)
    cp_id, cp_label = _counterparty_node(txn, labels)

    if direction == "debit":
        from_id, from_label, to_id, to_label = subject_id, subject_label, cp_id, cp_label
    else:
        from_id, from_label, to_id, to_label = cp_id, cp_label, subject_id, subject_label

    dt = _as_datetime(txn.txn_date)
    gap_hours: Optional[float] = None
    if dt and prev_dt:
        gap_hours = round((dt - prev_dt).total_seconds() / 3600.0, 2)

    band = _band_for(amount, bands)
    is_rapid = gap_hours is not None and gap_hours <= rapid_hop_hours
    hop_risk = min(1.0, pattern_risk + (0.10 if band else 0.0) + (0.05 if is_rapid else 0.0))

    return {
        "step": step,
        "row_id": txn.row_id,
        "txn_id": txn.reference_no or txn.row_id,
        "timestamp": _iso(txn.txn_date),
        "value_date": _iso(txn.value_date),
        "from_id": from_id,
        "from_label": from_label,
        "to_id": to_id,
        "to_label": to_label,
        "direction": direction,
        "amount": round(amount, 2),
        "channel": txn.channel or "",
        "narration": txn.narration or "",
        "gap_hours": gap_hours,
        "near_threshold": bool(band),
        "near_threshold_band": band.get("threshold") if band else None,
        "is_rapid": bool(is_rapid),
        "risk_score": round(hop_risk, 4),
        "severity": severity_from_risk(hop_risk),
    }


def _finalize(
    pattern: dict[str, Any],
    hops: list[dict[str, Any]],
    node_path: list[dict[str, Any]],
) -> dict[str, Any]:
    stamps = [_as_datetime(h["timestamp"]) for h in hops]
    stamps = [s for s in stamps if s]
    total_amount = round(sum(float(h["amount"]) for h in hops), 2)
    span_days = (
        round((max(stamps) - min(stamps)).total_seconds() / 86400.0, 2) if len(stamps) > 1 else 0.0
    )

    pattern.update(
        {
            "hops": hops,
            "hop_count": len(hops),
            "node_path": node_path,
            "row_ids": [h["row_id"] for h in hops],
            "node_ids": sorted({n["id"] for n in node_path}),
            "total_amount": total_amount,
            "span_days": span_days,
            "started_at": _iso(min(stamps)) if stamps else None,
            "ended_at": _iso(max(stamps)) if stamps else None,
            "hop_risk_formula": HOP_RISK_FORMULA,
            "severity": severity_from_risk(pattern["risk_score"]),
        }
    )
    return pattern


def _node_entry(
    node_id: str, labels: dict[str, str], subject_id: str, subject_label: str
) -> dict[str, Any]:
    if node_id == subject_id:
        return {"id": subject_id, "label": subject_label, "is_subject": True}
    return {"id": node_id, "label": labels.get(node_id, node_id), "is_subject": False}


def _cycle_patterns(
    cycles: list[dict[str, Any]],
    txn_by_row: dict[str, Any],
    subject_id: str,
    subject_label: str,
    labels: dict[str, str],
    opts: dict[str, Any],
) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    for cycle in cycles:
        rows = [txn_by_row[r] for r in cycle.get("contributing_row_ids", []) if r in txn_by_row]
        if not rows:
            continue
        rows.sort(key=lambda t: (_as_datetime(t.txn_date) or datetime.min, t.row_id))

        risk = float(cycle.get("cycle_risk_score") or 0.0)
        hops: list[dict[str, Any]] = []
        prev_dt: Optional[datetime] = None
        for idx, txn in enumerate(rows, start=1):
            hops.append(
                _build_hop(
                    txn, idx, subject_id, subject_label, labels,
                    opts["near_threshold_bands"], prev_dt, opts["rapid_hop_hours"], risk,
                )
            )
            prev_dt = _as_datetime(txn.txn_date)

        seq = [str(n) for n in cycle.get("nodes", [])]
        node_path = [_node_entry(n, labels, subject_id, subject_label) for n in seq]
        if node_path:
            # Close the loop so the UI renders A -> B -> C -> A.
            node_path.append({**node_path[0], "is_return": True})

        conservation = round(float(cycle.get("amount_conservation_ratio") or 0.0) * 100)
        patterns.append(
            _finalize(
                {
                    "pattern_id": "CYC_{}".format(cycle.get("cycle_id", len(patterns))),
                    "kind": "cycle",
                    "title": "{}-hop circular fund flow".format(cycle.get("hop_count", len(seq))),
                    "summary": (
                        "Funds returned to the originating account across "
                        "{} hops in {} days with {}% amount conservation.".format(
                            cycle.get("hop_count", len(seq)),
                            cycle.get("cycle_span_days", 0),
                            conservation,
                        )
                    ),
                    "formula": (
                        "cycle_risk = 0.35*amount_conservation + 0.30*velocity_compression "
                        "+ 0.20*cycle_recurrence + 0.15*inverse_hop_count"
                    ),
                    "risk_score": round(risk, 4),
                    "linked_rule_ids": ["R5_circular_flow_detected"],
                    "metrics": {
                        "amount_conservation_ratio": cycle.get("amount_conservation_ratio"),
                        "velocity_compression": cycle.get("velocity_compression"),
                        "cycle_recurrence": cycle.get("cycle_recurrence"),
                        "cycle_span_days": cycle.get("cycle_span_days"),
                    },
                },
                hops,
                node_path,
            )
        )
    return patterns


def _layering_patterns(
    txns: list[Any],
    subject_id: str,
    subject_label: str,
    labels: dict[str, str],
    opts: dict[str, Any],
) -> list[dict[str, Any]]:
    """Credit in -> debit out inside the holding window: a pass-through chain A -> B -> C."""
    max_hold_days = float(opts["layering_max_hold_days"])
    min_match = float(opts["layering_min_amount_match"])
    # Largest configured reporting threshold doubles as the materiality reference, so a
    # tiny same-day round-trip cannot outrank a large one purely on speed.
    materiality_ref = max(
        (float(b.get("threshold", 0)) for b in opts["near_threshold_bands"]), default=200000.0
    ) or 200000.0

    ordered = sorted(txns, key=lambda t: (_as_datetime(t.txn_date) or datetime.min, t.row_id))
    credits = [t for t in ordered if float(t.credit_amount or 0.0) > 0]
    debits = [t for t in ordered if float(t.debit_amount or 0.0) > 0]

    used_debits: set[str] = set()
    patterns: list[dict[str, Any]] = []

    for credit in credits:
        c_dt = _as_datetime(credit.txn_date)
        if c_dt is None:
            continue
        c_amt = float(credit.credit_amount or 0.0)

        for debit in debits:
            if debit.row_id in used_debits:
                continue
            d_dt = _as_datetime(debit.txn_date)
            if d_dt is None or d_dt < c_dt:
                continue
            hold_days = (d_dt - c_dt).total_seconds() / 86400.0
            if hold_days > max_hold_days:
                break

            d_amt = float(debit.debit_amount or 0.0)
            largest = max(c_amt, d_amt)
            amount_match = min(c_amt, d_amt) / largest if largest > 0 else 0.0
            if amount_match < min_match:
                continue

            speed = max(1.0 - (hold_days / max_hold_days if max_hold_days > 0 else 0.0), 0.0)
            materiality = min(largest / materiality_ref, 1.0)
            risk = (0.5 * amount_match + 0.5 * speed) * (0.6 + 0.4 * materiality)
            used_debits.add(debit.row_id)

            hops: list[dict[str, Any]] = []
            prev_dt: Optional[datetime] = None
            for idx, txn in enumerate((credit, debit), start=1):
                hops.append(
                    _build_hop(
                        txn, idx, subject_id, subject_label, labels,
                        opts["near_threshold_bands"], prev_dt, opts["rapid_hop_hours"], risk,
                    )
                )
                prev_dt = _as_datetime(txn.txn_date)

            source_id, source_label = _counterparty_node(credit, labels)
            dest_id, dest_label = _counterparty_node(debit, labels)
            node_path = [
                {"id": source_id, "label": source_label, "is_subject": False},
                {"id": subject_id, "label": subject_label, "is_subject": True},
                {"id": dest_id, "label": dest_label, "is_subject": False},
            ]

            patterns.append(
                _finalize(
                    {
                        "pattern_id": "LAY_{}_{}".format(credit.row_id, debit.row_id),
                        "kind": "layering",
                        "title": "Rapid pass-through (layering) chain",
                        "summary": (
                            "₹{:,.2f} received from {} left the account for {} within "
                            "{:.2f} days at {:.0f}% amount match.".format(
                                c_amt, source_label, dest_label, hold_days, amount_match * 100
                            )
                        ),
                        "formula": (
                            "layering_risk = (0.5*amount_match + 0.5*(1 - hold_days/max_hold_days)) "
                            "* (0.6 + 0.4*min(amount/materiality_ref, 1))"
                        ),
                        "risk_score": round(risk, 4),
                        "linked_rule_ids": ["R1_low_retention_high_turnover"],
                        "metrics": {
                            "amount_match": round(amount_match, 4),
                            "hold_days": round(hold_days, 4),
                            "inflow": round(c_amt, 2),
                            "outflow": round(d_amt, 2),
                            "materiality_ref": materiality_ref,
                        },
                    },
                    hops,
                    node_path,
                )
            )
            break

    # Keep the strongest chains; a busy account can produce hundreds of same-day pairs.
    patterns.sort(key=lambda p: (p["risk_score"], p["total_amount"]), reverse=True)
    max_chains = int(opts["max_layering_chains"])
    if len(patterns) > max_chains:
        dropped = len(patterns) - max_chains
        patterns = patterns[:max_chains]
        for p in patterns:
            p["truncation_note"] = (
                f"{dropped} lower-risk pass-through chain(s) not shown "
                f"(top {max_chains} by risk retained)."
            )
    return patterns


def _structuring_patterns(
    txns: list[Any],
    subject_id: str,
    subject_label: str,
    labels: dict[str, str],
    opts: dict[str, Any],
) -> list[dict[str, Any]]:
    """Repeated transfers parked just under a reporting threshold."""
    bands = opts["near_threshold_bands"]
    min_txns = int(opts["structuring_min_transactions"])

    grouped: dict[float, list[Any]] = {}
    for txn in txns:
        amount, _ = _amount_of(txn)
        band = _band_for(amount, bands)
        if band:
            grouped.setdefault(band["threshold"], []).append(txn)

    patterns: list[dict[str, Any]] = []
    for threshold, rows in grouped.items():
        if len(rows) < min_txns:
            continue
        rows.sort(key=lambda t: (_as_datetime(t.txn_date) or datetime.min, t.row_id))

        lower_pct = next(
            (
                float(b.get("lower_pct", 0.90))
                for b in bands
                if float(b.get("threshold", 0)) == threshold
            ),
            0.90,
        )
        amounts = [_amount_of(t)[0] for t in rows]
        mean_proximity = sum(a / threshold for a in amounts) / len(amounts)
        proximity_norm = (mean_proximity - lower_pct) / (1 - lower_pct) if lower_pct < 1 else 1.0
        proximity_norm = min(max(proximity_norm, 0.0), 1.0)
        count_norm = min(len(rows) / 5.0, 1.0)
        risk = 0.5 * count_norm + 0.5 * proximity_norm

        hops: list[dict[str, Any]] = []
        prev_dt: Optional[datetime] = None
        for idx, txn in enumerate(rows, start=1):
            hops.append(
                _build_hop(
                    txn, idx, subject_id, subject_label, labels,
                    bands, prev_dt, opts["rapid_hop_hours"], risk,
                )
            )
            prev_dt = _as_datetime(txn.txn_date)

        node_path = [{"id": subject_id, "label": subject_label, "is_subject": True}]
        seen = {subject_id}
        for txn in rows:
            cp_id, cp_label = _counterparty_node(txn, labels)
            if cp_id not in seen:
                seen.add(cp_id)
                node_path.append({"id": cp_id, "label": cp_label, "is_subject": False})

        patterns.append(
            _finalize(
                {
                    "pattern_id": "STR_{}".format(int(threshold)),
                    "kind": "structuring",
                    "title": "Structuring below the ₹{:,.0f} reporting threshold".format(threshold),
                    "summary": (
                        "{} transfers sit inside the {:.0f}%-100% band of the ₹{:,.0f} "
                        "threshold (mean proximity {:.1f}%).".format(
                            len(rows), lower_pct * 100, threshold, mean_proximity * 100
                        )
                    ),
                    "formula": (
                        "structuring_risk = 0.5*min(txn_count/5, 1) "
                        "+ 0.5*((mean(amount/threshold) - lower_pct) / (1 - lower_pct))"
                    ),
                    "risk_score": round(risk, 4),
                    "linked_rule_ids": ["R3_structuring_near_threshold"],
                    "metrics": {
                        "threshold": threshold,
                        "transaction_count": len(rows),
                        "mean_proximity": round(mean_proximity, 4),
                    },
                },
                hops,
                node_path,
            )
        )
    return patterns


def _dormancy_patterns(
    txns: list[Any],
    subject_id: str,
    subject_label: str,
    labels: dict[str, str],
    opts: dict[str, Any],
) -> list[dict[str, Any]]:
    """A quiet period longer than gap_days followed by a burst of activity."""
    d = opts["dormancy"]
    gap_days = float(d.get("gap_days", 30))
    burst_min = int(d.get("burst_min_transactions", 3))
    burst_window = float(d.get("burst_window_days", 3))

    ordered = [t for t in txns if _as_datetime(t.txn_date)]
    ordered.sort(key=lambda t: (_as_datetime(t.txn_date), t.row_id))
    if len(ordered) < 2:
        return []

    patterns: list[dict[str, Any]] = []
    i = 0
    while i < len(ordered) - 1:
        cur_dt = _as_datetime(ordered[i].txn_date)
        nxt_dt = _as_datetime(ordered[i + 1].txn_date)
        gap = (nxt_dt - cur_dt).total_seconds() / 86400.0
        if gap <= gap_days:
            i += 1
            continue

        burst_start = i + 1
        burst_end = burst_start
        start_dt = _as_datetime(ordered[burst_start].txn_date)
        while burst_end < len(ordered):
            span = (_as_datetime(ordered[burst_end].txn_date) - start_dt).total_seconds() / 86400.0
            if span > burst_window:
                break
            burst_end += 1

        rows = ordered[burst_start:burst_end]
        if len(rows) >= burst_min:
            burst_span = (
                (_as_datetime(rows[-1].txn_date) - start_dt).total_seconds() / 86400.0
                if len(rows) > 1
                else 0.0
            )
            dormancy_norm = min(gap / (gap_days * 3), 1.0)
            burst_norm = min(len(rows) / (burst_min * 2), 1.0)
            risk = 0.5 * dormancy_norm + 0.5 * burst_norm

            hops: list[dict[str, Any]] = []
            prev_dt: Optional[datetime] = None
            for idx, txn in enumerate(rows, start=1):
                hops.append(
                    _build_hop(
                        txn, idx, subject_id, subject_label, labels,
                        opts["near_threshold_bands"], prev_dt, opts["rapid_hop_hours"], risk,
                    )
                )
                prev_dt = _as_datetime(txn.txn_date)

            node_path = [{"id": subject_id, "label": subject_label, "is_subject": True}]
            seen = {subject_id}
            for txn in rows:
                cp_id, cp_label = _counterparty_node(txn, labels)
                if cp_id not in seen:
                    seen.add(cp_id)
                    node_path.append({"id": cp_id, "label": cp_label, "is_subject": False})

            patterns.append(
                _finalize(
                    {
                        "pattern_id": "DOR_{}".format(rows[0].row_id),
                        "kind": "dormancy_burst",
                        "title": "Dormancy followed by activity burst",
                        "summary": (
                            "{:.0f} dormant days ended with {} transactions inside "
                            "{:.1f} days.".format(gap, len(rows), burst_span)
                        ),
                        "formula": (
                            "dormancy_risk = 0.5*min(gap_days_observed / (3*gap_days), 1) "
                            "+ 0.5*min(burst_txn_count / (2*burst_min), 1)"
                        ),
                        "risk_score": round(risk, 4),
                        "linked_rule_ids": ["R2_dormancy_then_burst"],
                        "metrics": {
                            "dormant_days": round(gap, 2),
                            "burst_transaction_count": len(rows),
                            "burst_span_days": round(burst_span, 2),
                        },
                    },
                    hops,
                    node_path,
                )
            )
        i = burst_end

    return patterns


def build_patterns(
    statement_id: int,
    txns: list[Any],
    cycles: list[dict[str, Any]],
    triggered_rules: list[dict[str, Any]],
    node_labels: dict[str, str],
    subject_label: str = "Subject Account",
) -> list[dict[str, Any]]:
    """Assemble every suspicious pattern that has a row-level timeline."""
    opts = _defaults()
    subject_id = "ACCT_{}".format(statement_id)
    txn_by_row = {t.row_id: t for t in txns}
    rule_points = {r.get("id", ""): float(r.get("points", 0) or 0) for r in triggered_rules}

    patterns: list[dict[str, Any]] = []
    patterns += _cycle_patterns(cycles, txn_by_row, subject_id, subject_label, node_labels, opts)
    patterns += _layering_patterns(txns, subject_id, subject_label, node_labels, opts)
    patterns += _structuring_patterns(txns, subject_id, subject_label, node_labels, opts)
    patterns += _dormancy_patterns(txns, subject_id, subject_label, node_labels, opts)

    min_risk = float(opts["min_pattern_risk"])
    kept: list[dict[str, Any]] = []
    for p in patterns:
        linked = [r for r in p.get("linked_rule_ids", []) if r in rule_points]
        p["linked_rule_ids"] = linked
        p["rule_points"] = sum(rule_points[r] for r in linked)
        # A pattern whose rule actually fired is evidence regardless of its own score.
        if p["risk_score"] >= min_risk or linked:
            kept.append(p)

    kept.sort(
        key=lambda p: (SEVERITY_RANK.get(p["severity"], 0), p["risk_score"], p["total_amount"]),
        reverse=True,
    )
    return kept[: int(opts["max_patterns"])]
