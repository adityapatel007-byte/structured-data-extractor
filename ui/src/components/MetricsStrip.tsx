/**
 * MetricsStrip — cost, latency, tokens, and model, styled like the marginalia
 * on an accountant's ledger. Each is a small block with an eyebrow label and
 * a display-font number, separated by thin ruled dividers.
 *
 * The cost gets a wax-stamp treatment — a small angled disc behind the number.
 */
import type { ExtractionMetrics } from "@/types";

interface Props {
  metrics: ExtractionMetrics;
}

export function MetricsStrip({ metrics }: Props) {
  return (
    <div className="grid grid-cols-2 gap-6 border-t border-b border-[var(--rule)] py-6 sm:grid-cols-4">
      <Cell label="Cost / doc" value={formatCost(metrics.cost_usd)} stamp />
      <Cell label="Latency" value={formatLatency(metrics.latency_ms)} />
      <Cell
        label="Tokens"
        value={`${metrics.input_tokens.toLocaleString()} + ${metrics.output_tokens.toLocaleString()}`}
        small
      />
      <Cell label="Model" value={metrics.model} small mono />
    </div>
  );
}

/* ------------------------------------------------------------------------ */

function Cell({
  label,
  value,
  small,
  mono,
  stamp,
}: {
  label: string;
  value: string;
  small?: boolean;
  mono?: boolean;
  stamp?: boolean;
}) {
  return (
    <div className="relative">
      <p className="eyebrow mb-2">{label}</p>
      <p
        className={
          (mono ? "font-mono " : "font-display ") +
          "relative inline-block leading-none text-[var(--ink-strong)] " +
          (small ? "text-[18px] pt-1" : "text-[34px]")
        }
      >
        {stamp && <StampBg />}
        <span className="relative">{value}</span>
      </p>
    </div>
  );
}

function StampBg() {
  return (
    <svg
      aria-hidden
      className="pointer-events-none absolute -left-3 -top-3 h-14 w-14 -rotate-6 opacity-70"
      viewBox="0 0 60 60"
      fill="none"
    >
      <circle
        cx="30"
        cy="30"
        r="26"
        stroke="var(--accent)"
        strokeWidth="1.2"
        strokeDasharray="3 3"
      />
      <circle cx="30" cy="30" r="22" stroke="var(--accent)" strokeWidth="0.8" />
    </svg>
  );
}

/* -- formatters ----------------------------------------------------------- */

function formatCost(usd: number): string {
  if (usd < 0.001) return `$${(usd * 1000).toFixed(2)}m`; // in mills
  return `$${usd.toFixed(4)}`;
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}
