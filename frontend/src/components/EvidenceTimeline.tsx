import { useState } from "react";
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Clock,
  GitGraph,
  Repeat,
  Layers,
  Scissors,
  Moon,
  CheckCircle2,
} from "lucide-react";
import { PatternHop, SuspiciousPattern } from "../lib/api";
import {
  Badge,
  Card,
  Formula,
  LinkButton,
  Severity,
  SeverityBadge,
  Tone,
  inr,
  money,
} from "./ui";

type EvidenceTimelineProps = {
  patterns: SuspiciousPattern[];
  statementId: number;
  /** Compact mode starts every timeline collapsed. */
  compact?: boolean;
};

const KIND_META: Record<
  SuspiciousPattern["kind"],
  { label: string; tone: Tone; icon: typeof Repeat }
> = {
  cycle: { label: "Circular flow", tone: "accent", icon: Repeat },
  layering: { label: "Layering", tone: "info", icon: Layers },
  structuring: { label: "Structuring", tone: "warning", icon: Scissors },
  dormancy_burst: { label: "Dormancy burst", tone: "neutral", icon: Moon },
};

const SEVERITY_RAIL: Record<Severity, string> = {
  CRITICAL: "bg-red-500",
  HIGH: "bg-orange-500",
  MEDIUM: "bg-amber-500",
  LOW: "bg-ink-300",
};

const SEVERITY_ACCENT: Record<Severity, "danger" | "warning" | undefined> = {
  CRITICAL: "danger",
  HIGH: "warning",
  MEDIUM: "warning",
  LOW: undefined,
};

function formatTimestamp(value: string | null): string {
  if (!value) return "Date unavailable";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  const datePart = dt.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  const hasTime = dt.getHours() !== 0 || dt.getMinutes() !== 0;
  return hasTime
    ? `${datePart} · ${dt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}`
    : datePart;
}

function formatGap(hours: number | null): string | null {
  if (hours == null) return null;
  if (hours <= 0) return "same day";
  if (hours < 24) return `+${hours.toFixed(hours < 1 ? 2 : 0)}h later`;
  const days = hours / 24;
  return `+${days.toFixed(days < 10 ? 1 : 0)}d later`;
}

/* --------------------------------------------------------------- flow path */

function PathStrip({ pattern }: { pattern: SuspiciousPattern }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {pattern.node_path.map((node, i) => (
        <div key={`${node.id}-${i}`} className="flex items-center gap-1.5">
          <span
            className={`max-w-[170px] truncate rounded-md border px-2 py-1 text-[11px] font-semibold ${
              node.is_subject
                ? "border-violet-300 bg-violet-50 text-violet-800"
                : "border-ink-200 bg-white text-ink-700"
            } ${node.is_return ? "ring-1 ring-red-300" : ""}`}
            title={node.label}
          >
            {node.label}
          </span>
          {i < pattern.node_path.length - 1 && (
            <ArrowRight className="h-3.5 w-3.5 shrink-0 text-ink-300" />
          )}
        </div>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------- hop row */

function HopRow({ hop, isLast }: { hop: PatternHop; isLast: boolean }) {
  const gap = formatGap(hop.gap_hours);
  const rail = SEVERITY_RAIL[hop.severity] || SEVERITY_RAIL.LOW;

  return (
    <li className="relative pb-3 pl-9 last:pb-0">
      {!isLast && <span className="absolute bottom-0 left-[13px] top-6 w-px bg-ink-200" aria-hidden />}
      <span
        className={`absolute left-[6px] top-3.5 flex h-4 w-4 items-center justify-center rounded-full ring-[3px] ring-white ${rail}`}
        aria-hidden
      >
        <span className="num text-[8px] font-bold text-white">{hop.step}</span>
      </span>

      <div className="rounded-lg border border-ink-100 bg-white p-3">
        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-ink-400">
              <Clock className="h-3 w-3 shrink-0" />
              <span>{formatTimestamp(hop.timestamp)}</span>
              {gap && <span className="text-ink-300">· {gap}</span>}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[13px] font-semibold text-ink-800">
              <span className="max-w-[160px] truncate" title={hop.from_label}>
                {hop.from_label}
              </span>
              <ArrowRight className="h-3.5 w-3.5 shrink-0 text-ink-300" />
              <span className="max-w-[160px] truncate" title={hop.to_label}>
                {hop.to_label}
              </span>
            </div>
          </div>

          <div className="shrink-0 text-right">
            <div
              className={`num text-[15px] font-bold leading-none ${
                hop.direction === "debit" ? "text-red-600" : "text-emerald-700"
              }`}
            >
              {hop.direction === "debit" ? "−" : "+"}₹{inr.format(hop.amount)}
            </div>
            <div className="mt-1.5">
              <SeverityBadge
                severity={hop.severity}
                suffix={` · ${(hop.risk_score * 100).toFixed(0)}%`}
              />
            </div>
          </div>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-ink-100 pt-2 text-[11px] text-ink-400">
          <span className="font-mono">
            Txn <strong className="font-semibold text-ink-700">{hop.txn_id}</strong>
          </span>
          <span className="font-mono text-ink-300">row {hop.row_id}</span>
          {hop.channel && <span className="uppercase tracking-wide">{hop.channel}</span>}
          {hop.near_threshold && (
            <Badge tone="warning">near ₹{inr.format(hop.near_threshold_band ?? 0)} threshold</Badge>
          )}
          {hop.is_rapid && <Badge tone="info">rapid hop</Badge>}
        </div>

        {hop.narration && (
          <p className="mt-1.5 truncate text-[11px] text-ink-400" title={hop.narration}>
            {hop.narration}
          </p>
        )}
      </div>
    </li>
  );
}

/* ------------------------------------------------------------ pattern card */

function PatternCard({
  pattern,
  statementId,
  compact,
}: {
  pattern: SuspiciousPattern;
  statementId: number;
  compact: boolean;
}) {
  const [open, setOpen] = useState(!compact);
  const kind = KIND_META[pattern.kind] || KIND_META.cycle;
  const KindIcon = kind.icon;

  return (
    <Card accent={SEVERITY_ACCENT[pattern.severity]}>
      <div className="p-4">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={kind.tone} dot>
                <KindIcon className="h-3 w-3" /> {kind.label}
              </Badge>
              <SeverityBadge
                severity={pattern.severity}
                suffix={` · risk ${(pattern.risk_score * 100).toFixed(0)}%`}
              />
              <span className="font-mono text-[10px] text-ink-300">{pattern.pattern_id}</span>
            </div>
            <h4 className="mt-1.5 text-[14px] font-semibold text-ink-900">{pattern.title}</h4>
            <p className="mt-0.5 text-[12px] leading-relaxed text-ink-500">{pattern.summary}</p>
          </div>

          <LinkButton
            to={`/graph/${statementId}?focus=${encodeURIComponent(pattern.pattern_id)}`}
            variant="accent"
            icon={GitGraph}
            className="shrink-0"
          >
            View in Proof Graph <ArrowRight className="h-3 w-3" />
          </LinkButton>
        </div>

        <div className="mt-3">
          <PathStrip pattern={pattern} />
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            { label: "Transfers", value: String(pattern.hop_count) },
            { label: "Total value", value: money(pattern.total_amount) },
            { label: "Txn window", value: `${pattern.span_days.toFixed(2)} d` },
            {
              label: "Rule points",
              value: pattern.rule_points > 0 ? `+${pattern.rule_points}` : "—",
            },
          ].map((m) => (
            <div key={m.label} className="rounded-lg border border-ink-100 bg-ink-50/60 px-2.5 py-1.5">
              <span className="label-micro">{m.label}</span>
              <p className="num mt-0.5 text-[13px] font-semibold text-ink-900">{m.value}</p>
            </div>
          ))}
        </div>

        {pattern.linked_rule_ids.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {pattern.linked_rule_ids.map((r) => (
              <Badge key={r} tone="danger" mono>
                {r}
              </Badge>
            ))}
          </div>
        )}

        <button
          onClick={() => setOpen(!open)}
          className="mt-3 inline-flex items-center gap-1 text-[11px] font-semibold text-brand-700 hover:text-brand-900"
        >
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          {open ? "Hide" : "Show"} transaction timeline ({pattern.hops.length})
        </button>
      </div>

      {open && (
        <div className="animate-slide-down border-t border-ink-100 bg-ink-50/50 p-4">
          <ol className="m-0 list-none p-0">
            {pattern.hops.map((hop, i) => (
              <HopRow key={hop.row_id + hop.step} hop={hop} isLast={i === pattern.hops.length - 1} />
            ))}
          </ol>
          <Formula className="mt-2">
            {pattern.formula} · {pattern.hop_risk_formula}
          </Formula>
          {pattern.truncation_note && (
            <p className="mt-1 text-[10px] text-amber-700">{pattern.truncation_note}</p>
          )}
        </div>
      )}
    </Card>
  );
}

export function EvidenceTimeline({ patterns, statementId, compact = false }: EvidenceTimelineProps) {
  if (!patterns || patterns.length === 0) {
    return (
      <div className="flex items-start gap-2.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-3">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
        <p className="text-[12px] leading-relaxed text-emerald-800">
          <strong className="font-semibold">No suspicious multi-hop pattern detected.</strong> No
          circular flow, pass-through chain, structuring band or dormancy burst met the configured
          thresholds.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {patterns.map((p) => (
        <PatternCard key={p.pattern_id} pattern={p} statementId={statementId} compact={compact} />
      ))}
    </div>
  );
}
