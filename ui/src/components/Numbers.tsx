/**
 * Numbers — a magazine-style data page. Big display numerals, small
 * eyebrow labels, ruled dividers between rows. No cards, no gradients.
 * The point is to present the resume metrics as if a designer laid them out.
 */
import { motion } from "motion/react";

const ROWS = [
  {
    label: "Field-level F1",
    value: "0.94",
    sub: "SROIE test split",
  },
  {
    label: "Doc-level exact match",
    value: "78%",
    sub: "CORD test split",
  },
  {
    label: "Median latency",
    value: "1.9s",
    sub: "text-only PDFs",
  },
  {
    label: "Cost per doc",
    value: "$0.0004",
    sub: "GPT-5 nano, avg 2.4k input tokens",
  },
];

export function Numbers() {
  return (
    <section className="mx-auto w-full max-w-[1240px] border-t border-[var(--rule)] px-6 py-24 md:px-10">
      <div className="mb-14 flex items-end justify-between gap-6">
        <div>
          <p className="eyebrow mb-4">Quantified</p>
          <h2 className="font-display text-[clamp(38px,5vw,72px)] leading-[1] text-[var(--ink-strong)]">
            The numbers behind
            <br />
            <span className="font-display-italic">the pipeline.</span>
          </h2>
        </div>
        <p className="hidden max-w-[280px] text-[13px] leading-[1.6] text-[var(--ink-soft)] md:block">
          Every claim below comes from the eval harness in{" "}
          <code className="font-mono text-[12px]">src/eval/</code>.
          Reproduce with{" "}
          <code className="font-mono text-[12px]">python scripts/run_eval.py</code>.
        </p>
      </div>

      <div>
        {ROWS.map((r, i) => (
          <motion.div
            key={r.label}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{
              duration: 0.7,
              delay: i * 0.08,
              ease: [0.16, 1, 0.3, 1],
            }}
            className="grid grid-cols-[1fr_auto] items-baseline gap-6 border-t border-[var(--rule)] py-8 md:grid-cols-[1fr_auto_1fr]"
          >
            <p className="text-[13px] uppercase tracking-[0.16em] text-[var(--ink-soft)]">
              {r.label}
            </p>
            <p className="font-display text-[clamp(56px,7vw,108px)] leading-none text-[var(--ink-strong)]">
              {r.value}
            </p>
            <p className="hidden text-[13px] leading-[1.5] text-[var(--ink-mute)] md:block md:text-right">
              {r.sub}
            </p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
