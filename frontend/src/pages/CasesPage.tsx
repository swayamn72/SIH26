import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight, FolderKanban, GitGraph, Plus } from "lucide-react";
import { api, InvestigationCase } from "../lib/api";
import { Badge, Button, Card, CardHeader, EmptyState, LoadingPanel, PageHeader, formatDate } from "../components/ui";

export function CasesPage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<InvestigationCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listCases()
      .then(setCases)
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "Unable to load investigation cases."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingPanel label="Loading investigation cases" />;
  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={<Badge tone="accent" dot>Multi-statement investigation</Badge>}
        title="Investigation Cases"
        description="Select a persisted case to trace evidence-backed fund flows across its member statements."
      />
      <div className="mx-auto max-w-6xl p-4 sm:p-6">
        {error ? <EmptyState icon={AlertTriangle} title="Unable to load cases" description={error} /> : cases.length === 0 ? (
          <EmptyState
            icon={FolderKanban}
            title="No investigation cases yet"
            description="Create a case from confirmed statements through the case API, then run its analysis to materialize the cross-statement graph."
            actions={<Button variant="primary" icon={Plus} onClick={() => navigate("/")}>Back to statements</Button>}
          />
        ) : (
          <Card>
            <CardHeader title={`${cases.length} investigation case${cases.length === 1 ? "" : "s"}`} icon={FolderKanban} />
            <div className="divide-y divide-ink-100">
              {cases.map((item) => (
                <button key={item.id} onClick={() => navigate(`/cases/${item.id}/graph`)} className="flex w-full items-center justify-between gap-4 px-4 py-4 text-left hover:bg-ink-50 sm:px-5">
                  <span className="min-w-0">
                    <span className="flex flex-wrap items-center gap-2"><span className="truncate text-sm font-semibold text-ink-900">{item.name}</span>{item.analyzed_ts ? <Badge tone="success">Analysed</Badge> : <Badge tone="warning">Awaiting analysis</Badge>}</span>
                    <span className="mt-1 block truncate text-xs text-ink-500">{item.description || "No description provided"}</span>
                    <span className="mt-1 block text-[11px] text-ink-400">{item.statement_ids.length} statements · v{item.analysis_version} · updated {formatDate(item.analyzed_ts || item.created_ts)}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2 text-xs font-semibold text-brand-700"><GitGraph className="h-4 w-4" /> Open graph <ArrowRight className="h-4 w-4" /></span>
                </button>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
