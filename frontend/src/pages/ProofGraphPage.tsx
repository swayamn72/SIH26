import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import {
  GitGraph,
  LayoutDashboard,
  Search,
  Upload,
  ArrowRight,
  Crosshair,
  X,
  Clock,
  Layers,
  Network,
  Repeat,
} from "lucide-react";
import { api, GraphData, SuspiciousPattern } from "../lib/api";
import { ProofGraphCanvas } from "../components/ProofGraphCanvas";
import { useStatement } from "../lib/StatementContext";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  LinkButton,
  LoadingPanel,
  MetaItem,
  PageHeader,
  SeverityBadge,
  TierBadge,
  money,
} from "../components/ui";

export function ProofGraphPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentId, setCurrentId, statements } = useStatement();

  const effectiveId = id ? Number(id) : currentId;

  const [searchParams, setSearchParams] = useSearchParams();
  const focusId = searchParams.get("focus");

  const [graph, setGraph] = useState<GraphData | null>(null);
  const [patterns, setPatterns] = useState<SuspiciousPattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [mode, setMode] = useState<"single" | "merged">("single");

  const setFocus = (patternId: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (patternId) {
      next.set("focus", patternId);
    } else {
      next.delete("focus");
    }
    setSearchParams(next, { replace: true });
  };

  useEffect(() => {
    if (id && Number(id) !== currentId) {
      setCurrentId(Number(id));
    }
  }, [id, currentId, setCurrentId]);

  useEffect(() => {
    let cancelled = false;
    setSelectedNode(null);
    setSelectedEdge(null);
    setLoadError(null);

    const loadGraph = async () => {
      try {
        setLoading(true);
        if (mode === "merged") {
          const ids = statements.map((s) => s.id);
          if (ids.length < 2) {
            if (!cancelled) setGraph(null);
            return;
          }
          const result = await api.batchMerge(ids);
          if (!cancelled) setGraph(result);
          return;
        }

        if (!effectiveId) {
          if (!cancelled) setGraph(null);
          return;
        }

        const result = await api.getGraph(effectiveId);
        if (!cancelled) setGraph(result);
      } catch (error) {
        if (!cancelled) {
          setGraph(null);
          setLoadError(error instanceof Error ? error.message : "Unable to load the transaction graph.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadGraph();
    return () => {
      cancelled = true;
    };
  }, [effectiveId, mode, statements]);

  // Pattern timelines back the "View in Proof Graph" deep links (?focus=<pattern_id>).
  useEffect(() => {
    if (!effectiveId || mode === "merged") {
      setPatterns([]);
      return;
    }
    api
      .getPatterns(effectiveId)
      .then((res) => setPatterns(res.patterns || []))
      .catch(() => setPatterns([]));
  }, [effectiveId, mode]);

  const focusPattern = useMemo(
    () => patterns.find((p) => p.pattern_id === focusId) || null,
    [patterns, focusId],
  );

  if (loading) return <LoadingPanel label="Loading transaction graph" />;

  if (!effectiveId || !graph || graph.nodes.length === 0) {
    const hasEmptyGraph = !!graph && graph.nodes.length === 0;
    return (
      <div className="animate-fade-in">
        <PageHeader
          eyebrow={<Badge tone="info" dot>Step 5 · Network</Badge>}
          title="Proof Graph"
          description="The fund-flow network behind the case, with mule paths and circular flows highlighted."
        />
        <div className="p-4 sm:p-6">
          <EmptyState
            icon={GitGraph}
            title={
              loadError
                ? "Unable to load the graph"
                : hasEmptyGraph
                  ? `No transactions available for case #${effectiveId}`
                  : effectiveId
                    ? `No graph for case #${effectiveId}`
                    : "No case selected"
            }
            description={
              loadError
                ? `${loadError} Check the API connection and try again.`
                : effectiveId
                  ? "Confirm the extraction and run analysis first to build the transaction graph."
                  : "Select a case below, or upload a new statement."
            }
            actions={
              effectiveId ? (
                <Button
                  variant="primary"
                  size="md"
                  icon={ArrowRight}
                  onClick={() => navigate(`/review/${effectiveId}`)}
                >
                  Review & analyse
                </Button>
              ) : (
                <LinkButton to="/" variant="primary" size="md" icon={Upload}>
                  Go to upload
                </LinkButton>
              )
            }
          >
            {statements.length > 0 && (
              <>
                <p className="label-micro mb-2">Available cases</p>
                <div className="divide-y divide-ink-100 overflow-hidden rounded-lg border border-ink-100 bg-white">
                  {statements.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => {
                        setCurrentId(s.id);
                        navigate(`/graph/${s.id}`);
                      }}
                      className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition-colors hover:bg-brand-50/60"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-[13px] font-medium text-ink-800">
                          #{s.id} · {s.original_filename}
                        </span>
                        <span className="num text-[11px] text-ink-400">
                          {s.transaction_count || 0} transactions
                        </span>
                      </span>
                      <TierBadge tier={s.tier} score={s.fused_score} />
                    </button>
                  ))}
                </div>
              </>
            )}
          </EmptyState>
        </div>
      </div>
    );
  }

  const subjectNode = graph.nodes.find((n) => n.id.startsWith("ACCT_"));
  const selectedNodeData = graph.nodes.find((n) => n.id === selectedNode);
  const selectedEdgeData = graph.edges.find((e) => e.row_id === selectedEdge);

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={
          <>
            <Badge tone="info" dot>Step 5 · Network</Badge>
            <Badge tone="neutral" mono>
              {mode === "merged" ? "MERGED VIEW" : `CASE #${effectiveId}`}
            </Badge>
          </>
        }
        title="Proof Graph"
        description="Interactive fund-flow network. Click any node or edge to inspect it; open a pattern to isolate its hops."
        meta={
          <>
            <MetaItem label="Entities" value={graph.nodes.length} icon={Network} />
            <MetaItem label="Transfers" value={graph.edges.length} icon={Layers} />
            <MetaItem label="Circular flows" value={graph.cycles.length} icon={Repeat} />
          </>
        }
        actions={
          <>
            {mode === "single" ? (
              <Button icon={Layers} onClick={() => setMode("merged")}>
                Merged view
              </Button>
            ) : (
              <Button icon={Layers} onClick={() => setMode("single")}>
                Single case
              </Button>
            )}
            <LinkButton to={`/dashboard/${effectiveId}`} icon={LayoutDashboard}>
              Dashboard
            </LinkButton>
            <LinkButton to={`/evidence/${effectiveId}`} icon={Search}>
              Evidence
            </LinkButton>
          </>
        }
      />

      <div className="mx-auto max-w-[1500px] space-y-4 p-4 sm:p-6">
        {focusId && (
          <Card
            accent={focusPattern ? "warning" : undefined}
            className={focusPattern ? "border-amber-200 bg-amber-50/60" : ""}
          >
            <div className="p-3.5">
              {focusPattern ? (
                <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Crosshair className="h-4 w-4 shrink-0 text-amber-600" />
                      <span className="text-[12px] font-bold uppercase tracking-wide text-amber-900">
                        Focused on pattern
                      </span>
                      <span className="font-mono text-[10px] text-amber-700">
                        {focusPattern.pattern_id}
                      </span>
                      <SeverityBadge
                        severity={focusPattern.severity}
                        suffix={` · risk ${(focusPattern.risk_score * 100).toFixed(0)}%`}
                      />
                    </div>
                    <p className="mt-1.5 text-[14px] font-semibold text-ink-900">
                      {focusPattern.title}
                    </p>
                    <p className="mt-0.5 font-mono text-[11px] text-ink-600">
                      {focusPattern.node_path.map((n) => n.label).join(" → ")}
                    </p>
                    <p className="num mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-ink-500">
                      <Clock className="h-3 w-3" />
                      {focusPattern.hops.length} highlighted transfers ·{" "}
                      {money(focusPattern.total_amount)} · {focusPattern.span_days.toFixed(2)} days
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <LinkButton to={`/evidence/${effectiveId}`} icon={Search}>
                      Back to timeline
                    </LinkButton>
                    <Button icon={X} onClick={() => setFocus(null)}>
                      Clear focus
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-[12px] text-ink-500">
                    Pattern <span className="font-mono">{focusId}</span>{" "}
                    {patterns.length === 0
                      ? "is still loading, or this case has no patterns."
                      : "was not found in this case's patterns."}
                  </p>
                  <Button onClick={() => setFocus(null)}>Clear</Button>
                </div>
              )}
            </div>
          </Card>
        )}

        <div className="grid gap-4 lg:grid-cols-4">
          <div className="lg:col-span-3">
            <Card className="h-[52vh] min-h-[400px] sm:h-[62vh] lg:h-[640px]">
              <ProofGraphCanvas
                nodes={graph.nodes}
                edges={graph.edges}
                cycles={graph.cycles}
                muleRowIds={graph.mule_row_ids}
                muleNodes={graph.mule_nodes}
                focusRowIds={focusPattern?.row_ids}
                focusNodeIds={focusPattern?.node_ids}
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
            </Card>
          </div>

          <div className="space-y-4">
            {patterns.length > 0 && (
              <Card>
                <CardHeader
                  title="Suspicious patterns"
                  description="Select one to isolate its hops on the graph."
                  icon={Crosshair}
                />
                <div className="scroll-slim max-h-72 space-y-1.5 overflow-y-auto p-3">
                  {patterns.map((p) => {
                    const active = p.pattern_id === focusId;
                    return (
                      <button
                        key={p.pattern_id}
                        onClick={() => setFocus(active ? null : p.pattern_id)}
                        className={`w-full rounded-lg border p-2.5 text-left transition-colors ${
                          active
                            ? "border-amber-300 bg-amber-50"
                            : "border-ink-100 bg-white hover:border-ink-200 hover:bg-ink-50"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-[12px] font-semibold text-ink-800">
                            {p.title}
                          </span>
                          <SeverityBadge severity={p.severity} />
                        </div>
                        <p className="mt-0.5 truncate font-mono text-[10px] text-ink-400">
                          {p.node_path.map((n) => n.label).join(" → ")}
                        </p>
                        <p className="num mt-0.5 text-[10px] text-ink-400">
                          {p.hops.length} hops · {money(p.total_amount)}
                        </p>
                      </button>
                    );
                  })}
                </div>
                <div className="border-t border-ink-100 px-3 py-2">
                  <LinkButton to={`/evidence/${effectiveId}`} variant="ghost" icon={ArrowRight}>
                    Open full evidence timeline
                  </LinkButton>
                </div>
              </Card>
            )}

            <Card>
              <CardHeader title="Graph summary" icon={Network} />
              <div className="space-y-2 p-4 text-[12px]">
                <p className="flex justify-between text-ink-500">
                  <span>Entities (nodes)</span>
                  <strong className="num text-ink-900">{graph.nodes.length}</strong>
                </p>
                <p className="flex justify-between text-ink-500">
                  <span>Transfers (edges)</span>
                  <strong className="num text-ink-900">{graph.edges.length}</strong>
                </p>
                <p className="flex justify-between text-ink-500">
                  <span>Circular flows</span>
                  <strong className="num text-ink-900">{graph.cycles.length}</strong>
                </p>
                {subjectNode && typeof subjectNode.flow === "number" && (
                  <p className="flex justify-between border-t border-ink-100 pt-2 text-ink-500">
                    <span>Total volume</span>
                    <strong className="num text-ink-900">{money(subjectNode.flow)}</strong>
                  </p>
                )}
              </div>
            </Card>

            {selectedNodeData && (
              <Card accent="info">
                <div className="p-3.5">
                  <p className="label-micro">Selected entity</p>
                  <p className="mt-1 text-[13px] font-semibold text-ink-900">
                    {selectedNodeData.label}
                  </p>
                  <p className="num mt-0.5 text-[12px] text-ink-500">
                    Total transfer flow {money(selectedNodeData.flow)}
                  </p>
                </div>
              </Card>
            )}

            {selectedEdgeData && (
              <Card accent="info">
                <div className="p-3.5">
                  <p className="label-micro">Selected transfer</p>
                  <p className="num mt-1 text-[16px] font-bold text-brand-700">
                    {money(selectedEdgeData.amount)}
                  </p>
                  <p className="mt-0.5 font-mono text-[11px] text-ink-400">
                    row {selectedEdgeData.row_id}
                  </p>
                  <p className="mt-0.5 text-[11px] uppercase tracking-wide text-ink-500">
                    {selectedEdgeData.channel || "channel n/a"}
                  </p>
                </div>
              </Card>
            )}

            <Card>
              <CardHeader title="Legend" />
              <div className="space-y-2 p-4 text-[11px] text-ink-600">
                <p className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-violet-600 ring-2 ring-violet-200" />
                  Subject account
                </p>
                <p className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-brand-500 ring-2 ring-brand-100" />
                  Counterparty
                </p>
                <p className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-red-500 ring-2 ring-red-200" />
                  Mule / cycle entity
                </p>
                <p className="flex items-center gap-2 border-t border-ink-100 pt-2">
                  <span className="inline-block h-1 w-5 rounded bg-red-500" />
                  Mule transfer
                </p>
                <p className="flex items-center gap-2">
                  <span className="inline-block h-0.5 w-5 rounded bg-ink-400" />
                  Regular transfer
                </p>
                <p className="flex items-center gap-2">
                  <span className="inline-block h-1 w-5 rounded bg-amber-500" />
                  Focused pattern hop
                </p>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
