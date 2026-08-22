import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { AlertCircle, CheckCircle, ArrowRight, FileText, Upload } from "lucide-react";
import { api, StatementPreview } from "../lib/api";
import { useStatement } from "../lib/StatementContext";

const CANONICAL_FIELDS = [
  "txn_date", "value_date", "narration", "debit_amount",
  "credit_amount", "balance_after", "reference_no",
];

export function ExtractionReviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentId, setCurrentId, refreshStatements, statements } = useStatement();

  const effectiveId = id ? Number(id) : currentId;

  const [preview, setPreview] = useState<StatementPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);

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
    api.getPreview(effectiveId)
      .then((data) => {
        setPreview(data);
        setMapping(data.detected_column_mapping || {});
      })
      .catch(() => setPreview(null))
      .finally(() => setLoading(false));
  }, [effectiveId]);

  const handleConfirm = async () => {
    if (!effectiveId) return;
    setConfirming(true);
    try {
      // If mapping was changed, save mapping first
      if (Object.keys(mapping).length > 0) {
        await api.updateMapping(effectiveId, mapping);
      }
      await api.confirmExtraction(effectiveId);
      await refreshStatements();
      navigate(`/dashboard/${effectiveId}`);
    } catch (err) {
      alert("Failed to confirm extraction: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setConfirming(false);
    }
  };

  if (loading) return (
    <div className="p-8 text-gray-500 flex items-center gap-2">
      <FileText className="w-5 h-5 animate-pulse text-blue-600" /> Loading extraction preview...
    </div>
  );

  if (!effectiveId || !preview) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="bg-white border rounded-xl p-8 text-center shadow-sm space-y-4">
          <FileText className="w-12 h-12 mx-auto text-gray-400" />
          <div>
            <h2 className="text-lg font-bold text-gray-900">No Statement Selected for Review</h2>
            <p className="text-sm text-gray-500 mt-1">Select a statement from history or upload a new statement.</p>
          </div>

          {statements.length > 0 && (
            <div className="max-w-md mx-auto text-left border rounded-lg divide-y bg-gray-50/50 my-4">
              {statements.map((s) => (
                <button
                  key={s.id}
                  onClick={() => {
                    setCurrentId(s.id);
                    navigate(`/review/${s.id}`);
                  }}
                  className="w-full p-3 text-left hover:bg-blue-50/50 flex items-center justify-between text-xs transition-colors"
                >
                  <span className="font-medium text-gray-800">#{s.id}: {s.original_filename}</span>
                  <span className="text-blue-600 font-semibold">Review →</span>
                </button>
              ))}
            </div>
          )}

          <div>
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 shadow-sm"
            >
              <Upload className="w-4 h-4" /> Go to Upload Page
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const conf = preview.extraction_confidence;
  const confidenceLevel = conf == null ? "pending" : conf >= 0.98 ? "high" : conf >= 0.85 ? "medium" : "low";
  const confidenceColor = confidenceLevel === "high" ? "text-green-600 bg-green-50 border-green-200" : confidenceLevel === "pending" ? "text-blue-600 bg-blue-50 border-blue-200" : confidenceLevel === "medium" ? "text-amber-600 bg-amber-50 border-amber-200" : "text-red-600 bg-red-50 border-red-200";

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Extraction Review</h1>
        <p className="text-gray-500 text-xs sm:text-sm mt-0.5">
          Review detected column mapping for Statement #{effectiveId} before running detection rules.
        </p>
      </div>

      <div className={`rounded-xl border p-4 shadow-sm ${confidenceColor}`}>
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <div className="flex items-center gap-2">
            {confidenceLevel === "high" ? <CheckCircle className="w-5 h-5 shrink-0" /> : <AlertCircle className="w-5 h-5 shrink-0" />}
            <span className="font-semibold text-sm">
              Extraction Confidence: {conf == null ? "Ready for Analysis" : `${(conf * 100).toFixed(1)}%`}
            </span>
          </div>
          {preview.reconciliation_rate != null && (
            <span className="text-xs sm:ml-4 bg-white/60 px-2 py-0.5 rounded font-medium">
              Running Balance Reconciliation: {(preview.reconciliation_rate * 100).toFixed(1)}%
            </span>
          )}
        </div>
        {confidenceLevel === "low" && (
          <p className="text-xs mt-1">Low confidence — manual review of column mapping is recommended.</p>
        )}
      </div>

      <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
        <div className="bg-gray-50 border-b px-4 py-3 font-semibold text-sm text-gray-800 flex items-center justify-between">
          <span>Column Mapping ({preview.transaction_count} transactions detected)</span>
          <span className="text-xs font-normal text-gray-500">Auto-detected schema from statement structure</span>
        </div>
        {preview.detected_column_mapping && Object.entries(mapping).length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 p-4">
            {Object.entries(mapping).map(([col, field]) => (
              <div key={col} className="border rounded-lg p-3 bg-gray-50/50 space-y-1.5">
                <div className="text-xs font-semibold text-gray-600 truncate" title={col}>
                  Header: &ldquo;{col}&rdquo;
                </div>
                <select
                  value={field}
                  onChange={(e) => setMapping((prev) => ({ ...prev, [col]: e.target.value }))}
                  className="w-full text-xs font-medium border border-gray-300 rounded-md px-2 py-1.5 bg-white text-gray-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">— ignore —</option>
                  {CANONICAL_FIELDS.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-4 text-xs text-gray-500">No columns detected or statement already processed.</div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleConfirm}
          disabled={confirming}
          className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium text-sm flex items-center gap-2 shadow-sm transition-colors"
        >
          {confirming ? "Running Analysis..." : "Confirm & Analyze"} <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
