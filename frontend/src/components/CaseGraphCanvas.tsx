import { useEffect, useRef } from "react";
import cytoscape, { Core, ElementDefinition } from "cytoscape";
import { CaseGraphEdge, CaseGraphNode } from "../lib/api";

type CaseGraphCanvasProps = {
  nodes: CaseGraphNode[];
  edges: CaseGraphEdge[];
  selectedNodeId: string | null;
  selectedFindingEdgeIds: string[];
  onNodeClick: (nodeId: string) => void;
};

const riskClass = (node: CaseGraphNode) => (node.risk_tier === "high" ? "risk-high" : "risk-normal");

function edgeWidth(amount: number, maxAmount: number) {
  return 1.5 + Math.sqrt(Math.max(amount, 0) / Math.max(maxAmount, 1)) * 5;
}

export function CaseGraphCanvas({
  nodes,
  edges,
  selectedNodeId,
  selectedFindingEdgeIds,
  onNodeClick,
}: CaseGraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;

  useEffect(() => {
    if (!containerRef.current) return;

    const knownIds = new Set(nodes.map((node) => node.id));
    const safeEdges = edges.filter((edge) => knownIds.has(edge.source) && knownIds.has(edge.target));
    const maxAmount = Math.max(...safeEdges.map((edge) => edge.amount), 1);
    const elements: ElementDefinition[] = [
      ...nodes.map((node) => ({
        data: { id: node.id, label: node.label, kind: node.kind, risk: node.risk_tier },
        classes: `${node.kind === "subject_account" ? "node-subject" : "node-counterparty"} ${riskClass(node)}`,
      })),
      ...safeEdges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          amount: edge.amount,
          label: `₹${Math.round(edge.amount).toLocaleString("en-IN")}`,
          finding: edge.is_finding_edge,
        },
        classes: edge.is_finding_edge ? "edge-finding" : "edge-evidence",
        style: { width: edgeWidth(edge.amount, maxAmount) },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 7,
            color: "#1e293b",
            "font-size": "11px",
            "font-weight": 600,
            "font-family": "Inter, system-ui, sans-serif",
            "text-outline-width": 3,
            "text-outline-color": "#ffffff",
            "text-wrap": "ellipsis",
            "text-max-width": "135px",
            "border-width": 2,
          },
        },
        { selector: "node.node-subject", style: { shape: "round-rectangle", width: 76, height: 48 } },
        { selector: "node.node-counterparty", style: { shape: "ellipse", width: 54, height: 54 } },
        { selector: "node.risk-high", style: { "background-color": "#dc2626", "border-color": "#991b1b" } },
        { selector: "node.risk-normal", style: { "background-color": "#2563eb", "border-color": "#1d4ed8" } },
        {
          selector: "node:selected",
          style: { "border-color": "#f59e0b", "border-width": 5, "overlay-opacity": 0, "z-index": 100 },
        },
        {
          selector: "edge",
          style: {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.9,
            "line-cap": "round",
            "text-rotation": "autorotate",
            "font-size": "9px",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.86,
            "text-background-padding": "2px",
            "text-margin-y": -8,
          },
        },
        {
          selector: "edge.edge-evidence",
          style: { "line-color": "#94a3b8", "target-arrow-color": "#94a3b8", opacity: 0.58 },
        },
        {
          selector: "edge.edge-finding",
          style: { "line-color": "#dc2626", "target-arrow-color": "#dc2626", opacity: 0.92 },
        },
        {
          selector: ".finding-selected",
          style: {
            "line-style": "dashed",
            "line-color": "#f59e0b",
            "target-arrow-color": "#f59e0b",
            "line-dash-pattern": [10, 7],
            "line-dash-offset": 0,
            opacity: 1,
            "z-index": 90,
          },
        },
        { selector: ".finding-dim", style: { opacity: 0.1, "text-opacity": 0.08 } },
      ],
      layout: {
        name: "cose",
        animate: false,
        randomize: false,
        fit: true,
        padding: 42,
        nodeRepulsion: () => 700000,
        idealEdgeLength: () => 150,
      },
      maxZoom: 1.75,
    });
    cyRef.current = cy;
    cy.on("tap", "node", (event) => onNodeClickRef.current(event.target.id()));

    const resize = () => {
      cy.resize();
      cy.fit(undefined, 42);
    };
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observer?.observe(containerRef.current);
    window.addEventListener("resize", resize);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", resize);
      cy.destroy();
      cyRef.current = null;
    };
  }, [nodes, edges]);

  const selectedEdgeKey = selectedFindingEdgeIds.join(",");
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const selectedIds = new Set(selectedEdgeKey ? selectedEdgeKey.split(",") : []);
    cy.elements().removeClass("finding-selected finding-dim");
    if (!selectedIds.size) {
      cy.fit(undefined, 42);
      return;
    }
    const selected = cy.edges().filter((edge) => selectedIds.has(edge.id()));
    const involved = selected.union(selected.connectedNodes());
    cy.elements().not(involved).addClass("finding-dim");
    selected.addClass("finding-selected");
    cy.fit(involved, 70);

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let offset = 0;
    let frame = 0;
    const animate = () => {
      offset = (offset - 0.7) % 34;
      selected.style("line-dash-offset", offset);
      frame = window.requestAnimationFrame(animate);
    };
    frame = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(frame);
  }, [selectedEdgeKey]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.$(":selected").unselect();
    if (selectedNodeId) cy.$id(selectedNodeId).select();
  }, [selectedNodeId]);

  return (
    <div className="relative h-full min-h-[440px] w-full bg-[radial-gradient(circle_at_1px_1px,rgb(203_213_225/0.6)_1px,transparent_0)] [background-size:22px_22px]">
      <div ref={containerRef} className="h-full w-full" />
      <p className="pointer-events-none absolute bottom-4 left-4 text-[10px] font-medium text-ink-400">
        Shapes identify account observations · colour shows risk · edge width shows value
      </p>
    </div>
  );
}
