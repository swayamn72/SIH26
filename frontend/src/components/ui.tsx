/**
 * Console UI primitives.
 *
 * One place for the shapes every screen repeats: cards, section headers, risk
 * badges, buttons, stat tiles, tables and empty states. Pages compose these so
 * spacing, weight and colour stay identical across the app.
 */
import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { clsx } from "clsx";
import { LucideIcon } from "lucide-react";

/* ------------------------------------------------------------------ tokens */

export type Tier = "CONFIRMED_SUSPICIOUS" | "REVIEW_REQUIRED" | "LIKELY_LEGITIMATE" | string;
export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "accent";

export const TIER_META: Record<
  string,
  { label: string; tone: Tone; dot: string; text: string; soft: string; bar: string }
> = {
  CONFIRMED_SUSPICIOUS: {
    label: "Confirmed Suspicious",
    tone: "danger",
    dot: "bg-red-500",
    text: "text-red-700",
    soft: "bg-red-50 border-red-200",
    bar: "bg-red-500",
  },
  REVIEW_REQUIRED: {
    label: "Review Required",
    tone: "warning",
    dot: "bg-amber-500",
    text: "text-amber-700",
    soft: "bg-amber-50 border-amber-200",
    bar: "bg-amber-500",
  },
  LIKELY_LEGITIMATE: {
    label: "Likely Legitimate",
    tone: "success",
    dot: "bg-emerald-500",
    text: "text-emerald-700",
    soft: "bg-emerald-50 border-emerald-200",
    bar: "bg-emerald-500",
  },
};

export const SEVERITY_TONE: Record<Severity, Tone> = {
  CRITICAL: "danger",
  HIGH: "warning",
  MEDIUM: "warning",
  LOW: "neutral",
};

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-ink-50 text-ink-500 border-ink-200",
  info: "bg-brand-50 text-brand-700 border-brand-200",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  danger: "bg-red-50 text-red-700 border-red-200",
  accent: "bg-violet-50 text-violet-700 border-violet-200",
};

const TONE_DOT: Record<Tone, string> = {
  neutral: "bg-ink-300",
  info: "bg-brand-500",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
  accent: "bg-violet-500",
};

export const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export function money(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `₹${inr.format(value)}`;
}

export function compactMoney(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e7) return `₹${(value / 1e7).toFixed(2)} Cr`;
  if (abs >= 1e5) return `₹${(value / 1e5).toFixed(2)} L`;
  return `₹${inr.format(Math.round(value))}`;
}

/** Grouped number with no currency symbol — transfer ledgers carry their own currencies. */
export const grouped = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function compactNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return grouped.format(value);
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

/* ------------------------------------------------------------------- badge */

export function Badge({
  children,
  tone = "neutral",
  dot = false,
  mono = false,
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  dot?: boolean;
  mono?: boolean;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-semibold leading-5",
        TONE_CLASSES[tone],
        mono && "font-mono text-[10px]",
        className,
      )}
    >
      {dot && <span className={clsx("h-1.5 w-1.5 rounded-full", TONE_DOT[tone])} />}
      {children}
    </span>
  );
}

export function TierBadge({ tier, score }: { tier: Tier | null; score?: number | null }) {
  if (!tier) return <Badge tone="neutral">Not analysed</Badge>;
  const meta = TIER_META[tier];
  if (!meta) return <Badge tone="neutral">{String(tier).replace(/_/g, " ")}</Badge>;
  return (
    <Badge tone={meta.tone} dot>
      {meta.label}
      {score != null && <span className="num opacity-70">· {score.toFixed(0)}</span>}
    </Badge>
  );
}

export function SeverityBadge({ severity, suffix }: { severity: Severity; suffix?: string }) {
  return (
    <Badge tone={SEVERITY_TONE[severity] || "neutral"} dot>
      {severity}
      {suffix && <span className="font-normal opacity-80">{suffix}</span>}
    </Badge>
  );
}

/* ------------------------------------------------------------------ button */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "accent";
type ButtonSize = "sm" | "md";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 text-white border-brand-600 hover:bg-brand-700 hover:border-brand-700 shadow-card",
  secondary: "bg-white text-ink-700 border-ink-200 hover:bg-ink-50 hover:border-ink-300 shadow-card",
  ghost: "bg-transparent text-ink-500 border-transparent hover:bg-ink-100 hover:text-ink-800",
  danger: "bg-white text-red-600 border-red-200 hover:bg-red-50",
  accent: "bg-violet-600 text-white border-violet-600 hover:bg-violet-700 shadow-card",
};

const BUTTON_SIZE: Record<ButtonSize, string> = {
  sm: "h-8 px-2.5 text-xs gap-1.5",
  md: "h-9 px-3.5 text-[13px] gap-2",
};

function buttonClasses(variant: ButtonVariant, size: ButtonSize, className?: string) {
  return clsx(
    "inline-flex items-center justify-center rounded-lg border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
    BUTTON_VARIANT[variant],
    BUTTON_SIZE[size],
    className,
  );
}

export function Button({
  children,
  variant = "secondary",
  size = "sm",
  icon: Icon,
  className,
  ...rest
}: {
  children?: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: LucideIcon;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button className={buttonClasses(variant, size, className)} {...rest}>
      {Icon && <Icon className={size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"} />}
      {children}
    </button>
  );
}

export function LinkButton({
  to,
  children,
  variant = "secondary",
  size = "sm",
  icon: Icon,
  className,
  title,
}: {
  to: string;
  children?: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: LucideIcon;
  className?: string;
  title?: string;
}) {
  return (
    <Link to={to} title={title} className={buttonClasses(variant, size, className)}>
      {Icon && <Icon className={size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4"} />}
      {children}
    </Link>
  );
}

/* -------------------------------------------------------------------- card */

export function Card({
  children,
  className,
  padded = false,
  accent,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
  accent?: "danger" | "warning" | "success" | "info" | "accent";
}) {
  const accentBorder = accent
    ? {
        danger: "border-l-4 border-l-red-500",
        warning: "border-l-4 border-l-amber-500",
        success: "border-l-4 border-l-emerald-500",
        info: "border-l-4 border-l-brand-500",
        accent: "border-l-4 border-l-violet-500",
      }[accent]
    : undefined;

  return (
    <section
      className={clsx(
        "overflow-hidden rounded-xl border border-ink-100 bg-white shadow-card",
        accentBorder,
        padded && "p-4 sm:p-5",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function CardHeader({
  title,
  description,
  icon: Icon,
  actions,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  icon?: LucideIcon;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={clsx(
        "flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 bg-ink-50/50 px-4 py-3 sm:px-5",
        className,
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="h-4 w-4 shrink-0 text-ink-400" />}
          <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
        </div>
        {description && <p className="mt-0.5 text-xs leading-relaxed text-ink-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function CardBody({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={clsx("p-4 sm:p-5", className)}>{children}</div>;
}

/* ------------------------------------------------------------- page header */

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow?: ReactNode;
  title: string;
  description?: string;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-3 border-b border-ink-100 bg-white px-4 py-4 sm:px-6 sm:py-5 lg:flex-row lg:items-center lg:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 flex items-center gap-2">{eyebrow}</div>}
        <h1 className="text-lg font-semibold text-ink-900 sm:text-xl">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-xs text-ink-400 sm:text-[13px]">{description}</p>}
        {meta && <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">{meta}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function MetaItem({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <span className="flex items-center gap-1.5 text-[11px] text-ink-400">
      {Icon && <Icon className="h-3.5 w-3.5" />}
      <span>{label}</span>
      <strong className="num font-semibold text-ink-700">{value}</strong>
    </span>
  );
}

/* --------------------------------------------------------------- stat tile */

export function StatTile({
  label,
  value,
  hint,
  tone = "neutral",
  icon: Icon,
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
  icon?: LucideIcon;
  className?: string;
}) {
  const valueTone = {
    neutral: "text-ink-900",
    info: "text-brand-700",
    success: "text-emerald-700",
    warning: "text-amber-700",
    danger: "text-red-700",
    accent: "text-violet-700",
  }[tone];

  return (
    <div className={clsx("rounded-lg border border-ink-100 bg-white p-3", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="label-micro">{label}</span>
        {Icon && <Icon className="h-3.5 w-3.5 text-ink-300" />}
      </div>
      <p className={clsx("num mt-1 text-lg font-semibold leading-tight", valueTone)}>{value}</p>
      {hint && <p className="mt-0.5 text-[11px] leading-snug text-ink-400">{hint}</p>}
    </div>
  );
}

/* ------------------------------------------------------------- key / value */

export function KeyValue({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="label-micro">{label}</dt>
      <dd className={clsx("num mt-0.5 text-sm font-medium text-ink-800", mono && "font-mono text-xs")}>
        {value}
      </dd>
    </div>
  );
}

/* ------------------------------------------------------------------- table */

export function Table({ children, minWidth }: { children: ReactNode; minWidth?: number }) {
  return (
    <div className="scroll-slim overflow-x-auto">
      <table className="w-full text-[13px]" style={minWidth ? { minWidth } : undefined}>
        {children}
      </table>
    </div>
  );
}

export function Th({
  children,
  align = "left",
  className,
}: {
  children?: ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}) {
  return (
    <th
      className={clsx(
        "whitespace-nowrap px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-400",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  align = "left",
  className,
}: {
  children?: ReactNode;
  align?: "left" | "right" | "center";
  className?: string;
}) {
  return (
    <td
      className={clsx(
        "px-3 py-2 text-ink-700",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className,
      )}
    >
      {children}
    </td>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-ink-100 bg-ink-50/60">
      <tr>{children}</tr>
    </thead>
  );
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-ink-100">{children}</tbody>;
}

/* -------------------------------------------------------------- empty/load */

export function EmptyState({
  icon: Icon,
  title,
  description,
  actions,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <Card className="mx-auto max-w-2xl">
      <div className="px-6 py-10 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-ink-100 bg-ink-50">
          <Icon className="h-5 w-5 text-ink-400" />
        </div>
        <h2 className="text-base font-semibold text-ink-900">{title}</h2>
        {description && <p className="mx-auto mt-1 max-w-md text-[13px] text-ink-400">{description}</p>}
        {actions && <div className="mt-5 flex flex-wrap items-center justify-center gap-2">{actions}</div>}
      </div>
      {children && <div className="border-t border-ink-100 bg-ink-50/40 px-5 py-4 text-left">{children}</div>}
    </Card>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton", className)} />;
}

export function LoadingPanel({ label }: { label: string }) {
  return (
    <div className="space-y-4 p-4 sm:p-6" aria-busy="true" aria-label={label}>
      <div className="flex items-center gap-3">
        <Skeleton className="h-8 w-8 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3.5 w-56" />
          <Skeleton className="h-3 w-80" />
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
      </div>
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );
}

/* ---------------------------------------------------------------- progress */

export function ProgressBar({
  value,
  tone = "info",
  className,
}: {
  value: number;
  tone?: Tone;
  className?: string;
}) {
  const bar = {
    neutral: "bg-ink-400",
    info: "bg-brand-500",
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    danger: "bg-red-500",
    accent: "bg-violet-500",
  }[tone];

  return (
    <div className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-ink-100", className)}>
      <div className={clsx("h-full rounded-full transition-all", bar)} style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }} />
    </div>
  );
}

/* --------------------------------------------------------------- callout */

export function Callout({
  tone = "info",
  title,
  children,
  icon: Icon,
}: {
  tone?: Tone;
  title?: ReactNode;
  children: ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <div className={clsx("rounded-lg border px-3.5 py-3 text-xs leading-relaxed", TONE_CLASSES[tone])}>
      <div className="flex gap-2.5">
        {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0" />}
        <div className="min-w-0">
          {title && <p className="mb-0.5 font-semibold">{title}</p>}
          <div className="opacity-90">{children}</div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ mono */

export function Formula({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={clsx(
        "break-words rounded-md border border-ink-100 bg-ink-50/70 px-2.5 py-1.5 font-mono text-[10px] leading-relaxed text-ink-400",
        className,
      )}
    >
      {children}
    </p>
  );
}
