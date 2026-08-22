from typing import Any

import networkx as nx

from app.config_loader import load_config


def _collapse_to_simple(G: nx.MultiDiGraph) -> nx.DiGraph:
    simple = nx.DiGraph()
    for u, v, data in G.edges(data=True):
        if simple.has_edge(u, v):
            simple[u][v]["count"] = simple[u][v].get("count", 0) + 1
            simple[u][v]["total_amount"] = simple[u][v].get("total_amount", 0) + data.get("amount", 0)
        else:
            simple.add_edge(u, v, count=1, total_amount=data.get("amount", 0))
    return simple


def _score_cycle(cycle: list[str], G: nx.MultiDiGraph) -> dict[str, Any]:
    cfg = load_config("thresholds")
    weights = cfg.get("cycle_risk_weights", {})
    w_conservation = weights.get("amount_conservation", 0.35)
    w_velocity = weights.get("velocity_compression", 0.30)
    w_recurrence = weights.get("cycle_recurrence", 0.20)
    w_inverse_hops = weights.get("inverse_hop_count", 0.15)

    hop_count = len(cycle)

    amounts: list[float] = []
    min_ts = float("inf")
    max_ts = float("-inf")
    row_ids: list[str] = []

    for i in range(hop_count):
        u = cycle[i]
        v = cycle[(i + 1) % hop_count]
        edge_dict = G.get_edge_data(u, v)
        if edge_dict:
            for _key, data in edge_dict.items():
                amt = data.get("amount", 0)
                amounts.append(float(amt))
                row_ids.append(data.get("row_id", ""))
        node_data = G.nodes.get(u, {})
        if "first_seen" in node_data and node_data["first_seen"] < min_ts:
            min_ts = node_data["first_seen"]
        if "last_seen" in node_data and node_data["last_seen"] > max_ts:
            max_ts = node_data["last_seen"]

    if amounts:
        import statistics
        mean_amt = statistics.mean(amounts)
        cv = statistics.stdev(amounts) / mean_amt if mean_amt > 0 and len(amounts) > 1 else 0
        amount_conservation = max(0.0, 1.0 - cv)
    else:
        amount_conservation = 0.0

    cycle_span_days = (max_ts - min_ts) / (3600 * 24) if max_ts > min_ts else 0.1
    velocity_compression = hop_count / cycle_span_days if cycle_span_days > 0 else 0

    normalized_velocity = min(velocity_compression / 10, 1.0)
    normalized_inverse_hops = 1.0 / max(hop_count, 1)

    # Cycle recurrence: ratio of total parallel (multi) edges to hop_count.
    # Repeated transactions between the same parties signal a recurring layering pattern.
    total_edge_count = len(amounts)
    cycle_recurrence = min(total_edge_count / max(hop_count, 1), 1.0) if hop_count > 0 else 0.0

    cycle_risk = (
        w_conservation * amount_conservation
        + w_velocity * normalized_velocity
        + w_recurrence * cycle_recurrence
        + w_inverse_hops * normalized_inverse_hops
    )

    return {
        "hop_count": hop_count,
        "amount_conservation_ratio": round(amount_conservation, 4),
        "cycle_span_days": round(cycle_span_days, 2),
        "velocity_compression": round(velocity_compression, 4),
        "cycle_recurrence": round(cycle_recurrence, 4),
        "cycle_risk_score": round(cycle_risk, 4),
        "contributing_row_ids": row_ids,
    }


def detect_cycles(G: nx.MultiDiGraph) -> list[dict[str, Any]]:
    cfg = load_config("thresholds")
    cyc = cfg.get("cycle", {})
    max_length = cyc.get("max_cycle_length", 6)
    dense_cap = cyc.get("dense_component_edge_cap", 1000)
    min_risk = cyc.get("min_cycle_risk_score", 0.6)

    simple = _collapse_to_simple(G)

    sccs = list(nx.strongly_connected_components(simple))
    results: list[dict[str, Any]] = []

    for component in sccs:
        if len(component) < 2:
            continue

        sub = G.subgraph(component)
        edge_count = sub.number_of_edges()
        if edge_count > dense_cap:
            results.append({
                "cycle_id": f"dense_{len(results)}",
                "nodes": list(component),
                "hop_count": 0,
                "amount_conservation_ratio": None,
                "cycle_span_days": None,
                "velocity_compression": None,
                "cycle_risk_score": 0.0,
                "contributing_row_ids": [],
                "warning": "Pathologically dense component — full enumeration skipped",
            })
            continue

        simple_sub = simple.subgraph(component)
        try:
            cycles = list(nx.simple_cycles(simple_sub))
        except Exception:
            continue

        for cycle in cycles:
            if len(cycle) > max_length:
                continue
            scored = _score_cycle(list(cycle), G)
            if scored["cycle_risk_score"] >= min_risk:
                scored["cycle_id"] = f"C{len(results)}"
                scored["nodes"] = list(cycle)
                results.append(scored)

    results.sort(key=lambda c: c.get("cycle_risk_score", 0), reverse=True)
    return results
