/**
 * JsonView — pretty-printed, syntax-highlighted JSON with a copy button.
 * No dependencies — a small tokenizer that hits the keys/strings/numbers/
 * booleans we care about. Style-tunable via CSS variables so the palette
 * shifts cleanly between light and dark.
 */
import { useMemo, useState } from "react";

interface Props {
  data: unknown;
  maxHeight?: string;
}

export function JsonView({ data, maxHeight = "420px" }: Props) {
  const pretty = useMemo(() => JSON.stringify(data, null, 2), [data]);
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(pretty);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard denied */
    }
  };

  return (
    <div className="relative overflow-hidden rounded-[6px] border border-[var(--rule)] bg-[var(--surface-2)]">
      <div className="flex items-center justify-between border-b border-[var(--rule)] px-4 py-2.5">
        <span className="eyebrow">extraction_result.json</span>
        <button
          type="button"
          onClick={onCopy}
          className="rounded-full border border-[var(--rule)] px-3 py-1 text-[11px] tracking-wide text-[var(--ink-soft)] transition-colors duration-300 hover:border-[var(--ink)] hover:text-[var(--ink)]"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        style={{ maxHeight }}
        className="overflow-auto px-5 py-4 font-mono text-[12.5px] leading-[1.7] text-[var(--ink)]"
      >
        <code dangerouslySetInnerHTML={{ __html: highlight(pretty) }} />
      </pre>
    </div>
  );
}

/* ------------------------------------------------------------------------ */

// Minimal JSON syntax highlighter — enough to distinguish keys, strings,
// numbers, booleans, and null. Uses spans with CSS variable colors.
function highlight(json: string): string {
  const esc = json
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return esc.replace(
    /("(?:\\.|[^"\\])*"(?:\s*:)?)|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (m) => {
      if (/^"/.test(m)) {
        if (/:$/.test(m)) {
          return `<span style="color:var(--accent)">${m.replace(/:$/, "")}</span>:`;
        }
        return `<span style="color:var(--sage)">${m}</span>`;
      }
      if (/true|false/.test(m)) {
        return `<span style="color:var(--mustard)">${m}</span>`;
      }
      if (/null/.test(m)) {
        return `<span style="color:var(--ink-mute)">${m}</span>`;
      }
      // number
      return `<span style="color:var(--ink-strong)">${m}</span>`;
    }
  );
}
