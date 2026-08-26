import { useState } from "react";
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  GitGraph,
  Repeat,
  Gauge,
  Coins,
  Users,
  Moon,
  Sigma,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ScrollText,
} from "lucide-react";
import { FlagReason, WhyFlagged } from "../lib/api";
import {
  Badge,
  Card,
  Formula,
  LinkButton,
  SeverityBadge,
  TBody,
  THead,
  Table,
  Td,
  Th,
  TierBadge,
  Tone,
  formatDate,
  inr,
  money,
} from "./ui";

type WhyFlaggedPanelProps = {
  data: WhyFlagged;
  statementId: number;
};

const CATEGORY_ICON: Record<string, typeof Repeat> = {
  graph: Repeat,
  velocity: Gauge,
  structuring: Coins,
  network: Users,
  lifecycle: Moon,
  statistical: Sigma,
  rule: ShieldAlert,
};

const RISK_STYLE: Record<
  WhyFlagged["risk_level"],
  { text: string; soft: string; border: string; tone: Tone; label: string }
> = {
  HIGH: {
    text: "text-red-700",
    soft: "bg-red-50",
    border: "border-red-200",
    tone: "danger",
    label: "High risk",
  },
  MEDIUM: {
    text: "text-amber-700",
    soft: "bg-amber-50",
    border: "border-amber-200",
    tone: "warning",
    label: "Medium risk",
  },
  LOW: {
    text: "text-emerald-700",
    soft: "bg-emerald-50",
    border: "border-emerald-200",
    tone: "success",
    label: "Low risk",
  },
};

/* --------------------------------------------------------------- score dial */

function ScoreScale({ data }: { data: WhyFlagged }) {
  const style = RISK_STYLE[data.risk_level];
  const { likely_legitimate_max: low, confirmed_suspicious_min: high } = data.thresholds;
  const pos = Math.min(Math.max(data.risk_score, 0), 100);

  return (
    <div>
      <div className="flex items-baseline gap-1.5">
        <span className={`num text-[40px] font-bold leading-none tracking-tight ${style.text}`}>
          {data.risk_score.toFixed(0)}
        </span>
        <span className="num text-sm font-medium text-ink-300">/ 100</span>
      </div>

      <div className="relative mt-4">
        {/* Zoned track: clear · review · suspicious */}
        <div className="flex h-2 w-full overflow-hidden rounded-full">
          <div className="bg-emerald-400/70" style={{ width: `${low}%` }} />
          <div className="bg-amber-300/70" style={{ width: `${high - low}%` }} />
          <div className="bg-red-400/70" style={{ width: `${100 - high}%` }} />
        </div>

        {/* Needle */}
        <div
          className="absolute -top-1 flex flex-col items-center"
          style={{ left: `${pos}%`, transform: "translateX(-50%)" }}
        >
          <span
            className={`h-4 w-1 rounded-full ring-2 ring-white ${
              data.risk_level === "HIGH"
                ? "bg-red-600"
                : data.risk_level === "MEDIUM"
                ? "bg-amber-500"
                : "bg-emerald-600"
            }`}
          />
        </div>

        {/* Tier boundaries */}
        <div className="relative mt-1 h-3">
          <span
            className="num absolute -translate-x-1/2 text-[10px] font-semibold text-ink-400"
            style={{ left: `${low}%` }}
          >
            {low}
          </span>
          <span
            className="num absolute -translate-x-1/2 text-[10px] font-semibold text-ink-400"
            style={{ left: `${high}%` }}
          >
            {high}
          </span>
        </div>

        {/* Zone names, centred under their band */}
        <div className="flex text-[9px] font-semibold uppercase tracking-[0.06em]">
          <span className="text-center text-emerald-600" style={{ width: `${low}%` }}>
            Clear
          </span>
          <span className="text-center text-amber-600" style={{ width: `${high - low}%` }}>
            Review
          </span>
          <span className="text-center text-red-600" style={{ width: `${100 - high}%` }}>
            Suspicious
          </span>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-2 border-t border-ink-100 pt-3">
        {data.score_breakdown.slice(0, 2).map((b) => (
          <div key={b.component}>
            <dt className="label-micro truncate">{b.component}</dt>
            <dd className="num mt-0.5 text-[13px] font-semibold text-ink-800">
              {b.points_of_fused} pts
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/* --------------------------------------------------------------- confidence */

function ConfidenceBlock({ data }: { data: WhyFlagged }) {
  const [open, setOpen] = useState(false);
  const c = data.confidence;

  return (
    <div>
      <div className="flex items-baseline gap-1.5">
        <span className="num text-[40px] font-bold leading-none tracking-tight text-ink-900">
          {c.score.toFixed(0)}
          <span className="text-2xl text-ink-300">%</span>
        </span>
      </div>
      <p className="mt-1 text-[11px] text-ink-400">Weighted from four measured inputs</p>

      <div className="mt-3 space-y-2">
        {c.components.map((comp) => (
          <div key={comp.name}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="truncate text-[11px] font-medium text-ink-600" title={comp.description}>
                {comp.name}
              </span>
              <span className="num shrink-0 font-mono text-[10px] text-ink-400">
                {(comp.value * 100).toFixed(0)}% × {comp.weight}
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
              <div
                className="h-full rounded-full bg-brand-500"
                style={{ width: `${Math.min(comp.value * 100, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={() => setOpen(!open)}
        className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-semibold text-brand-700 hover:text-brand-900"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        How this is computed
      </button>

      {open && (
        <div className="mt-2 space-y-2 animate-slide-down">
          <Formula>{c.formula}</Formula>
          <div className="space-y-1 rounded-lg border border-ink-100 bg-ink-50/60 p-2.5">
            <p className="label-micro mb-1">Detector agreement</p>
            {c.detector_agreement.map((d) => (
              <div key={d.detector} className="flex items-center gap-1.5 text-[11px] text-ink-600">
                {d.agrees ? (
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                ) : (
                  <XCircle className="h-3.5 w-3.5 shrink-0 text-ink-300" />
                )}
                <span className="flex-1">{d.detector}</span>
                <span className="text-ink-400">{d.flagged ? "flagged" : "quiet"}</span>
              </div>
            ))}
          </div>
          {c.components.map((comp) => (
            <p key={comp.name} className="text-[10px] leading-relaxed text-ink-400">
              <strong className="font-semibold text-ink-600">{comp.name}:</strong> {comp.description}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- rule clauses */

function ClauseRow({ clause }: { clause: FlagReason["rules"][number]["clauses"][number] }) {
  if (!clause.field) {
    return <span className="font-mono text-[11px] text-ink-500">{clause.expression}</span>;
  }
  const actual =
    clause.actual_value != null
      ? String(Number(clause.actual_value.toFixed(4)))
      : "n/a";

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
      <span className="text-ink-600">{clause.field}</span>
      <span className="num rounded border border-ink-200 bg-white px-1.5 py-0.5 font-bold text-ink-900">
        {actual}
      </span>
      <span className="text-ink-400">{clause.operator}</span>
      <span className="num rounded border border-ink-100 bg-ink-50 px-1.5 py-0.5 text-ink-500">
        {clause.threshold_value != null ? clause.threshold_value : clause.threshold_expression}
      </span>
      {clause.holds ? (
        <span className="inline-flex items-center gap-1 rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-bold text-red-600">
          breached
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 rounded bg-ink-50 px-1.5 py-0.5 text-[10px] font-medium text-ink-400">
          within limit
        </span>
      )}
    </span>
  );
}

/* ------------------------------------------------------------- reason card */

function ReasonCard({
  reason,
  rank,
  statementId,
  defaultOpen,
}: {
  reason: FlagReason;
  rank: number;
  statementId: number;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const Icon = CATEGORY_ICON[reason.category] || ShieldAlert;

  const evidenceCount =
    reason.transactions.length +
    reason.features.length +
    (reason.counterparties?.length || 0) +
    (reason.deviations?.length || 0) +
    reason.rules.length;

  const accent =
    reason.severity === "CRITICAL" ? "danger" : reason.severity === "HIGH" ? "warning" : undefined;

  return (
    <Card accent={accent as "danger" | "warning" | undefined}>
      <div className="p-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-ink-900 text-[11px] font-bold text-white">
            {rank}
          </span>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Icon className="h-4 w-4 shrink-0 text-ink-400" />
              <h4 className="text-[14px] font-semibold text-ink-900">{reason.title}</h4>
              <SeverityBadge severity={reason.severity} />
              {reason.is_score_driver ? (
                <Badge tone="info">
                  {reason.contribution_pct}% of score
                  {reason.rule_points > 0 && ` · +${reason.rule_points} pts`}
                </Badge>
              ) : (
                <Badge tone="neutral">supporting</Badge>
              )}
            </div>

            <p className="mt-1.5 text-[13px] font-medium leading-relaxed text-ink-800">
              {reason.headline}
            </p>
            {reason.detail && (
              <p className="mt-1 text-[11px] leading-relaxed text-ink-400">{reason.detail}</p>
            )}

            {reason.metrics.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {reason.metrics.map((m) => (
                  <span
                    key={m.label}
                    className="rounded-md border border-ink-100 bg-ink-50/70 px-2 py-1 text-[11px] text-ink-500"
                  >
                    {m.label}{" "}
                    <strong className="num ml-0.5 font-semibold text-ink-900">{m.value}</strong>
                  </span>
                ))}
              </div>
            )}

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <button
                onClick={() => setOpen(!open)}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-700 hover:text-brand-900"
              >
                {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                {open ? "Hide" : "Show"} underlying evidence ({evidenceCount})
              </button>

              {reason.graph_pattern_id && (
                <LinkButton
                  to={`/graph/${statementId}?focus=${encodeURIComponent(reason.graph_pattern_id)}`}
                  variant="secondary"
                  icon={GitGraph}
                  className="border-violet-200 text-violet-700 hover:bg-violet-50"
                >
                  View in Proof Graph <ArrowRight className="h-3 w-3" />
                </LinkButton>
              )}
            </div>
          </div>
        </div>
      </div>

      {open && (
        <div className="animate-slide-down space-y-4 border-t border-ink-100 bg-ink-50/50 p-4">
          {reason.rules.length > 0 && (
            <div>
              <p className="label-micro mb-2">Rule that fired</p>
              <div className="space-y-2">
                {reason.rules.map((r) => (
                  <div key={r.id} className="rounded-lg border border-ink-100 bg-white p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-[11px] font-bold text-red-700">{r.id}</span>
                      <span className="num text-[11px] text-ink-400">
                        +{r.points} pts · {r.contribution_pct}% of final score
                      </span>
                    </div>
                    {r.description && (
                      <p className="mt-1 text-[12px] text-ink-600">{r.description}</p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {r.clauses.map((c, i) => (
                        <span key={c.expression + i} className="flex items-center gap-2">
                          {i > 0 && (
                            <span className="text-[10px] font-bold text-ink-300">{r.joiner}</span>
                          )}
                          <ClauseRow clause={c} />
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {reason.features.length > 0 && (
            <div>
              <p className="label-micro mb-2">Computed features</p>
              <div className="overflow-hidden rounded-lg border border-ink-100 bg-white">
                <Table minWidth={520}>
                  <THead>
                    <Th>Feature</Th>
                    <Th align="right">Value</Th>
                    <Th align="right">Threshold</Th>
                    <Th>Formula</Th>
                  </THead>
                  <TBody>
                    {reason.features.map((f) => (
                      <tr key={f.name}>
                        <Td className="font-mono text-[12px] text-ink-800">{f.name}</Td>
                        <Td align="right" className="num text-[12px] font-bold text-ink-900">
                          {typeof f.value === "number" ? f.value.toFixed(3) : String(f.value)}
                        </Td>
                        <Td align="right" className="num font-mono text-[11px] text-ink-400">
                          {f.threshold_value != null ? `${f.operator} ${f.threshold_value}` : "—"}
                        </Td>
                        <Td className="font-mono text-[10px] text-ink-300">{f.formula}</Td>
                      </tr>
                    ))}
                  </TBody>
                </Table>
              </div>
            </div>
          )}

          {reason.deviations && reason.deviations.length > 0 && (
            <div>
              <p className="label-micro mb-2">Features outside the robust baseline</p>
              <div className="grid gap-1.5 sm:grid-cols-2">
                {reason.deviations.map((d) => (
                  <div
                    key={d.name}
                    className="flex items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50/60 px-2.5 py-2"
                  >
                    <span className="truncate font-mono text-[11px] font-medium text-ink-700" title={d.name}>
                      {d.name}
                    </span>
                    <span className="num shrink-0 text-[11px] font-bold text-amber-800">
                      {typeof d.value === "number" ? d.value.toFixed(3) : String(d.value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {reason.counterparties && reason.counterparties.length > 0 && (
            <div>
              <p className="label-micro mb-2">Counterparties on a detected pattern</p>
              <div className="overflow-hidden rounded-lg border border-ink-100 bg-white">
                <Table minWidth={560}>
                  <THead>
                    <Th>Counterparty</Th>
                    <Th align="right">Txns</Th>
                    <Th align="right">Received</Th>
                    <Th align="right">Sent</Th>
                    <Th>Patterns</Th>
                  </THead>
                  <TBody>
                    {reason.counterparties.map((cp) => (
                      <tr key={cp.counterparty_id}>
                        <Td className="text-[12px] font-semibold text-ink-800">{cp.counterparty}</Td>
                        <Td align="right" className="num text-[12px]">
                          {cp.transaction_count}
                        </Td>
                        <Td align="right" className="num text-[12px] text-emerald-700">
                          {money(cp.inflow)}
                        </Td>
                        <Td align="right" className="num text-[12px] text-red-600">
                          {money(cp.outflow)}
                        </Td>
                        <Td className="font-mono text-[10px] text-ink-300">
                          {cp.patterns.join(", ") || "—"}
                        </Td>
                      </tr>
                    ))}
                  </TBody>
                </Table>
              </div>
              {(reason.counterparties_withheld || 0) > 0 && (
                <p className="mt-1 text-[10px] text-ink-400">
                  +{reason.counterparties_withheld} more counterparties on this pattern.
                </p>
              )}
            </div>
          )}

          {reason.transactions.length > 0 && (
            <div>
              <p className="label-micro mb-2">Transactions behind this reason</p>
              <div className="overflow-hidden rounded-lg border border-ink-100 bg-white">
                <Table minWidth={620}>
                  <THead>
                    <Th>Date</Th>
                    <Th>Txn ID</Th>
                    <Th>Counterparty</Th>
                    <Th>Channel</Th>
                    <Th align="right">Amount</Th>
                  </THead>
                  <TBody>
                    {reason.transactions.map((t) => (
                      <tr key={t.row_id}>
                        <Td className="whitespace-nowrap text-[12px] text-ink-500">
                          {formatDate(t.timestamp)}
                        </Td>
                        <Td className="font-mono text-[11px] text-ink-800">{t.txn_id}</Td>
                        <Td className="text-[12px] text-ink-700">{t.counterparty}</Td>
                        <Td className="text-[11px] uppercase tracking-wide text-ink-400">
                          {t.channel || "—"}
                        </Td>
                        <Td
                          align="right"
                          className={`num text-[12px] font-bold ${
                            t.direction === "debit" ? "text-red-600" : "text-emerald-700"
                          }`}
                        >
                          {t.direction === "debit" ? "−" : "+"}₹{inr.format(t.amount)}
                        </Td>
                      </tr>
                    ))}
                  </TBody>
                </Table>
              </div>
              {reason.transactions_withheld > 0 && (
                <p className="mt-1 text-[10px] text-ink-400">
                  +{reason.transactions_withheld} more transactions contributed to this reason.
                </p>
              )}
            </div>
          )}

          {reason.how_computed && <Formula>{reason.how_computed}</Formula>}
        </div>
      )}
    </Card>
  );
}

/* -------------------------------------------------------------------- panel */

export function WhyFlaggedPanel({ data, statementId }: WhyFlaggedPanelProps) {
  const style = RISK_STYLE[data.risk_level];
  const drivers = data.reasons.filter((r) => r.is_score_driver);
  const supporting = data.reasons.filter((r) => !r.is_score_driver);
  const isFlagged = data.risk_level !== "LOW";
  const cov = data.evidence_coverage;

  return (
    <Card className="animate-fade-in">
      <header
        className={`flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-5 ${style.soft} ${style.border}`}
      >
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/60 bg-white/80">
            <HelpCircle className={`h-4.5 w-4.5 ${style.text}`} />
          </span>
          <div>
            <h2 className="text-[15px] font-semibold text-ink-900">
              {isFlagged ? "Why was this flagged?" : "Why was this cleared?"}
            </h2>
            <p className="text-[11px] text-ink-500">
              Ranked, evidence-backed drivers behind the decision — every claim traces to a rule,
              feature or transaction.
            </p>
          </div>
        </div>
        <TierBadge tier={data.tier} />
      </header>

      <div className="space-y-5 p-4 sm:p-5">
        {/* Headline numbers */}
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-ink-100 bg-white p-4">
            <span className="label-micro">Risk score</span>
            <ScoreScale data={data} />
          </div>

          <div className={`rounded-xl border p-4 ${style.border} ${style.soft}`}>
            <span className="label-micro">Risk level</span>
            <div className="mt-2 flex items-center gap-2.5">
              <span className="text-3xl leading-none">{data.risk_level_emoji}</span>
              <div>
                <p className={`text-2xl font-bold leading-none ${style.text}`}>{data.risk_level}</p>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-wide text-ink-400">
                  {data.tier}
                </p>
              </div>
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-ink-600">{data.decision_reason}</p>
          </div>

          <div className="rounded-xl border border-ink-100 bg-white p-4">
            <span className="label-micro">Decision confidence</span>
            <ConfidenceBlock data={data} />
          </div>
        </div>

        {/* Score composition */}
        <div className="rounded-xl border border-ink-100 bg-ink-50/50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="label-micro">How the score of {data.risk_score.toFixed(1)} was composed</p>
            <span className="font-mono text-[10px] text-ink-400">{data.score_formula}</span>
          </div>
          <div className="mt-2.5 flex h-2.5 overflow-hidden rounded-full bg-ink-200">
            {data.score_breakdown.map((b, i) => (
              <div
                key={b.component}
                className={i === 0 ? "bg-brand-600" : i === 1 ? "bg-violet-500" : "bg-teal-500"}
                style={{ width: `${b.points_of_fused}%` }}
                title={`${b.component}: ${b.points_of_fused} points`}
              />
            ))}
          </div>
          <div className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1.5">
            {data.score_breakdown.map((b, i) => (
              <span key={b.component} className="flex items-center gap-1.5 text-[11px] text-ink-500">
                <span
                  className={`h-2 w-2 rounded-full ${
                    i === 0 ? "bg-brand-600" : i === 1 ? "bg-violet-500" : "bg-teal-500"
                  }`}
                />
                {b.component}
                <strong className="num font-semibold text-ink-900">{b.points_of_fused} pts</strong>
                <span className="num text-ink-300">
                  (weight {b.weight} · raw {b.raw_value ?? "—"})
                </span>
              </span>
            ))}
          </div>
        </div>

        {/* Reasons */}
        <div>
          <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
            <div>
              <h3 className="text-[14px] font-semibold text-ink-900">
                {isFlagged ? "Top reasons for flagging" : "What the detectors found"}
              </h3>
              <p className="mt-0.5 text-[11px] text-ink-400">
                Ranked by contribution to the final score. Expand any reason for the rule clause,
                features and transactions it came from.
              </p>
            </div>
            <span className="flex items-center gap-1.5 whitespace-nowrap text-[11px] text-ink-400">
              <ScrollText className="h-3.5 w-3.5" />
              <span className="num">{cov.transactions_examined}</span> txns ·
              <span className="num">
                {cov.rules_triggered}/{cov.rules_evaluated}
              </span>{" "}
              rules ·<span className="num">{cov.features_computed}</span> features ·
              <span className="num">{cov.patterns_detected}</span> patterns
            </span>
          </div>

          {data.reasons.length === 0 ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-3 text-[12px] text-emerald-800">
              <strong className="font-semibold">No evidence against this account.</strong> No rule
              fired, no circular flow was found, and no feature deviated from the robust baseline.
            </div>
          ) : (
            <div className="space-y-2.5">
              {drivers.map((r, i) => (
                <ReasonCard
                  key={r.id}
                  reason={r}
                  rank={i + 1}
                  statementId={statementId}
                  defaultOpen={i === 0}
                />
              ))}

              {supporting.length > 0 && (
                <>
                  <p className="label-micro pt-2">Supporting evidence · no score contribution</p>
                  {supporting.map((r, i) => (
                    <ReasonCard
                      key={r.id}
                      reason={r}
                      rank={drivers.length + i + 1}
                      statementId={statementId}
                      defaultOpen={false}
                    />
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
