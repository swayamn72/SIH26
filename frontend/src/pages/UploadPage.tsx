import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Upload,
  File as FileIcon,
  X,
  AlertCircle,
  Trash2,
  ArrowRight,
  FileText,
  GitGraph,
  Search,
  LayoutDashboard,
  Calendar,
  FolderOpen,
  CheckCircle2,
  ShieldCheck,
  Database,
} from "lucide-react";
import { api } from "../lib/api";
import { useStatement } from "../lib/StatementContext";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  EmptyState,
  MetaItem,
  PageHeader,
  StatTile,
  TBody,
  THead,
  Table,
  Td,
  Th,
  TierBadge,
  formatDate,
} from "../components/ui";

type UploadResult = {
  results: {
    statement_id: number;
    original_filename: string;
    ood_score: number;
    ood_signals: Record<string, number>;
    status: string;
  }[];
  errors: Record<string, unknown>[];
};

export function UploadPage() {
  const navigate = useNavigate();
  const { statements, currentId, setCurrentId, refreshStatements, deleteStatement } = useStatement();
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files).filter((f) =>
      f.name.match(/\.(pdf|csv|xlsx|xls)$/i),
    );
    setFiles((prev) => [...prev, ...dropped]);
  }, []);

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const res = (await api.upload(files)) as UploadResult;
      setResult(res);
      await refreshStatements();
      if (res.results && res.results.length > 0) {
        const firstId = res.results[0]?.statement_id;
        if (firstId != null) {
          setCurrentId(firstId);
        }
      }
      setFiles([]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleOpenStatement = (id: number, target: "review" | "dashboard" | "evidence" | "graph") => {
    setCurrentId(id);
    navigate(`/${target}/${id}`);
  };

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (
      window.confirm(
        `Delete case #${id}? This removes its transactions and analysis from the local database.`,
      )
    ) {
      await deleteStatement(id);
    }
  };

  const analysed = statements.filter((s) => s.tier != null);
  const suspicious = statements.filter((s) => s.tier === "CONFIRMED_SUSPICIOUS").length;
  const review = statements.filter((s) => s.tier === "REVIEW_REQUIRED").length;
  const totalTxns = statements.reduce((acc, s) => acc + (s.transaction_count || 0), 0);

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={
          <Badge tone="info" dot>
            Step 1 · Ingestion
          </Badge>
        }
        title="Upload & Cases"
        description="Ingest PDF, CSV or XLSX bank statements. Parsing, scoring and storage all happen on this machine — nothing is transmitted."
        meta={
          statements.length > 0 ? (
            <>
              <MetaItem label="Cases" value={statements.length} icon={FolderOpen} />
              <MetaItem label="Analysed" value={analysed.length} icon={ShieldCheck} />
              <MetaItem label="Transactions" value={totalTxns} icon={Database} />
            </>
          ) : undefined
        }
      />

      <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
        {statements.length > 0 && (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Total cases" value={statements.length} hint="Stored in local SQLite" />
            <StatTile
              label="Confirmed suspicious"
              value={suspicious}
              tone={suspicious > 0 ? "danger" : "neutral"}
              hint="Score ≥ 75 with rules fired"
            />
            <StatTile
              label="Review required"
              value={review}
              tone={review > 0 ? "warning" : "neutral"}
              hint="Needs analyst sign-off"
            />
            <StatTile
              label="Awaiting analysis"
              value={statements.length - analysed.length}
              hint="Extraction not confirmed"
            />
          </div>
        )}

        {/* Upload */}
        <Card>
          <CardHeader
            title="Upload statements"
            description="Drop one or more files, or browse. Multi-file uploads are analysed independently."
            icon={Upload}
          />
          <div className="p-4 sm:p-5">
            <div
              onDrop={onDrop}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onClick={() => document.getElementById("file-input")?.click()}
              className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
                dragging
                  ? "border-brand-500 bg-brand-50"
                  : "border-ink-200 bg-ink-50/60 hover:border-brand-400 hover:bg-brand-50/40"
              }`}
            >
              <input
                id="file-input"
                type="file"
                multiple
                accept=".pdf,.csv,.xlsx,.xls"
                className="hidden"
                onChange={(e) => setFiles((prev) => [...prev, ...Array.from(e.target.files || [])])}
              />
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-ink-200 bg-white shadow-card">
                <Upload className="h-5 w-5 text-brand-600" />
              </div>
              <p className="text-sm font-semibold text-ink-900">Drop bank statements here</p>
              <p className="mt-1 text-xs text-ink-400">
                PDF · CSV · XLSX — or <span className="font-medium text-brand-600">browse files</span>
              </p>
            </div>

            {files.length > 0 && (
              <div className="mt-4">
                <p className="label-micro mb-2">{files.length} file(s) ready</p>
                <div className="space-y-1.5">
                  {files.map((f, i) => (
                    <div
                      key={`${f.name}-${i}`}
                      className="flex items-center justify-between gap-2 rounded-lg border border-ink-100 bg-ink-50/60 px-3 py-2"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <FileIcon className="h-4 w-4 shrink-0 text-brand-600" />
                        <span className="truncate text-[13px] font-medium text-ink-800">{f.name}</span>
                        <span className="num shrink-0 text-[11px] text-ink-400">
                          {(f.size / 1024).toFixed(1)} KB
                        </span>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          removeFile(i);
                        }}
                        className="rounded p-1 text-ink-300 transition-colors hover:bg-red-50 hover:text-red-600"
                        aria-label={`Remove ${f.name}`}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>

                <Button
                  variant="primary"
                  size="md"
                  className="mt-4"
                  onClick={handleUpload}
                  disabled={uploading}
                  icon={uploading ? undefined : ArrowRight}
                >
                  {uploading ? "Parsing statement…" : "Upload & analyse"}
                </Button>
              </div>
            )}

            {error && (
              <div className="mt-4">
                <Callout tone="danger" title="Upload failed" icon={AlertCircle}>
                  {error}
                </Callout>
              </div>
            )}

            {result && (
              <div className="mt-5 space-y-2">
                <p className="label-micro">Latest upload</p>

                {result.errors?.map((e, i) => (
                  <Callout key={i} tone="danger" icon={AlertCircle} title={String(e.filename ?? "File rejected")}>
                    {String(e.error ?? "Rejected")}
                  </Callout>
                ))}

                {result.results.map((r) => (
                  <div
                    key={r.statement_id}
                    className="flex flex-col justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50/70 px-3.5 py-3 sm:flex-row sm:items-center"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                        <span className="text-[13px] font-semibold text-ink-900">
                          Case #{r.statement_id} · {r.original_filename}
                        </span>
                        <Badge tone="success">
                          Statement fit {(r.ood_score * 100).toFixed(0)}%
                        </Badge>
                      </div>
                      <p className="mt-0.5 pl-6 text-[11px] text-ink-500">
                        Parsed and stored locally. Verify the column mapping before scoring.
                      </p>
                    </div>
                    <Button
                      variant="primary"
                      icon={ArrowRight}
                      onClick={() => handleOpenStatement(r.statement_id, "review")}
                    >
                      Review extraction
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Case list */}
        {statements.length === 0 ? (
          <EmptyState
            icon={FolderOpen}
            title="No cases yet"
            description="Upload a bank statement above to run the deterministic mule-account detection pipeline."
          />
        ) : (
          <Card>
            <CardHeader
              title={`Case history (${statements.length})`}
              description="Every uploaded statement, its decision tier and the analyst surfaces available for it."
              icon={FolderOpen}
            />
            <Table minWidth={880}>
              <THead>
                <Th>Case</Th>
                <Th>Statement</Th>
                <Th>Period</Th>
                <Th align="right">Txns</Th>
                <Th>Decision</Th>
                <Th align="right">Score</Th>
                <Th align="right">Actions</Th>
              </THead>
              <TBody>
                {statements.map((s) => {
                  const isSelected = s.id === currentId;
                  const hasAnalysis = s.tier != null;

                  return (
                    <tr
                      key={s.id}
                      className={`transition-colors ${
                        isSelected ? "bg-brand-50/50" : "hover:bg-ink-50/70"
                      }`}
                    >
                      <Td className="whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <span
                            className={`h-4 w-0.5 rounded-full ${
                              isSelected ? "bg-brand-500" : "bg-transparent"
                            }`}
                          />
                          <span className="num text-[13px] font-semibold text-ink-900">#{s.id}</span>
                        </div>
                      </Td>

                      <Td>
                        <p
                          className="max-w-[220px] truncate text-[13px] font-medium text-ink-800"
                          title={s.original_filename || ""}
                        >
                          {s.original_filename || "Untitled statement"}
                        </p>
                        <p className="text-[11px] text-ink-400">
                          Uploaded{" "}
                          {new Date(s.upload_ts).toLocaleString(undefined, {
                            dateStyle: "medium",
                            timeStyle: "short",
                          })}
                        </p>
                      </Td>

                      <Td className="whitespace-nowrap text-[12px] text-ink-500">
                        {s.observed_start && s.observed_end ? (
                          <span className="flex items-center gap-1.5">
                            <Calendar className="h-3.5 w-3.5 text-ink-300" />
                            {formatDate(s.observed_start)} – {formatDate(s.observed_end)}
                          </span>
                        ) : (
                          "—"
                        )}
                      </Td>

                      <Td align="right" className="num text-[13px] font-medium">
                        {s.transaction_count ?? "—"}
                      </Td>

                      <Td>
                        {hasAnalysis ? (
                          <TierBadge tier={s.tier} />
                        ) : (
                          <Badge tone="neutral">{s.status}</Badge>
                        )}
                      </Td>

                      <Td align="right">
                        {s.fused_score != null ? (
                          <span className="num text-[13px] font-bold text-ink-900">
                            {s.fused_score.toFixed(0)}
                            <span className="font-normal text-ink-300">/100</span>
                          </span>
                        ) : (
                          <span className="text-ink-300">—</span>
                        )}
                      </Td>

                      <Td align="right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            title="Extraction review"
                            onClick={() => handleOpenStatement(s.id, "review")}
                          >
                            <FileText className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            title="Evidence explorer"
                            onClick={() => handleOpenStatement(s.id, "evidence")}
                          >
                            <Search className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            title="Proof graph"
                            onClick={() => handleOpenStatement(s.id, "graph")}
                          >
                            <GitGraph className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant={hasAnalysis ? "primary" : "secondary"}
                            icon={LayoutDashboard}
                            onClick={() => handleOpenStatement(s.id, hasAnalysis ? "dashboard" : "review")}
                          >
                            {hasAnalysis ? "Open" : "Analyse"}
                          </Button>
                          <Button
                            variant="ghost"
                            title="Delete case"
                            onClick={(e) => handleDelete(s.id, e)}
                            className="hover:bg-red-50 hover:text-red-600"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </Td>
                    </tr>
                  );
                })}
              </TBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  );
}
