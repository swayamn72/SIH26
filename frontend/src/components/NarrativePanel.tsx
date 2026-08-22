type NarrativePanelProps = {
  text: string;
  source: "ai" | "template";
  showToggle?: boolean;
  onToggle?: () => void;
};

export function NarrativePanel({ text, source, showToggle, onToggle }: NarrativePanelProps) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">
            {source === "ai" ? "AI-Generated Summary" : "Computed Summary"}
          </span>
          {source === "ai" && (
            <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">AI</span>
          )}
        </div>
        {showToggle && onToggle && (
          <button
            onClick={onToggle}
            className="text-xs text-blue-600 hover:underline"
          >
            Show {source === "ai" ? "computed" : "AI"} summary
          </button>
        )}
      </div>
      <p className="text-sm text-gray-700 leading-relaxed">{text}</p>
      {source === "ai" && (
        <p className="text-xs text-gray-400 mt-2">
          AI-generated summary — verify against the evidence table below.
        </p>
      )}
    </div>
  );
}
