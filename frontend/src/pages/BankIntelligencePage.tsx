import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
  Radio,
  FileStack,
  Link2,
} from "lucide-react";
import { api, BankListResponse, BankProfile, IntelSource } from "../lib/api";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  EmptyState,
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

const SIGNAL_LABELS: Record<string, string> = {
  ifsc: "IFSC in narration",
  ifsc_partial: "partial IFSC",
  reference_prefix: "bank code on reference",
  upi_handle: "UPI handle",
  name: "bank name in text",
};

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

  const [sources, setSources] = useState<IntelSource[]>([]);
  const [source, setSource] = useState("statements");
  const [data, setData] = useState<BankListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [tier, setTier] = useState("");
  const [hidePartial, setHidePartial] = useState(true);
  const [sort, setSort] = useState("risk_score");

  const refreshSources = useCallback(async () => {
    const list = await api.listIntelSources().catch(() => [] as IntelSource[]);
    setSources(list);
    return list;
  }, []);

  useEffect(() => {
    refreshSources();
  }, [refreshSources]);

  // Re-reads on every visit and whenever the source changes: the statement corpus
  // is recomputed server-side, so adding a statement is reflected with no refresh.
  useEffect(() => {
    setLoading(true);
    api
      .getBanks({ source, sort, order: sort === "bank_code" ? "asc" : "desc" })
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [source, sort]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const ds = await api.uploadTransferDataset(file);
      await refreshSources();
      setSource(`ledger:${ds.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message.replace(/^API \d+: /, "") : "Ingestion failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteLedger = async () => {
    const active = sources.find((s) => s.key === source);
    if (!active?.dataset_id) return;
    if (!window.confirm("Delete this ledger and every profile computed from it?")) return;
    await api.deleteTransferDataset(active.dataset_id).catch(() => null);
    await refreshSources();
    setSource("statements");
  };

  const banks = useMemo(() => {
    let rows = data?.banks ?? [];
    if (search.trim()) {
      const needle = search.trim().toLowerCase();
      rows = rows.filter(
        (b) =>
          b.bank_code.toLowerCase().includes(needle) ||
          b.display_name.toLowerCase().includes(needle),
      );
    }
    if (tier) rows = rows.filter((b) => b.risk_tier === tier);
    if (hidePartial) rows = rows.filter((b) => b.evidence_basis !== "partial");
    return rows;
  }, [data, search, tier, hidePartial]);

  const partialCount = (data?.banks ?? []).filter((b) => b.evidence_basis === "partial").length;
  const summary = data?.summary;
  const coverage = summary?.coverage;
  const isLive = summary?.source_kind !== "ledger";
  const tierCounts = summary?.tier_counts || {};
  const evaluation = summary?.label_evaluation;
  const activeSource = sources.find((s) => s.key === source);

  const ledgerInput = (
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
  );

  if (loading && !data) return <LoadingPanel label="Loading bank intelligence" />;

  const nothingToShow = !summary || (summary.bank_count === 0 && (data?.banks ?? []).length === 0);

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={
          <>
            <Badge tone="info" dot>Institution intelligence</Badge>
            {isLive ? (
              <Badge tone="success" dot>
                <Radio className="h-3 w-3" /> live from statements
              </Badge>
            ) : (
              <Badge tone="neutral" mono>UPLOADED LEDGER</Badge>
            )}
          </>
        }
        title="Bank Intelligence"
        description={
          isLive
            ? "Built from the statements in this case file. Every statement you add is folded in automatically — including rings that only appear once several statements are held together."
            : "Built from an uploaded interbank transfer ledger."
        }
        meta={
          summary && (
            <>
              <MetaItem label="Institutions" value={summary.bank_count} icon={Building2} />
              <MetaItem
                label="Transfers"
                value={grouped.format(summary.transfer_count || 0)}
                icon={Database}
              />
              <MetaItem label="Circular flows" value={summary.cycle_count || 0} icon={Repeat} />
              {coverage && (
                <MetaItem
                  label="Statements"
                  value={coverage.statements_included}
                  icon={FileStack}
                />
              )}
            </>
          )
        }
        actions={
          <>
            {sources.length > 1 && (
              <div className="relative">
                <select
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  className="h-8 cursor-pointer appearance-none rounded-lg border border-ink-200 bg-white pl-2.5 pr-7 text-xs font-medium text-ink-700 outline-none hover:border-ink-300"
                >
                  {sources.map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 top-2.5 h-3.5 w-3.5 text-ink-400" />
              </div>
            )}
            <Button icon={Upload} onClick={() => document.getElementById("ledger-input")?.click()}>
              {uploading ? "Ingesting…" : "Add ledger"}
            </Button>
            {!isLive && activeSource?.dataset_id && (
              <Button icon={Trash2} variant="danger" onClick={handleDeleteLedger}>
                Delete ledger
              </Button>
            )}
          </>
        }
      />

      <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6">
        {ledgerInput}

        {error && (
          <Callout tone="danger" icon={AlertCircle} title="Could not read that ledger">
            {error}
          </Callout>
        )}

        {nothingToShow ? (
          <EmptyState
            icon={Landmark}
            title={isLive ? "No institutions yet" : "This ledger has no profiles"}
            description={
              isLive
                ? "Upload and analyse bank statements — each one's own bank is identified from its header, and counterparty banks from the narration. Institution profiles appear as soon as the first statement is analysed."
                : "The ledger produced no institution profiles."
            }
            actions={
              <>
                <Button
                  variant="primary"
                  size="md"
                  icon={Upload}
                  onClick={() => navigate("/")}
                >
                  Upload statements
                </Button>
                <Button
                  size="md"
                  icon={Database}
                  onClick={() => document.getElementById("ledger-input")?.click()}
                >
                  Or load a transfer ledger
                </Button>
              </>
            }
          >
            <p className="label-micro mb-2">How a counterparty's bank is identified</p>
            <div className="space-y-1.5 text-[11px] leading-relaxed text-ink-500">
              <p>
                <span className="font-mono text-ink-700">IMPS/CR/…/SBIN0001122/…</span> — IFSC in the
                narration
              </p>
              <p>
                <span className="font-mono text-ink-700">RTGS/CR/SBIN20240201/…</span> — bank code
                prefixing the reference
              </p>
              <p>
                <span className="font-mono text-ink-700">…@okhdfcbank</span> — UPI handle
              </p>
              <p className="text-ink-400">
                Rows with nothing to go on stay unattributed rather than being guessed at — they
                still count toward their own bank's volume, but form no institution.
              </p>
            </div>
          </EmptyState>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
              <StatTile
                label="High risk"
                value={tierCounts.HIGH ?? 0}
                tone={(tierCounts.HIGH ?? 0) > 0 ? "danger" : "neutral"}
                hint="Score ≥ 45"
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
                value={(summary?.avg_risk_score ?? 0).toFixed(1)}
                hint="Across all institutions"
              />
              <StatTile
                label="Circular flows"
                value={summary?.cycle_count ?? 0}
                tone={(summary?.cycle_count ?? 0) > 0 ? "accent" : "neutral"}
                hint="Amount-conserving loops"
                icon={Repeat}
              />
            </div>

            {coverage && (
              <Card>
                <CardHeader
                  title="Evidence coverage"
                  description="What these profiles were built from, and how much of it could be attributed to a named institution."
                  icon={Link2}
                  actions={
                    <Badge tone={coverage.attribution_rate >= 0.5 ? "success" : "warning"} dot>
                      {percent(coverage.attribution_rate, 0)} attributed
                    </Badge>
                  }
                />
                <div className="grid gap-4 p-4 sm:p-5 lg:grid-cols-3">
                  <div>
                    <p className="label-micro mb-1.5">Statements folded in</p>
                    <p className="num text-[13px] font-semibold text-ink-900">
                      {coverage.statements_included} of {coverage.statements_total}
                      {coverage.statements_skipped > 0 && (
                        <span className="ml-1 font-normal text-amber-700">
                          ({coverage.statements_skipped} without an identifiable bank)
                        </span>
                      )}
                    </p>
                    <div className="mt-2 space-y-1">
                      {coverage.subject_banks.map((b) => (
                        <p key={b.bank_code} className="text-[11px] text-ink-500">
                          <span className="font-mono text-ink-700">{b.bank_code}</span> ·{" "}
                          {b.bank_name}
                        </p>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="label-micro mb-1.5">Counterparty attribution</p>
                    <ProgressBar
                      value={coverage.attribution_rate * 100}
                      tone={coverage.attribution_rate >= 0.5 ? "success" : "warning"}
                    />
                    <p className="num mt-1.5 text-[11px] text-ink-500">
                      {grouped.format(coverage.counterparty_attributed)} attributed ·{" "}
                      {grouped.format(coverage.counterparty_unattributed)} unattributed of{" "}
                      {grouped.format(coverage.transactions_used)}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {Object.entries(coverage.attribution_signals).map(([signal, count]) => (
                        <Badge key={signal} tone="neutral">
                          {SIGNAL_LABELS[signal] || signal}: {count}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="label-micro mb-1.5">Reading these profiles</p>
                    <p className="text-[11px] leading-relaxed text-ink-500">
                      <strong className="font-semibold text-ink-700">
                        {summary?.direct_bank_count ?? 0} direct
                      </strong>{" "}
                      — a statement issued by that bank is held.{" "}
                      <strong className="font-semibold text-ink-700">
                        {summary?.partial_bank_count ?? 0} partial
                      </strong>{" "}
                      — only seen from the other side of someone else's statement, so volumes are a
                      fragment, not the institution's real total.
                    </p>
                    {coverage.mirrored_transfers_deduplicated > 0 && (
                      <p className="num mt-2 text-[11px] text-ink-400">
                        {coverage.mirrored_transfers_deduplicated} transfer(s) seen from both sides
                        were counted once.
                      </p>
                    )}
                  </div>
                </div>
              </Card>
            )}

            {evaluation && (
              <Callout tone="info" icon={Info} title="Scored against the ledger's own labels">
                <span className="num">{evaluation.banks_scored_high}</span> institutions scored high
                risk; <span className="num">{evaluation.high_scored_and_labelled}</span> of those
                carry transfers the ledger labels as laundering.{" "}
                <span className="num">{evaluation.banks_touching_labelled_transfers}</span>{" "}
                institutions touch a labelled transfer at all — receiving one does not by itself
                imply culpability. {evaluation.note}
              </Callout>
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
                    {partialCount > 0 && (
                      <button
                        onClick={() => setHidePartial(!hidePartial)}
                        className={`h-8 rounded-lg border px-2.5 text-[11px] font-semibold transition-colors ${
                          hidePartial
                            ? "border-ink-200 bg-white text-ink-500 hover:bg-ink-50"
                            : "border-amber-300 bg-amber-50 text-amber-700"
                        }`}
                        title="Institutions seen only through someone else's statement"
                      >
                        {hidePartial ? `Show ${partialCount} partial` : `Hiding nothing`}
                      </button>
                    )}
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

              <Table minWidth={1120}>
                <THead>
                  <Th>Institution</Th>
                  <Th>Risk</Th>
                  <Th>Tier</Th>
                  <Th>Evidence</Th>
                  <Th align="right">Transactions</Th>
                  <Th align="right">Received</Th>
                  <Th align="right">Sent</Th>
                  <Th align="right">Connected</Th>
                  <Th align="right">Avg transfer</Th>
                  <Th align="right">On cycles</Th>
                </THead>
                <TBody>
                  {banks.map((b) => (
                    <tr
                      key={b.bank_code}
                      onClick={() =>
                        navigate(
                          `/banks/${encodeURIComponent(b.bank_code)}?source=${encodeURIComponent(source)}`,
                        )
                      }
                      className={`cursor-pointer transition-colors ${
                        b.risk_tier === "HIGH" ? "bg-red-50/40 hover:bg-red-50/70" : "hover:bg-ink-50/70"
                      }`}
                    >
                      <Td>
                        <div className="flex items-center gap-2">
                          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-ink-200 bg-ink-50">
                            <Landmark className="h-3 w-3 text-ink-400" />
                          </span>
                          <div className="min-w-0">
                            <p className="truncate text-[13px] font-semibold text-ink-900">
                              {b.display_name}
                            </p>
                            <p className="font-mono text-[10px] text-ink-400">{b.bank_code}</p>
                          </div>
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
                      <Td>
                        <Badge tone={b.evidence_basis === "direct" ? "info" : "warning"}>
                          {b.evidence_basis}
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

              {hidePartial && partialCount > 0 && (
                <div className="border-t border-ink-100 bg-ink-50/50 px-4 py-2.5">
                  <p className="text-[11px] text-ink-400">
                    {partialCount} institution(s) hidden — seen only through another bank's
                    statement, so their volumes are fragments.{" "}
                    <button
                      onClick={() => setHidePartial(false)}
                      className="font-semibold text-brand-700 hover:text-brand-900"
                    >
                      Show them anyway
                    </button>
                  </p>
                </div>
              )}
            </Card>

            {coverage && coverage.per_statement.length > 0 && (
              <Card>
                <CardHeader
                  title="Statements behind these profiles"
                  description="Which bank each statement was traced to, and how it was identified."
                  icon={FileStack}
                />
                <Table minWidth={720}>
                  <THead>
                    <Th>Case</Th>
                    <Th>Statement</Th>
                    <Th>Traced to</Th>
                    <Th>Identified by</Th>
                    <Th align="right">Transactions</Th>
                    <Th align="right">Attributed</Th>
                  </THead>
                  <TBody>
                    {coverage.per_statement.map((row) => (
                      <tr key={row.statement_id} className="hover:bg-ink-50/70">
                        <Td className="num text-[13px] font-semibold text-ink-900">
                          #{row.statement_id}
                        </Td>
                        <Td className="max-w-[260px] truncate text-[12px] text-ink-700">
                          <Link
                            to={`/dashboard/${row.statement_id}`}
                            className="hover:text-brand-700"
                          >
                            {row.filename || "Untitled statement"}
                          </Link>
                        </Td>
                        <Td>
                          {row.skipped ? (
                            <Badge tone="warning">not identified</Badge>
                          ) : (
                            <span className="text-[12px] font-medium text-ink-800">
                              {row.bank_name}
                            </span>
                          )}
                        </Td>
                        <Td className="font-mono text-[11px] text-ink-400">{row.bank_signal}</Td>
                        <Td align="right" className="num text-[12px]">
                          {grouped.format(row.transactions)}
                        </Td>
                        <Td align="right" className="num text-[12px]">
                          {row.transactions > 0
                            ? `${percent(row.attributed / row.transactions, 0)}`
                            : "—"}
                        </Td>
                      </tr>
                    ))}
                  </TBody>
                </Table>
              </Card>
            )}

            {!isLive && data?.dataset && (
              <Card>
                <CardHeader
                  title={`Ledger #${data.dataset.id} · ${data.dataset.original_filename ?? "transfer ledger"}`}
                  description={
                    data.dataset.observed_start
                      ? `${formatDate(data.dataset.observed_start)} – ${formatDate(data.dataset.observed_end)} · ${grouped.format(data.dataset.row_count)} transfers across ${data.dataset.account_count} accounts`
                      : `${grouped.format(data.dataset.row_count)} transfers`
                  }
                  icon={Database}
                  actions={
                    <div className="flex flex-wrap items-center gap-1.5">
                      {data.dataset.currencies.slice(0, 5).map((c) => (
                        <Badge key={c} tone="neutral">
                          {c}
                        </Badge>
                      ))}
                    </div>
                  }
                />
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}
