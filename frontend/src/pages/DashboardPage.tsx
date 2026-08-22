import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { LayoutDashboard, GitGraph, Search, FileText, ArrowRight, Upload } from "lucide-react";
import { RiskGauge } from "../components/RiskGauge";
import { MetricCard } from "../components/MetricCard";
import { RuleTriggerList } from "../components/RuleTriggerList";
import { TransactionTable } from "../components/TransactionTable";
import { NarrativePanel } from "../components/NarrativePanel";
import { api, EvidenceBundle } from "../lib/api";
import { useStatement } from "../lib/StatementContext";

export function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentId, setCurrentId, statements } = useStatement();

  const effectiveId = id ? Number(id) : currentId;

  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [narrative, setNarrative] = useState<{ text: string; source: string } | null>(null);
  const [transactions, setTransactions] = useState<{ rows: Record<string, unknown>[]; total: number }>({ rows: [], total: 0 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

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
    setNotFound(false);

    Promise.all([
      api.getEvidence(effectiveId).catch(() => null),
      api.getTransactions(effectiveId).catch(() => ({ rows: [], total: 0 })),
    ])
      .then(([evBundle, txns]) => {
        if (!evBundle) {
          setNotFound(true);
        } else {
          setBundle(evBundle);
        }
        if (txns) setTransactions(txns as any);
      })
      .finally(() => setLoading(false));

    // Fetch the LLM narrative separately since it takes a long time
    api.getNarrative(effectiveId)
      .then((narr) => {
        if (narr) setNarrative(narr);
      })
      .catch(() => null);
  }, [effectiveId]);

  if (loading) {
    return (
      <div className="p-8 text-gray-500 flex items-center gap-2">
        <LayoutDashboard className="w-5 h-5 animate-pulse text-blue-600" /> Loading analysis dashboard...
      </div>
    );
  }

  if (!effectiveId || notFound || !bundle) {
    return (
      <div className="p-4 sm:p-6 max-w-4xl mx-auto">
        <div className="bg-white border rounded-xl p-6 sm:p-8 text-center shadow-sm space-y-4">
          <LayoutDashboard className="w-12 h-12 mx-auto text-gray-400" />
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              {!effectiveId ? "No Statement Selected" : `Statement #${effectiveId} Not Yet Analyzed`}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              {!effectiveId
                ? "Select a statement from history or upload a new statement."
                : "You need to confirm the column mapping before detection rules can run."}
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
                      navigate(s.tier ? `/dashboard/${s.id}` : `/review/${s.id}`);
                    }}
                    className="w-full p-3 text-left hover:bg-blue-50/50 flex items-center justify-between text-xs transition-colors"
                  >
                    <div className="truncate mr-2">
                      <span className="font-semibold text-gray-800">#{s.id}: {s.original_filename}</span>
                      <p className="text-[11px] text-gray-500 mt-0.5">{s.transaction_count || 0} txns · {s.tier || s.status}</p>
                    </div>
                    <span className="text-blue-600 font-semibold shrink-0">{s.tier ? "Open Dashboard →" : "Review →"}</span>
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

  const features = bundle?.features || [];
  const rules = bundle?.triggered_rules || [];
  const decision = bundle?.final_decision || {};
  const cycles = bundle?.cycles_detected || [];
  const summary = bundle?.account_summary || {};
  const tier = (decision.tier as string) || "REVIEW_REQUIRED";
  const score = (decision.fused_score as number) || 0;

  const chartData = features
    .filter((f) => typeof f.value === "number")
    .slice(0, 10)
    .map((f) => ({ name: f.name, value: f.value as number, family: f.family }));

  const anomaly = bundle?.anomaly_detail || null;
  const madFeatures = (anomaly?.mad_flagged_features as Record<string, number>) || {};
  const madCount = Object.keys(madFeatures).length;
  const ruleScoreNum = typeof decision.rule_score === "number" ? decision.rule_score : (rules.reduce((acc, r) => acc + ((r.points as number) || 0), 0));
  const anomalyScorePct = typeof decision.anomaly_score === "number" 
    ? (decision.anomaly_score * 100) 
    : (features.length > 0 ? (madCount / Math.max(features.length, 1)) * 100 : 0);

  const decisionReason = (decision.decision_reason as string) || (
    tier === "CONFIRMED_SUSPICIOUS"
      ? `Fused risk score (${score.toFixed(1)} >= 75) with active regulatory fraud rules triggered.`
      : tier === "LIKELY_LEGITIMATE"
      ? `Fused score (${score.toFixed(1)} <= 25) with 0 severe rules triggered and normal anomaly sub-score (${anomalyScorePct.toFixed(1)}% < 30%).`
      : rules.length === 0 && score <= 25
      ? `0 deterministic rules triggered (Rule Score: 0.0), but statistical anomaly sub-score (${anomalyScorePct.toFixed(1)}%) exceeded the strict auto-clear threshold (< 30.0%). Conservative AML policy requires human sign-off.`
      : `Ambiguous risk score (${score.toFixed(1)} / 100) requiring investigator verification.`
  );

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Mule Detection Dashboard</h1>
            <span className="text-xs bg-blue-100 text-blue-800 font-bold px-2 py-0.5 rounded">
              Statement #{effectiveId}
            </span>
          </div>
          <p className="text-gray-500 text-xs sm:text-sm mt-1">
            {summary.original_filename as string || "Bank Statement"} · {summary.transaction_count as number} transactions analyzed
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/graph/${effectiveId}`}
            className="px-3.5 py-1.5 bg-white border border-gray-300 rounded-lg text-xs font-medium hover:bg-gray-50 flex items-center gap-1.5 shadow-sm transition-colors"
          >
            <GitGraph className="w-3.5 h-3.5 text-purple-600" /> Proof Graph
          </Link>
          <Link
            to={`/evidence/${effectiveId}`}
            className="px-3.5 py-1.5 bg-white border border-gray-300 rounded-lg text-xs font-medium hover:bg-gray-50 flex items-center gap-1.5 shadow-sm transition-colors"
          >
            <Search className="w-3.5 h-3.5 text-blue-600" /> Evidence Bundle
          </Link>
          <Link
            to={`/review/${effectiveId}`}
            className="px-3.5 py-1.5 bg-white border border-gray-300 rounded-lg text-xs font-medium hover:bg-gray-50 flex items-center gap-1.5 shadow-sm transition-colors"
          >
            <FileText className="w-3.5 h-3.5 text-gray-600" /> Column Mapping
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 space-y-3">
          <div className="bg-white border rounded-xl p-4 shadow-sm text-center">
            <RiskGauge score={score} tier={tier as "CONFIRMED_SUSPICIOUS" | "REVIEW_REQUIRED" | "LIKELY_LEGITIMATE"} />
            <div className="mt-2 text-xs text-gray-400 font-mono">{decision.score_formula_used as string}</div>
            
            <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t text-left">
              <div className="p-2 bg-gray-50 rounded border">
                <span className="text-[10px] uppercase font-semibold text-gray-400 block">Rule Score</span>
                <span className="text-xs font-bold text-gray-800">{ruleScoreNum.toFixed(1)} pts</span>
                <span className="text-[10px] text-gray-500 block">65% weight</span>
              </div>
              <div className="p-2 bg-gray-50 rounded border">
                <span className="text-[10px] uppercase font-semibold text-gray-400 block">Anomaly Sub-Score</span>
                <span className={`text-xs font-bold ${anomalyScorePct >= 30 ? "text-amber-700" : "text-green-700"}`}>
                  {anomalyScorePct.toFixed(1)}%
                </span>
                <span className="text-[10px] text-gray-500 block">&lt; 30% to auto-clear</span>
              </div>
            </div>
          </div>

          <div className={`p-3 rounded-xl border text-xs shadow-sm ${
            tier === "CONFIRMED_SUSPICIOUS" 
              ? "bg-red-50/80 border-red-200 text-red-800" 
              : tier === "LIKELY_LEGITIMATE" 
              ? "bg-green-50/80 border-green-200 text-green-800" 
              : "bg-amber-50/80 border-amber-200 text-amber-800"
          }`}>
            <div className="font-semibold mb-1 flex items-center justify-between">
              <span>Decision Policy Rationale</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/70">{tier}</span>
            </div>
            <p className="text-[11px] leading-relaxed">{decisionReason}</p>
          </div>
        </div>
        <div className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-3">
          {features.slice(0, 8).map((f) => (
            <MetricCard
              key={f.name as string}
              title={f.name as string}
              value={f.value != null ? (typeof f.value === "number" ? f.value.toFixed(2) : String(f.value)) : "N/A"}
              formula={f.formula as string}
              explanation={f.explanation as string}
            />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <h3 className="font-semibold text-sm mb-3">Triggered Rules</h3>
          <RuleTriggerList rules={rules as any[]} />
          {cycles.length > 0 && (
            <div className="mt-4">
              <h4 className="font-semibold text-sm mb-2">Detected Cycles</h4>
              {cycles.map((c) => (
                <div key={c.cycle_id as string} className="border border-purple-200 bg-purple-50 rounded-lg p-3 mb-2">
                  <div className="font-mono text-xs font-bold text-purple-700">{c.cycle_id as string}</div>
                  <div className="text-sm">{c.hop_count as number}-hop cycle</div>
                  <div className="text-xs text-gray-500">Risk: {c.cycle_risk_score != null ? ((c.cycle_risk_score as number) * 100).toFixed(0) : "N/A"}%</div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="lg:col-span-2 space-y-4">
          {chartData.length > 0 && (
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <h3 className="font-semibold text-sm mb-3">Feature Distribution</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData}>
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="value" fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {narrative && narrative.text && (
            <NarrativePanel
              text={narrative.text}
              source={narrative.source as "ai" | "template"}
            />
          )}
        </div>
      </div>

      <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
        <div className="border-b px-4 py-3 font-semibold text-sm text-gray-800 flex items-center justify-between">
          <span>Transaction Audit Table</span>
          <span className="text-xs font-normal text-gray-500">{transactions.total} total rows</span>
        </div>
        <TransactionTable
          rows={transactions.rows as any[]}
          total={transactions.total}
          page={page}
          pageSize={100}
          onPageChange={setPage}
        />
      </div>
    </div>
  );
}
