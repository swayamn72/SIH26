import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  FileSearch,
  Upload,
  Columns3,
  ShieldCheck,
} from "lucide-react";
import { api, StatementPreview } from "../lib/api";
import { useStatement } from "../lib/StatementContext";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  EmptyState,
  LinkButton,
  LoadingPanel,
  MetaItem,
  PageHeader,
  StatTile,
  Tone,
} from "../components/ui";

const CANONICAL_FIELDS = [
  "txn_date",
  "value_date",
  "narration",
  "debit_amount",
  "credit_amount",
  "balance_after",
  "reference_no",
];

const REQUIRED_FIELDS = ["txn_date", "narration"];

export function ExtractionReviewPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentId, setCurrentId, refreshStatements, statements } = useStatement();

  const effectiveId = id ? Number(id) : currentId;

  const [preview, setPreview] = useState<StatementPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);
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
    api
      .getPreview(effectiveId)
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
    setError(null);
    try {
      if (Object.keys(mapping).length > 0) {
        await api.updateMapping(effectiveId, mapping);
      }
      await api.confirmExtraction(effectiveId);
      await refreshStatements();
      navigate(`/dashboard/${effectiveId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConfirming(false);
    }
  };

  if (loading) return <LoadingPanel label="Loading extraction preview" />;

  if (!effectiveId || !preview) {
    return (
      <div className="animate-fade-in">
        <PageHeader
          eyebrow={<Badge tone="info" dot>Step 2 · Verification</Badge>}
          title="Extraction Review"
          description="Confirm how each statement column maps to the canonical transaction schema before scoring runs."
        />
        <div className="p-4 sm:p-6">
          <EmptyState
            icon={FileSearch}
            title={effectiveId ? `No preview for case #${effectiveId}` : "No case selected"}
            description={
              effectiveId
                ? "This statement may already be analysed, or its parse preview is unavailable."
                : "Pick a case from the list below, or upload a new statement."
            }
            actions={<LinkButton to="/" variant="primary" size="md" icon={Upload}>Go to upload</LinkButton>}
          >
            {statements.length > 0 && (
              <>
                <p className="label-micro mb-2">Available cases</p>
                <div className="divide-y divide-ink-100 overflow-hidden rounded-lg border border-ink-100 bg-white">
                  {statements.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => {
                        setCurrentId(s.id);
                        navigate(`/review/${s.id}`);
                      }}
                      className="flex w-full items-center justify-between px-3 py-2.5 text-left transition-colors hover:bg-brand-50/60"
                    >
                      <span className="truncate text-[13px] font-medium text-ink-800">
                        #{s.id} · {s.original_filename}
                      </span>
                      <span className="shrink-0 text-xs font-semibold text-brand-600">Review →</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </EmptyState>
        </div>
      </div>
    );
  }

  const conf = preview.extraction_confidence;
  const level = conf == null ? "pending" : conf >= 0.98 ? "high" : conf >= 0.85 ? "medium" : "low";
  const levelTone: Tone =
    level === "high" ? "success" : level === "pending" ? "info" : level === "medium" ? "warning" : "danger";

  const mappedFields = Object.values(mapping).filter(Boolean);
  const missingRequired = REQUIRED_FIELDS.filter((f) => !mappedFields.includes(f));
  const columns = Object.entries(mapping);

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={
          <>
            <Badge tone="info" dot>Step 2 · Verification</Badge>
            <Badge tone="neutral" mono>CASE #{effectiveId}</Badge>
          </>
        }
        title="Extraction Review"
        description="Every downstream score depends on this mapping. Confirm the detected schema, adjust anything mis-read, then run detection."
        meta={
          <>
            <MetaItem label="Rows parsed" value={preview.transaction_count} />
            <MetaItem label="Columns detected" value={columns.length} icon={Columns3} />
          </>
        }
        actions={
          <Button
            variant="primary"
            size="md"
            icon={ArrowRight}
            onClick={handleConfirm}
            disabled={confirming}
          >
            {confirming ? "Running detection…" : "Confirm & analyse"}
          </Button>
        }
      />

      <div className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            label="Extraction confidence"
            value={conf == null ? "Ready" : `${(conf * 100).toFixed(1)}%`}
            tone={levelTone}
            hint={level === "pending" ? "Awaiting confirmation" : `Confidence tier: ${level}`}
          />
          <StatTile
            label="Balance reconciliation"
            value={
              preview.reconciliation_rate != null
                ? `${(preview.reconciliation_rate * 100).toFixed(1)}%`
                : "—"
            }
            tone={
              preview.reconciliation_rate != null && preview.reconciliation_rate >= 0.98
                ? "success"
                : "warning"
            }
            hint="Rows whose running balance checks out"
          />
          <StatTile
            label="Statement fit (OOD)"
            value={preview.ood_score != null ? `${(preview.ood_score * 100).toFixed(0)}%` : "—"}
            tone={preview.ood_score != null && preview.ood_score >= 0.7 ? "success" : "warning"}
            hint="Match to a known statement shape"
          />
          <StatTile label="Transactions" value={preview.transaction_count} hint="Parsed from this file" />
        </div>

        {level === "low" && (
          <Callout tone="danger" icon={AlertCircle} title="Low extraction confidence">
            Verify each column below before analysing — a mis-mapped amount column will distort every
            downstream score.
          </Callout>
        )}

        {missingRequired.length > 0 && (
          <Callout tone="warning" icon={AlertCircle} title="Required fields unmapped">
            <span className="font-mono">{missingRequired.join(", ")}</span> must be mapped for the
            detection rules to run correctly.
          </Callout>
        )}

        {error && (
          <Callout tone="danger" icon={AlertCircle} title="Analysis failed">
            {error}
          </Callout>
        )}

        <Card>
          <CardHeader
            title="Column mapping"
            description="Left: the header found in your file. Right: the canonical field it feeds."
            icon={Columns3}
            actions={
              <Badge tone={missingRequired.length === 0 ? "success" : "warning"} dot>
                {mappedFields.length} of {columns.length} columns mapped
              </Badge>
            }
          />
          {columns.length > 0 ? (
            <div className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-3">
              {columns.map(([col, field]) => {
                const isRequired = REQUIRED_FIELDS.includes(field);
                return (
                  <div
                    key={col}
                    className={`rounded-lg border p-3 transition-colors ${
                      field ? "border-ink-100 bg-white" : "border-dashed border-ink-200 bg-ink-50/60"
                    }`}
                  >
                    <div className="mb-2 flex min-h-[22px] items-center justify-between gap-2">
                      <span className="label-micro">Source header</span>
                      {isRequired && <Badge tone="info">required</Badge>}
                    </div>
                    <p
                      className="mb-2.5 truncate font-mono text-[12px] font-medium text-ink-800"
                      title={col}
                    >
                      {col}
                    </p>
                    <label className="label-micro mb-1 block">Maps to</label>
                    <select
                      value={field}
                      onChange={(e) => setMapping((prev) => ({ ...prev, [col]: e.target.value }))}
                      className="w-full cursor-pointer rounded-md border border-ink-200 bg-white px-2 py-1.5 font-mono text-[12px] font-medium text-ink-800 outline-none transition-colors hover:border-ink-300 focus:border-brand-500"
                    >
                      <option value="">— ignore —</option>
                      {CANONICAL_FIELDS.map((f) => (
                        <option key={f} value={f}>
                          {f}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-5 text-[13px] text-ink-400">
              No columns detected, or this statement has already been processed.
            </div>
          )}
        </Card>

        <Card padded className="bg-ink-50/40">
          <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
            <div className="flex items-start gap-2.5">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              <div>
                <p className="text-[13px] font-semibold text-ink-900">Ready to run detection</p>
                <p className="text-[11px] text-ink-400">
                  Confirming applies the mapping, computes all features, evaluates every rule and builds
                  the evidence bundle for case #{effectiveId}.
                </p>
              </div>
            </div>
            <Button
              variant="primary"
              size="md"
              icon={confirming ? undefined : CheckCircle2}
              onClick={handleConfirm}
              disabled={confirming}
            >
              {confirming ? "Running detection…" : "Confirm & analyse"}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
