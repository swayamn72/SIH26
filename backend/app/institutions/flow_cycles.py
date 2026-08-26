"""Circular fund-flow detection for interbank ledgers.

Why not `graph.cycle_detector` here: that module enumerates every simple cycle in
each strongly-connected component, which is correct for a statement graph (a star
around one account, so components stay tiny) but combinatorially hopeless on a
connected transfer network — a few hundred accounts with ordinary traffic contain
millions of simple cycles, and almost none of them are laundering.

A laundering loop has three properties ordinary traffic does not: it returns to
its origin, it does so quickly, and the amount survives each hop nearly intact.
So instead of enumerating structure, this walks *forward in time* from each
transfer and keeps only paths where value is conserved — which prunes the search
to a handful of branches per seed and finds rings rather than noise.
"""

from typing import Any, Optional

from app.config_loader import load_config


def _weights() -> dict[str, float]:
    cfg = load_config("thresholds")
    w = cfg.get("cycle_risk_weights", {}) or {}
    return {
        "amount_conservation": float(w.get("amount_conservation", 0.35)),
        "velocity_compression": float(w.get("velocity_compression", 0.30)),
        "cycle_recurrence": float(w.get("cycle_recurrence", 0.20)),
        "inverse_hop_count": float(w.get("inverse_hop_count", 0.15)),
    }


def _settings() -> dict[str, Any]:
    cfg = load_config("thresholds")
    fc = (cfg.get("bank_intelligence", {}) or {}).get("flow_cycles", {}) or {}
    return {
        "max_hops": int(fc.get("max_hops", 6)),
        # A 2-hop loop is a payment and its refund — common and usually benign.
        # A ring worth investigating routes through at least one intermediary.
        "min_hops": int(fc.get("min_hops", 3)),
        "window_days": float(fc.get("window_days", 10)),
        "amount_tolerance": float(fc.get("amount_tolerance", 0.25)),
        "min_amount_percentile": float(fc.get("min_amount_percentile", 0.6)),
        "max_cycles": int(fc.get("max_cycles", 250)),
        "max_expansions": int(fc.get("max_expansions", 400_000)),
        "min_risk_score": float(fc.get("min_risk_score", 0.5)),
    }


def _score(
    amounts: list[float], span_days: float, hop_count: int, recurrence: int, weights: dict[str, float]
) -> dict[str, float]:
    """Same four-factor shape the statement-level cycle score uses."""
    import statistics

    if amounts:
        mean_amt = statistics.mean(amounts)
        cv = statistics.stdev(amounts) / mean_amt if mean_amt > 0 and len(amounts) > 1 else 0.0
        conservation = max(0.0, 1.0 - cv)
    else:
        conservation = 0.0

    span = max(span_days, 0.01)
    velocity = min((hop_count / span) / 10.0, 1.0)
    recurrence_norm = min(recurrence / 3.0, 1.0)
    inverse_hops = 1.0 / max(hop_count, 1)

    risk = (
        weights["amount_conservation"] * conservation
        + weights["velocity_compression"] * velocity
        + weights["cycle_recurrence"] * recurrence_norm
        + weights["inverse_hop_count"] * inverse_hops
    )

    return {
        "amount_conservation_ratio": round(conservation, 4),
        "velocity_compression": round((hop_count / span), 4),
        "cycle_recurrence": round(recurrence_norm, 4),
        "cycle_risk_score": round(min(risk, 1.0), 4),
    }


def find_conserved_cycles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find amount-conserving loops that return to their originating account.

    Each row needs: from_account, to_account, from_bank, to_bank, amount, ts_seconds.
    Returns cycles ordered by risk, each carrying the transfer indices that formed it.
    """
    opts = _settings()
    weights = _weights()

    usable = [
        (i, r)
        for i, r in enumerate(rows)
        if r.get("from_account") and r.get("to_account") and r.get("ts_seconds") is not None
    ]
    if len(usable) < 2:
        return []

    amounts_sorted = sorted(r["amount"] for _, r in usable)
    idx = int(len(amounts_sorted) * opts["min_amount_percentile"])
    min_amount = amounts_sorted[min(idx, len(amounts_sorted) - 1)]

    # Outgoing transfers per account, in time order — the walk only ever moves forward.
    outgoing: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for i, r in usable:
        outgoing.setdefault(r["from_account"], []).append((i, r))
    for edges in outgoing.values():
        edges.sort(key=lambda pair: pair[1]["ts_seconds"])

    window_seconds = opts["window_days"] * 86400.0
    tolerance = opts["amount_tolerance"]
    max_hops = opts["max_hops"]

    expansions = 0
    found: dict[tuple, dict[str, Any]] = {}

    def within_tolerance(amount: float, principal: float) -> bool:
        if principal <= 0:
            return False
        return abs(amount - principal) / principal <= tolerance

    for seed_idx, seed in usable:
        if len(found) >= opts["max_cycles"] or expansions >= opts["max_expansions"]:
            break
        if seed["amount"] < min_amount:
            continue

        origin = seed["from_account"]
        principal = seed["amount"]
        deadline = seed["ts_seconds"] + window_seconds

        # Iterative DFS: (current account, last timestamp, path of transfer indices)
        stack: list[tuple[str, float, list[int], set[str]]] = [
            (seed["to_account"], seed["ts_seconds"], [seed_idx], {origin, seed["to_account"]})
        ]

        while stack:
            if expansions >= opts["max_expansions"]:
                break
            account, last_ts, path, visited = stack.pop()

            for next_idx, nxt in outgoing.get(account, []):
                if nxt["ts_seconds"] < last_ts or nxt["ts_seconds"] > deadline:
                    continue
                if next_idx in path:
                    continue
                if not within_tolerance(nxt["amount"], principal):
                    continue

                expansions += 1
                if expansions >= opts["max_expansions"]:
                    break

                target = nxt["to_account"]

                if target == origin:
                    if len(path) + 1 < opts["min_hops"]:
                        continue
                    indices = path + [next_idx]
                    accounts = [rows[i]["from_account"] for i in indices]
                    # Keyed on the account set alone: the same ring running weekly is
                    # one pattern with a recurrence count, not fifty separate findings.
                    key = tuple(sorted(set(accounts)))
                    if key in found:
                        # Same ring reached by another path: widen the transfer set.
                        # Recurrence and value are derived from that set afterwards,
                        # never incremented per path, or permutations inflate both.
                        entry = found[key]
                        entry["transfer_indices"] = sorted(
                            set(entry["transfer_indices"]) | set(indices)
                        )
                        continue

                    cycle_rows = [rows[i] for i in indices]
                    stamps = [r["ts_seconds"] for r in cycle_rows]
                    span_days = (max(stamps) - min(stamps)) / 86400.0
                    banks: list[str] = []
                    for r in cycle_rows:
                        if not banks or banks[-1] != r["from_bank"]:
                            banks.append(r["from_bank"])
                    found[key] = {
                        "accounts": accounts,
                        "banks": banks,
                        "transfer_indices": indices,
                        "hop_count": len(indices),
                        "principal": round(principal, 2),
                        "total_amount": round(sum(r["amount"] for r in cycle_rows), 2),
                        "cycle_span_days": round(span_days, 3),
                        "recurrence": 1,
                        "amounts": [r["amount"] for r in cycle_rows],
                    }
                    continue

                if len(path) + 1 < max_hops and target not in visited:
                    stack.append(
                        (target, nxt["ts_seconds"], path + [next_idx], visited | {target})
                    )

    cycles: list[dict[str, Any]] = []
    for i, cycle in enumerate(found.values()):
        # One "round" is one loop's worth of transfers.
        indices = cycle["transfer_indices"]
        cycle["total_amount"] = round(sum(rows[j]["amount"] for j in indices), 2)
        cycle["recurrence"] = max(1, round(len(indices) / max(cycle["hop_count"], 1)))
        cycle["transfer_count"] = len(indices)
        scored = _score(
            cycle.pop("amounts"),
            cycle["cycle_span_days"],
            cycle["hop_count"],
            cycle["recurrence"],
            weights,
        )
        if scored["cycle_risk_score"] < opts["min_risk_score"]:
            continue
        cycle.update(scored)
        cycles.append(cycle)

    cycles.sort(key=lambda c: -c["cycle_risk_score"])
    for i, cycle in enumerate(cycles):
        cycle["cycle_id"] = f"FC{i}"
    return cycles[: opts["max_cycles"]]


def bank_cycle_index(cycles: list[dict[str, Any]]) -> tuple[set[int], dict[str, list[str]]]:
    """Transfer indices that sit on a cycle, and the cycle ids each bank appears in."""
    transfer_indices: set[int] = set()
    by_bank: dict[str, list[str]] = {}
    for cycle in cycles:
        transfer_indices.update(cycle.get("transfer_indices", []))
        for bank in cycle.get("banks", []):
            by_bank.setdefault(str(bank), []).append(cycle.get("cycle_id", ""))
    return transfer_indices, by_bank


def cycles_for_bank(cycles: list[dict[str, Any]], bank_code: str) -> list[dict[str, Any]]:
    return [c for c in cycles if bank_code in c.get("banks", [])]


def summarise(cycles: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not cycles:
        return None
    return {
        "count": len(cycles),
        "top_risk": cycles[0]["cycle_risk_score"],
        "total_value": round(sum(c["total_amount"] for c in cycles), 2),
        "banks_involved": sorted({b for c in cycles for b in c.get("banks", [])}),
    }
