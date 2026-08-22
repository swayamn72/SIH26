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

export function RuleTriggerList({ rules }: RuleTriggerListProps) {
  if (!rules || rules.length === 0) {
    return <div className="text-sm text-gray-400 italic">No rules triggered.</div>;
  }

  const sorted = [...rules].sort((a, b) => (b.points || 0) - (a.points || 0));

  return (
    <div className="space-y-2">
      {sorted.map((r) => (
        <div key={r.id} className="rounded-lg border border-red-100 bg-red-50 p-3">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs font-bold text-red-700">{r.id}</span>
            <span className="text-xs font-bold text-red-600">+{r.points} pts</span>
          </div>
          {r.description && <p className="text-sm mt-1 text-gray-800">{r.description}</p>}
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-xs text-gray-600">
            {r.computed_value != null && (
              <span>
                Value: <strong>{typeof r.computed_value === "number" ? r.computed_value.toFixed(3) : String(r.computed_value)}</strong>
              </span>
            )}
            {r.threshold != null && <span>Threshold: <strong>{r.threshold}</strong></span>}
            {r.condition && (
              <span>
                Condition: <code className="bg-red-100/70 px-1 py-0.5 rounded font-mono text-[11px]">{r.condition}</code>
              </span>
            )}
          </div>
          {r.contributing_row_ids && r.contributing_row_ids.length > 0 && (
            <div className="mt-1 text-xs text-gray-400">
              {r.contributing_row_ids.length} contributing transaction(s)
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
