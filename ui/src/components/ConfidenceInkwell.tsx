/**
 * ConfidenceInkwell — the confidence score, rendered as an ink well.
 *
 * A tall rectangular vessel. Ink fills from the bottom to the score. The
 * meniscus (top surface) has a subtle wobble via `<animate>` for that "still
 * settling" feel — signals it's a live measurement, not a static bar.
 *
 * Color shifts by confidence tier: sage (>0.85), mustard (0.6-0.85), coral (<0.6).
 */
import { motion } from "motion/react";

interface Props {
  score: number; // 0..1
}

export function ConfidenceInkwell({ score }: Props) {
  const pct = Math.max(0, Math.min(1, score));
  const tier = pct >= 0.85 ? "high" : pct >= 0.6 ? "mid" : "low";
  const color =
    tier === "high"
      ? "var(--confidence-high)"
      : tier === "mid"
      ? "var(--confidence-mid)"
      : "var(--confidence-low)";
  const label = tier === "high" ? "High" : tier === "mid" ? "Fair" : "Low";

  return (
    <div className="flex items-end gap-6">
      <div className="relative h-24 w-14 overflow-hidden rounded-[3px] border border-[var(--rule)] bg-[var(--surface-2)]">
        {/* Ink fill */}
        <motion.div
          className="absolute inset-x-0 bottom-0"
          initial={{ height: 0 }}
          animate={{ height: `${pct * 100}%` }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          style={{ background: color }}
        >
          {/* Meniscus — a subtle wave at the top of the ink */}
          <svg
            viewBox="0 0 100 8"
            preserveAspectRatio="none"
            className="absolute -top-[3px] left-0 h-2 w-full"
          >
            <path
              d="M0 6 Q 25 0 50 6 T 100 6 L 100 8 L 0 8 Z"
              fill={color}
            />
            <animate
              attributeName="opacity"
              values="1;0.7;1"
              dur="3.2s"
              repeatCount="indefinite"
            />
          </svg>
        </motion.div>
        {/* Tick marks on the side of the well */}
        <div className="pointer-events-none absolute right-0 top-0 h-full w-2">
          {[0.25, 0.5, 0.75].map((t) => (
            <div
              key={t}
              className="absolute right-0 h-px w-2 bg-[var(--rule)]"
              style={{ bottom: `${t * 100}%` }}
            />
          ))}
        </div>
      </div>

      <div>
        <p className="eyebrow mb-1">Confidence</p>
        <p className="font-display text-[52px] leading-none text-[var(--ink-strong)]">
          {(pct * 100).toFixed(0)}
          <span className="ml-1 text-[24px] text-[var(--ink-soft)]">%</span>
        </p>
        <p className="mt-1 text-[12px] tracking-wide text-[var(--ink-soft)]">
          {label} · self-reported
        </p>
      </div>
    </div>
  );
}
