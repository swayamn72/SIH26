const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  if (!(options?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${BASE}${path}`, {
    headers: { ...headers, ...(options?.headers as Record<string, string>) },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export type HealthStatus = {
  status: string;
  app: string;
  version: string;
  timestamp: string;
  offline_mode: boolean;
};

export type StatementPreview = {
  statement_id: number;
  status: string;
  ood_score: number;
  ood_signals: Record<string, number>;
  reconciliation_rate: number;
  extraction_confidence: number;
  transaction_count: number;
  detected_column_mapping: Record<string, string>;
};

export type EvidenceBundle = {
  account_summary: Record<string, unknown>;
  final_decision: Record<string, unknown>;
  triggered_rules: Record<string, unknown>[];
  features: Record<string, unknown>[];
  cycles_detected: Record<string, unknown>[];
  anomaly_detail: Record<string, unknown> | null;
  supervised_detail: Record<string, unknown> | null;
  guardrail_log: Record<string, unknown>;
};

export type GraphData = {
  nodes: { id: string; label: string; flow: number }[];
  edges: { source: string; target: string; amount: number; channel: string; row_id: string }[];
  cycles: { cycle_id: string; nodes: string[]; cycle_risk_score: number; hop_count: number }[];
  mule_row_ids?: string[];
  mule_nodes?: string[];
};

export type StatementItem = {
  id: number;
  original_filename: string | null;
  upload_ts: string;
  status: string;
  ood_score: number | null;
  ood_tier: string | null;
  extraction_confidence: number | null;
  reconciliation_rate: number | null;
  transaction_count: number | null;
  observed_start: string | null;
  observed_end: string | null;
  tier: string | null;
  fused_score: number | null;
};

export type PagedTransactions = {
  rows: Record<string, unknown>[];
  total: number;
  page: number;
  page_size: number;
};

export const api = {
  health: () => request<HealthStatus>("/health"),
  offlineCheck: () => request<{ status: string; message: string }>("/health/offline-check"),

  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<{ results: { statement_id: number; original_filename: string; ood_score: number; ood_signals: Record<string, number>; status: string }[]; errors: Record<string, unknown>[] }>("/statements/upload", {
      method: "POST",
      body: form,
    });
  },

  getPreview: (id: number) => request<StatementPreview>(`/statements/${id}/preview`),

  updateMapping: (id: number, mapping: Record<string, string>) =>
    request<{ status: string }>(`/statements/${id}/mapping`, {
      method: "POST",
      body: JSON.stringify({ column_mapping: mapping }),
    }),

  confirmExtraction: (id: number) =>
    request<{ status: string }>(`/statements/${id}/confirm`, { method: "POST" }),

  getEvidence: (id: number) => request<EvidenceBundle>(`/statements/${id}/evidence`),

  getTransactions: async (id: number, page = 1, pageSize = 100) => {
    const offset = (page - 1) * pageSize;
    const res = await request<{ total: number; offset: number; limit: number; items: Record<string, unknown>[] }>(`/statements/${id}/transactions?offset=${offset}&limit=${pageSize}`);
    return {
      rows: res.items,
      total: res.total,
      page,
      page_size: pageSize,
    };
  },

  getGraph: (id: number) => request<GraphData>(`/statements/${id}/graph`),

  getNarrative: async (id: number) => {
    const res = await request<{ statement_id: number; narrative: string; source: string }>(`/statements/${id}/narrative`);
    return { text: res.narrative, source: res.source };
  },

  batchMerge: (statement_ids: number[]) =>
    request<GraphData>("/statements/batch/merge", {
      method: "POST",
      body: JSON.stringify({ statement_ids }),
    }),

  exportReport: async (id: number) => {
    const res = await fetch(`${BASE}/statements/${id}/export`, { method: "POST" });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `statement_${id}_report`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  listStatements: () => request<StatementItem[]>("/statements"),
  deleteStatement: (id: number) => request<{ status: string; statement_id: number }>(`/statements/${id}`, { method: "DELETE" }),
  purgeAll: () => request<{ status: string }>("/statements/purge/all", { method: "POST" }),
  getConfig: () => request<Record<string, unknown>>("/config/thresholds"),

  updateConfig: (config: Record<string, unknown>) =>
    request<{ status: string }>("/config/thresholds", {
      method: "PUT",
      body: JSON.stringify(config),
    }),
};
