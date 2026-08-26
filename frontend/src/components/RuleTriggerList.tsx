import { ShieldCheck } from "lucide-react";
import { Badge } from "./ui";

type RuleTrigger = {
  id: string;
  description?: string;
  condition?: string;
  computed_value?: number | null;
  threshold?: number | null;
  points: number;
  contributing_row_ids?: string[];
};

type RuleTriggerListProps = {
  rules: RuleTrigger[];
};

function severityTone(points: number) {
  if (points >= 25) return "danger" as const;
  if (points >= 20) return "warning" as const;
  return "neutral" as const;
}

export function RuleTriggerList({ rules }: RuleTriggerListProps) {
  if (!rules || rules.length === 0) {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-3">
        <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600" />
        <p className="text-[12px] text-emerald-800">
          <strong className="font-semibold">No rule breached.</strong> Every deterministic AML rule
          evaluated within limits.
        </p>
      </div>
    );
  }

  const sorted = [...rules].sort((a, b) => (b.points || 0) - (a.points || 0));
  const maxPoints = Math.max(...sorted.map((r) => r.points || 0), 1);

  return (
    <div className="space-y-2">
      {sorted.map((r) => (
        <div key={r.id} className="rounded-lg border border-ink-100 bg-white p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-mono text-[11px] font-bold text-red-700">{r.id}</span>
            <Badge tone={severityTone(r.points)}>+{r.points} pts</Badge>
          </div>

          {r.description && <p className="mt-1 text-[12px] text-ink-700">{r.description}</p>}

          <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-ink-100">
            <div
              className="h-full rounded-full bg-red-500"
              style={{ width: `${((r.points || 0) / maxPoints) * 100}%` }}
            />
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-400">
            {r.computed_value != null && (
              <span>
                value{" "}
                <strong className="num font-semibold text-ink-700">
                  {typeof r.computed_value === "number"
                    ? r.computed_value.toFixed(3)
                    : String(r.computed_value)}
                </strong>
              </span>
            )}
            {r.condition && (
              <code className="rounded border border-ink-100 bg-ink-50 px-1.5 py-0.5 font-mono text-[10px] text-ink-500">
                {r.condition}
              </code>
            )}
            {r.contributing_row_ids && r.contributing_row_ids.length > 0 && (
              <span className="num">{r.contributing_row_ids.length} contributing rows</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
