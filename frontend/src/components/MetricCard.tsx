import { clsx } from "clsx";

type MetricCardProps = {
  title: string;
  value: string | number;
  formula?: string;
  explanation?: string;
  variant?: "default" | "danger" | "warning" | "success";
};

export function MetricCard({ title, value, formula, explanation, variant = "default" }: MetricCardProps) {
  return (
    <div
      className={clsx(
        "rounded-lg border bg-white p-4 shadow-sm transition-shadow hover:shadow-md",
        variant === "danger" && "border-red-200 bg-red-50",
        variant === "warning" && "border-amber-200 bg-amber-50",
        variant === "success" && "border-green-200 bg-green-50",
      )}
      title={formula ? `Formula: ${formula}` : undefined}
    >
      <div className="text-sm text-gray-500 mb-1">{title}</div>
      <div
        className={clsx(
          "text-2xl font-bold",
          variant === "danger" && "text-red-700",
          variant === "warning" && "text-amber-700",
          variant === "success" && "text-green-700",
        )}
      >
        {value}
      </div>
      {explanation && <div className="text-xs text-gray-400 mt-1">{explanation}</div>}
    </div>
  );
}
