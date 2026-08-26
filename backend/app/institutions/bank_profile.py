"""Behavioural profiling for institutions in a transfer ledger.

Turns a multi-party ledger into one profile per bank: how much it moved, who it
moved it with, through which instruments and currencies, where it sits in the
network, and a risk score assembled from documented, individually inspectable
components.

Ground-truth labels (an "Is Laundering" column, when present) are deliberately
excluded from the score and reported separately, so the score can be evaluated
against them rather than trained on them.
"""

from typing import Any, Optional

import networkx as nx
import pandas as pd

from app.config_loader import load_config
from app.institutions.flow_cycles import bank_cycle_index, find_conserved_cycles

DEFAULT_WEIGHTS = {
    "cycle_exposure": 0.24,
    "structuring_share": 0.18,
    "network_centrality": 0.16,
    "account_concentration": 0.14,
    "cross_currency_share": 0.12,
    "high_risk_format_share": 0.10,
    "burst_velocity": 0.06,
}

# "Objectively concerning" level for each component, independent of peers. A bank
# at or above this scores the component fully even if every peer looks the same.
ABSOLUTE_REFERENCES = {
    "cycle_exposure": 0.10,
    "structuring_share": 0.15,
    "network_centrality": 0.25,
    "account_concentration": 0.50,
    "cross_currency_share": 0.40,
    "high_risk_format_share": 0.50,
    "burst_velocity": 0.25,
}

COMPONENT_DESCRIPTIONS = {
    "cycle_exposure": "Share of this bank's transfers that sit on a detected circular fund path.",
    "structuring_share": "Share of transfers parked just below a cash-reporting threshold.",
    "network_centrality": "How often the bank sits on the path between two other institutions.",
    "account_concentration": "How concentrated its value is in a handful of its own accounts (HHI).",
    "cross_currency_share": "Share of transfers where the settlement currency changed.",
    "high_risk_format_share": "Share moved by the instruments most used for layering (wire, cash).",
    "burst_velocity": "Share of all its transfers falling on its single busiest day.",
}

# Instruments that carry the least friction and the most laundering exposure.
HIGH_RISK_FORMATS = {"wire", "cash", "crypto", "bitcoin", "reinvestment"}

TOP_N = 8


def _defaults() -> dict[str, Any]:
    cfg = load_config("thresholds")
    bi = cfg.get("bank_intelligence", {}) or {}
    weights = {**DEFAULT_WEIGHTS, **(bi.get("risk_weights") or {})}
    return {
        "weights": weights,
        "near_threshold_bands": bi.get(
            "near_threshold_bands",
            [{"threshold": 10000, "lower_pct": 0.9}, {"threshold": 50000, "lower_pct": 0.9}],
        ),
        "high_risk_tier_min": float(bi.get("high_risk_tier_min", 70)),
        "medium_risk_tier_min": float(bi.get("medium_risk_tier_min", 40)),
        "max_banks_profiled": int(bi.get("max_banks_profiled", 500)),
        "absolute_references": {**ABSOLUTE_REFERENCES, **(bi.get("absolute_references") or {})},
        "peer_z_threshold": float(
            (cfg.get("anomaly", {}) or {}).get("robust_zscore_threshold", 3.5)
        ),
    }


def _risk_tier(score: float, opts: dict[str, Any]) -> str:
    if score >= opts["high_risk_tier_min"]:
        return "HIGH"
    if score >= opts["medium_risk_tier_min"]:
        return "MEDIUM"
    return "LOW"


def _near_threshold_mask(amounts: pd.Series, bands: list[dict]) -> pd.Series:
    mask = pd.Series(False, index=amounts.index)
    for band in bands:
        threshold = float(band.get("threshold", 10000))
        lower = threshold * float(band.get("lower_pct", 0.9))
        mask |= (amounts >= lower) & (amounts <= threshold)
    return mask


def _robust_peer_scale(values: list[float], value: float, threshold: float) -> tuple[float, float]:
    """How far above its peers this bank sits, as a robust z clipped to [0,1].

    Uses median absolute deviation rather than mean/σ so one extreme institution
    cannot mask the rest. Returns (scaled, raw_z).
    """
    import statistics

    if len(values) < 3:
        return 0.0, 0.0
    median = statistics.median(values)
    deviations = [abs(v - median) for v in values]
    mad = statistics.median(deviations)
    if mad > 0:
        spread = 1.4826 * mad
    else:
        # More than half the banks sit at the median (usually zero), so MAD is
        # degenerate — exactly the case where a signal is concentrated in a few
        # institutions. Mean absolute deviation still separates them, and stays
        # zero when every bank really is identical.
        spread = sum(deviations) / len(deviations)
    if spread <= 0:
        return 0.0, 0.0
    z = (value - median) / spread
    if z <= 0:
        return 0.0, round(z, 3)
    return min(z / threshold, 1.0), round(z, 3)


def _hhi(values: pd.Series) -> float:
    total = float(values.sum())
    if total <= 0:
        return 0.0
    shares = values / total
    return float((shares**2).sum())


def _top_records(frame: pd.DataFrame, label_col: str, n: int = TOP_N) -> list[dict[str, Any]]:
    return [
        {
            "name": str(row[label_col]),
            "transfer_count": int(row["transfer_count"]),
            "total_amount": round(float(row["total_amount"]), 2),
        }
        for _, row in frame.head(n).iterrows()
    ]


def _bank_centrality(edges: pd.DataFrame, bank_codes: list[str]) -> dict[str, dict[str, float]]:
    """Degree, betweenness and PageRank on the aggregated bank graph.

    Betweenness is sampled above a node count where the exact O(V*E) computation
    would make an upload feel hung; the sample size is reported so the number is
    never mistaken for exact.
    """
    G = nx.DiGraph()
    G.add_nodes_from(bank_codes)
    for _, row in edges.iterrows():
        G.add_edge(row["from_bank"], row["to_bank"], weight=float(row["transfer_count"]))

    metrics: dict[str, dict[str, float]] = {
        n: {
            "in_degree": float(G.in_degree(n)),
            "out_degree": float(G.out_degree(n)),
            "betweenness_centrality": 0.0,
            "betweenness_sampled": 0.0,
        }
        for n in G.nodes()
    }

    node_count = G.number_of_nodes()
    if node_count >= 4:
        sample = None if node_count <= 150 else 150
        try:
            betweenness = nx.betweenness_centrality(G, k=sample, normalized=True)
            for n, val in betweenness.items():
                metrics[n]["betweenness_centrality"] = round(val, 6)
                metrics[n]["betweenness_sampled"] = 1.0 if sample else 0.0
        except Exception:
            pass
        try:
            for n, val in nx.pagerank(G, weight="weight").items():
                metrics[n]["pagerank"] = round(val, 6)
        except Exception:
            pass

    return metrics


def build_bank_intelligence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute edges, institution-level cycles and one profile per bank."""
    opts = _defaults()
    weights = opts["weights"]

    if not rows:
        return {"banks": [], "edges": [], "cycles": [], "summary": {}}

    df = pd.DataFrame(rows)
    df["amount"] = df["amount_paid"].where(df["amount_paid"] > 0, df["amount_received"])
    df["amount"] = df["amount"].fillna(0.0)
    df["ts"] = pd.to_datetime(df["txn_ts"], errors="coerce")
    df["day"] = df["ts"].dt.floor("D")
    df["format_norm"] = df["payment_format"].fillna("unspecified").astype(str).str.strip().str.lower()
    df["cross_currency"] = (
        df["payment_currency"].notna()
        & df["receiving_currency"].notna()
        & (df["payment_currency"] != df["receiving_currency"])
    )
    df["near_threshold"] = _near_threshold_mask(df["amount"], opts["near_threshold_bands"])
    df["corridor"] = df["payment_currency"].fillna("?") + " → " + df["receiving_currency"].fillna("?")

    # ---------------------------------------------------------------- edges
    edges = (
        df.groupby(["from_bank", "to_bank"], dropna=False)
        .agg(
            transfer_count=("amount", "size"),
            total_amount=("amount", "sum"),
            labelled_laundering_count=("is_labelled_laundering", "sum"),
        )
        .reset_index()
    )
    edges["labelled_laundering_count"] = edges["labelled_laundering_count"].astype(int)

    # ------------------------------------------------- per-bank time bounds
    epoch = pd.Timestamp("1970-01-01")
    sent_ts = df.groupby("from_bank")["ts"].agg(["min", "max"])
    recv_ts = df.groupby("to_bank")["ts"].agg(["min", "max"])
    bounds = sent_ts.join(recv_ts, how="outer", lsuffix="_s", rsuffix="_r")
    bounds["first_seen"] = bounds[["min_s", "min_r"]].min(axis=1)
    bounds["last_seen"] = bounds[["max_s", "max_r"]].max(axis=1)

    sent_totals = df.groupby("from_bank")["amount"].sum()
    recv_totals = df.groupby("to_bank")["amount"].sum()
    flow = sent_totals.add(recv_totals, fill_value=0.0)

    seen = pd.DataFrame({
        "bank_code": flow.index,
        "flow": flow.values,
    })
    seen["first_seen"] = [
        (bounds["first_seen"].get(b) - epoch).total_seconds()
        if pd.notna(bounds["first_seen"].get(b))
        else 0.0
        for b in seen["bank_code"]
    ]
    seen["last_seen"] = [
        (bounds["last_seen"].get(b) - epoch).total_seconds()
        if pd.notna(bounds["last_seen"].get(b))
        else 0.0
        for b in seen["bank_code"]
    ]

    # ------------------------------------------------- ranks and flow cycles
    centrality = _bank_centrality(edges, list(seen["bank_code"]))

    # Cycles are found between accounts, then attributed up to the institutions
    # that carried them — a loop between banks says nothing in a connected network.
    epoch_ts = df["ts"]
    cycle_input = [
        {
            "from_account": row["from_account"],
            "to_account": row["to_account"],
            "from_bank": row["from_bank"],
            "to_bank": row["to_bank"],
            "amount": float(row["amount"]),
            "ts_seconds": (
                (epoch_ts.iloc[i] - epoch).total_seconds() if pd.notna(epoch_ts.iloc[i]) else None
            ),
        }
        for i, row in enumerate(df.to_dict("records"))
    ]
    try:
        cycles = find_conserved_cycles(cycle_input)
    except Exception:
        cycles = []

    cycle_transfer_idx, cycle_ids_by_bank = bank_cycle_index(cycles)
    df["on_cycle"] = False
    if cycle_transfer_idx:
        df.iloc[
            sorted(cycle_transfer_idx), df.columns.get_loc("on_cycle")
        ] = True

    max_betweenness = max(
        (m.get("betweenness_centrality", 0.0) for m in centrality.values()), default=0.0
    )

    # ------------------------------------------------------------ profiles
    profiles: list[dict[str, Any]] = []
    bank_codes = list(seen["bank_code"])

    for code in bank_codes:
        outgoing = df[df["from_bank"] == code]
        incoming = df[df["to_bank"] == code]
        involved = pd.concat([outgoing, incoming])

        transfer_count = int(len(involved))
        if transfer_count == 0:
            continue

        total_sent = float(outgoing["amount"].sum())
        total_received = float(incoming["amount"].sum())

        partners = set(outgoing["to_bank"].dropna()) | set(incoming["from_bank"].dropna())
        partners.discard(code)

        # Counterparty banks by value moved
        partner_frame = (
            pd.concat([
                outgoing.assign(partner=outgoing["to_bank"], direction="sent"),
                incoming.assign(partner=incoming["from_bank"], direction="received"),
            ])
            .groupby("partner")
            .agg(transfer_count=("amount", "size"), total_amount=("amount", "sum"))
            .reset_index()
            .sort_values("total_amount", ascending=False)
        )

        # Instrument mix
        format_counts = involved["format_norm"].value_counts()
        format_mix = [
            {
                "format": str(fmt),
                "count": int(count),
                "share": round(float(count) / transfer_count, 4),
            }
            for fmt, count in format_counts.items()
        ]
        wire_share = round(float(format_counts.get("wire", 0)) / transfer_count, 4)
        high_risk_share = round(
            float(sum(format_counts.get(f, 0) for f in HIGH_RISK_FORMATS)) / transfer_count, 4
        )

        # Currency corridors
        corridor_frame = (
            involved.groupby("corridor")
            .agg(transfer_count=("amount", "size"), total_amount=("amount", "sum"))
            .reset_index()
            .sort_values("total_amount", ascending=False)
        )
        cross_currency_share = round(float(involved["cross_currency"].sum()) / transfer_count, 4)

        # Own accounts
        own_accounts = pd.concat([
            outgoing[["from_account", "amount"]].rename(columns={"from_account": "account"}),
            incoming[["to_account", "amount"]].rename(columns={"to_account": "account"}),
        ]).dropna(subset=["account"])
        account_frame = (
            own_accounts.groupby("account")
            .agg(transfer_count=("amount", "size"), total_amount=("amount", "sum"))
            .reset_index()
            .sort_values("total_amount", ascending=False)
        )
        account_concentration = _hhi(account_frame["total_amount"]) if not account_frame.empty else 0.0

        # Activity shape
        day_counts = involved["day"].value_counts()
        active_days = int(day_counts.size)
        busiest_day_count = int(day_counts.iloc[0]) if active_days else 0
        burst_velocity = round(busiest_day_count / transfer_count, 4) if transfer_count else 0.0
        busiest_day = (
            str(day_counts.index[0].date()) if active_days and pd.notna(day_counts.index[0]) else None
        )

        structuring_share = round(float(involved["near_threshold"].sum()) / transfer_count, 4)

        # Cycle exposure: this bank's own transfers that sit on a detected loop
        cycle_transfers = int(involved["on_cycle"].sum())
        cycle_exposure = round(cycle_transfers / transfer_count, 4)

        cent = centrality.get(code, {})
        betweenness = float(cent.get("betweenness_centrality", 0.0))
        network_centrality = round(betweenness / max_betweenness, 4) if max_betweenness > 0 else 0.0

        component_values = {
            "cycle_exposure": cycle_exposure,
            "structuring_share": structuring_share,
            "network_centrality": network_centrality,
            "account_concentration": round(account_concentration, 4),
            "cross_currency_share": cross_currency_share,
            "high_risk_format_share": high_risk_share,
            "burst_velocity": burst_velocity,
        }

        first_seen = bounds["first_seen"].get(code)
        last_seen = bounds["last_seen"].get(code)

        profiles.append({
            "bank_code": code,
            "display_name": code.replace("BANK_", "Bank "),
            "component_values": component_values,
            "transfer_count": transfer_count,
            "sent_count": int(len(outgoing)),
            "received_count": int(len(incoming)),
            "total_sent": round(total_sent, 2),
            "total_received": round(total_received, 2),
            "net_flow": round(total_received - total_sent, 2),
            "avg_transfer": round(float(involved["amount"].mean()), 2),
            "median_transfer": round(float(involved["amount"].median()), 2),
            "max_transfer": round(float(involved["amount"].max()), 2),
            "connected_banks": len(partners),
            "counterparty_banks": _top_records(partner_frame, "partner"),
            "format_mix": format_mix[:TOP_N],
            "wire_share": wire_share,
            "high_risk_format_share": high_risk_share,
            "currency_corridors": _top_records(corridor_frame, "corridor"),
            "cross_currency_share": cross_currency_share,
            "account_count": int(account_frame.shape[0]),
            "account_concentration_hhi": round(account_concentration, 4),
            "top_accounts": _top_records(account_frame, "account", 5),
            "active_days": active_days,
            "busiest_day": busiest_day,
            "busiest_day_transfers": busiest_day_count,
            "burst_velocity": burst_velocity,
            "structuring_share": structuring_share,
            "near_threshold_transfers": int(involved["near_threshold"].sum()),
            "threshold_bands": opts["near_threshold_bands"],
            "first_seen": first_seen.isoformat() if pd.notna(first_seen) else None,
            "last_seen": last_seen.isoformat() if pd.notna(last_seen) else None,
            "centrality": {
                "in_degree": cent.get("in_degree", 0.0),
                "out_degree": cent.get("out_degree", 0.0),
                "betweenness_centrality": round(betweenness, 6),
                "pagerank": cent.get("pagerank"),
            },
            "cycle_ids": sorted(set(cycle_ids_by_bank.get(code, []))),
            "cycle_exposure": cycle_exposure,
            "cycle_transfers": cycle_transfers,
            # Ground truth: never an input to risk_score, reported for evaluation only.
            "labelled_laundering_transfers": int(involved["is_labelled_laundering"].sum()),
            "labelled_laundering_share": round(
                float(involved["is_labelled_laundering"].sum()) / transfer_count, 4
            ),
        })

    # ------------------------------------------------------------- scoring
    # A bank's legitimate volume always dwarfs its illicit volume, so a raw share
    # can never reach a meaningful score. Each component is therefore scored on
    # whichever is worse: its absolute level, or how far it sits above its peers.
    _score_profiles(profiles, weights, opts)

    profiles.sort(key=lambda p: -p["risk_score"])
    profiles = profiles[: opts["max_banks_profiled"]]

    # ------------------------------------------------------------- summary
    ts_min = df["ts"].min()
    ts_max = df["ts"].max()
    has_labels = bool(df["is_labelled_laundering"].any())

    summary: dict[str, Any] = {
        "bank_count": len(bank_codes),
        "transfer_count": int(len(df)),
        "total_value": round(float(df["amount"].sum()), 2),
        "edge_count": int(len(edges)),
        "cycle_count": len(cycles),
        "account_count": int(
            pd.concat([df["from_account"], df["to_account"]]).dropna().nunique()
        ),
        "observed_start": ts_min.isoformat() if pd.notna(ts_min) else None,
        "observed_end": ts_max.isoformat() if pd.notna(ts_max) else None,
        "currencies": sorted(
            {
                str(c)
                for c in pd.concat([df["payment_currency"], df["receiving_currency"]]).dropna().unique()
                if str(c)
            }
        ),
        "payment_formats": sorted({str(f) for f in df["format_norm"].dropna().unique() if str(f)}),
        "cross_currency_share": round(float(df["cross_currency"].sum()) / max(len(df), 1), 4),
        "high_risk_tier_min": opts["high_risk_tier_min"],
        "medium_risk_tier_min": opts["medium_risk_tier_min"],
        "risk_weights": weights,
        "has_labels": has_labels,
    }

    if has_labels:
        flagged = {p["bank_code"] for p in profiles if p["risk_tier"] == "HIGH"}
        with_labels = {p["bank_code"] for p in profiles if p["labelled_laundering_transfers"] > 0}
        summary["label_evaluation"] = {
            "labelled_transfers": int(df["is_labelled_laundering"].sum()),
            "banks_touching_labelled_transfers": len(with_labels),
            "banks_scored_high": len(flagged),
            "high_scored_and_labelled": len(flagged & with_labels),
            "labelled_but_not_high": len(with_labels - flagged),
            "note": "Labels are excluded from the risk score; shown to evaluate it, not to fit it.",
        }

    return {
        "banks": profiles,
        "edges": edges.to_dict("records"),
        "cycles": cycles,
        "summary": summary,
    }


def _score_profiles(
    profiles: list[dict[str, Any]], weights: dict[str, float], opts: dict[str, Any]
) -> None:
    """Assign risk_score / risk_tier / risk_components in place."""
    if not profiles:
        return

    references = opts["absolute_references"]
    z_threshold = opts["peer_z_threshold"]
    names = list(DEFAULT_WEIGHTS.keys())
    distributions = {
        name: [float(p["component_values"].get(name, 0.0)) for p in profiles] for name in names
    }

    for profile in profiles:
        raw = profile.pop("component_values")
        components: list[dict[str, Any]] = []
        total = 0.0

        for name in names:
            value = float(raw.get(name, 0.0))
            weight = float(weights.get(name, 0.0))
            reference = float(references.get(name, 1.0)) or 1.0

            absolute = min(value / reference, 1.0)
            relative, z = _robust_peer_scale(distributions[name], value, z_threshold)
            severity = max(absolute, relative)
            points = 100.0 * weight * severity
            total += points

            components.append({
                "name": name,
                "value": round(value, 4),
                "weight": weight,
                "severity": round(severity, 4),
                "absolute_scale": round(absolute, 4),
                "peer_scale": round(relative, 4),
                "peer_z": z,
                "reference": reference,
                "driver": "peers" if relative > absolute else "level",
                "points": round(points, 2),
                "description": COMPONENT_DESCRIPTIONS.get(name, ""),
            })

        components.sort(key=lambda c: -c["points"])
        profile["risk_score"] = round(min(total, 100.0), 1)
        profile["risk_tier"] = _risk_tier(profile["risk_score"], opts)
        profile["risk_components"] = components
        profile["risk_formula"] = (
            "bank_risk = 100 × Σ(weight_i × max(value_i / reference_i, robust_z_i / 3.5))"
        )


def profile_for(
    banks: list[dict[str, Any]], bank_code: str
) -> Optional[dict[str, Any]]:
    for bank in banks:
        if bank["bank_code"] == bank_code:
            return bank
    return None
