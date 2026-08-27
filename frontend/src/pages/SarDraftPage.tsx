import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Download, FileJson, FileText, ShieldAlert } from "lucide-react";
import { api, SarDraft } from "../lib/api";
import { Badge, Button, Card, EmptyState, LoadingPanel, PageHeader } from "../components/ui";

const fiveWLabels: Record<keyof SarDraft["five_w_narrative"], string> = {
  who: "Who", what: "What", when: "When", where: "Where", why: "Why",
};

// Case evidence has no currency field, so do not infer one in a jurisdiction-neutral draft.
const formatValue = (value: number) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);

export function SarDraftPage() {
  const { caseId, findingId } = useParams<{ caseId: string; findingId: string }>();
  const [draft, setDraft] = useState<SarDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"json" | "html" | null>(null);

  useEffect(() => {
    if (!caseId || !findingId) return;
    let cancelled = false;
    api.getSarDraft(Number(caseId), findingId).then(
      (result) => !cancelled && setDraft(result),
      (reason: unknown) => !cancelled && setError(reason instanceof Error ? reason.message : "Unable to generate the draft."),
    );
    return () => { cancelled = true; };
  }, [caseId, findingId]);

  const exportDraft = async (format: "json" | "html") => {
    if (!caseId || !findingId) return;
    setExporting(format);
    try { await api.exportSarDraft(Number(caseId), findingId, format); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Export failed."); }
    finally { setExporting(null); }
  };

  if (!draft && !error) return <LoadingPanel label="Building evidence-cited investigator draft" />;
  if (error && !draft) return <div className="p-6"><EmptyState icon={ShieldAlert} title="Draft unavailable" description={error} /></div>;
  if (!draft) return null;

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={<><Badge tone="warning" dot>SAR/STR investigator draft</Badge><Badge tone="danger">NOT FILED</Badge></>}
        title={`Draft for ${draft.case.name}`}
        description="Deterministic structured content derived from the cited finding. Investigator-owned review is required."
        actions={<>
          <Button icon={FileJson} disabled={exporting !== null} onClick={() => void exportDraft("json")}>{exporting === "json" ? "Exporting…" : "Export JSON"}</Button>
          <Button icon={Download} variant="primary" disabled={exporting !== null} onClick={() => void exportDraft("html")}>{exporting === "html" ? "Exporting…" : "Export HTML"}</Button>
        </>}
      />
      <div className="mx-auto max-w-6xl space-y-4 p-4 sm:p-6">
        <Card accent="warning" className="border-amber-200 bg-amber-50/60 p-4">
          <div className="flex gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" /><div><p className="text-sm font-semibold text-amber-900">Not a filing or legal determination</p><p className="mt-1 text-xs leading-relaxed text-amber-800">{draft.non_filing_notice}</p></div></div>
        </Card>
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="p-4 lg:col-span-2">
            <p className="label-micro">Activity summary</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <div><p className="text-[11px] text-ink-500">Activity period</p><p className="mt-1 text-sm font-semibold">{draft.activity.start_date || "Not available"} – {draft.activity.end_date || "Not available"}</p><p className="text-[10px] text-ink-400">{draft.activity.date_precision} precision</p></div>
              <div><p className="text-[11px] text-ink-500">Aggregate movement</p><p className="num mt-1 text-lg font-bold text-brand-700">{formatValue(draft.activity.total_suspicious_value)}</p><p className="text-[10px] text-ink-400">Currency unavailable in source evidence</p></div>
              <div><p className="text-[11px] text-ink-500">Cited transfers</p><p className="num mt-1 text-lg font-bold">{draft.activity.transfer_count}</p></div>
            </div>
          </Card>
          <Card accent="danger" className="p-4"><div className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-red-600" /><div><p className="text-sm font-semibold">Reviewer confirmation required</p><p className="mt-1 text-xs text-ink-600">{draft.reviewer_confirmation.message}</p><Badge tone="danger" className="mt-3">Pending confirmation</Badge></div></div></Card>
        </div>
        <Card><div className="border-b border-ink-100 px-4 py-3"><p className="text-sm font-semibold">Available subject data</p><p className="text-xs text-ink-500">Only data retained in the cited statement metadata is shown.</p></div><div className="divide-y divide-ink-100">{draft.subject_data.length ? draft.subject_data.map((subject) => <div key={subject.statement_id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs"><span><strong>{subject.account_holder || "Account holder unavailable"}</strong> · Statement #{subject.statement_id}</span><span className="text-ink-500">{subject.institution || "Institution unavailable"} · <code>{subject.source_evidence_id}</code></span></div>) : <p className="p-4 text-xs text-ink-500">No subject data is available.</p>}</div></Card>
        <Card><div className="border-b border-ink-100 px-4 py-3"><p className="text-sm font-semibold">Five-W narrative</p><p className="text-xs text-ink-500">Structured, evidence-bound, and jurisdiction-neutral.</p></div><div className="grid divide-y divide-ink-100 md:grid-cols-2 md:divide-x md:divide-y-0">{(Object.keys(fiveWLabels) as (keyof SarDraft["five_w_narrative"])[]).map((key) => <div key={key} className="p-4"><p className="label-micro">{fiveWLabels[key]}</p><p className="mt-1.5 text-[13px] leading-relaxed text-ink-700">{draft.five_w_narrative[key]}</p></div>)}</div></Card>
        <Card><div className="border-b border-ink-100 px-4 py-3"><p className="text-sm font-semibold">Ordered graph path and citations</p></div><div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-xs"><thead className="bg-ink-50 text-[10px] uppercase tracking-wide text-ink-500"><tr><th className="px-4 py-2">Step</th><th>From</th><th>To</th><th>Amount</th><th>Date</th><th className="px-4">Evidence IDs</th></tr></thead><tbody className="divide-y divide-ink-100">{draft.ordered_graph_path.map((hop) => <tr key={hop.edge_id}><td className="num px-4 py-3">{hop.step}</td><td>{hop.from_label}</td><td>{hop.to_label}</td><td className="num">{formatValue(hop.amount)}</td><td>{hop.txn_date}</td><td className="px-4 font-mono text-[10px] text-ink-500">{hop.evidence_ids.join(", ")}</td></tr>)}</tbody></table></div></Card>
        <div className="grid gap-4 lg:grid-cols-2"><Card className="p-4"><p className="text-sm font-semibold">Limitations</p><ul className="mt-2 list-disc space-y-1.5 pl-4 text-xs leading-relaxed text-ink-600">{draft.limitations.map((item) => <li key={item}>{item}</li>)}</ul></Card><Card className="p-4"><p className="text-sm font-semibold">Unresolved required fields</p><ul className="mt-2 list-disc space-y-1.5 pl-4 text-xs leading-relaxed text-ink-600">{draft.missing_required_fields.map((item) => <li key={item}>{item}</li>)}</ul></Card></div>
        <Link to={`/cases/${caseId}/graph`} className="inline-flex items-center gap-2 text-xs font-medium text-brand-700 hover:text-brand-800"><FileText className="h-4 w-4" /> Back to case graph</Link>
      </div>
    </div>
  );
}
