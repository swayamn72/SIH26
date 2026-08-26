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

export type PatternSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export type PatternHop = {
  step: number;
  row_id: string;
  txn_id: string;
  timestamp: string | null;
  value_date: string | null;
  from_id: string;
  from_label: string;
  to_id: string;
  to_label: string;
  direction: "debit" | "credit";
  amount: number;
  channel: string;
  narration: string;
  gap_hours: number | null;
  near_threshold: boolean;
  near_threshold_band: number | null;
  is_rapid: boolean;
  risk_score: number;
  severity: PatternSeverity;
};

export type PatternNode = {
  id: string;
  label: string;
  is_subject: boolean;
  is_return?: boolean;
};

export type SuspiciousPattern = {
  pattern_id: string;
  kind: "cycle" | "layering" | "structuring" | "dormancy_burst";
  title: string;
  summary: string;
  formula: string;
  hop_risk_formula: string;
  risk_score: number;
  severity: PatternSeverity;
  hop_count: number;
  total_amount: number;
  span_days: number;
  started_at: string | null;
  ended_at: string | null;
  node_path: PatternNode[];
  hops: PatternHop[];
  row_ids: string[];
  node_ids: string[];
  linked_rule_ids: string[];
  rule_points: number;
  metrics: Record<string, number | null>;
  truncation_note?: string;
};

export type RuleClause = {
  expression: string;
  field: string | null;
  operator: string | null;
  threshold_expression: string | null;
  threshold_value: number | null;
  actual_value: number | null;
  holds: boolean | null;
};

export type ReasonRule = {
  id: string;
  description: string;
  condition: string;
  points: number;
  joiner: string;
  clauses: RuleClause[];
  contribution_pct: number;
};

export type ReasonFeature = {
  name: string;
  value: number | string | null;
  formula: string;
  explanation: string;
  family?: string;
  threshold_value?: number | null;
  operator?: string | null;
  rule_id?: string;
};

export type ReasonTransaction = {
  row_id: string;
  txn_id: string;
  timestamp: string | null;
  counterparty: string;
  counterparty_id: string;
  amount: number;
  direction: "debit" | "credit";
  channel: string;
  narration: string;
};

export type ReasonCounterparty = {
  counterparty_id: string;
  counterparty: string;
  transaction_count: number;
  total_amount: number;
  inflow: number;
  outflow: number;
  patterns: string[];
};

export type FlagReason = {
  id: string;
  title: string;
  category: string;
  severity: PatternSeverity;
  headline: string;
  detail: string;
  how_computed: string;
  metrics: { label: string; value: string | number }[];
  rules: ReasonRule[];
  rule_points: number;
  contribution_pct: number;
  is_score_driver: boolean;
  features: ReasonFeature[];
  transactions: ReasonTransaction[];
  transactions_withheld: number;
  counterparties?: ReasonCounterparty[];
  counterparties_withheld?: number;
  deviations?: { name: string; value: number; formula: string; explanation: string }[];
  pattern_ids: string[];
  graph_pattern_id: string | null;
};

export type WhyFlagged = {
  statement_id: number;
  tier: string;
  risk_score: number;
  risk_level: "HIGH" | "MEDIUM" | "LOW";
  risk_level_emoji: string;
  thresholds: { likely_legitimate_max: number; confirmed_suspicious_min: number };
  decision_reason: string;
  score_formula: string;
  score_breakdown: {
    component: string;
    weight: number;
    raw_value: number | null;
    points_of_fused: number;
  }[];
  confidence: {
    score: number;
    formula: string;
    components: { name: string; value: number; weight: number; description: string }[];
    detector_agreement: { detector: string; flagged: boolean; agrees: boolean }[];
  };
  reasons: FlagReason[];
  evidence_coverage: {
    transactions_examined: number;
    counterparties_seen: number;
    patterns_detected: number;
    rules_evaluated: number;
    rules_triggered: number;
    features_computed: number;
  };
};

export type PatternsResponse = {
  statement_id: number;
  subject_node_id: string;
  subject_label: string;
  patterns: SuspiciousPattern[];
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

  getPatterns: (id: number) => request<PatternsResponse>(`/statements/${id}/patterns`),

  getWhyFlagged: (id: number) => request<WhyFlagged>(`/statements/${id}/why-flagged`),

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
