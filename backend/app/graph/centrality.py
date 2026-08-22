import networkx as nx


def compute_centrality_metrics(G: nx.MultiDiGraph) -> dict[str, dict[str, float]]:
    simple = nx.DiGraph()
    for u, v in G.edges():
        if simple.has_edge(u, v):
            simple[u][v]["weight"] = simple[u][v].get("weight", 0) + 1
        else:
            simple.add_edge(u, v, weight=1)

    node_count = simple.number_of_nodes()

    metrics: dict[str, dict[str, float]] = {}
    for n in simple.nodes():
        in_deg = simple.in_degree(n)
        out_deg = simple.out_degree(n)
        total_deg = in_deg + out_deg
        degree_ratio = out_deg / max(in_deg, 1)

        in_flow = sum(d.get("total_amount", 0) for _, _, d in G.in_edges(n, data=True))
        out_flow = sum(d.get("total_amount", 0) for _, _, d in G.out_edges(n, data=True))
        flow_ratio = out_flow / max(in_flow, 1)

        metrics[n] = {
            "in_degree": float(in_deg),
            "out_degree": float(out_deg),
            "degree_ratio": round(degree_ratio, 4),
            "in_flow": round(in_flow, 2),
            "out_flow": round(out_flow, 2),
            "flow_ratio": round(flow_ratio, 4),
        }

    if node_count >= 5:
        try:
            betweenness = nx.betweenness_centrality(simple, normalized=True, weight="weight")
            for n, val in betweenness.items():
                if n in metrics:
                    metrics[n]["betweenness_centrality"] = round(val, 6)
        except Exception:
            pass

        try:
            pagerank = nx.pagerank(simple, weight="weight")
            for n, val in pagerank.items():
                if n in metrics:
                    metrics[n]["pagerank"] = round(val, 6)
        except Exception:
            pass

    return metrics
