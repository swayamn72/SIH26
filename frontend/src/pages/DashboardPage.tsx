import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import {
  LayoutDashboard,
  GitGraph,
  Search,
  FileText,
  Upload,
  ArrowRight,
  ShieldAlert,
  Repeat,
  Table2,
  SlidersHorizontal,
  Calendar,
  Database,
} from "lucide-react";
import { RuleTriggerList } from "../components/RuleTriggerList";
import { TransactionTable } from "../components/TransactionTable";
import { NarrativePanel } from "../components/NarrativePanel";
import { WhyFlaggedPanel } from "../components/WhyFlaggedPanel";
import { api, EvidenceBundle, PagedTransactions, WhyFlagged } from "../lib/api";
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
  ProgressBar,
  TierBadge,
  formatDate,
} from "../components/ui";

type FeatureRow = {
  name: string;
  value: unknown;
  formula?: unknown;
  explanation?: unknown;
  family?: unknown;
};

const FAMILY_LABEL: Record<string, string> = {
  lifecycle: "Account lifecycle",
  behavior: "Balance behaviour",
  velocity: "Velocity",
  structuring: "Amount structuring",
  network: "Counterparty network",
  identity: "Identity proxies",
  graph: "Graph",
};

/** Ratio-style features (0–1) get a bar; absolute magnitudes just show the number. */
function FeatureGrid({ features }: { features: FeatureRow[] }) {
  const grouped = features.reduce<Record<string, FeatureRow[]>>((acc, f) => {
    const family = String(f.family || "other");
    (acc[family] ||= []).push(f);
    return acc;
  }, {});

  const families = Object.keys(grouped).sort();

  return (
    <div className="space-y-4">
      {families.map((family) => (
        <div key={family}>
          <p className="label-micro mb-2">{FAMILY_LABEL[family] || family}</p>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {(grouped[family] || []).map((f) => {
              const num = typeof f.value === "number" ? f.value : null;
              // Only genuine 0–1 proportions get a percentage bar; counts like
              // dormancy_breaks would otherwise read as "100%".
              const isRatio =
                num != null && num >= 0 && num <= 1 && /(_ratio|_score|_hhi)$/.test(f.name);
              return (
                <div
                  key={f.name}
                  className="rounded-lg border border-ink-100 bg-white p-2.5"
                  title={String(f.formula || "")}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span
                      className="truncate font-mono text-[11px] text-ink-500"
                      title={f.name}
                    >
                      {f.name}
                    </span>
                    <span className="num shrink-0 text-[13px] font-semibold text-ink-900">
                      {num != null ? (isRatio ? `${(num * 100).toFixed(1)}%` : num.toFixed(2)) : "—"}
                    </span>
                  </div>
                  {isRatio && <ProgressBar value={num * 100} className="mt-1.5" tone="info" />}
                  {!!f.explanation && (
                    <p className="mt-1 truncate text-[10px] text-ink-400">{String(f.explanation)}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentId, setCurrentId, statements, currentStatement } = useStatement();

  const effectiveId = id ? Number(id) : currentId;

  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [whyFlagged, setWhyFlagged] = useState<WhyFlagged | null>(null);
  const [narrative, setNarrative] = useState<{ text: string; source: string } | null>(null);
  const [transactions, setTransactions] = useState<PagedTransactions>({
    rows: [],
    total: 0,
    page: 1,
    page_size: 100,
  });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (id && Number(id) !== currentId) {
      setCurrentId(Number(id));
    }
  }, [id, currentId, setCurrentId]);

  useEffect(() => {
    setPage(1);
  }, [effectiveId]);

  useEffect(() => {
    if (!effectiveId) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    setLoadError(null);
    setBundle(null);
    setWhyFlagged(null);
    setNarrative(null);

    Promise.all([
      api.getEvidence(effectiveId),
      api.getTransactions(effectiveId, page),
      api.getWhyFlagged(effectiveId).catch(() => null),
    ])
      .then(([evBundle, txns, why]) => {
        if (cancelled) return;
        setBundle(evBundle);
        setTransactions(txns);
        setWhyFlagged(why);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Unable to load this case.";
        setLoadError(message);
        setNotFound(message.includes("API 404"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    // Narrative generation is slow — let it land on its own.
    api
      .getNarrative(effectiveId)
      .then((narr) => {
        if (!cancelled) setNarrative(narr);
      })
      .catch(() => null);

    return () => {
      cancelled = true;
    };
  }, [effectiveId, page]);

  if (loading) return <LoadingPanel label="Loading risk dashboard" />;

  if (!effectiveId || notFound || !bundle) {
    return (
      <div className="animate-fade-in">
        <PageHeader
          eyebrow={<Badge tone="info" dot>Step 3 · Decision</Badge>}
          title="Risk Dashboard"
          description="The scored view of a case: why it was flagged, which rules fired and the transactions behind them."
        />
        <div className="p-4 sm:p-6">
          <EmptyState
            icon={LayoutDashboard}
            title={
              loadError && !notFound
                ? "Unable to load this dashboard"
                : effectiveId
                  ? `Case #${effectiveId} has not been analysed`
                  : "No case selected"
            }
            description={
              loadError && !notFound
                ? `${loadError} Check the API connection and try again.`
                : effectiveId
                  ? "Confirm the column mapping in Extraction Review to run the detection pipeline for this statement."
                  : "Select a case below or upload a new statement to begin."
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
                        navigate(s.tier ? `/dashboard/${s.id}` : `/review/${s.id}`);
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

  const features = (bundle.features || []) as FeatureRow[];
  const rules = bundle.triggered_rules || [];
  const decision = bundle.final_decision || {};
  const cycles = bundle.cycles_detected || [];
  const summary = bundle.account_summary || {};
  const tier = (decision.tier as string) || "REVIEW_REQUIRED";
  const period = summary.observed_period as { start?: string; end?: string } | undefined;

  // Rule points are directly comparable, so this chart is meaningful as-is.
  const ruleChart = [...rules]
    .map((r) => ({
      name: String(r.id).replace(/^R\d+_/, ""),
      points: Number(r.points) || 0,
      id: String(r.id),
    }))
    .sort((a, b) => b.points - a.points);

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={
          <>
            <Badge tone="info" dot>Step 3 · Decision</Badge>
            <Badge tone="neutral" mono>CASE #{effectiveId}</Badge>
            <TierBadge tier={tier} score={decision.fused_score as number} />
          </>
        }
        title="Risk Dashboard"
        description={
          currentStatement?.original_filename
            ? `Scored view of ${currentStatement.original_filename}.`
            : "Scored view of the selected statement."
        }
        meta={
          <>
            <MetaItem label="Transactions" value={(summary.transaction_count as number) ?? "—"} icon={Database} />
            {period?.start && (
              <MetaItem
                label="Period"
                value={`${formatDate(period.start)} – ${formatDate(period.end || null)}`}
                icon={Calendar}
              />
            )}
            <MetaItem label="Rules fired" value={rules.length} icon={ShieldAlert} />
            <MetaItem label="Cycles" value={cycles.length} icon={Repeat} />
          </>
        }
        actions={
          <>
            <LinkButton to={`/evidence/${effectiveId}`} icon={Search}>
              Evidence
            </LinkButton>
            <LinkButton to={`/graph/${effectiveId}`} icon={GitGraph}>
              Proof graph
            </LinkButton>
            <LinkButton to={`/review/${effectiveId}`} icon={FileText}>
              Mapping
            </LinkButton>
          </>
        }
      />

      <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6">
        {whyFlagged && <WhyFlaggedPanel data={whyFlagged} statementId={effectiveId as number} />}

        <div className="grid gap-5 lg:grid-cols-3">
          <div className="space-y-5 lg:col-span-1">
            <Card>
              <CardHeader
                title="Triggered rules"
                description="Deterministic AML rules that breached their threshold."
                icon={ShieldAlert}
                actions={<Badge tone={rules.length ? "danger" : "success"}>{rules.length} fired</Badge>}
              />
              <div className="p-4">
                <RuleTriggerList rules={rules as any[]} />
              </div>
            </Card>

            {cycles.length > 0 && (
              <Card>
                <CardHeader
                  title="Detected cycles"
                  description="Closed fund loops found in the transaction graph."
                  icon={Repeat}
                  actions={<Badge tone="accent">{cycles.length}</Badge>}
                />
                <div className="space-y-2 p-4">
                  {cycles.map((c) => (
                    <div
                      key={c.cycle_id as string}
                      className="rounded-lg border border-violet-200 bg-violet-50/60 p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[11px] font-bold text-violet-800">
                          {c.cycle_id as string}
                        </span>
                        <Badge tone="accent">
                          risk{" "}
                          {c.cycle_risk_score != null
                            ? `${((c.cycle_risk_score as number) * 100).toFixed(0)}%`
                            : "—"}
                        </Badge>
                      </div>
                      <p className="num mt-1 text-[12px] text-ink-700">
                        {c.hop_count as number}-hop loop
                      </p>
                      <LinkButton
                        to={`/graph/${effectiveId}?focus=${encodeURIComponent(`CYC_${c.cycle_id as string}`)}`}
                        icon={GitGraph}
                        className="mt-2 border-violet-200 text-violet-700 hover:bg-violet-100"
                      >
                        View in Proof Graph
                      </LinkButton>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>

          <div className="space-y-5 lg:col-span-2">
            {ruleChart.length > 0 && (
              <Card>
                <CardHeader
                  title="Rule contribution"
                  description="Points each breached rule added to the deterministic rule score."
                  icon={SlidersHorizontal}
                />
                <div className="p-4">
                  <ResponsiveContainer width="100%" height={Math.max(ruleChart.length * 42, 120)}>
                    <BarChart data={ruleChart} layout="vertical" margin={{ left: 8, right: 24 }}>
                      <XAxis
                        type="number"
                        tick={{ fontSize: 10, fill: "#64748B" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={150}
                        tick={{ fontSize: 10, fill: "#475569" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        cursor={{ fill: "rgba(15,23,42,0.04)" }}
                        contentStyle={{
                          borderRadius: 8,
                          border: "1px solid #E2E8F0",
                          fontSize: 12,
                          boxShadow: "0 8px 24px -6px rgb(15 23 42 / 0.14)",
                        }}
                        formatter={(v: number) => [`${v} points`, "Contribution"]}
                      />
                      <Bar dataKey="points" radius={[0, 4, 4, 0]} barSize={16}>
                        {ruleChart.map((r) => (
                          <Cell
                            key={r.id}
                            fill={r.points >= 25 ? "#DC2626" : r.points >= 20 ? "#EA580C" : "#D97706"}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            {narrative && narrative.text && (
              <NarrativePanel text={narrative.text} source={narrative.source as "ai" | "template"} />
            )}
          </div>
        </div>

        {features.length > 0 && (
          <Card>
            <CardHeader
              title={`Account fingerprint (${features.length} features)`}
              description="Every deterministic feature the scorer computed, grouped by family. Ratios are shown as bars; hover for the formula."
              icon={SlidersHorizontal}
            />
            <div className="p-4 sm:p-5">
              <FeatureGrid features={features} />
            </div>
          </Card>
        )}

        <Card>
          <CardHeader
            title="Transaction audit table"
            description="Every parsed row, with rule and cycle tags applied by the analysis."
            icon={Table2}
            actions={<Badge tone="neutral">{transactions.total} rows</Badge>}
          />
          <TransactionTable
            rows={transactions.rows}
            total={transactions.total}
            page={page}
            pageSize={100}
            onPageChange={setPage}
          />
        </Card>
      </div>
    </div>
  );
}
