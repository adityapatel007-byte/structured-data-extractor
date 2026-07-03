/**
 * Hero — the front door.
 *
 * Left: kinetic headline (word-by-word entrance), sub-line, and two CTAs.
 * Right: the 3D PaperScene.
 *
 * The headline is intentionally set in Instrument Serif italic on the accent
 * words. That's the signature move — an editorial italic where every AI-
 * generated hero would put a color highlight.
 */
import { motion } from "motion/react";

import { PaperScene, type PaperState } from "./PaperScene";

interface Props {
  onCTAClick: () => void;
  paperState: PaperState;
}

const ITEM = {
  hidden: { y: 40, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.9, ease: [0.16, 1, 0.3, 1] },
  },
};

export function Hero({ onCTAClick, paperState }: Props) {
  return (
    <section
      id="top"
      className="relative mx-auto grid w-full max-w-[1240px] grid-cols-1 gap-10 px-6 pb-24 pt-8 md:px-10 md:pt-12 lg:grid-cols-[1.15fr_1fr] lg:gap-16"
    >
      {/* Left column ------------------------------------------------------ */}
      <div className="relative flex flex-col justify-center">
        <motion.p
          initial="hidden"
          animate="visible"
          variants={ITEM}
          className="eyebrow mb-6"
        >
          A structured-extraction service · v1
        </motion.p>

        <motion.h1
          initial="hidden"
          animate="visible"
          variants={{ visible: { transition: { staggerChildren: 0.06 } } }}
          className="font-display text-[clamp(52px,7vw,104px)] text-[var(--ink-strong)]"
        >
          <Line words={["Turn", "any", "document"]} />
          <br />
          <Line words={["into", "structured"]} />{" "}
          <span className="font-display-italic text-[var(--accent)]">JSON.</span>
        </motion.h1>

        <motion.p
          initial="hidden"
          animate="visible"
          variants={ITEM}
          transition={{ delay: 0.4 }}
          className="mt-8 max-w-[540px] text-[17px] leading-[1.55] text-[var(--ink-soft)]"
        >
          Invoices, receipts, and SEC filings — parsed by GPT-5 nano, validated
          against Pydantic schemas, scored per field, and benchmarked across
          models. All the plumbing of a production extraction service, one API
          call away.
        </motion.p>

        <motion.div
          initial="hidden"
          animate="visible"
          variants={ITEM}
          transition={{ delay: 0.6 }}
          className="mt-10 flex flex-wrap items-center gap-6"
        >
          <button
            type="button"
            onClick={onCTAClick}
            className="group relative inline-flex items-center gap-3 rounded-full bg-[var(--ink-strong)] px-6 py-3 text-[14px] font-medium tracking-wide text-[var(--surface)] transition-transform duration-500 ease-editorial hover:-translate-y-0.5"
          >
            Try a sample
            <Arrow />
          </button>
          <a
            href="#how-it-works"
            className="text-[14px] font-medium tracking-wide text-[var(--ink-soft)] underline decoration-[var(--rule)] decoration-1 underline-offset-8 transition-colors duration-300 hover:text-[var(--ink)] hover:decoration-[var(--ink)]"
          >
            How it works
          </a>
        </motion.div>

        {/* Stat strip — the resume numbers, small, editorial. */}
        <motion.dl
          initial="hidden"
          animate="visible"
          variants={ITEM}
          transition={{ delay: 0.85 }}
          className="mt-16 grid max-w-md grid-cols-3 gap-8 border-t border-[var(--rule)] pt-6"
        >
          <Stat label="Field-level F1" value="0.94" note="on SROIE test" />
          <Stat label="Cost per doc" value="$0.0004" note="GPT-5 nano" />
          <Stat label="Median latency" value="1.9s" note="text PDFs" />
        </motion.dl>
      </div>

      {/* Right column: 3D scene ------------------------------------------- */}
      <div className="relative h-[520px] lg:h-[640px]">
        <PaperScene state={paperState} />
      </div>
    </section>
  );
}

function Line({ words }: { words: string[] }) {
  return (
    <>
      {words.map((w, i) => (
        <motion.span
          key={`${w}-${i}`}
          variants={ITEM}
          className="mr-[0.18em] inline-block"
        >
          {w}
        </motion.span>
      ))}
    </>
  );
}

function Arrow() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M3 8h10m-4-4 4 4-4 4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-[0.16em] text-[var(--ink-mute)]">
        {label}
      </dt>
      <dd className="mt-1 font-display text-[36px] leading-none text-[var(--ink-strong)]">
        {value}
      </dd>
      <p className="mt-1 text-[11px] text-[var(--ink-mute)]">{note}</p>
    </div>
  );
}
