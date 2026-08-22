import { clsx } from "clsx";

type RiskGaugeProps = {
  score: number;
  tier: "CONFIRMED_SUSPICIOUS" | "REVIEW_REQUIRED" | "LIKELY_LEGITIMATE";
};

const tierColors: Record<string, string> = {
  CONFIRMED_SUSPICIOUS: "text-red-600 border-red-500 bg-red-50",
  REVIEW_REQUIRED: "text-amber-600 border-amber-500 bg-amber-50",
  LIKELY_LEGITIMATE: "text-green-600 border-green-500 bg-green-50",
};

export function RiskGauge({ score, tier }: RiskGaugeProps) {
  return (
    <div className={clsx("rounded-lg border-2 p-6 text-center", tierColors[tier])}>
      <div className="text-5xl font-bold mb-2">{Math.round(score)}</div>
      <div className="text-sm font-semibold uppercase tracking-wide">{tier.replace(/_/g, " ")}</div>
      <div className="mt-2 w-full bg-gray-200 rounded-full h-2.5">
        <div
          className={clsx(
            "h-2.5 rounded-full transition-all",
            tier === "CONFIRMED_SUSPICIOUS" && "bg-red-500",
            tier === "REVIEW_REQUIRED" && "bg-amber-500",
            tier === "LIKELY_LEGITIMATE" && "bg-green-500",
          )}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
    </div>
  );
}
