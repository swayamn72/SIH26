import { useEffect, useRef } from "react";
import cytoscape, { Core, ElementDefinition } from "cytoscape";

type GraphNode = { id: string; label: string; flow: number };
type GraphEdge = { source: string; target: string; amount: number; channel: string; row_id: string };
type CycleInfo = { cycle_id: string; nodes: string[]; cycle_risk_score: number; hop_count: number; contributing_row_ids?: string[] };

type ProofGraphCanvasProps = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  cycles: CycleInfo[];
  muleRowIds?: string[];
  muleNodes?: string[];
  selectedNode?: string | null;
  selectedEdge?: string | null;
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeRowId: string) => void;
};

export function ProofGraphCanvas({
  nodes,
  edges,
  cycles,
  muleRowIds = [],
  muleNodes = [],
  selectedNode,
  selectedEdge,
  onNodeClick,
  onEdgeClick,
}: ProofGraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  // Store callbacks in refs so changes to callback functions never trigger canvas rebuilds
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;

  const onEdgeClickRef = useRef(onEdgeClick);
  onEdgeClickRef.current = onEdgeClick;

  useEffect(() => {
    if (!containerRef.current) return;

    const maxFlow = Math.max(...nodes.map((n) => (typeof n.flow === "number" ? n.flow : 0)), 1);

    // Collect all mule node IDs and mule edge row IDs
    const cycleNodeIds = new Set<string>();
    const cycleEdgeRowIds = new Set<string>(muleRowIds);

    cycles.forEach((c) => {
      if (c.nodes) {
        c.nodes.forEach((n) => cycleNodeIds.add(n));
      }
      if (c.contributing_row_ids) {
        c.contributing_row_ids.forEach((r) => cycleEdgeRowIds.add(r));
      }
    });

    muleNodes.forEach((n) => cycleNodeIds.add(n));

    const isAccountNode = (id: string) =>
      id.startsWith("ACCT_") || id === "ACCT_SUBJECT" || id === "ACCT_MERGED";

    // Sort nodes deterministically: Account node first, then other nodes alphabetically by ID
    const sortedNodes = [...nodes].sort((a, b) => {
      const aIsAcct = isAccountNode(a.id);
      const bIsAcct = isAccountNode(b.id);
      if (aIsAcct && !bIsAcct) return -1;
      if (!aIsAcct && bIsAcct) return 1;
      return a.id.localeCompare(b.id);
    });

    const elements: ElementDefinition[] = [
      ...sortedNodes.map((n) => {
        const flowVal = typeof n.flow === "number" ? n.flow : 0;
        const isAcct = isAccountNode(n.id);
        const isMule = !isAcct && cycleNodeIds.has(n.id);

        let nodeClass = "node-regular";
        if (isAcct) {
          nodeClass = "node-account";
        } else if (isMule) {
          nodeClass = "node-mule";
        }

        const baseSize = isAcct ? 150 : 80;
        const size = baseSize + (flowVal / maxFlow) * (isAcct ? 24 : 18);

        return {
          data: { id: n.id, label: n.label, flow: flowVal },
          classes: nodeClass,
          style: {
            width: size,
            height: size,
          },
        };
      }),
      ...edges.map((e) => {
        const amtVal = typeof e.amount === "number" ? e.amount : 0;
        const isMuleEdge =
          cycleEdgeRowIds.has(e.row_id) ||
          (cycleNodeIds.has(e.source) && cycleNodeIds.has(e.target));

        const edgeClass = isMuleEdge ? "edge-mule" : "edge-regular";

        return {
          data: {
            source: e.source,
            target: e.target,
            label: `₹${amtVal.toFixed(0)}`,
            amount: amtVal,
            channel: e.channel,
            row_id: e.row_id,
          },
          classes: edgeClass,
        };
      }),
    ];

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        // Base Node Style
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-valign": "center",
            "text-halign": "center",
            color: "#ffffff",
            "font-size": "20px",
            "font-weight": "bold",
            "font-family": "Inter, system-ui, sans-serif",
            "text-outline-width": 1.5,
            "text-outline-color": "rgba(0, 0, 0, 0.5)",
          },
        },
        // 🟣 Account Node: Purple
        {
          selector: "node.node-account",
          style: {
            "background-color": "#8b5cf6",
            "border-width": 4,
            "border-color": "#6d28d9",
            "font-weight": "bold",
            "font-size": "25px",
            "z-index": 100,
          },
        },
        // 🔴 Mule Node: Red & Bold
        {
          selector: "node.node-mule",
          style: {
            "background-color": "#ef4444",
            "border-width": 4,
            "border-color": "#b91c1c",
            "font-weight": "bold",
            "font-size": "20px",
            "z-index": 90,
          },
        },
        // 🔵 Standard Counterparties: Blue
        {
          selector: "node.node-regular",
          style: {
            "background-color": "#3b82f6",
            "border-width": 2,
            "border-color": "#1d4ed8",
            "font-size": "20px",
            "z-index": 10,
          },
        },
        // Selected Node
        {
          selector: "node:selected",
          style: {
            "border-width": 5,
            "border-color": "#f59e0b",
            "border-opacity": 1,
          },
        },

        // Base Edge Style
        {
          selector: "edge",
          style: {
            "curve-style": "bezier",
          },
        },
        // ⚪ Regular Transactions: Darker & Crisp
        {
          selector: "edge.edge-regular",
          style: {
            width: 1.5,
            "line-color": "#64748b",
            "target-arrow-color": "#64748b",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.85,
            opacity: 0.85,
            "z-index": 1,
          },
        },
        // 🔴 Mule Transactions: Red & Bold
        {
          selector: "edge.edge-mule",
          style: {
            width: 3.5,
            "line-color": "#ef4444",
            "target-arrow-color": "#ef4444",
            "target-arrow-shape": "triangle",
            "arrow-scale": 1.2,
            opacity: 1.0,
            "z-index": 50,
            "line-style": "solid",
          },
        },
        // Selected Edge
        {
          selector: "edge:selected",
          style: {
            width: 4,
            "line-color": "#f59e0b",
            "target-arrow-color": "#f59e0b",
            opacity: 1.0,
            "z-index": 999,
          },
        },
      ],
      layout: {
        name: "concentric",
        concentric: (node: any) => (node.hasClass("node-account") ? 2 : 1),
        levelWidth: () => 1,
        animate: false,
        startAngle: (3 / 2) * Math.PI,
        clockwise: true,
        equidistant: false,
        minNodeSpacing: 50,
        spacingFactor: 1.25,
        avoidOverlap: true,
      },
      userZoomingEnabled: true,
      userPanningEnabled: true,
    });

    cyRef.current.on("tap", "node", (evt) => {
      onNodeClickRef.current?.(evt.target.id());
    });
    cyRef.current.on("tap", "edge", (evt) => {
      onEdgeClickRef.current?.(evt.target.data("row_id"));
    });

    // Responsive: Observe dimension changes and re-fit graph
    let resizeTimer: any = null;
    const handleResize = () => {
      if (!cyRef.current) return;
      cyRef.current.resize();
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        cyRef.current?.fit(undefined, 30);
      }, 100);
    };

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined" && containerRef.current) {
      resizeObserver = new ResizeObserver(() => {
        handleResize();
      });
      resizeObserver.observe(containerRef.current);
    }

    window.addEventListener("resize", handleResize);

    return () => {
      if (resizeTimer) clearTimeout(resizeTimer);
      window.removeEventListener("resize", handleResize);
      resizeObserver?.disconnect();
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [nodes, edges, cycles, muleRowIds, muleNodes]);

  // Sync selected state into Cytoscape without re-running layout
  useEffect(() => {
    if (!cyRef.current) return;
    cyRef.current.$(":selected").unselect();
    if (selectedNode) {
      cyRef.current.$(`node[id = "${selectedNode}"]`).select();
    }
  }, [selectedNode]);

  useEffect(() => {
    if (!cyRef.current) return;
    if (selectedEdge) {
      cyRef.current.$(`edge[row_id = "${selectedEdge}"]`).select();
    }
  }, [selectedEdge]);

  const handleZoomIn = () => {
    if (!cyRef.current) return;
    cyRef.current.zoom({
      level: cyRef.current.zoom() * 1.25,
      renderedPosition: {
        x: cyRef.current.width() / 2,
        y: cyRef.current.height() / 2,
      },
    });
  };

  const handleZoomOut = () => {
    if (!cyRef.current) return;
    cyRef.current.zoom({
      level: cyRef.current.zoom() * 0.8,
      renderedPosition: {
        x: cyRef.current.width() / 2,
        y: cyRef.current.height() / 2,
      },
    });
  };

  const handleFit = () => {
    if (!cyRef.current) return;
    cyRef.current.fit(undefined, 30);
  };

  return (
    <div className="relative w-full h-full min-h-[350px]">
      <div ref={containerRef} className="w-full h-full" />
      {/* Floating Canvas Controls for Responsive Touch & Desktop Access */}
      <div className="absolute bottom-3 right-3 flex items-center gap-1.5 bg-white/90 backdrop-blur border border-gray-200 rounded-lg p-1 shadow-md z-10">
        <button
          onClick={handleZoomIn}
          title="Zoom In"
          className="p-1.5 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors text-xs font-bold"
        >
          +
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom Out"
          className="p-1.5 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors text-xs font-bold"
        >
          −
        </button>
        <div className="w-px h-4 bg-gray-200" />
        <button
          onClick={handleFit}
          title="Fit to Screen"
          className="px-2 py-1 text-[11px] text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded font-medium transition-colors"
        >
          Fit
        </button>
      </div>
    </div>
  );
}
