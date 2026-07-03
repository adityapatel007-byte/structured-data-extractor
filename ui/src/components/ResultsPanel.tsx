/**
 * ResultsPanel — the right column when we have a result. Composes:
 *   - ConfidenceInkwell (top)
 *   - MetricsStrip (cost / latency / tokens / model)
 *   - JsonView (extracted data)
 *   - WarningsList
 *
 * Empty and error states are handled inline — no separate components needed
 * for something this small.
 */
import { AnimatePresence, motion } from "motion/react";

import type { APIError } from "@/lib/api";
import type { ExtractResponse } from "@/types";

import { ConfidenceInkwell } from "./ConfidenceInkwell";
import { JsonView } from "./JsonView";
import { MetricsStrip } from "./MetricsStrip";
import { WarningsList } from "./WarningsList";

interface Props {
  status: "idle" | "loading" | "success" | "error";
  response: ExtractResponse | null;
  error: APIError | null;
}

const ITEM = {
  hidden: { y: 24, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] },
  },
};

export function ResultsPanel({ status, response, error }: Props) {
  return (
    <AnimatePresence mode="wait">
      {status === "idle" && <Empty key="empty" />}
      {status === "loading" && <Loading key="loading" />}
      {status === "error" && error && <ErrorView key="error" error={error} />}
      {status === "success" && response && (
        <motion.div
          key="result"
          initial="hidden"
          animate="visible"
          exit={{ opacity: 0, transition: { duration: 0.3 } }}
          variants={{ visible: { transition: { staggerChildren: 0.08 } } }}
          className="flex flex-col gap-8"
        >
          <motion.div variants={ITEM}>
            <ConfidenceInkwell score={response.result.overall_confidence} />
          </motion.div>
          <motion.div variants={ITEM}>
            <MetricsStrip metrics={response.metrics} />
          </motion.div>
          <motion.div variants={ITEM}>
            <p className="eyebrow mb-3">Extracted data</p>
            <JsonView data={response.result.data} />
          </motion.div>
          <motion.div variants={ITEM}>
            <p className="eyebrow mb-3">Warnings</p>
            <WarningsList warnings={response.result.warnings} />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------------ */

function Empty() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.6 } }}
      exit={{ opacity: 0 }}
      className="relative flex h-full min-h-[420px] flex-col items-start justify-center gap-4 rounded-[6px] border border-dashed border-[var(--rule)] bg-transparent p-8"
    >
      <p className="eyebrow">Awaiting document</p>
      <p className="font-display text-[38px] leading-[1] text-[var(--ink-strong)]">
        The result will land here —
      </p>
      <p className="max-w-[420px] text-[14px] leading-[1.6] text-[var(--ink-soft)]">
        Confidence, cost, latency, and the extracted JSON. Every field
        cross-checked against a Pydantic schema before it reaches you.
      </p>
      <div className="mt-6 flex items-center gap-3 text-[12px] text-[var(--ink-mute)]">
        <span className="h-px w-8 bg-[var(--rule)]" />
        <span>Try one of the samples on the left</span>
      </div>
    </motion.div>
  );
}

function Loading() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col gap-6"
    >
      <p className="eyebrow">Extracting…</p>
      <p className="font-display text-[36px] leading-[1] text-[var(--ink-strong)]">
        Reading the sheet.
      </p>
      <div className="flex flex-col gap-3">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} delay={i * 0.15} />
        ))}
      </div>
    </motion.div>
  );
}

function Skeleton({ delay }: { delay: number }) {
  return (
    <motion.div
      initial={{ opacity: 0.4, backgroundColor: "var(--rule)" }}
      animate={{
        opacity: [0.4, 0.7, 0.4],
        transition: { duration: 1.8, repeat: Infinity, delay },
      }}
      className="h-3 rounded-[2px]"
      style={{ width: `${60 + Math.random() * 30}%` }}
    />
  );
}

function ErrorView({ error }: { error: APIError }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="flex flex-col gap-3 rounded-[6px] border-l-2 border-[var(--accent)] bg-[var(--accent-soft)] p-6"
    >
      <p className="eyebrow" style={{ color: "var(--accent)" }}>
        Extraction failed
      </p>
      <p className="font-display text-[26px] leading-[1.1] text-[var(--ink-strong)]">
        {error.message}
      </p>
      <p className="font-mono text-[12px] text-[var(--ink-soft)]">
        code: {error.code}
        {error.requestId && ` · request_id: ${error.requestId}`}
      </p>
    </motion.div>
  );
}
