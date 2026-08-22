import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { Download, AlertCircle, CheckCircle, Search, GitGraph, Upload, ArrowRight, BarChart2, FileText } from "lucide-react";
import { api, EvidenceBundle } from "../lib/api";
import { useStatement } from "../lib/StatementContext";

export function EvidenceExplorerPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentId, setCurrentId, statements } = useStatement();

  const effectiveId = id ? Number(id) : currentId;

  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
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
    api.getEvidence(effectiveId)
      .then(setBundle)
      .catch((err) => {
        setBundle(null);
        setError(err instanceof Error ? err.message : "Failed to load evidence bundle");
      })
      .finally(() => setLoading(false));
  }, [effectiveId]);

  const handleExport = async () => {
    if (!effectiveId) return;
    try {
      await api.exportReport(effectiveId);
    } catch {
      // fallback: download JSON
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

  if (loading) {
    return (
      <div className="p-8 text-gray-500 flex items-center gap-2">
        <Search className="w-5 h-5 animate-pulse text-blue-600" /> Loading evidence bundle...
      </div>
    );
  }

  if (!effectiveId || !bundle) {
    return (
      <div className="p-4 sm:p-6 max-w-4xl mx-auto">
        <div className="bg-white border rounded-xl p-6 sm:p-8 text-center shadow-sm space-y-4">
          <Search className="w-12 h-12 mx-auto text-gray-400" />
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              {!effectiveId ? "No Statement Selected" : `Evidence Bundle Not Found for Statement #${effectiveId}`}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              {!effectiveId
                ? "Select a statement from history or upload a new statement."
                : "Make sure you have confirmed extraction to generate the evidence bundle."}
            </p>
          </div>

          {effectiveId && (
            <div>
              <button
                onClick={() => navigate(`/review/${effectiveId}`)}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 shadow-sm transition-colors"
              >
                Review & Confirm Extraction <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          )}

          {statements.length > 0 && (
            <div className="mt-6 pt-6 border-t text-left">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Available Statements</h3>
              <div className="max-w-md mx-auto border rounded-lg divide-y bg-gray-50/50">
                {statements.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      setCurrentId(s.id);
                      navigate(`/evidence/${s.id}`);
                    }}
                    className="w-full p-3 text-left hover:bg-blue-50/50 flex items-center justify-between text-xs transition-colors"
                  >
                    <div className="truncate mr-2">
                      <span className="font-semibold text-gray-800">#{s.id}: {s.original_filename}</span>
                      <p className="text-[11px] text-gray-500 mt-0.5">{s.transaction_count || 0} txns · {s.tier || s.status}</p>
                    </div>
                    <span className="text-blue-600 font-semibold shrink-0">View Evidence →</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-4 py-2 border rounded-lg text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <Upload className="w-3.5 h-3.5" /> Upload New Statement
            </Link>
          </div>
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

  const fusedScoreNum = typeof decision.fused_score === "number" ? decision.fused_score : 0;
  const ruleScoreNum = typeof decision.rule_score === "number" ? decision.rule_score : (rules.reduce((acc, r) => acc + ((r.points as number) || 0), 0));
  const anomalyScorePct = typeof decision.anomaly_score === "number" 
    ? (decision.anomaly_score * 100) 
    : (features.length > 0 ? (madKeys.length / Math.max(features.length, 1)) * 100 : 0);

  const decisionReason = (decision.decision_reason as string) || (
    decision.tier === "CONFIRMED_SUSPICIOUS"
      ? `Fused risk score (${fusedScoreNum.toFixed(1)} >= 75) with active regulatory fraud rules triggered.`
      : decision.tier === "LIKELY_LEGITIMATE"
      ? `Fused score (${fusedScoreNum.toFixed(1)} <= 25) with 0 severe rules triggered and normal anomaly sub-score (${anomalyScorePct.toFixed(1)}% < 30%).`
      : rules.length === 0 && fusedScoreNum <= 25
      ? `0 deterministic rules triggered (Rule Score: 0.0), but statistical anomaly sub-score (${anomalyScorePct.toFixed(1)}%) exceeded the strict auto-clear threshold (< 30.0%). Conservative AML policy requires human sign-off.`
      : `Ambiguous risk score (${fusedScoreNum.toFixed(1)} / 100) requiring investigator verification.`
  );

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Evidence Explorer</h1>
            <span className="text-xs bg-blue-100 text-blue-800 font-bold px-2 py-0.5 rounded">
              Statement #{effectiveId}
            </span>
          </div>
          <p className="text-gray-500 text-xs sm:text-sm mt-1">Full audit trail & deterministic proof bundle</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link to={`/dashboard/${effectiveId}`} className="px-3 py-1.5 bg-white border rounded-lg text-xs font-medium hover:bg-gray-50 flex items-center gap-1.5 shadow-sm transition-colors">
            <BarChart2 className="w-3.5 h-3.5" /> Dashboard
          </Link>
          <Link to={`/graph/${effectiveId}`} className="px-3 py-1.5 bg-white border rounded-lg text-xs font-medium hover:bg-gray-50 flex items-center gap-1.5 shadow-sm transition-colors">
            <GitGraph className="w-3.5 h-3.5 text-purple-600" /> Proof Graph
          </Link>
          <button onClick={() => setRawJson(!rawJson)} className="px-3 py-1.5 bg-white border rounded-lg text-xs font-medium hover:bg-gray-50 flex items-center gap-1.5 shadow-sm transition-colors">
            <FileText className="w-3.5 h-3.5 text-gray-600" /> {rawJson ? "Formatted View" : "Raw JSON"}
          </button>
          <button onClick={handleExport} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 flex items-center gap-1.5 shadow-sm transition-colors">
            <Download className="w-3.5 h-3.5" /> Export PDF
          </button>
        </div>
      </div>

      {loading && <div className="text-center py-12 text-sm text-gray-400">Loading evidence bundle...</div>}
      {error && <div className="text-center py-12 text-sm text-red-500">{error}</div>}

      {bundle && rawJson && (
        <div className="bg-gray-900 text-gray-100 rounded-xl p-4 overflow-x-auto text-xs font-mono">
          <pre>{JSON.stringify(bundle, null, 2)}</pre>
        </div>
      )}

      {bundle && !rawJson && (
        <div className="space-y-6">
          <div className="bg-white border rounded-xl p-5 shadow-sm">
            <h3 className="font-semibold text-sm text-gray-800 mb-3">Account Summary</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div><span className="text-gray-400 text-xs">Statement ID</span><p className="font-semibold text-gray-800">#{effectiveId}</p></div>
              <div><span className="text-gray-400 text-xs">Observed Period</span><p className="font-semibold text-gray-800">{(summary.observed_period as any)?.start || "N/A"} — {(summary.observed_period as any)?.end || "N/A"}</p></div>
              <div><span className="text-gray-400 text-xs">Total Transactions</span><p className="font-semibold text-gray-800">{summary.transaction_count as number}</p></div>
              <div><span className="text-gray-400 text-xs">Extraction Confidence</span><p className="font-semibold text-gray-800">{summary.extraction_confidence != null ? `${((summary.extraction_confidence as number) * 100).toFixed(1)}%` : "N/A"}</p></div>
            </div>
          </div>

          <div className="bg-white border rounded-xl p-5 shadow-sm">
            <h3 className="font-semibold text-sm text-gray-800 mb-3">Final Decision & Score Breakdown</h3>
            <div className="flex flex-wrap items-center gap-3">
              <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                decision.tier === "CONFIRMED_SUSPICIOUS" ? "bg-red-100 text-red-700" :
                decision.tier === "LIKELY_LEGITIMATE" ? "bg-green-100 text-green-700" :
                "bg-amber-100 text-amber-700"
              }`}>{decision.tier as string}</span>
              <span className="text-sm text-gray-700">Fused Score: <strong>{fusedScoreNum.toFixed(1)}</strong> / 100</span>
            </div>

            <div className={`mt-3 p-3 rounded-lg border text-xs ${
              decision.tier === "CONFIRMED_SUSPICIOUS" 
                ? "bg-red-50 border-red-200 text-red-800" 
                : decision.tier === "LIKELY_LEGITIMATE"
                ? "bg-green-50 border-green-200 text-green-800"
                : "bg-amber-50 border-amber-200 text-amber-800"
            }`}>
              <div className="font-semibold mb-0.5">Decision Policy Rationale:</div>
              <p>{decisionReason}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
              <div className="p-3 bg-gray-50 border rounded-lg">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-medium text-gray-700">Deterministic Rules Score</span>
                  <span className="font-bold text-gray-900">{ruleScoreNum.toFixed(1)} pts</span>
                </div>
                <div className="text-[11px] text-gray-500 mt-1">Weight: 65% in fusion formula · Active triggers: {rules.length}</div>
              </div>
              <div className="p-3 bg-gray-50 border rounded-lg">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-medium text-gray-700">Statistical Anomaly Sub-Score</span>
                  <span className={`font-bold ${anomalyScorePct >= 30 ? "text-amber-700" : "text-green-700"}`}>
                    {anomalyScorePct.toFixed(1)}%
                  </span>
                </div>
                <div className="text-[11px] text-gray-500 mt-1">
                  Weight: 35% · Auto-clear threshold: &lt; 30.0% · Flagged deviations: {madKeys.length}
                </div>
              </div>
            </div>

            <p className="text-xs font-mono text-gray-500 mt-3 bg-gray-50 p-2 rounded border">{decision.score_formula_used as string}</p>
          </div>

          {anomaly && (
            <div className="bg-white border rounded-xl p-5 shadow-sm">
              <div className="flex justify-between items-center mb-3">
                <h3 className="font-semibold text-sm text-gray-800">Statistical Anomaly Details (Unsupervised MAD & Isolation Forest)</h3>
                <span className="text-xs font-mono px-2 py-0.5 bg-gray-100 rounded text-gray-600">
                  Isolation Forest: {typeof anomaly.isolation_forest_score === "number" ? ((anomaly.isolation_forest_score as number) * 100).toFixed(1) : "0.0"}%
                </span>
              </div>
              <p className="text-xs text-gray-500 mb-3">
                Features deviating from the statistical median absolute deviation (MAD) baseline. If &ge; 30% of features deviate, the system automatically mandates human review.
              </p>
              {madKeys.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                  {madKeys.map((key) => (
                    <div key={key} className="p-2.5 bg-amber-50/60 border border-amber-200/80 rounded-lg text-xs">
                      <div className="font-mono font-semibold text-amber-900 truncate" title={key}>{key}</div>
                      <div className="text-gray-600 mt-0.5 flex justify-between">
                        <span>Observed value:</span>
                        <strong className="font-mono text-gray-800">
                          {typeof madFeatures[key] === "number" ? madFeatures[key].toFixed(2) : String(madFeatures[key])}
                        </strong>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-green-700 bg-green-50 p-3 rounded-lg border border-green-200">
                  ✓ No significant statistical deviations detected across features.
                </div>
              )}
            </div>
          )}

          {rules.length > 0 && (
            <div className="bg-white border rounded-xl p-5 shadow-sm">
              <h3 className="font-semibold text-sm text-gray-800 mb-3">Triggered Rules ({rules.length})</h3>
              <div className="space-y-2">
                {rules.map((r) => (
                  <div key={r.id as string} className="border border-red-100 bg-red-50/70 rounded-lg p-3 text-xs">
                    <div className="flex justify-between font-semibold">
                      <span className="font-mono text-red-700">{r.id as string}</span>
                      <span className="text-red-800">+{r.points as number} pts</span>
                    </div>
                    <p className="text-gray-700 mt-1">{r.description as string}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {features.length > 0 && (
            <div className="bg-white border rounded-xl p-5 shadow-sm">
              <h3 className="font-semibold text-sm text-gray-800 mb-3">Deterministic Features ({features.length})</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b text-left text-gray-500 uppercase tracking-wider bg-gray-50/50">
                      <th className="px-3 py-2">Feature</th>
                      <th className="px-3 py-2">Value</th>
                      <th className="px-3 py-2">Formula</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {features.map((f) => (
                      <tr key={f.name as string} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-mono text-gray-900 font-semibold">{f.name as string}</td>
                        <td className="px-3 py-2 font-medium">{f.value != null ? (typeof f.value === "number" ? f.value.toFixed(3) : String(f.value)) : "N/A"}</td>
                        <td className="px-3 py-2 font-mono text-gray-400 text-[11px]">{f.formula as string}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {cycles.length > 0 && (
            <div className="bg-white border rounded-xl p-5 shadow-sm">
              <h3 className="font-semibold text-sm text-gray-800 mb-3">Cycles Detected ({cycles.length})</h3>
              {cycles.map((c) => (
                <div key={c.cycle_id as string} className="border border-purple-200 bg-purple-50/70 rounded-lg p-3 mb-2 text-xs">
                  <p className="font-mono font-bold text-purple-800">{c.cycle_id as string}</p>
                  <p className="mt-0.5">{c.hop_count as number}-hop cycle · Risk: {c.cycle_risk_score != null ? ((c.cycle_risk_score as number) * 100).toFixed(0) : "0"}%</p>
                  <p className="text-gray-500 mt-1 font-mono">Sequence: {(c.nodes as string[])?.join(" → ")}</p>
                </div>
              ))}
            </div>
          )}

          <div className="bg-white border rounded-xl p-5 shadow-sm">
            <h3 className="font-semibold text-sm text-gray-800 mb-3">Guardrail Log</h3>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="flex items-center gap-2">
                {guardrail.ood_check_passed ? <CheckCircle className="w-4 h-4 text-green-600" /> : <AlertCircle className="w-4 h-4 text-red-600" />}
                <span className="font-medium">OOD Check: {guardrail.ood_check_passed ? "Passed" : "Failed"}</span>
              </div>
              <div>Reconciliation Rate: <strong>{guardrail.reconciliation_rate != null ? `${((guardrail.reconciliation_rate as number) * 100).toFixed(1)}%` : "N/A"}</strong></div>
              <div>Extraction Confidence: <strong>{guardrail.extraction_confidence as string}</strong></div>
              <div>Manual Mapping Used: <strong>{guardrail.manual_mapping_used ? "Yes" : "No"}</strong></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
