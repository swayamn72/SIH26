from typing import Optional

import networkx as nx
import pandas as pd


def build_transaction_graph(
    df: pd.DataFrame,
    subject_account_id: str = "ACCT_SUBJECT",
    node_labels: Optional[dict[str, str]] = None,
) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    G.add_node(subject_account_id, label=subject_account_id, flow=0.0,
               first_seen=float("inf"), last_seen=float("-inf"))

    for _, row in df.iterrows():
        counterparty = str(row.get("counterparty_id", "UNKNOWN"))
        if pd.isna(counterparty) or counterparty in ("", "nan", "UNKNOWN"):
            counterparty = f"CPTY_{row.name}"
            
        c_label = (node_labels or {}).get(counterparty, counterparty)

        # Extract Unix timestamp for node time-range tracking.
        txn_ts: float = float("inf")
        raw_date = row.get("txn_date")
        if raw_date is not None and not (isinstance(raw_date, float) and pd.isna(raw_date)):
            try:
                txn_ts = pd.Timestamp(raw_date).timestamp()
            except Exception:
                txn_ts = float("inf")

        def _update_timestamps(node_id: str) -> None:
            """Update first_seen / last_seen for a node."""
            if txn_ts == float("inf"):
                return
            cur_first = G.nodes[node_id].get("first_seen", float("inf"))
            cur_last = G.nodes[node_id].get("last_seen", float("-inf"))
            G.nodes[node_id]["first_seen"] = min(cur_first, txn_ts)
            G.nodes[node_id]["last_seen"] = max(cur_last, txn_ts)

        if pd.notna(row.get("debit_amount")) and float(row["debit_amount"]) > 0:
            amt = float(row["debit_amount"])
            G.add_edge(subject_account_id, counterparty, amount=amt, channel=str(row.get("channel", "")), row_id=str(row.get("row_id", "")))
            G.nodes[subject_account_id]["flow"] = G.nodes[subject_account_id].get("flow", 0) + amt
            if counterparty not in G.nodes:
                G.add_node(counterparty, label=c_label, flow=0.0,
                           first_seen=float("inf"), last_seen=float("-inf"))
            G.nodes[counterparty]["flow"] = G.nodes[counterparty].get("flow", 0) + amt
            G.nodes[counterparty]["label"] = c_label
            _update_timestamps(subject_account_id)
            _update_timestamps(counterparty)

        if pd.notna(row.get("credit_amount")) and float(row["credit_amount"]) > 0:
            amt = float(row["credit_amount"])
            G.add_edge(counterparty, subject_account_id, amount=amt, channel=str(row.get("channel", "")), row_id=str(row.get("row_id", "")))
            if counterparty not in G.nodes:
                G.add_node(counterparty, label=c_label, flow=0.0,
                           first_seen=float("inf"), last_seen=float("-inf"))
            G.nodes[counterparty]["flow"] = G.nodes[counterparty].get("flow", 0) + amt
            G.nodes[counterparty]["label"] = c_label
            G.nodes[subject_account_id]["flow"] = G.nodes[subject_account_id].get("flow", 0) + amt
            _update_timestamps(counterparty)
            _update_timestamps(subject_account_id)

    return G


def graph_to_json(G: nx.MultiDiGraph) -> dict:
    nodes = [
        {"id": n, "label": str(G.nodes[n].get("label", n)), "flow": G.nodes[n].get("flow", 0)}
        for n in G.nodes
    ]
    edges = [
        {"source": u, "target": v, "amount": d.get("amount", 0), "channel": d.get("channel", ""), "row_id": d.get("row_id", "")}
        for u, v, k, d in G.edges(keys=True, data=True)
    ]
    return {"nodes": nodes, "edges": edges}
