import { useEffect, useRef } from "react";
import cytoscape, { Core, ElementDefinition } from "cytoscape";

type GraphNode = { id: string; label: string; flow: number };
type GraphEdge = { source: string; target: string; amount: number; channel: string; row_id: string };
type CycleInfo = { cycle_id: string; nodes: string[]; cycle_risk_score: number; hop_count: number; contributing_row_ids?: string[] };

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

type ProofGraphCanvasProps = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  cycles: CycleInfo[];
  muleRowIds?: string[];
  muleNodes?: string[];
  /** Rows/nodes of a pattern opened from the evidence timeline — everything else is dimmed. */
  focusRowIds?: string[];
  focusNodeIds?: string[];
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
  focusRowIds = [],
  focusNodeIds = [],
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

    const safeNodes = Array.isArray(nodes)
      ? nodes.filter((node): node is GraphNode => typeof node?.id === "string" && typeof node.label === "string")
      : [];
    const knownNodeIds = new Set(safeNodes.map((node) => node.id));
    const safeEdges = Array.isArray(edges)
      ? edges.filter(
          (edge): edge is GraphEdge =>
            typeof edge?.source === "string" &&
            typeof edge.target === "string" &&
            typeof edge.row_id === "string" &&
            knownNodeIds.has(edge.source) &&
            knownNodeIds.has(edge.target),
        )
      : [];
    const safeCycles = Array.isArray(cycles) ? cycles : [];
    const maxFlow = Math.max(...safeNodes.map((n) => (Number.isFinite(n.flow) ? n.flow : 0)), 1);

    // Collect all mule node IDs and mule edge row IDs.
    const cycleNodeIds = new Set<string>();
    const cycleEdgeRowIds = new Set<string>(strings(muleRowIds));

    safeCycles.forEach((c) => {
      strings(c.nodes).forEach((nodeId) => cycleNodeIds.add(nodeId));
      strings(c.contributing_row_ids).forEach((rowId) => cycleEdgeRowIds.add(rowId));
    });

    strings(muleNodes).forEach((nodeId) => cycleNodeIds.add(nodeId));

    const isAccountNode = (id: string) =>
      id.startsWith("ACCT_") || id === "ACCT_SUBJECT" || id === "ACCT_MERGED";

    // Sort nodes deterministically: Account node first, then other nodes alphabetically by ID
    const sortedNodes = [...safeNodes].sort((a, b) => {
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

        const baseSize = isAcct ? 92 : 56;
        const size = baseSize + (flowVal / maxFlow) * (isAcct ? 20 : 16);

        return {
          data: { id: n.id, label: n.label, flow: flowVal },
          classes: nodeClass,
          style: {
            width: size,
            height: size,
          },
        };
      }),
      ...safeEdges.map((e) => {
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
            // Labels sit under the node with a white halo: readable at any zoom,
            // and it lets the nodes themselves stay small and uncluttered.
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 6,
            color: "#1E2E4A",
            "font-size": "11px",
            "font-weight": 600,
            "font-family": "Inter, system-ui, sans-serif",
            "text-outline-width": 3,
            "text-outline-color": "#ffffff",
            "text-wrap": "ellipsis",
            "text-max-width": "120px",
          },
        },
        // 🟣 Account Node: Purple
        {
          selector: "node.node-account",
          style: {
            "background-color": "#7C3AED",
            "border-width": 3,
            "border-color": "#5B21B6",
            "font-weight": 700,
            "font-size": "12px",
            "z-index": 100,
          },
        },
        // 🔴 Mule Node: Red & Bold
        {
          selector: "node.node-mule",
          style: {
            "background-color": "#DC2626",
            "border-width": 3,
            "border-color": "#991B1B",
            "font-weight": 600,
            "font-size": "11px",
            "z-index": 90,
          },
        },
        // 🔵 Standard Counterparties: Blue
        {
          selector: "node.node-regular",
          style: {
            "background-color": "#2563EB",
            "border-width": 2,
            "border-color": "#1D4ED8",
            "font-size": "11px",
            "z-index": 10,
          },
        },
        // Selected Node
        {
          selector: "node:selected",
          style: {
            "border-width": 5,
            "border-color": "#F59E0B",
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
            width: 1.2,
            "line-color": "#94A3B8",
            "target-arrow-color": "#94A3B8",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            opacity: 0.8,
            "z-index": 1,
          },
        },
        // 🔴 Mule Transactions: Red & Bold
        {
          selector: "edge.edge-mule",
          style: {
            width: 3,
            "line-color": "#DC2626",
            "target-arrow-color": "#DC2626",
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
        // Timeline focus: everything outside the opened pattern fades back
        {
          selector: ".focus-dim",
          style: {
            opacity: 0.08,
            "text-opacity": 0.08,
            "z-index": 0,
          },
        },
        {
          selector: "node.focus-hit",
          style: {
            "border-width": 6,
            "border-color": "#f59e0b",
            "border-opacity": 1,
            "z-index": 900,
          },
        },
        {
          selector: "edge.focus-hit",
          style: {
            width: 5,
            "line-color": "#f59e0b",
            "target-arrow-color": "#f59e0b",
            "arrow-scale": 1.4,
            opacity: 1.0,
            "z-index": 950,
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
      // Keeps fit-to-pattern from magnifying a two-node chain past readability.
      maxZoom: 1.5,
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

  // Highlight the pattern opened from the evidence timeline and zoom to it.
  const focusRowKey = focusRowIds.join(",");
  const focusNodeKey = focusNodeIds.join(",");
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const rowSet = new Set(focusRowKey ? focusRowKey.split(",") : []);
    const nodeSet = new Set(focusNodeKey ? focusNodeKey.split(",") : []);

    cy.elements().removeClass("focus-dim focus-hit");
    if (rowSet.size === 0 && nodeSet.size === 0) {
      // Focus cleared - return to the whole network rather than staying zoomed in.
      cy.animate({ fit: { eles: cy.elements(), padding: 30 } }, { duration: 300 });
      return;
    }

    const focusEdges = cy.edges().filter((e) => rowSet.has(String(e.data("row_id"))));
    const focused = focusEdges
      .union(cy.nodes().filter((n) => nodeSet.has(n.id())))
      .union(focusEdges.connectedNodes());

    if (focused.length === 0) return;

    cy.elements().not(focused).addClass("focus-dim");
    focused.addClass("focus-hit");
    cy.animate({ fit: { eles: focused, padding: 60 } }, { duration: 400 });
  }, [focusRowKey, focusNodeKey, nodes, edges]);

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
    <div className="relative h-full min-h-[350px] w-full bg-[radial-gradient(circle_at_1px_1px,rgb(203_213_225/0.55)_1px,transparent_0)] [background-size:22px_22px]">
      <div ref={containerRef} className="h-full w-full" />

      {/* Floating canvas controls */}
      <div className="absolute bottom-3 right-3 z-10 flex items-center gap-0.5 rounded-lg border border-ink-200 bg-white/95 p-1 shadow-raised backdrop-blur">
        <button
          onClick={handleZoomIn}
          title="Zoom in"
          className="h-7 w-7 rounded-md text-sm font-bold text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
        >
          +
        </button>
        <button
          onClick={handleZoomOut}
          title="Zoom out"
          className="h-7 w-7 rounded-md text-sm font-bold text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
        >
          −
        </button>
        <span className="mx-0.5 h-4 w-px bg-ink-200" />
        <button
          onClick={handleFit}
          title="Fit graph to screen"
          className="h-7 rounded-md px-2 text-[11px] font-medium text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900"
        >
          Fit
        </button>
      </div>

      <p className="pointer-events-none absolute bottom-4 left-4 z-10 text-[10px] font-medium text-ink-400">
        Scroll to zoom · drag to pan · click a node or edge for detail
      </p>
    </div>
  );
}
