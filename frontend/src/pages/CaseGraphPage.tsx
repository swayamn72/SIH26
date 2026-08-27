import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, ChevronLeft, ChevronRight, FileText, GitGraph, Network, RefreshCw, Route, X } from "lucide-react";
import { CaseGraphCanvas } from "../components/CaseGraphCanvas";
import { Badge, Button, Card, CardHeader, EmptyState, LoadingPanel, formatDate, money } from "../components/ui";
import {
  api,
  CaseFindingDetail,
  CaseGraph,
  CaseGraphNode,
  CaseNodeTransactionPage,
  InvestigationCase,
} from "../lib/api";

const TXN_PAGE_SIZE = 10;

function caseStatus(graph: CaseGraph) {
  const peak = Math.max(0, ...graph.findings.map((finding) => finding.risk_score));
  return peak >= 0.75 ? "Confirmed suspicious" : peak > 0 ? "Review required" : "No active finding";
}

function nodeKind(node: CaseGraphNode) {
  return node.kind === "subject_account" ? "Statement subject" : "Counterparty observation";
}

export function CaseGraphPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const id = Number(caseId);
  const [cases, setCases] = useState<InvestigationCase[]>([]);
  const [activeCase, setActiveCase] = useState<InvestigationCase | null>(null);
  const [graph, setGraph] = useState<CaseGraph | null>(null);
  const [finding, setFinding] = useState<CaseFindingDetail | null>(null);
  const [selectedNode, setSelectedNode] = useState<CaseGraphNode | null>(null);
  const [transactions, setTransactions] = useState<CaseNodeTransactionPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingDrawer, setLoadingDrawer] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reanalyzing, setReanalyzing] = useState(false);

  const loadCase = async () => {
    if (!Number.isFinite(id)) return;
    setLoading(true);
    setError(null);
    try {
      const [caseList, detail, graphPayload] = await Promise.all([api.listCases(), api.getCase(id), api.getCaseGraph(id)]);
      setCases(caseList);
      setActiveCase(detail);
      setGraph(graphPayload);
      const initialFinding = graphPayload.findings[0];
      setFinding(initialFinding ? await api.getCaseFinding(id, initialFinding.id) : null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load this investigation case.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCase();
    // The case id is the route's source of truth.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (!selectedNode || !Number.isFinite(id)) return;
    let cancelled = false;
    setLoadingDrawer(true);
    api
      .getCaseNodeTransactions(id, selectedNode.id, offset, TXN_PAGE_SIZE, finding?.id)
      .then((page) => {
        if (!cancelled) setTransactions(page);
      })
      .catch(() => {
        if (!cancelled) setTransactions(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingDrawer(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, selectedNode, offset, finding?.id]);

  const selectedFindingEdgeIds = finding?.edge_ids || [];
  const selectedPath = useMemo(
    () => finding?.node_sequence.map((nodeId) => graph?.nodes.find((node) => node.id === nodeId)?.label || "Observed entity").join(" → ") || "",
    [finding, graph?.nodes],
  );

  const selectNode = (nodeId: string) => {
    const node = graph?.nodes.find((item) => item.id === nodeId) || null;
    setSelectedNode(node);
    setOffset(0);
  };

  const selectFinding = async (findingId: string) => {
    if (!Number.isFinite(id)) return;
    try {
      const next = await api.getCaseFinding(id, findingId);
      setFinding(next);
      setOffset(0);
    } catch {
      setFinding(null);
    }
  };

  const reanalyze = async () => {
    if (!Number.isFinite(id)) return;
    setReanalyzing(true);
    try {
      await api.analyzeCase(id);
      await loadCase();
    } finally {
      setReanalyzing(false);
    }
  };

  if (loading) return <LoadingPanel label="Loading investigation case" />;
  if (error || !activeCase || !graph) {
    return (
      <div className="p-4 sm:p-6">
        <EmptyState
          icon={AlertTriangle}
          title="Unable to open case graph"
          description={error || "This investigation case no longer exists."}
          actions={<Button variant="primary" onClick={() => navigate("/")}>Back to cases</Button>}
        />
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <header className="border-b border-ink-100 bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-[1700px] flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link to="/" className="rounded-lg border border-ink-200 p-2 text-ink-500 hover:bg-ink-50" aria-label="Back to cases">
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="truncate text-[16px] font-semibold text-ink-950">{activeCase.name}</h1>
                <Badge tone={graph.findings.length ? "danger" : "neutral"} dot>{caseStatus(graph)}</Badge>
              </div>
              <p className="mt-0.5 text-[11px] text-ink-500">
                Case #{activeCase.id} · {activeCase.statement_ids.length} statements · analysis v{activeCase.analysis_version}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select
              aria-label="Select investigation case"
              value={activeCase.id}
              onChange={(event) => navigate(`/cases/${event.target.value}/graph`)}
              className="h-8 max-w-48 rounded-lg border border-ink-200 bg-white px-2 text-xs text-ink-700"
            >
              {cases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
            <Link to={`/cases/${id}/findings`} className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-ink-200 bg-white px-2.5 text-xs font-medium text-ink-700 shadow-card hover:bg-ink-50">
              <FileText className="h-3.5 w-3.5" /> SAR/STR draft
            </Link>
            <Button icon={RefreshCw} disabled={reanalyzing} onClick={reanalyze}>{reanalyzing ? "Analysing…" : "Reanalyse"}</Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1700px] gap-4 p-4 sm:p-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card className="min-h-[650px]">
          <CardHeader
            title="Fund-flow network"
            description="Selected findings isolate their ordered path. Arrow direction follows the observed money movement."
            icon={GitGraph}
            actions={<Badge tone="info">{graph.nodes.length} entities · {graph.edges.length} transfers</Badge>}
          />
          <div className="h-[620px]">
            <CaseGraphCanvas
              nodes={graph.nodes}
              edges={graph.edges}
              selectedNodeId={selectedNode?.id || null}
              selectedFindingEdgeIds={selectedFindingEdgeIds}
              onNodeClick={selectNode}
            />
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-ink-100 px-4 py-2 text-[10px] text-ink-500">
            <span><b className="text-red-600">Red</b> high-risk entity</span>
            <span><b className="text-brand-600">Blue</b> observed entity</span>
            <span><b>Rectangle</b> statement subject</span>
            <span><b>Circle</b> counterparty observation</span>
            <span><b className="text-amber-600">Dashed amber</b> selected finding path</span>
          </div>
        </Card>

        <aside className="space-y-4">
          <Card>
            <CardHeader title="Findings" description="Choose a path to isolate its evidence hops." icon={Route} />
            <div className="space-y-2 p-3">
              {graph.findings.length === 0 ? (
                <p className="rounded-lg border border-dashed border-ink-200 p-3 text-xs text-ink-500">No conserved multi-hop path has been detected in this case.</p>
              ) : graph.findings.map((item) => {
                const active = item.id === finding?.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => void selectFinding(item.id)}
                    className={`w-full rounded-lg border p-3 text-left transition-colors ${active ? "border-amber-300 bg-amber-50" : "border-ink-100 hover:border-ink-300 hover:bg-ink-50"}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-ink-900">{item.hop_count}-hop conserved flow</span>
                      <Badge tone="danger">Risk {Math.round(item.risk_score * 100)}</Badge>
                    </div>
                    <p className="mt-1 text-[11px] text-ink-500">{item.edge_ids.length} linked transfers · {item.source_row_ids.length} source rows</p>
                  </button>
                );
              })}
            </div>
          </Card>

          {finding && (
            <Card accent="warning">
              <CardHeader title="Ordered hops" description={selectedPath} icon={Network} />
              <div className="space-y-0 p-3">
                {finding.ordered_hops.map((hop, index) => {
                  const source = graph.nodes.find((node) => node.id === hop.source)?.label || "Observed entity";
                  const target = graph.nodes.find((node) => node.id === hop.target)?.label || "Observed entity";
                  return (
                    <button key={hop.edge_id} className="group flex w-full gap-2 border-l border-amber-200 pb-3 pl-3 text-left last:pb-0" onClick={() => selectNode(hop.target)}>
                      <span className="-ml-[21px] flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-500 text-[9px] font-bold text-white">{index + 1}</span>
                      <span className="min-w-0">
                        <span className="block truncate text-[11px] font-semibold text-ink-800">{source} → {target}</span>
                        <span className="num block text-[10px] text-ink-500">{money(hop.amount)} · {formatDate(hop.txn_date)}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
              <div className="border-t border-amber-100 px-3 py-2 text-[10px] text-amber-800">
                <b>Formula:</b> {String(finding.detail.formula || "Evidence-backed conserved flow.")}
                {(finding.detail.limitations || []).map((limitation) => <p key={limitation} className="mt-1">Limitation: {limitation}</p>)}
                <Link
                  to={`/cases/${id}/findings/${encodeURIComponent(finding.id)}/sar-draft`}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-white px-2 py-1.5 text-[11px] font-semibold text-amber-900 hover:bg-amber-100"
                >
                  <FileText className="h-3.5 w-3.5" /> Open SAR/STR draft
                </Link>
              </div>
            </Card>
          )}

          <Card>
            <CardHeader title="Evidence boundaries" icon={FileText} />
            <ul className="space-y-1.5 p-3 text-[11px] leading-relaxed text-ink-500">
              {graph.limitations.map((limitation) => <li key={limitation}>• {limitation}</li>)}
            </ul>
          </Card>
        </aside>
      </div>

      {selectedNode && (
        <div className="fixed inset-y-0 right-0 z-[60] flex w-full max-w-[460px] flex-col border-l border-ink-200 bg-white shadow-2xl" role="dialog" aria-label="Node transaction evidence">
          <header className="flex items-start justify-between gap-3 border-b border-ink-100 px-5 py-4">
            <div className="min-w-0">
              <p className="label-micro">{nodeKind(selectedNode)}</p>
              <h2 className="mt-1 truncate text-[15px] font-semibold text-ink-950">{selectedNode.label}</h2>
              <p className="mt-1 text-[11px] text-ink-500">{selectedNode.institution || "Institution unavailable"} · source-backed transaction rows</p>
            </div>
            <button onClick={() => setSelectedNode(null)} className="rounded-lg p-2 text-ink-400 hover:bg-ink-100 hover:text-ink-700" aria-label="Close transaction drawer"><X className="h-4 w-4" /></button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {loadingDrawer ? <p className="text-xs text-ink-500">Loading transaction evidence…</p> : !transactions?.items.length ? (
              <p className="rounded-lg border border-dashed border-ink-200 p-3 text-xs text-ink-500">No matching source rows are available for this selection.</p>
            ) : transactions.items.map((item) => (
              <article key={`${item.edge_id}-${item.row_id}`} className="mb-2 rounded-lg border border-ink-100 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div><p className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">{item.direction} transfer</p><p className="num mt-1 text-sm font-bold text-ink-950">{money(item.amount)}</p></div>
                  <span className="text-[10px] text-ink-400">{formatDate(item.txn_date)}</span>
                </div>
                <p className="mt-2 text-xs text-ink-700">{item.narration || "Narration unavailable"}</p>
                <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] text-ink-500">
                  <span className="truncate" title={item.source_filename || ""}>Source: {item.source_filename || "Unavailable"}</span>
                  <span className="truncate">Row: {item.row_id}</span>
                  <span className="truncate">Statement #{item.statement_id}</span>
                  <span className="truncate">Ref: {item.reference_no || "Unavailable"}</span>
                </div>
              </article>
            ))}
          </div>
          <footer className="flex items-center justify-between border-t border-ink-100 px-4 py-3">
            <span className="text-[11px] text-ink-500">{transactions ? `${transactions.total} source rows` : ""}</span>
            <div className="flex gap-2">
              <Button icon={ChevronLeft} disabled={!transactions || offset === 0} onClick={() => setOffset(Math.max(0, offset - TXN_PAGE_SIZE))}>Previous</Button>
              <Button icon={ChevronRight} disabled={!transactions || offset + TXN_PAGE_SIZE >= transactions.total} onClick={() => setOffset(offset + TXN_PAGE_SIZE)}>Next</Button>
            </div>
          </footer>
        </div>
      )}
    </div>
  );
}
