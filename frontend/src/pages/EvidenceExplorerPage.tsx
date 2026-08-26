import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Download,
  AlertCircle,
  CheckCircle2,
  Search,
  GitGraph,
  Upload,
  ArrowRight,
  LayoutDashboard,
  FileJson,
  ListTree,
  ShieldAlert,
  Sigma,
  Repeat,
  ScrollText,
  Braces,
} from "lucide-react";
import { api, EvidenceBundle, SuspiciousPattern } from "../lib/api";
import { EvidenceTimeline } from "../components/EvidenceTimeline";
import { useStatement } from "../lib/StatementContext";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  Formula,
  KeyValue,
  LinkButton,
  LoadingPanel,
  MetaItem,
  PageHeader,
  StatTile,
  TBody,
  THead,
  Table,
  Td,
  Th,
  TierBadge,
  formatDate,
} from "../components/ui";

export function EvidenceExplorerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentId, setCurrentId, statements } = useStatement();

  const effectiveId = id ? Number(id) : currentId;

  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [patterns, setPatterns] = useState<SuspiciousPattern[]>([]);
  const [rawJson, setRawJson] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id && Number(id) !== currentId) {
      setCurrentId(Number(id));
    }
  }, [id, currentId, setCurrentId]);

  useEffect(() => {
    if (!effectiveId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    api
      .getEvidence(effectiveId)
      .then(setBundle)
      .catch((err) => {
        setBundle(null);
        setError(err instanceof Error ? err.message : "Failed to load evidence bundle");
      })
      .finally(() => setLoading(false));

    api
      .getPatterns(effectiveId)
      .then((res) => setPatterns(res.patterns || []))
      .catch(() => setPatterns([]));
  }, [effectiveId]);

  const handleExport = async () => {
    if (!effectiveId) return;
    try {
      await api.exportReport(effectiveId);
    } catch {
      if (bundle) {
        const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `evidence-${effectiveId}.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    }
  };

  if (loading) return <LoadingPanel label="Loading evidence bundle" />;

  if (!effectiveId || !bundle) {
    return (
      <div className="animate-fade-in">
        <PageHeader
          eyebrow={<Badge tone="info" dot>Step 4 · Audit trail</Badge>}
          title="Evidence Explorer"
          description="The complete, reproducible proof bundle behind a decision — patterns, rules, features and guardrails."
        />
        <div className="p-4 sm:p-6">
          <EmptyState
            icon={Search}
            title={effectiveId ? `No evidence bundle for case #${effectiveId}` : "No case selected"}
            description={
              effectiveId
                ? "Confirm the extraction to generate the evidence bundle for this statement."
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
                        navigate(`/evidence/${s.id}`);
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

  const summary = bundle?.account_summary || {};
  const decision = bundle?.final_decision || {};
  const rules = bundle?.triggered_rules || [];
  const features = bundle?.features || [];
  const cycles = bundle?.cycles_detected || [];
  const guardrail = bundle?.guardrail_log || {};
  const anomaly = bundle?.anomaly_detail || null;
  const madFeatures = (anomaly?.mad_flagged_features as Record<string, number>) || {};
  const madKeys = Object.keys(madFeatures);
  const period = summary.observed_period as { start?: string; end?: string } | undefined;

  const timelineCycleIds = new Set(
    patterns.filter((p) => p.kind === "cycle").map((p) => p.pattern_id.replace(/^CYC_/, "")),
  );
  const cyclesWithoutTimeline = cycles.filter((c) => !timelineCycleIds.has(String(c.cycle_id)));

  const fusedScoreNum = typeof decision.fused_score === "number" ? decision.fused_score : 0;
  const ruleScoreNum =
    typeof decision.rule_score === "number"
      ? decision.rule_score
      : rules.reduce((acc, r) => acc + ((r.points as number) || 0), 0);
  const anomalyScorePct =
    typeof decision.anomaly_score === "number"
      ? decision.anomaly_score * 100
      : features.length > 0
      ? (madKeys.length / Math.max(features.length, 1)) * 100
      : 0;

  const decisionReason =
    (decision.decision_reason as string) ||
    (decision.tier === "CONFIRMED_SUSPICIOUS"
      ? `Fused risk score (${fusedScoreNum.toFixed(1)} ≥ 75) with active regulatory fraud rules triggered.`
      : decision.tier === "LIKELY_LEGITIMATE"
      ? `Fused score (${fusedScoreNum.toFixed(1)} ≤ 25) with 0 severe rules triggered and a normal anomaly sub-score (${anomalyScorePct.toFixed(1)}% < 30%).`
      : `Ambiguous risk score (${fusedScoreNum.toFixed(1)} / 100) requiring investigator verification.`);

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={
          <>
            <Badge tone="info" dot>Step 4 · Audit trail</Badge>
            <Badge tone="neutral" mono>CASE #{effectiveId}</Badge>
            <TierBadge tier={decision.tier as string} score={fusedScoreNum} />
          </>
        }
        title="Evidence Explorer"
        description="Everything the decision rests on, in the order an auditor would read it: patterns, rules, features, statistics and data-quality guardrails."
        meta={
          <>
            <MetaItem label="Patterns" value={patterns.length} icon={ListTree} />
            <MetaItem label="Rules fired" value={rules.length} icon={ShieldAlert} />
            <MetaItem label="Features" value={features.length} icon={Sigma} />
          </>
        }
        actions={
          <>
            <LinkButton to={`/dashboard/${effectiveId}`} icon={LayoutDashboard}>
              Dashboard
            </LinkButton>
            <LinkButton to={`/graph/${effectiveId}`} icon={GitGraph}>
              Proof graph
            </LinkButton>
            <Button icon={rawJson ? ScrollText : Braces} onClick={() => setRawJson(!rawJson)}>
              {rawJson ? "Formatted view" : "Raw JSON"}
            </Button>
            <Button variant="primary" icon={Download} onClick={handleExport}>
              Export report
            </Button>
          </>
        }
      />

      <div className="mx-auto max-w-[1200px] space-y-5 p-4 sm:p-6">
        {error && (
          <Card padded className="border-red-200 bg-red-50">
            <p className="flex items-center gap-2 text-[13px] text-red-700">
              <AlertCircle className="h-4 w-4" /> {error}
            </p>
          </Card>
        )}

        {rawJson ? (
          <Card>
            <CardHeader
              title="Raw evidence bundle"
              description="The exact JSON persisted for this case — reproducible and diffable."
              icon={FileJson}
            />
            <pre className="scroll-slim max-h-[70vh] overflow-auto bg-ink-950 p-4 font-mono text-[11px] leading-relaxed text-ink-100">
              {JSON.stringify(bundle, null, 2)}
            </pre>
          </Card>
        ) : (
          <>
            {/* Account summary */}
            <Card>
              <CardHeader
                title="Account summary"
                description="Provenance of the analysed statement."
                icon={ScrollText}
              />
              <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-4">
                <KeyValue label="Case" value={`#${effectiveId}`} />
                <KeyValue
                  label="Observed period"
                  value={
                    period?.start
                      ? `${formatDate(period.start)} – ${formatDate(period.end || null)}`
                      : "—"
                  }
                />
                <KeyValue label="Transactions" value={(summary.transaction_count as number) ?? "—"} />
                <KeyValue
                  label="Extraction confidence"
                  value={
                    summary.extraction_confidence != null
                      ? `${((summary.extraction_confidence as number) * 100).toFixed(1)}%`
                      : "—"
                  }
                />
              </div>
            </Card>

            {/* Decision */}
            <Card>
              <CardHeader
                title="Final decision & score breakdown"
                description="How the fused score was produced and which policy branch decided the tier."
                icon={Sigma}
                actions={<TierBadge tier={decision.tier as string} score={fusedScoreNum} />}
              />
              <div className="space-y-4 p-4 sm:p-5">
                <div
                  className={`rounded-lg border px-3.5 py-3 text-[12px] leading-relaxed ${
                    decision.tier === "CONFIRMED_SUSPICIOUS"
                      ? "border-red-200 bg-red-50 text-red-800"
                      : decision.tier === "LIKELY_LEGITIMATE"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border-amber-200 bg-amber-50 text-amber-800"
                  }`}
                >
                  <p className="mb-0.5 font-semibold">Decision policy rationale</p>
                  <p>{decisionReason}</p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <StatTile
                    label="Fused score"
                    value={`${fusedScoreNum.toFixed(1)} / 100`}
                    tone={
                      decision.tier === "CONFIRMED_SUSPICIOUS"
                        ? "danger"
                        : decision.tier === "LIKELY_LEGITIMATE"
                        ? "success"
                        : "warning"
                    }
                    hint="Weighted fusion of all detectors"
                  />
                  <StatTile
                    label="Deterministic rules"
                    value={`${ruleScoreNum.toFixed(1)} pts`}
                    hint={`65% weight · ${rules.length} rules fired`}
                  />
                  <StatTile
                    label="Statistical anomaly"
                    value={`${anomalyScorePct.toFixed(1)}%`}
                    tone={anomalyScorePct >= 30 ? "warning" : "success"}
                    hint={`35% weight · auto-clear below 30% · ${madKeys.length} deviations`}
                  />
                </div>

                <Formula>{decision.score_formula_used as string}</Formula>
              </div>
            </Card>

            {/* Evidence timeline */}
            <Card>
              <CardHeader
                title={`Evidence timeline — suspicious patterns${patterns.length ? ` (${patterns.length})` : ""}`}
                description="Hop-by-hop fund movement for every detected pattern: timestamp, amount, transaction ID and severity per transfer."
                icon={ListTree}
                actions={
                  patterns.length > 0 && (
                    <LinkButton to={`/graph/${effectiveId}`} icon={GitGraph}>
                      Open full graph
                    </LinkButton>
                  )
                }
              />
              <div className="p-4 sm:p-5">
                <EvidenceTimeline patterns={patterns} statementId={effectiveId as number} />
              </div>
            </Card>

            {/* Rules */}
            {rules.length > 0 && (
              <Card>
                <CardHeader
                  title={`Triggered rules (${rules.length})`}
                  description="Each deterministic rule that breached its configured threshold."
                  icon={ShieldAlert}
                />
                <div className="space-y-2 p-4 sm:p-5">
                  {rules.map((r) => {
                    const linked = patterns.filter((p) => p.linked_rule_ids.includes(r.id as string));
                    const firstLinked = linked[0];
                    return (
                      <div
                        key={r.id as string}
                        className="rounded-lg border border-red-200 bg-red-50/60 p-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-mono text-[11px] font-bold text-red-700">
                            {r.id as string}
                          </span>
                          <Badge tone="danger">+{r.points as number} pts</Badge>
                        </div>
                        <p className="mt-1 text-[12px] text-ink-700">{r.description as string}</p>
                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                          <span className="text-[11px] text-ink-500">
                            {linked.length > 0
                              ? `${linked.length} pattern timeline${linked.length > 1 ? "s" : ""} linked`
                              : "No row-level timeline linked"}
                          </span>
                          <LinkButton
                            to={
                              firstLinked
                                ? `/graph/${effectiveId}?focus=${encodeURIComponent(firstLinked.pattern_id)}`
                                : `/graph/${effectiveId}`
                            }
                            icon={GitGraph}
                            className="border-violet-200 text-violet-700 hover:bg-violet-50"
                          >
                            View in Proof Graph <ArrowRight className="h-3 w-3" />
                          </LinkButton>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            )}

            {/* Anomaly */}
            {anomaly && (
              <Card>
                <CardHeader
                  title="Statistical anomaly detail"
                  description="Unsupervised checks: robust MAD deviation and isolation forest. These do not know the rules, so agreement is independent corroboration."
                  icon={Sigma}
                  actions={
                    <Badge tone="neutral" mono>
                      isolation forest{" "}
                      {typeof anomaly.isolation_forest_score === "number"
                        ? `${((anomaly.isolation_forest_score as number) * 100).toFixed(1)}%`
                        : "0.0%"}
                    </Badge>
                  }
                />
                <div className="p-4 sm:p-5">
                  {madKeys.length > 0 ? (
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                      {madKeys.map((key) => (
                        <div
                          key={key}
                          className="rounded-lg border border-amber-200 bg-amber-50/60 p-2.5"
                        >
                          <p
                            className="truncate font-mono text-[11px] font-semibold text-amber-900"
                            title={key}
                          >
                            {key}
                          </p>
                          <div className="mt-1 flex justify-between text-[11px] text-ink-500">
                            <span>observed</span>
                            <strong className="num font-semibold text-ink-800">
                              {typeof madFeatures[key] === "number"
                                ? madFeatures[key].toFixed(2)
                                : String(madFeatures[key])}
                            </strong>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-3 text-[12px] text-emerald-800">
                      <CheckCircle2 className="h-4 w-4 shrink-0" />
                      No significant statistical deviation across the computed features.
                    </p>
                  )}
                </div>
              </Card>
            )}

            {/* Features */}
            {features.length > 0 && (
              <Card>
                <CardHeader
                  title={`Deterministic features (${features.length})`}
                  description="Every feature the scorer computed, with the exact formula used."
                  icon={Sigma}
                />
                <Table minWidth={720}>
                  <THead>
                    <Th>Feature</Th>
                    <Th align="right">Value</Th>
                    <Th>Family</Th>
                    <Th>Formula</Th>
                  </THead>
                  <TBody>
                    {features.map((f) => (
                      <tr key={f.name as string} className="hover:bg-ink-50/70">
                        <Td className="font-mono text-[12px] font-medium text-ink-800">
                          {f.name as string}
                        </Td>
                        <Td align="right" className="num text-[12px] font-semibold text-ink-900">
                          {f.value != null
                            ? typeof f.value === "number"
                              ? f.value.toFixed(3)
                              : String(f.value)
                            : "—"}
                        </Td>
                        <Td>
                          <Badge tone="neutral">{(f.family as string) || "—"}</Badge>
                        </Td>
                        <Td className="font-mono text-[10px] text-ink-300">{f.formula as string}</Td>
                      </tr>
                    ))}
                  </TBody>
                </Table>
              </Card>
            )}

            {/* Cycles without a timeline */}
            {cyclesWithoutTimeline.length > 0 && (
              <Card>
                <CardHeader
                  title={`Cycles without a row-level timeline (${cyclesWithoutTimeline.length})`}
                  description="Detected in the graph, but their contributing rows are no longer resolvable, so they cannot be replayed hop by hop."
                  icon={Repeat}
                />
                <div className="space-y-2 p-4 sm:p-5">
                  {cyclesWithoutTimeline.map((c) => (
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
                      <p className="num mt-1 text-[12px] text-ink-600">
                        {c.hop_count as number}-hop cycle
                      </p>
                      <p className="mt-1 font-mono text-[11px] text-ink-400">
                        {(c.nodes as string[])?.join(" → ")}
                      </p>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Guardrails */}
            <Card>
              <CardHeader
                title="Data-quality guardrails"
                description="Checks that gate whether a score may be trusted at all."
                icon={CheckCircle2}
              />
              <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-4">
                <KeyValue
                  label="OOD check"
                  value={
                    <span className="flex items-center gap-1.5">
                      {guardrail.ood_check_passed ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      ) : (
                        <AlertCircle className="h-4 w-4 text-red-600" />
                      )}
                      {guardrail.ood_check_passed ? "Passed" : "Failed"}
                    </span>
                  }
                />
                <KeyValue
                  label="Reconciliation rate"
                  value={
                    guardrail.reconciliation_rate != null
                      ? `${((guardrail.reconciliation_rate as number) * 100).toFixed(1)}%`
                      : "—"
                  }
                />
                <KeyValue
                  label="Extraction confidence"
                  value={String(guardrail.extraction_confidence ?? "—")}
                />
                <KeyValue
                  label="Manual mapping used"
                  value={guardrail.manual_mapping_used ? "Yes" : "No"}
                />
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
