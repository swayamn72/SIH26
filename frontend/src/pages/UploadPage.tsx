import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, File, X, CheckCircle, AlertCircle, Trash2, ArrowRight, ShieldAlert, FileText, GitGraph, Search, LayoutDashboard, Calendar, Clock } from "lucide-react";
import { api } from "../lib/api";
import { useStatement } from "../lib/StatementContext";

type UploadResult = {
  results: { statement_id: number; original_filename: string; ood_score: number; ood_signals: Record<string, number>; status: string }[];
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
    const dropped = Array.from(e.dataTransfer.files).filter(
      (f) => f.name.match(/\.(pdf|csv|xlsx|xls)$/i),
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
    if (window.confirm(`Delete Statement #${id}? This will remove all associated transactions and analysis.`)) {
      await deleteStatement(id);
    }
  };

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mb-1">Statement Upload & History</h1>
        <p className="text-gray-500 text-xs sm:text-sm">Upload PDF, CSV, or XLSX bank statements for local, deterministic mule analysis.</p>
      </div>

      {/* Upload Box */}
      <div className="bg-white border rounded-xl p-4 sm:p-6 shadow-sm">
        <div
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          className={`border-2 border-dashed rounded-lg p-6 sm:p-10 text-center transition-colors cursor-pointer ${
            dragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 bg-gray-50/50"
          }`}
          onClick={() => document.getElementById("file-input")?.click()}
        >
          <input
            id="file-input"
            type="file"
            multiple
            accept=".pdf,.csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => setFiles((prev) => [...prev, ...Array.from(e.target.files || [])])}
          />
          <Upload className="w-8 h-8 sm:w-10 sm:h-10 mx-auto text-blue-600 mb-3" />
          <p className="text-sm sm:text-base font-semibold text-gray-800 mb-1">Drag & drop bank statements here</p>
          <p className="text-[11px] sm:text-xs text-gray-400">Supported formats: PDF, CSV, XLSX (Air-gapped / Local only)</p>
        </div>

        {files.length > 0 && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">{files.length} file(s) selected</h3>
            <div className="space-y-2">
              {files.map((f, i) => (
                <div key={i} className="flex items-center justify-between bg-gray-50 border rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2 truncate mr-2">
                    <File className="w-4 h-4 text-blue-600 shrink-0" />
                    <span className="text-xs sm:text-sm font-medium text-gray-800 truncate">{f.name}</span>
                    <span className="text-[10px] sm:text-xs text-gray-400 shrink-0">({(f.size / 1024).toFixed(1)} KB)</span>
                  </div>
                  <button onClick={() => removeFile(i)} className="text-gray-400 hover:text-red-500 p-1">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="mt-4 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium text-sm flex items-center gap-2 shadow-sm transition-colors"
            >
              {uploading ? (
                <>Processing Statement...</>
              ) : (
                <>Upload & Analyze <ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
            <div>
              <p className="font-medium text-red-700 text-sm">Upload Error</p>
              <p className="text-xs text-red-600 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* Upload Results for immediate upload */}
        {result && (
          <div className="mt-6 space-y-3">
            <h3 className="text-sm font-semibold text-gray-700">Recent Upload Result</h3>

            {result.errors && result.errors.length > 0 && (
              <div className="space-y-2">
                {result.errors.map((e, i) => (
                  <div key={i} className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2.5 text-xs">
                    <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                    <div>
                      <p className="font-semibold text-red-800">{String((e as Record<string, unknown>).filename ?? "File")}</p>
                      <p className="text-red-600">{String((e as Record<string, unknown>).error ?? "Rejected")}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {result.results.map((r, i) => (
              <div key={i} className="bg-blue-50/60 border border-blue-200 rounded-lg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-gray-900 text-sm">Statement #{r.statement_id}: {r.original_filename}</span>
                    <span className="text-xs bg-green-100 text-green-800 font-semibold px-2 py-0.5 rounded">
                      OOD: {(r.ood_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">Successfully ingested and mapped into database.</p>
                </div>
                <button
                  onClick={() => handleOpenStatement(r.statement_id, "review")}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700 flex items-center gap-1.5 shadow-sm self-start sm:self-auto"
                >
                  Review Extraction <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Persistent Statement History Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base sm:text-lg font-bold text-gray-900">Statements History ({statements.length})</h2>
            <p className="text-xs text-gray-500">All uploaded statements are saved locally in SQLite. Click any statement to inspect.</p>
          </div>
        </div>

        {statements.length === 0 ? (
          <div className="bg-white border rounded-xl p-8 text-center text-gray-400">
            <FileText className="w-10 h-10 mx-auto text-gray-300 mb-2" />
            <p className="text-sm font-medium">No statements in history</p>
            <p className="text-xs text-gray-400 mt-1">Upload a bank statement above to start analyzing.</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {statements.map((s) => {
              const isSelected = s.id === currentId;
              const hasAnalysis = s.tier != null;

              return (
                <div
                  key={s.id}
                  className={`bg-white border rounded-xl p-4 transition-all shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                    isSelected ? "border-blue-500 ring-2 ring-blue-100 bg-blue-50/20" : "hover:border-gray-300"
                  }`}
                >
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-sm text-gray-900">#{s.id}</span>
                      <span className="font-semibold text-sm text-gray-800 truncate max-w-xs" title={s.original_filename || ""}>
                        {s.original_filename || "Untitled Statement"}
                      </span>

                      {/* Status / Tier Badge */}
                      {s.tier === "CONFIRMED_SUSPICIOUS" ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                          <ShieldAlert className="w-3 h-3" /> Suspicious ({s.fused_score?.toFixed(1)})
                        </span>
                      ) : s.tier === "LIKELY_LEGITIMATE" ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                          <CheckCircle className="w-3 h-3" /> Legitimate ({s.fused_score?.toFixed(1)})
                        </span>
                      ) : s.tier === "REVIEW_REQUIRED" ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                          <AlertCircle className="w-3 h-3" /> Review Required ({s.fused_score?.toFixed(1)})
                        </span>
                      ) : (
                        <span className="text-[11px] font-medium bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                          {s.status}
                        </span>
                      )}

                      {isSelected && (
                        <span className="text-[10px] uppercase tracking-wider font-bold bg-blue-600 text-white px-2 py-0.5 rounded">
                          Active Tab Target
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-xs text-gray-500 flex-wrap">
                      {s.transaction_count != null && (
                        <span><strong>{s.transaction_count}</strong> transactions</span>
                      )}
                      {s.observed_start && s.observed_end && (
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-gray-400" />
                          {s.observed_start} to {s.observed_end}
                        </span>
                      )}
                      {s.upload_ts && (
                        <span className="flex items-center gap-1 text-gray-400">
                          <Clock className="w-3 h-3" />
                          {new Date(s.upload_ts).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 shrink-0">
                    <button
                      onClick={() => handleOpenStatement(s.id, "review")}
                      className="px-2.5 sm:px-3 py-1.5 text-xs font-medium border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-1 text-gray-700 transition-colors"
                      title="Extraction Column Review"
                    >
                      <FileText className="w-3.5 h-3.5" /> Review
                    </button>

                    <button
                      onClick={() => handleOpenStatement(s.id, "dashboard")}
                      className={`px-2.5 sm:px-3 py-1.5 text-xs font-medium rounded-lg flex items-center gap-1 transition-colors ${
                        hasAnalysis
                          ? "bg-blue-600 text-white hover:bg-blue-700 shadow-sm"
                          : "border border-blue-200 text-blue-700 bg-blue-50 hover:bg-blue-100"
                      }`}
                      title="Open Detection Dashboard"
                    >
                      <LayoutDashboard className="w-3.5 h-3.5" /> Dashboard
                    </button>

                    <button
                      onClick={() => handleOpenStatement(s.id, "graph")}
                      className="px-2.5 sm:px-3 py-1.5 text-xs font-medium border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-1 text-gray-700 transition-colors"
                      title="Proof Graph"
                    >
                      <GitGraph className="w-3.5 h-3.5" /> Graph
                    </button>

                    <button
                      onClick={() => handleOpenStatement(s.id, "evidence")}
                      className="px-2.5 sm:px-3 py-1.5 text-xs font-medium border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-1 text-gray-700 transition-colors"
                      title="Evidence Explorer"
                    >
                      <Search className="w-3.5 h-3.5" /> Evidence
                    </button>

                    <button
                      onClick={(e) => handleDelete(s.id, e)}
                      className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="Delete Statement"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
