/**
 * WarningsList — model-flagged concerns rendered as marginalia strokes.
 * Info/warning/error rendered with different left-border colors so the reader
 * can scan severity without reading.
 */
import type { ExtractionWarning } from "@/types";

interface Props {
  warnings: ExtractionWarning[];
}

const COLORS: Record<ExtractionWarning["severity"], string> = {
  info: "var(--ink-mute)",
  warning: "var(--mustard)",
  error: "var(--accent)",
};

export function WarningsList({ warnings }: Props) {
  if (!warnings.length) {
    return (
      <p className="text-[13px] italic text-[var(--ink-mute)]">
        No warnings — model reported no concerns.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {warnings.map((w, i) => (
        <li
          key={i}
          className="border-l-2 py-1.5 pl-4 text-[13px] leading-[1.6] text-[var(--ink-soft)]"
          style={{ borderLeftColor: COLORS[w.severity] }}
        >
          {w.field && (
            <span className="mr-2 font-mono text-[12px] text-[var(--ink-mute)]">
              {w.field}
            </span>
          )}
          {w.message}
        </li>
      ))}
    </ul>
  );
}
