import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { GitGraph, LayoutDashboard, Search, Upload, ArrowRight } from "lucide-react";
import { api, GraphData } from "../lib/api";
import { ProofGraphCanvas } from "../components/ProofGraphCanvas";
import { useStatement } from "../lib/StatementContext";

export function ProofGraphPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentId, setCurrentId, statements } = useStatement();

  const effectiveId = id ? Number(id) : currentId;

  const [graph, setGraph] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [mode, setMode] = useState<"single" | "merged">("single");

  useEffect(() => {
    if (id && Number(id) !== currentId) {
      setCurrentId(Number(id));
    }
  }, [id, currentId, setCurrentId]);

  useEffect(() => {
    if (mode === "merged") {
      const ids = statements.map((s) => s.id);
      if (ids.length >= 2) {
        setLoading(true);
        api.batchMerge(ids)
          .then(setGraph)
          .catch(() => setGraph(null))
          .finally(() => setLoading(false));
        return;
      }
    }

    if (!effectiveId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api.getGraph(effectiveId)
      .then(setGraph)
      .catch(() => setGraph(null))
      .finally(() => setLoading(false));
  }, [effectiveId, mode, statements]);

  if (loading) return (
    <div className="p-8 flex items-center gap-3 text-gray-500">
      <GitGraph className="w-5 h-5 animate-pulse text-purple-600" /> Loading transaction graph...
    </div>
  );

  if (!effectiveId || !graph) {
    return (
      <div className="p-4 sm:p-6 max-w-4xl mx-auto">
        <div className="bg-white border rounded-xl p-6 sm:p-8 text-center shadow-sm space-y-4">
          <GitGraph className="w-12 h-12 mx-auto text-gray-400" />
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              {!effectiveId ? "No Statement Selected" : `Transaction Graph Not Available for Statement #${effectiveId}`}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              {!effectiveId
                ? "Select a statement from history or upload a new statement."
                : "Confirm the extraction and run analysis first to build the transaction graph."}
            </p>
          </div>

          {effectiveId && (
            <div>
              <button
                onClick={() => navigate(`/review/${effectiveId}`)}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 shadow-sm transition-colors"
              >
                Review & Confirm Extraction <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {statements.length > 0 && (
            <div className="mt-6 pt-6 border-t text-left">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Available Statements</h3>
              <div className="max-w-md mx-auto border rounded-lg divide-y bg-gray-50/50">
                {statements.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      setCurrentId(s.id);
                      navigate(`/graph/${s.id}`);
                    }}
                    className="w-full p-3 text-left hover:bg-blue-50/50 flex items-center justify-between text-xs transition-colors"
                  >
                    <div className="truncate mr-2">
                      <span className="font-semibold text-gray-800">#{s.id}: {s.original_filename}</span>
                      <p className="text-[11px] text-gray-500 mt-0.5">{s.transaction_count || 0} txns · {s.tier || s.status}</p>
                    </div>
                    <span className="text-purple-600 font-semibold shrink-0">View Graph →</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-4 py-2 border rounded-lg text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <Upload className="w-3.5 h-3.5" /> Upload New Statement
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const subjectNode = graph.nodes.find((n) => n.id === "ACCT_SUBJECT");
  const selectedNodeData = graph.nodes.find((n) => n.id === selectedNode);
  const selectedEdgeData = graph.edges.find((e) => e.row_id === selectedEdge);

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Proof Graph</h1>
            <span className="text-xs bg-purple-100 text-purple-800 font-bold px-2 py-0.5 rounded">
              Statement #{effectiveId}
            </span>
          </div>
          <p className="text-gray-500 text-xs sm:text-sm mt-1">Interactive transaction flow network with cycle highlighting</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {mode === "single" ? (
            <button onClick={() => setMode("merged")} className="px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-gray-50 bg-white shadow-sm transition-colors">
              Merged View
            </button>
          ) : (
            <button onClick={() => setMode("single")} className="px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-gray-50 bg-white shadow-sm transition-colors">
              Single Account
            </button>
          )}
          <Link
            to={`/dashboard/${effectiveId}`}
            className="px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-gray-50 bg-white flex items-center gap-1.5 shadow-sm transition-colors"
          >
            <LayoutDashboard className="w-3.5 h-3.5 text-blue-600" /> Dashboard
          </Link>
          <Link
            to={`/evidence/${effectiveId}`}
            className="px-3 py-1.5 text-xs font-medium border rounded-lg hover:bg-gray-50 bg-white flex items-center gap-1.5 shadow-sm transition-colors"
          >
            <Search className="w-3.5 h-3.5 text-blue-600" /> Evidence
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3">
          <div className="bg-white border rounded-xl overflow-hidden shadow-sm h-[50vh] sm:h-[60vh] lg:h-[620px] min-h-[380px]">
            <ProofGraphCanvas
              nodes={graph.nodes}
              edges={graph.edges}
              cycles={graph.cycles}
              muleRowIds={graph.mule_row_ids}
              muleNodes={graph.mule_nodes}
              selectedNode={selectedNode}
              selectedEdge={selectedEdge}
              onNodeClick={(nodeId) => {
                setSelectedNode(nodeId);
                setSelectedEdge(null);
              }}
              onEdgeClick={(edgeRowId) => {
                setSelectedEdge(edgeRowId);
                setSelectedNode(null);
              }}
            />
          </div>
        </div>
        <div className="space-y-3">
          <div className="bg-white border rounded-xl p-4 shadow-sm">
            <h3 className="font-semibold text-sm text-gray-800 mb-2">Graph Summary</h3>
            <div className="text-xs text-gray-600 space-y-1.5">
              <p className="flex justify-between"><span>Entities (Nodes):</span> <strong>{graph.nodes.length}</strong></p>
              <p className="flex justify-between"><span>Transfers (Edges):</span> <strong>{graph.edges.length}</strong></p>
              <p className="flex justify-between"><span>Circular Flows:</span> <strong>{graph.cycles.length}</strong></p>
              {subjectNode && typeof subjectNode.flow === "number" && (
                <p className="flex justify-between">
                  <span>Total Volume:</span> <strong>₹{subjectNode.flow.toFixed(2)}</strong>
                </p>
              )}
            </div>
          </div>

          {graph.cycles && graph.cycles.length > 0 && (
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <h3 className="font-semibold text-sm text-gray-800 mb-2">Detected Cycles</h3>
              <div className="space-y-2">
                {graph.cycles.map((c) => (
                  <div key={c.cycle_id} className="text-xs border border-red-200 bg-red-50/80 rounded-lg p-2.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-red-800 font-mono">{c.cycle_id}</span>
                      <span className="bg-red-100 text-red-700 px-1.5 py-0.5 rounded text-[10px] font-bold">
                        Risk: {c.cycle_risk_score != null ? ((c.cycle_risk_score as number) * 100).toFixed(0) : "0"}%
                      </span>
                    </div>
                    <p className="text-gray-700 mt-1 font-mono text-[11px] font-medium">{c.nodes ? c.nodes.join(" → ") : ""}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {selectedNodeData && (
            <div className="bg-blue-50/80 border border-blue-200 rounded-xl p-3.5 text-xs shadow-sm">
              <h3 className="font-semibold text-blue-900">Selected Node</h3>
              <p className="font-medium mt-1 text-gray-800">{selectedNodeData.label}</p>
              <p className="text-gray-600 mt-0.5">
                Total Transfer Flow: ₹{typeof selectedNodeData.flow === "number" ? selectedNodeData.flow.toFixed(2) : "0.00"}
              </p>
            </div>
          )}

          {selectedEdgeData && (
            <div className="bg-blue-50/80 border border-blue-200 rounded-xl p-3.5 text-xs shadow-sm">
              <h3 className="font-semibold text-blue-900">Selected Transaction</h3>
              <p className="font-mono text-gray-700 mt-1">Row: {selectedEdgeData.row_id}</p>
              <p className="font-bold text-blue-700 text-sm mt-0.5">
                ₹{typeof selectedEdgeData.amount === "number" ? selectedEdgeData.amount.toFixed(2) : "0.00"}
              </p>
              <p className="text-gray-500">Channel: {selectedEdgeData.channel || "N/A"}</p>
            </div>
          )}

          <div className="bg-gray-50 border rounded-xl p-3.5 text-xs text-gray-600 space-y-2 shadow-sm">
            <p className="font-semibold text-gray-800 mb-1">Graph Legend</p>
            <p className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 bg-purple-600 rounded-full shadow-sm" />
              <span><strong>Account Entity</strong> (Purple)</span>
            </p>
            <p className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 bg-blue-500 rounded-full shadow-sm" />
              <span><strong>Counterparty Node</strong> (Blue)</span>
            </p>
            <p className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 bg-red-500 rounded-full ring-2 ring-red-300 shadow-sm" />
              <span className="text-red-700 font-semibold">Mule Node / Cycle Entity (Red Bold)</span>
            </p>
            <p className="flex items-center gap-2">
              <span className="inline-block w-5 h-1 bg-red-500 rounded align-middle" />
              <span className="text-red-700 font-semibold">Mule Transaction (Bold Red Flow)</span>
            </p>
            <p className="flex items-center gap-2">
              <span className="inline-block w-5 h-0.5 bg-slate-500 align-middle" />
              <span className="text-gray-600">Regular Transaction Flow (Slate)</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
