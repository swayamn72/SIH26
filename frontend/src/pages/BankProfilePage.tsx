import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Landmark,
  ArrowLeft,
  ArrowDownLeft,
  ArrowUpRight,
  Building2,
  Repeat,
  Coins,
  Users,
  Activity,
  Wallet,
  Network,
  Gauge,
  CalendarClock,
  Info,
  ShieldAlert,
} from "lucide-react";
import { api, BankDetailResponse, RiskComponent } from "../lib/api";
import {
  Badge,
  Button,
  Callout,
  Card,
  CardHeader,
  EmptyState,
  Formula,
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

const COMPONENT_LABELS: Record<string, string> = {
  cycle_exposure: "Circular-flow exposure",
  structuring_share: "Structuring below threshold",
  network_centrality: "Network position",
  account_concentration: "Account concentration",
  cross_currency_share: "Cross-currency settlement",
  high_risk_format_share: "High-risk instruments",
  burst_velocity: "Burst velocity",
};

function ComponentRow({ component }: { component: RiskComponent }) {
  const tone: Tone =
    component.severity >= 0.7 ? "danger" : component.severity >= 0.4 ? "warning" : "neutral";

  return (
    <div className="rounded-lg border border-ink-100 bg-white p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-semibold text-ink-900">
            {COMPONENT_LABELS[component.name] || component.name}
          </span>
          <Badge tone={component.driver === "peers" ? "accent" : "info"}>
            {component.driver === "peers" ? "outlier vs peers" : "absolute level"}
          </Badge>
        </div>
        <span className="num text-[13px] font-bold text-ink-900">
          {component.points.toFixed(1)}
          <span className="font-normal text-ink-300"> pts</span>
        </span>
      </div>

      <div className="mt-2">
        <ProgressBar value={component.severity * 100} tone={tone} />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] text-ink-400">
        <span>
          value <strong className="text-ink-700">{percent(component.value, 2)}</strong>
        </span>
        <span>
          reference <strong className="text-ink-700">{percent(component.reference, 0)}</strong>
        </span>
        <span>
          peer z <strong className="text-ink-700">{component.peer_z.toFixed(2)}</strong>
        </span>
        <span>
          weight <strong className="text-ink-700">{component.weight}</strong>
        </span>
      </div>

      <p className="mt-1.5 text-[11px] leading-relaxed text-ink-400">{component.description}</p>
    </div>
  );
}

export function BankProfilePage() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();

  const [data, setData] = useState<BankDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!code) return;
    setLoading(true);
    api
      .getBankProfile(code)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [code]);

  if (loading) return <LoadingPanel label="Loading bank profile" />;

  if (!data) {
    return (
      <div className="animate-fade-in">
        <PageHeader
          eyebrow={<Badge tone="info" dot>Institution intelligence</Badge>}
          title="Bank profile"
          description="Behavioural profile for a single institution."
        />
        <div className="p-4 sm:p-6">
          <EmptyState
            icon={Landmark}
            title={`No profile for ${code}`}
            description="This institution is not in the most recent ledger, or the ledger has been deleted."
            actions={
              <Button variant="primary" size="md" icon={ArrowLeft} onClick={() => navigate("/banks")}>
                Back to institutions
              </Button>
            }
          />
        </div>
      </div>
    );
  }

  const p = data.profile;
  const tone = TIER_TONE[p.risk_tier] || "neutral";
  const outgoing = data.neighbourhood.filter((n) => n.direction === "outgoing");
  const incoming = data.neighbourhood.filter((n) => n.direction === "incoming");
  const maxFormatShare = Math.max(...p.format_mix.map((f) => f.share), 0.0001);

  return (
    <div className="animate-fade-in">
      <PageHeader
        eyebrow={
          <>
            <Badge tone="info" dot>Institution intelligence</Badge>
            <Badge tone="neutral" mono>
              LEDGER #{data.dataset.id}
            </Badge>
            <Badge tone={tone} dot>
              {p.risk_tier} RISK · {p.risk_score.toFixed(0)}
            </Badge>
          </>
        }
        title={p.display_name}
        description="Behavioural profile assembled from this institution's own traffic in the ledger — every number below is a count or a ratio, not a prediction."
        meta={
          <>
            <MetaItem label="Transfers" value={grouped.format(p.transfer_count)} icon={Activity} />
            <MetaItem label="Accounts" value={p.account_count} icon={Wallet} />
            <MetaItem
              label="Active"
              value={
                p.first_seen ? `${formatDate(p.first_seen)} – ${formatDate(p.last_seen)}` : "—"
              }
              icon={CalendarClock}
            />
          </>
        }
        actions={
          <Button icon={ArrowLeft} onClick={() => navigate("/banks")}>
            All institutions
          </Button>
        }
      />

      <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6">
        {/* The profile card */}
        <Card accent={p.risk_tier === "HIGH" ? "danger" : p.risk_tier === "MEDIUM" ? "warning" : undefined}>
          <CardHeader
            title="Behavioural profile"
            description="The institution at a glance."
            icon={Landmark}
            actions={
              p.cycle_ids.length > 0 && (
                <Badge tone="accent" dot>
                  on {p.cycle_ids.length} circular flow{p.cycle_ids.length > 1 ? "s" : ""}
                </Badge>
              )
            }
          />
          <div className="grid grid-cols-2 gap-3 p-4 sm:p-5 lg:grid-cols-4 xl:grid-cols-7">
            <StatTile
              label="Transactions"
              value={grouped.format(p.transfer_count)}
              hint={`${grouped.format(p.received_count)} in · ${grouped.format(p.sent_count)} out`}
              icon={Activity}
            />
            <StatTile
              label="Money received"
              value={compactNumber(p.total_received)}
              tone="success"
              hint={grouped.format(p.total_received)}
              icon={ArrowDownLeft}
            />
            <StatTile
              label="Money sent"
              value={compactNumber(p.total_sent)}
              tone="danger"
              hint={grouped.format(p.total_sent)}
              icon={ArrowUpRight}
            />
            <StatTile
              label="Connected banks"
              value={p.connected_banks}
              hint={`${outgoing.length} out · ${incoming.length} in`}
              icon={Network}
            />
            <StatTile
              label="Avg transaction"
              value={compactNumber(p.avg_transfer)}
              hint={`median ${compactNumber(p.median_transfer)}`}
              icon={Coins}
            />
            <StatTile
              label="Wire usage"
              value={percent(p.wire_share, 0)}
              tone={p.wire_share >= 0.5 ? "warning" : "neutral"}
              hint={`high-risk instruments ${percent(p.high_risk_format_share, 0)}`}
              icon={Gauge}
            />
            <StatTile
              label="Risk score"
              value={`${p.risk_score.toFixed(0)}/100`}
              tone={tone}
              hint={`${p.risk_tier} tier`}
              icon={ShieldAlert}
            />
          </div>
        </Card>

        <div className="grid gap-5 lg:grid-cols-5">
          {/* Score breakdown */}
          <div className="lg:col-span-3">
            <Card>
              <CardHeader
                title="How this score was built"
                description="Each component is scored on whichever is worse: its absolute level, or how far it sits above the other institutions in this ledger."
                icon={ShieldAlert}
                actions={
                  <span className="num text-[13px] font-bold text-ink-900">
                    {p.risk_score.toFixed(1)}
                    <span className="font-normal text-ink-300"> / 100</span>
                  </span>
                }
              />
              <div className="space-y-2 p-4 sm:p-5">
                {p.risk_components.map((c) => (
                  <ComponentRow key={c.name} component={c} />
                ))}
                <Formula>{p.risk_formula}</Formula>
                {p.labelled_laundering_transfers > 0 && (
                  <Callout tone="info" icon={Info} title="Ledger labels for this institution">
                    <span className="num">{p.labelled_laundering_transfers}</span> of its{" "}
                    <span className="num">{p.transfer_count}</span> transfers (
                    {percent(p.labelled_laundering_share)}) are labelled laundering in the source
                    ledger. Labels never enter the score — they are shown so you can judge it.
                  </Callout>
                )}
              </div>
            </Card>
          </div>

          <div className="space-y-5 lg:col-span-2">
            {/* Instrument mix */}
            <Card>
              <CardHeader title="Instrument mix" description="How value leaves and arrives." icon={Coins} />
              <div className="space-y-2.5 p-4">
                {p.format_mix.map((f) => (
                  <div key={f.format}>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-[12px] font-medium capitalize text-ink-700">{f.format}</span>
                      <span className="num text-[11px] text-ink-400">
                        {percent(f.share, 1)} · {grouped.format(f.count)}
                      </span>
                    </div>
                    <ProgressBar
                      value={(f.share / maxFormatShare) * 100}
                      tone={["wire", "cash"].includes(f.format) ? "warning" : "info"}
                      className="mt-1"
                    />
                  </div>
                ))}
              </div>
            </Card>

            {/* Corridors */}
            <Card>
              <CardHeader
                title="Settlement corridors"
                description="Currency in → currency out. A change of currency is a conversion, not a location."
                icon={Repeat}
                actions={<Badge tone="neutral">{percent(p.cross_currency_share, 1)} cross-currency</Badge>}
              />
              <Table minWidth={320}>
                <THead>
                  <Th>Corridor</Th>
                  <Th align="right">Transfers</Th>
                  <Th align="right">Value</Th>
                </THead>
                <TBody>
                  {p.currency_corridors.map((c) => (
                    <tr key={c.name}>
                      <Td className="font-mono text-[11px] text-ink-700">{c.name}</Td>
                      <Td align="right" className="num text-[12px]">
                        {grouped.format(c.transfer_count)}
                      </Td>
                      <Td align="right" className="num text-[12px]">
                        {compactNumber(c.total_amount)}
                      </Td>
                    </tr>
                  ))}
                </TBody>
              </Table>
            </Card>

            {/* Activity */}
            <Card>
              <CardHeader title="Activity shape" icon={CalendarClock} />
              <div className="grid grid-cols-2 gap-3 p-4">
                <StatTile label="Active days" value={p.active_days} hint="Days with any transfer" />
                <StatTile
                  label="Busiest day"
                  value={p.busiest_day ? formatDate(p.busiest_day) : "—"}
                  hint={`${p.busiest_day_transfers} transfers · ${percent(p.burst_velocity, 1)} of all`}
                />
                <StatTile
                  label="Near-threshold"
                  value={grouped.format(p.near_threshold_transfers)}
                  tone={p.structuring_share >= 0.1 ? "warning" : "neutral"}
                  hint={`${percent(p.structuring_share, 1)} of transfers`}
                />
                <StatTile
                  label="Largest transfer"
                  value={compactNumber(p.max_transfer)}
                  hint={`net flow ${compactNumber(p.net_flow)}`}
                />
              </div>
            </Card>
          </div>
        </div>

        {/* Circular flows */}
        {data.cycles.length > 0 && (
          <Card accent="accent">
            <CardHeader
              title={`Circular flows through this institution (${data.cycles.length})`}
              description="Loops that returned to their originating account with the value largely intact — found between accounts, then attributed to the banks that carried them."
              icon={Repeat}
            />
            <div className="space-y-2 p-4 sm:p-5">
              {data.cycles.map((c) => (
                <div key={c.cycle_id} className="rounded-lg border border-violet-200 bg-violet-50/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[11px] font-bold text-violet-800">
                        {c.cycle_id}
                      </span>
                      <Badge tone="accent">risk {percent(c.cycle_risk_score, 0)}</Badge>
                      <Badge tone="neutral">{c.hop_count} hops</Badge>
                      {c.recurrence > 1 && (
                        <Badge tone="warning">ran {c.recurrence} times</Badge>
                      )}
                    </div>
                    <span className="num text-[12px] font-semibold text-ink-800">
                      {compactNumber(c.total_amount)} moved
                    </span>
                  </div>

                  <p className="mt-2 font-mono text-[11px] text-ink-600">
                    {c.banks.map((b) => b.replace("BANK_", "Bank ")).join(" → ")} →{" "}
                    {c.banks[0]?.replace("BANK_", "Bank ")}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-ink-400">
                    accounts {c.accounts.join(" → ")} → {c.accounts[0]}
                  </p>

                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-500">
                    <span>
                      amount conserved{" "}
                      <strong className="num text-ink-800">
                        {percent(c.amount_conservation_ratio, 0)}
                      </strong>
                    </span>
                    <span>
                      closed in <strong className="num text-ink-800">{c.cycle_span_days.toFixed(2)} d</strong>
                    </span>
                    <span>
                      principal <strong className="num text-ink-800">{compactNumber(c.principal)}</strong>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          {/* Counterparty banks */}
          <Card>
            <CardHeader
              title={`Counterparty institutions (${p.counterparty_banks.length} of ${p.connected_banks})`}
              description="Ranked by value moved with this bank."
              icon={Building2}
            />
            <Table minWidth={420}>
              <THead>
                <Th>Institution</Th>
                <Th align="right">Transfers</Th>
                <Th align="right">Value</Th>
                <Th align="right" />
              </THead>
              <TBody>
                {p.counterparty_banks.map((c) => (
                  <tr key={c.name} className="hover:bg-ink-50/70">
                    <Td className="text-[12px] font-semibold text-ink-800">
                      {c.name.replace("BANK_", "Bank ")}
                    </Td>
                    <Td align="right" className="num text-[12px]">
                      {grouped.format(c.transfer_count)}
                    </Td>
                    <Td align="right" className="num text-[12px]">
                      {compactNumber(c.total_amount)}
                    </Td>
                    <Td align="right">
                      <button
                        onClick={() => navigate(`/banks/${encodeURIComponent(c.name)}`)}
                        className="text-[11px] font-semibold text-brand-700 hover:text-brand-900"
                      >
                        Open →
                      </button>
                    </Td>
                  </tr>
                ))}
              </TBody>
            </Table>
          </Card>

          {/* Accounts */}
          <Card>
            <CardHeader
              title="Its own accounts"
              description="Concentration matters: a handful of accounts carrying most of the value is a mule signature."
              icon={Users}
              actions={
                <Badge tone={p.account_concentration_hhi >= 0.4 ? "warning" : "neutral"}>
                  HHI {p.account_concentration_hhi.toFixed(3)}
                </Badge>
              }
            />
            <Table minWidth={360}>
              <THead>
                <Th>Account</Th>
                <Th align="right">Transfers</Th>
                <Th align="right">Value</Th>
              </THead>
              <TBody>
                {p.top_accounts.map((a) => (
                  <tr key={a.name}>
                    <Td className="font-mono text-[11px] text-ink-700">{a.name}</Td>
                    <Td align="right" className="num text-[12px]">
                      {grouped.format(a.transfer_count)}
                    </Td>
                    <Td align="right" className="num text-[12px]">
                      {compactNumber(a.total_amount)}
                    </Td>
                  </tr>
                ))}
              </TBody>
            </Table>
            <div className="border-t border-ink-100 px-4 py-2.5">
              <p className="text-[11px] text-ink-400">
                <span className="num font-semibold text-ink-700">{p.account_count}</span> accounts seen
                in total · betweenness{" "}
                <span className="num font-semibold text-ink-700">
                  {(p.centrality.betweenness_centrality ?? 0).toFixed(4)}
                </span>
                {p.centrality.betweenness_sampled ? " (sampled)" : ""}
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
