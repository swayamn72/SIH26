import pytest
import networkx as nx
from app.graph.cycle_detector import detect_cycles


class TestCycleDetection:
    def test_three_node_cycle_detected(self):
        G = nx.MultiDiGraph()
        G.add_node("A", flow=100)
        G.add_node("B", flow=100)
        G.add_node("C", flow=100)
        G.add_edge("A", "B", amount=100, channel="NEFT", row_id="r1")
        G.add_edge("B", "C", amount=100, channel="NEFT", row_id="r2")
        G.add_edge("C", "A", amount=100, channel="NEFT", row_id="r3")

        cycles = detect_cycles(G)
        assert len(cycles) > 0
        assert any(c.get("hop_count", 0) == 3 for c in cycles)

    def test_no_cycle_in_linear_graph(self):
        G = nx.MultiDiGraph()
        G.add_node("A", flow=100)
        G.add_node("B", flow=50)
        G.add_node("C", flow=25)
        G.add_edge("A", "B", amount=50, channel="NEFT", row_id="r1")
        G.add_edge("B", "C", amount=25, channel="NEFT", row_id="r2")

        cycles = detect_cycles(G)
        assert len(cycles) == 0

    def test_empty_graph_no_cycles(self):
        G = nx.MultiDiGraph()
        cycles = detect_cycles(G)
        assert len(cycles) == 0
