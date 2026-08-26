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

/* ------------------------------------------------- bank intelligence */

export type TransferDataset = {
  id: number;
  original_filename: string | null;
  upload_ts: string;
  status: string;
  row_count: number;
  rows_skipped: number;
  truncated: boolean;
  bank_count: number;
  account_count: number;
  total_value: number;
  observed_start: string | null;
  observed_end: string | null;
  has_labels: boolean;
  detected_column_mapping: Record<string, string>;
  currencies: string[];
  payment_formats: string[];
};

export type IntelSource = {
  key: string;
  kind: "statements" | "ledger";
  label: string;
  description: string;
  bank_count: number;
  transfer_count: number;
  is_live: boolean;
  has_labels: boolean;
  dataset_id: number | null;
};

export type LedgerCoverage = {
  statements_total: number;
  statements_included: number;
  statements_skipped: number;
  transactions_used: number;
  transfer_rows: number;
  counterparty_attributed: number;
  counterparty_unattributed: number;
  attribution_rate: number;
  mirrored_transfers_deduplicated: number;
  attribution_signals: Record<string, number>;
  subject_banks: { bank_code: string; bank_name: string }[];
  direct_banks: string[];
  per_statement: {
    statement_id: number;
    filename: string | null;
    bank_code: string;
    bank_name: string;
    bank_signal: string;
    transactions: number;
    attributed: number;
    skipped: boolean;
  }[];
};

export type RiskComponent = {
  name: string;
  value: number;
  weight: number;
  severity: number;
  absolute_scale: number;
  peer_scale: number;
  peer_z: number;
  reference: number;
  driver: "peers" | "level";
  points: number;
  description: string;
};

export type NamedTotal = { name: string; transfer_count: number; total_amount: number };

export type FlowCycle = {
  cycle_id: string;
  accounts: string[];
  banks: string[];
  hop_count: number;
  principal: number;
  total_amount: number;
  cycle_span_days: number;
  recurrence: number;
  amount_conservation_ratio: number;
  velocity_compression: number;
  cycle_recurrence: number;
  cycle_risk_score: number;
  transfer_count?: number;
  transfer_indices?: number[];
};

export type BankProfile = {
  bank_code: string;
  display_name: string;
  risk_score: number;
  risk_tier: "HIGH" | "MEDIUM" | "LOW";
  risk_components: RiskComponent[];
  risk_formula: string;
  transfer_count: number;
  sent_count: number;
  received_count: number;
  total_sent: number;
  total_received: number;
  net_flow: number;
  avg_transfer: number;
  median_transfer: number;
  max_transfer: number;
  connected_banks: number;
  counterparty_banks: NamedTotal[];
  format_mix: { format: string; count: number; share: number }[];
  wire_share: number;
  high_risk_format_share: number;
  currency_corridors: NamedTotal[];
  cross_currency_share: number;
  account_count: number;
  account_concentration_hhi: number;
  top_accounts: NamedTotal[];
  active_days: number;
  busiest_day: string | null;
  busiest_day_transfers: number;
  burst_velocity: number;
  structuring_share: number;
  near_threshold_transfers: number;
  threshold_bands: { threshold: number; lower_pct: number }[];
  first_seen: string | null;
  last_seen: string | null;
  centrality: Record<string, number | null>;
  cycle_ids: string[];
  cycle_exposure: number;
  cycle_transfers: number;
  evidence_basis: "direct" | "partial";
  is_subject_bank: boolean;
  has_currency_data: boolean;
  labelled_laundering_transfers: number;
  labelled_laundering_share: number;
};

export type BankListResponse = {
  dataset: TransferDataset | null;
  summary: {
    bank_count: number;
    transfer_count: number;
    total_value: number;
    account_count: number;
    cycle_count: number;
    tier_counts: Record<string, number>;
    avg_risk_score: number;
    top_bank: string | null;
    has_labels: boolean;
    source?: string;
    source_kind?: "statements" | "ledger";
    direct_bank_count?: number;
    partial_bank_count?: number;
    coverage?: LedgerCoverage;
    label_evaluation?: {
      banks_touching_labelled_transfers: number;
      banks_scored_high: number;
      high_scored_and_labelled: number;
      labelled_but_not_high: number;
      note: string;
    };
  };
  banks: BankProfile[];
  total: number;
};

export type BankDetailResponse = {
  source: string;
  dataset: TransferDataset | null;
  coverage: LedgerCoverage | null;
  profile: BankProfile;
  neighbourhood: {
    from_bank: string;
    to_bank: string;
    transfer_count: number;
    total_amount: number;
    direction: "incoming" | "outgoing";
  }[];
  cycles: FlowCycle[];
};

export type BankGraphResponse = {
  dataset_id: number;
  nodes: {
    id: string;
    label: string;
    flow: number;
    risk_score: number;
    risk_tier: string;
    transfer_count: number;
    connected_banks: number;
  }[];
  edges: {
    source: string;
    target: string;
    amount: number;
    transfer_count: number;
    row_id: string;
    labelled_laundering_count: number;
  }[];
  cycles: FlowCycle[];
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

  // ---------------------------------------------------- bank intelligence
  listIntelSources: () => request<IntelSource[]>("/intel/sources"),

  listTransferDatasets: () => request<TransferDataset[]>("/intel/datasets"),

  uploadTransferDataset: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<TransferDataset>("/intel/datasets/upload", { method: "POST", body: form });
  },

  deleteTransferDataset: (id: number) =>
    request<{ status: string }>(`/intel/datasets/${id}`, { method: "DELETE" }),

  getBanks: (params: {
    source?: string;
    search?: string;
    tier?: string;
    evidence?: string;
    sort?: string;
    order?: string;
    limit?: number;
  } = {}) => {
    const q = new URLSearchParams();
    q.set("source", params.source || "statements");
    if (params.search) q.set("search", params.search);
    if (params.tier) q.set("tier", params.tier);
    if (params.evidence) q.set("evidence", params.evidence);
    if (params.sort) q.set("sort", params.sort);
    if (params.order) q.set("order", params.order);
    q.set("limit", String(params.limit ?? 200));
    return request<BankListResponse>(`/intel/banks?${q.toString()}`);
  },

  getBankProfile: (bankCode: string, source = "statements") =>
    request<BankDetailResponse>(
      `/intel/banks/${encodeURIComponent(bankCode)}?source=${encodeURIComponent(source)}`,
    ),

  getBankGraph: (source = "statements") =>
    request<BankGraphResponse>(`/intel/graph?source=${encodeURIComponent(source)}`),

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
