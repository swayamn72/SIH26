import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Landmark,
  Upload,
  Search,
  AlertCircle,
  Repeat,
  Database,
  Building2,
  ArrowUpRight,
  ArrowDownLeft,
  Target,
  Trash2,
  ChevronDown,
  Info,
} from "lucide-react";
import { api, BankListResponse, BankProfile, TransferDataset } from "../lib/api";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  LoadingPanel,
  MetaItem,
  PageHeader,
  ProgressBar,
  StatTile,
  TBody,
  THead,
  Table,
  Td,
  Th,
  Tone,
  compactNumber,
  formatDate,
  grouped,
  percent,
} from "../components/ui";

const TIER_TONE: Record<string, Tone> = { HIGH: "danger", MEDIUM: "warning", LOW: "neutral" };

const SORTS: { key: string; label: string }[] = [
  { key: "risk_score", label: "Risk score" },
  { key: "transfer_count", label: "Transactions" },
  { key: "total_received", label: "Money received" },
  { key: "total_sent", label: "Money sent" },
  { key: "connected_banks", label: "Connected banks" },
  { key: "avg_transfer", label: "Average transfer" },
  { key: "bank_code", label: "Bank code" },
];

function RiskCell({ bank }: { bank: BankProfile }) {
  const tone: Tone = TIER_TONE[bank.risk_tier] || "neutral";
  return (
    <div className="flex items-center gap-2.5">
      <span
        className={`num w-9 shrink-0 text-right text-[13px] font-bold ${
          bank.risk_tier === "HIGH"
            ? "text-red-700"
            : bank.risk_tier === "MEDIUM"
            ? "text-amber-700"
            : "text-ink-500"
        }`}
      >
        {bank.risk_score.toFixed(0)}
      </span>
      <ProgressBar value={bank.risk_score} tone={tone} className="w-20" />
    </div>
  );
}

export function BankIntelligencePage() {
  const navigate = useNavigate();

  const [datasets, setDatasets] = useState<TransferDataset[]>([]);
  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [data, setData] = useState<BankListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const [search, setSearch] = useState("");
  const [tier, setTier] = useState<string>("");
  const [sort, setSort] = useState("risk_score");

  const refreshDatasets = useCallback(async () => {
    const list = await api.listTransferDatasets().catch(() => []);
    setDatasets(list);
    setDatasetId((prev) => (prev != null && list.some((d) => d.id === prev) ? prev : list[0]?.id ?? null));
    return list;
  }, []);

  useEffect(() => {
    refreshDatasets().finally(() => setLoading(false));
  }, [refreshDatasets]);

  useEffect(() => {
    if (datasets.length === 0) {
      setData(null);
      return;
    }
    setLoading(true);
    api
      .getBanks({ datasetId: datasetId ?? undefined, sort, order: sort === "bank_code" ? "asc" : "desc" })
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [datasets, datasetId, sort]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const ds = await api.uploadTransferDataset(file);
      const list = await refreshDatasets();
      setDatasetId(ds.id ?? list[0]?.id ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message.replace(/^API \d+: /, "") : "Ingestion failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    if (datasetId == null) return;
    if (!window.confirm(`Delete this ledger and every profile computed from it?`)) return;
    await api.deleteTransferDataset(datasetId).catch(() => null);
    const list = await refreshDatasets();
    setDatasetId(list[0]?.id ?? null);
  };

  const banks = useMemo(() => {
    let rows = data?.banks ?? [];
    if (search.trim()) {
      const needle = search.trim().toLowerCase();
      rows = rows.filter((b) => b.bank_code.toLowerCase().includes(needle));
    }
    if (tier) rows = rows.filter((b) => b.risk_tier === tier);
    return rows;
  }, [data, search, tier]);

  const dropzone = (
    <div
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const file = Array.from(e.dataTransfer.files)[0];
        if (file) handleUpload(file);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onClick={() => document.getElementById("ledger-input")?.click()}
      className={`cursor-pointer rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors ${
        dragging
          ? "border-brand-500 bg-brand-50"
          : "border-ink-200 bg-ink-50/60 hover:border-brand-400 hover:bg-brand-50/40"
      }`}
    >
      <input
        id="ledger-input"
        type="file"
        accept=".csv,.xlsx,.xls,.txt"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleUpload(file);
        }}
      />
      <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-ink-200 bg-white shadow-card">
        <Landmark className="h-5 w-5 text-brand-600" />
      </div>
      <p className="text-sm font-semibold text-ink-900">
        {uploading ? "Profiling institutions…" : "Drop an interbank transfer ledger"}
      </p>
      <p className="mt-1 text-xs text-ink-400">
        CSV or XLSX with sender/receiver bank columns — headers are detected automatically
      </p>
    </div>
  );

  if (loading && !data && datasets.length === 0 && !uploading) {
    return <LoadingPanel label="Loading bank intelligence" />;
  }

  if (datasets.length === 0) {
    return (
      <div className="animate-fade-in">
        <PageHeader
          eyebrow={<Badge tone="info" dot>Institution intelligence</Badge>}
          title="Bank Intelligence"
          description="Profile every institution in a transfer ledger: what it moved, who it moved it with, and where it sits in the laundering network."
        />
        <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
          {error && (
            <Callout tone="danger" icon={AlertCircle} title="Could not read that ledger">
              {error}
            </Callout>
          )}
          <Card>
            <CardHeader
              title="Load a transfer ledger"
              description="A statement is one account's history. This view needs a multi-party ledger where each row names both institutions."
              icon={Upload}
            />
            <div className="p-4 sm:p-5">{dropzone}</div>
          </Card>
          <Card padded className="bg-ink-50/40">
            <p className="label-micro mb-2">Columns recognised</p>
            <div className="flex flex-wrap gap-1.5">
              {[
                "Timestamp",
                "From Bank",
                "Account",
                "To Bank",
                "Account.1",
                "Amount Paid",
                "Payment Currency",
                "Amount Received",
                "Receiving Currency",
                "Payment Format",
                "Is Laundering",
              ].map((c) => (
                <Badge key={c} tone="neutral" mono>
                  {c}
                </Badge>
              ))}
            </div>
            <p className="mt-2.5 text-[11px] leading-relaxed text-ink-400">
              Synonyms are matched too (sender bank, beneficiary bank, amount, channel…). Only the two
              institution columns are strictly required. An <span className="font-mono">Is Laundering</span>{" "}
              column, if present, is used to evaluate the score — never to compute it.
            </p>
          </Card>
        </div>
      </div>
    );
  }

  const dataset = data?.dataset;
  const summary = data?.summary;
  const tierCounts = summary?.tier_counts || {};
  const evaluation = summary?.label_evaluation;

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={
          <>
            <Badge tone="info" dot>Institution intelligence</Badge>
            {dataset?.truncated && <Badge tone="warning">row cap reached</Badge>}
            {dataset?.has_labels && <Badge tone="accent">ground truth available</Badge>}
          </>
        }
        title="Bank Intelligence"
        description="Every institution in the ledger, profiled on behaviour rather than on a single prediction — so a flagged bank can be investigated, not just scored."
        meta={
          summary && (
            <>
              <MetaItem label="Banks" value={summary.bank_count} icon={Building2} />
              <MetaItem label="Transfers" value={grouped.format(summary.transfer_count)} icon={Database} />
              <MetaItem label="Value" value={compactNumber(summary.total_value)} />
              <MetaItem label="Circular flows" value={summary.cycle_count} icon={Repeat} />
            </>
          )
        }
        actions={
          <>
            {datasets.length > 1 && (
              <div className="relative">
                <select
                  value={datasetId ?? ""}
                  onChange={(e) => setDatasetId(Number(e.target.value))}
                  className="h-8 cursor-pointer appearance-none rounded-lg border border-ink-200 bg-white pl-2.5 pr-7 text-xs font-medium text-ink-700 outline-none hover:border-ink-300"
                >
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      #{d.id} · {d.original_filename}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 top-2.5 h-3.5 w-3.5 text-ink-400" />
              </div>
            )}
            <Button icon={Upload} onClick={() => document.getElementById("ledger-input")?.click()}>
              {uploading ? "Ingesting…" : "Load ledger"}
            </Button>
            <Button icon={Trash2} variant="danger" onClick={handleDelete}>
              Delete
            </Button>
          </>
        }
      />

      <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6">
        <input
          id="ledger-input"
          type="file"
          accept=".csv,.xlsx,.xls,.txt"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUpload(file);
          }}
        />

        {error && (
          <Callout tone="danger" icon={AlertCircle} title="Could not read that ledger">
            {error}
          </Callout>
        )}

        {summary && (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <StatTile
              label="High risk"
              value={tierCounts.HIGH ?? 0}
              tone={(tierCounts.HIGH ?? 0) > 0 ? "danger" : "neutral"}
              hint={`Score ≥ ${45}`}
              icon={Target}
            />
            <StatTile
              label="Medium risk"
              value={tierCounts.MEDIUM ?? 0}
              tone={(tierCounts.MEDIUM ?? 0) > 0 ? "warning" : "neutral"}
              hint="Worth a look"
            />
            <StatTile label="Low risk" value={tierCounts.LOW ?? 0} hint="Nothing stood out" />
            <StatTile
              label="Average score"
              value={summary.avg_risk_score.toFixed(1)}
              hint="Across all institutions"
            />
            <StatTile
              label="Circular flows"
              value={summary.cycle_count}
              tone={summary.cycle_count > 0 ? "accent" : "neutral"}
              hint="Amount-conserving loops"
              icon={Repeat}
            />
          </div>
        )}

        {evaluation && (
          <Callout tone="info" icon={Info} title="Scored against the ledger's own labels">
            <span className="num">{evaluation.banks_scored_high}</span> institutions scored high risk;{" "}
            <span className="num">{evaluation.high_scored_and_labelled}</span> of those carry transfers
            the ledger labels as laundering.{" "}
            <span className="num">{evaluation.banks_touching_labelled_transfers}</span> institutions
            touch a labelled transfer at all — receiving one does not by itself imply culpability.{" "}
            {evaluation.note}
          </Callout>
        )}

        {dataset && (
          <Card>
            <CardHeader
              title={`Ledger #${dataset.id} · ${dataset.original_filename ?? "transfer ledger"}`}
              description={
                dataset.observed_start
                  ? `${formatDate(dataset.observed_start)} – ${formatDate(dataset.observed_end)} · ${grouped.format(dataset.row_count)} transfers across ${dataset.account_count} accounts`
                  : `${grouped.format(dataset.row_count)} transfers across ${dataset.account_count} accounts`
              }
              icon={Database}
              actions={
                <div className="flex flex-wrap items-center gap-1.5">
                  {dataset.currencies.slice(0, 5).map((c) => (
                    <Badge key={c} tone="neutral">
                      {c}
                    </Badge>
                  ))}
                  {dataset.payment_formats.slice(0, 5).map((f) => (
                    <Badge key={f} tone="info">
                      {f}
                    </Badge>
                  ))}
                </div>
              }
            />
            {(dataset.truncated || dataset.rows_skipped > 0) && (
              <div className="border-b border-ink-100 bg-amber-50/60 px-4 py-2 text-[11px] text-amber-800 sm:px-5">
                {dataset.truncated && "Row cap reached — profiles cover the rows that were read. "}
                {dataset.rows_skipped > 0 &&
                  `${grouped.format(dataset.rows_skipped)} rows skipped for missing an institution identifier.`}
              </div>
            )}
          </Card>
        )}

        <Card>
          <CardHeader
            title={`Institution profiles (${banks.length})`}
            description="Click any institution to open its behavioural profile and score breakdown."
            icon={Building2}
            actions={
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-ink-300" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Find a bank"
                    className="h-8 w-36 rounded-lg border border-ink-200 bg-white pl-8 pr-2 text-xs text-ink-700 outline-none placeholder:text-ink-300 hover:border-ink-300 focus:border-brand-500"
                  />
                </div>
                <div className="flex items-center gap-1">
                  {["", "HIGH", "MEDIUM", "LOW"].map((t) => (
                    <button
                      key={t || "all"}
                      onClick={() => setTier(t)}
                      className={`h-8 rounded-lg border px-2.5 text-[11px] font-semibold transition-colors ${
                        tier === t
                          ? "border-brand-300 bg-brand-50 text-brand-700"
                          : "border-ink-200 bg-white text-ink-500 hover:bg-ink-50"
                      }`}
                    >
                      {t || "All"}
                    </button>
                  ))}
                </div>
                <div className="relative">
                  <select
                    value={sort}
                    onChange={(e) => setSort(e.target.value)}
                    className="h-8 cursor-pointer appearance-none rounded-lg border border-ink-200 bg-white pl-2.5 pr-7 text-xs font-medium text-ink-700 outline-none hover:border-ink-300"
                  >
                    {SORTS.map((s) => (
                      <option key={s.key} value={s.key}>
                        Sort: {s.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-2 top-2.5 h-3.5 w-3.5 text-ink-400" />
                </div>
              </div>
            }
          />

          <Table minWidth={1080}>
            <THead>
              <Th>Bank</Th>
              <Th>Risk</Th>
              <Th>Tier</Th>
              <Th align="right">Transactions</Th>
              <Th align="right">Received</Th>
              <Th align="right">Sent</Th>
              <Th align="right">Connected</Th>
              <Th align="right">Avg transfer</Th>
              <Th align="right">Wire</Th>
              <Th align="right">On cycles</Th>
            </THead>
            <TBody>
              {banks.map((b) => (
                <tr
                  key={b.bank_code}
                  onClick={() => navigate(`/banks/${encodeURIComponent(b.bank_code)}`)}
                  className={`cursor-pointer transition-colors ${
                    b.risk_tier === "HIGH" ? "bg-red-50/40 hover:bg-red-50/70" : "hover:bg-ink-50/70"
                  }`}
                >
                  <Td>
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-ink-200 bg-ink-50">
                        <Landmark className="h-3 w-3 text-ink-400" />
                      </span>
                      <span className="text-[13px] font-semibold text-ink-900">{b.display_name}</span>
                    </div>
                  </Td>
                  <Td>
                    <RiskCell bank={b} />
                  </Td>
                  <Td>
                    <Badge tone={TIER_TONE[b.risk_tier] || "neutral"} dot>
                      {b.risk_tier}
                    </Badge>
                  </Td>
                  <Td align="right" className="num text-[13px] font-medium">
                    {grouped.format(b.transfer_count)}
                  </Td>
                  <Td align="right" className="num text-[13px] text-emerald-700">
                    <span className="inline-flex items-center gap-1">
                      <ArrowDownLeft className="h-3 w-3" />
                      {compactNumber(b.total_received)}
                    </span>
                  </Td>
                  <Td align="right" className="num text-[13px] text-red-600">
                    <span className="inline-flex items-center gap-1">
                      <ArrowUpRight className="h-3 w-3" />
                      {compactNumber(b.total_sent)}
                    </span>
                  </Td>
                  <Td align="right" className="num text-[13px]">
                    {b.connected_banks}
                  </Td>
                  <Td align="right" className="num text-[13px]">
                    {compactNumber(b.avg_transfer)}
                  </Td>
                  <Td align="right" className="num text-[13px] text-ink-500">
                    {percent(b.wire_share, 0)}
                  </Td>
                  <Td align="right">
                    {b.cycle_transfers > 0 ? (
                      <Badge tone="accent">{b.cycle_transfers}</Badge>
                    ) : (
                      <span className="text-ink-300">—</span>
                    )}
                  </Td>
                </tr>
              ))}
              {banks.length === 0 && (
                <tr>
                  <Td align="center" className="py-6 text-[12px] text-ink-400">
                    No institution matches these filters.
                  </Td>
                </tr>
              )}
            </TBody>
          </Table>
        </Card>
      </div>
    </div>
  );
}
