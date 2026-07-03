/**
 * Dropzone — a large paper-textured zone that accepts PDF and images.
 *
 * States:
 *   idle     : hairline border, "Drop a document" copy, sample buttons visible
 *   over     : border deepens, corner marks pulse in
 *   selected : filename appears, "extract" primary CTA lights up
 *   busy     : dashed border animates, ghost typewriter under filename
 */
import { motion, AnimatePresence } from "motion/react";
import { useCallback, useRef, useState } from "react";

import type { DocType } from "@/types";
import { SAMPLE_DOCS, loadSampleAsFile, type SampleDoc } from "@/lib/samples";

const ACCEPT = "application/pdf,image/png,image/jpeg,image/webp,image/tiff,image/bmp";

interface Props {
  file: File | null;
  docType: DocType;
  setFile: (f: File | null) => void;
  setDocType: (d: DocType) => void;
  onExtract: () => void;
  onSample: (sample: SampleDoc) => void;
  busy: boolean;
}

export function Dropzone({
  file,
  docType,
  setFile,
  setDocType,
  onExtract,
  onSample,
  busy,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const onFiles = useCallback(
    (files: FileList | null) => {
      if (!files || !files[0]) return;
      setFile(files[0]);
    },
    [setFile]
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setOver(false);
    onFiles(e.dataTransfer.files);
  };

  const pickSample = async (sample: SampleDoc) => {
    try {
      const f = await loadSampleAsFile(sample);
      setFile(f);
      setDocType(sample.docType);
      onSample(sample);
    } catch (err) {
      console.warn("Sample load failed", err);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* --- The dropzone card ------------------------------------------- */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        data-cursor="focus"
        className="relative overflow-hidden rounded-[6px] border border-[var(--rule)] bg-[var(--surface)] transition-colors duration-500 ease-editorial"
        style={{
          borderColor: over ? "var(--ink)" : undefined,
        }}
      >
        {/* Corner tick marks — appear when dragging over */}
        <Corners active={over} />

        <div className="flex min-h-[280px] flex-col items-center justify-center gap-4 px-8 py-14 text-center">
          <p className="eyebrow">Upload</p>
          <h2 className="font-display text-[42px] leading-none text-[var(--ink-strong)]">
            {file ? "Ready to extract" : "Drop a document"}
          </h2>
          <AnimatePresence mode="wait">
            {file ? (
              <motion.p
                key="fname"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="font-mono text-[13px] text-[var(--ink-soft)]"
              >
                {file.name}
                <span className="ml-2 text-[var(--ink-mute)]">
                  · {(file.size / 1024).toFixed(1)} KB
                </span>
              </motion.p>
            ) : (
              <motion.p
                key="prompt"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="max-w-[380px] text-[14px] leading-[1.55] text-[var(--ink-soft)]"
              >
                PDF or image. Up to 10 MB. We keep nothing — every extraction is
                stateless.
              </motion.p>
            )}
          </AnimatePresence>

          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="mt-3 text-[13px] font-medium tracking-wide text-[var(--ink)] underline decoration-[var(--rule)] decoration-1 underline-offset-8 transition-colors hover:decoration-[var(--ink)]"
          >
            {file ? "Choose a different file" : "or browse for a file"}
          </button>

          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => onFiles(e.target.files)}
          />
        </div>

        {/* Progress bar during extraction */}
        <AnimatePresence>
          {busy && (
            <motion.div
              className="absolute inset-x-0 bottom-0 h-[2px] bg-[var(--accent)]"
              initial={{ scaleX: 0, transformOrigin: "left" }}
              animate={{
                scaleX: [0, 0.7, 0.85, 0.95],
                transition: { duration: 6, ease: "easeOut" },
              }}
              exit={{ scaleX: 1, opacity: 0, transition: { duration: 0.4 } }}
            />
          )}
        </AnimatePresence>
      </div>

      {/* --- Options row ------------------------------------------------- */}
      <div className="flex flex-wrap items-center justify-between gap-6 border-t border-[var(--rule)] pt-6">
        <DocTypePicker value={docType} onChange={setDocType} />

        <button
          type="button"
          disabled={!file || busy}
          onClick={onExtract}
          className="group inline-flex items-center gap-3 rounded-full bg-[var(--accent)] px-6 py-3 text-[14px] font-medium tracking-wide text-white transition-all duration-500 ease-editorial hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:bg-[var(--rule)] disabled:text-[var(--ink-mute)]"
        >
          {busy ? "Extracting…" : "Extract"}
          {!busy && <Arrow />}
        </button>
      </div>

      {/* --- Sample buttons --------------------------------------------- */}
      <div className="flex flex-col gap-2">
        <p className="eyebrow">Or try a sample</p>
        <div className="flex flex-wrap gap-2">
          {SAMPLE_DOCS.map((s) => (
            <button
              key={s.id}
              type="button"
              disabled={busy}
              onClick={() => pickSample(s)}
              className="rounded-full border border-[var(--rule)] bg-[var(--surface)] px-4 py-1.5 text-[12px] tracking-wide text-[var(--ink-soft)] transition-colors duration-300 hover:border-[var(--ink)] hover:text-[var(--ink)] disabled:opacity-50"
            >
              {s.label} <span className="text-[var(--ink-mute)]">↗</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------ */

function DocTypePicker({
  value,
  onChange,
}: {
  value: DocType;
  onChange: (v: DocType) => void;
}) {
  const opts: { key: DocType; label: string }[] = [
    { key: "receipt", label: "Receipt" },
    { key: "invoice", label: "Invoice" },
  ];
  return (
    <div className="flex items-center gap-2">
      <span className="eyebrow mr-2">Type</span>
      {opts.map((o) => {
        const active = value === o.key;
        return (
          <button
            key={o.key}
            type="button"
            onClick={() => onChange(o.key)}
            className="relative rounded-full px-4 py-1.5 text-[12px] tracking-wide transition-colors duration-300"
            style={{
              color: active ? "var(--surface)" : "var(--ink-soft)",
            }}
          >
            {active && (
              <motion.span
                layoutId="doctype-pill"
                transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                className="absolute inset-0 rounded-full bg-[var(--ink-strong)]"
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function Corners({ active }: { active: boolean }) {
  const stroke = "var(--ink)";
  const s = 24;
  const off = 16;
  const style = { transition: "opacity 400ms cubic-bezier(0.16,1,0.3,1)" };
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0"
      style={{ opacity: active ? 1 : 0, ...style }}
    >
      {/* Four L-shaped corner marks */}
      {[
        { top: off, left: off, path: `M0 ${s} L0 0 L${s} 0` },
        { top: off, right: off, path: `M${-s} 0 L0 0 L0 ${s}` },
        { bottom: off, left: off, path: `M0 ${-s} L0 0 L${s} 0` },
        { bottom: off, right: off, path: `M${-s} 0 L0 0 L0 ${-s}` },
      ].map((c, i) => (
        <svg
          key={i}
          width={s}
          height={s}
          viewBox={`${c.left !== undefined ? 0 : -s} ${
            c.top !== undefined ? 0 : -s
          } ${s} ${s}`}
          className="absolute"
          style={{
            top: c.top,
            left: c.left,
            right: c.right,
            bottom: c.bottom,
          }}
        >
          <path d={c.path} stroke={stroke} strokeWidth="1.4" fill="none" />
        </svg>
      ))}
    </div>
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
