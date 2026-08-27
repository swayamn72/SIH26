import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, FileWarning, GitBranch } from "lucide-react";
import { api, SarCaseGraph } from "../lib/api";
import { Badge, Card, EmptyState, LoadingPanel, SeverityBadge } from "../components/ui";

/** Minimal entry point from persisted case findings to the investigator draft. */
export function CaseFindingsPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [graph, setGraph] = useState<SarCaseGraph | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    api.getSarCaseGraph(Number(caseId)).then(
      (result) => !cancelled && setGraph(result),
      (reason: unknown) => !cancelled && setError(reason instanceof Error ? reason.message : "Unable to load case findings."),
    );
    return () => { cancelled = true; };
  }, [caseId]);

  if (!graph && !error) return <LoadingPanel label="Loading case findings" />;
  if (error) return <div className="p-6"><EmptyState icon={FileWarning} title="Unable to load case findings" description={error} /></div>;
  if (!graph || graph.findings.length === 0) {
    return <div className="p-6"><EmptyState icon={GitBranch} title="No case findings available" description="Run case analysis before generating an evidence-cited investigator draft." /></div>;
  }

  return (
    <div className="animate-fade-in p-4 sm:p-6">
      <div className="mx-auto max-w-5xl space-y-3">
        <div><Badge tone="info" dot>Case investigation</Badge><h1 className="mt-2 text-xl font-semibold text-ink-950">Case #{graph.case_id} findings</h1><p className="mt-1 text-sm text-ink-500">Open a finding to create a deterministic, evidence-cited SAR/STR investigator draft.</p></div>
        {graph.findings.map((finding) => (
          <Card key={finding.id} className="p-4">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><div className="flex flex-wrap items-center gap-2"><SeverityBadge severity={finding.risk_score >= 0.75 ? "HIGH" : "MEDIUM"} /><Badge mono>{finding.id}</Badge></div><h2 className="mt-2 text-sm font-semibold text-ink-900">{finding.kind.replace(/_/g, " ")}</h2><p className="mt-1 text-xs text-ink-500">{finding.hop_count} ordered hops · {finding.source_row_ids.length} cited source row(s)</p></div><Link to={`/cases/${graph.case_id}/findings/${encodeURIComponent(finding.id)}/sar-draft`} className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-brand-600 bg-brand-600 px-3.5 text-[13px] font-medium text-white shadow-card hover:bg-brand-700">Open SAR/STR draft <ArrowRight className="h-4 w-4" /></Link></div>
          </Card>
        ))}
      </div>
    </div>
  );
}
