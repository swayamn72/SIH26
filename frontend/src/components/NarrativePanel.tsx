import { Sparkles, FileText, AlertTriangle } from "lucide-react";
import { Badge, Card, CardHeader } from "./ui";

type NarrativePanelProps = {
  text: string;
  source: "ai" | "template";
  showToggle?: boolean;
  onToggle?: () => void;
};

export function NarrativePanel({ text, source, showToggle, onToggle }: NarrativePanelProps) {
  const isAi = source === "ai";

  return (
    <Card>
      <CardHeader
        title={isAi ? "Case narrative" : "Computed case narrative"}
        icon={isAi ? Sparkles : FileText}
        description={
          isAi
            ? "Drafted by the local model from the evidence bundle."
            : "Generated deterministically from the evidence bundle — no model involved."
        }
        actions={
          <div className="flex items-center gap-2">
            <Badge tone={isAi ? "accent" : "neutral"}>{isAi ? "LLM draft" : "Deterministic"}</Badge>
            {showToggle && onToggle && (
              <button
                onClick={onToggle}
                className="text-[11px] font-semibold text-brand-700 hover:text-brand-900"
              >
                Show {isAi ? "computed" : "AI"} version
              </button>
            )}
          </div>
        }
      />
      <div className="p-4 sm:p-5">
        <p className="whitespace-pre-line text-[13px] leading-relaxed text-ink-700">{text}</p>
        {isAi && (
          <p className="mt-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Model-written prose. The scores, rules and transactions it references are shown verbatim
            elsewhere on this page — verify against those before citing it.
          </p>
        )}
      </div>
    </Card>
  );
}
