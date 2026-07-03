/**
 * ExtractSection — the interactive core. Wires Dropzone <-> useExtract <->
 * ResultsPanel. The parent (App) needs to know when we're extracting so the
 * hero's 3D paper can respond, so we lift the state up via `onStateChange`.
 */
import { useEffect, useState } from "react";
import { motion } from "motion/react";

import { useExtract } from "@/hooks/useExtract";
import type { DocType } from "@/types";
import type { PaperState } from "./PaperScene";

import { Dropzone } from "./Dropzone";
import { ResultsPanel } from "./ResultsPanel";

interface Props {
  onStateChange: (s: PaperState) => void;
  bindExtract: (fn: () => void) => void;
}

export function ExtractSection({ onStateChange, bindExtract }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<DocType>("receipt");
  const { status, response, error, run, reset } = useExtract();

  const busy = status === "loading";

  // Bubble status up so hero's 3D paper can react.
  useEffect(() => {
    if (status === "loading") onStateChange("extracting");
    else if (status === "success") onStateChange("extracted");
    else onStateChange("idle");
  }, [status, onStateChange]);

  const doExtract = () => {
    if (!file) return;
    run({ file, docType });
  };

  // The hero's "Try a sample" CTA scrolls here + focuses the browse. Expose
  // that hook to the parent via bindExtract.
  useEffect(() => {
    bindExtract(() => {
      const el = document.getElementById("extract");
      el?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [bindExtract]);

  return (
    <section
      id="extract"
      className="relative mx-auto w-full max-w-[1240px] border-t border-[var(--rule)] px-6 py-24 md:px-10"
    >
      <div className="mb-14 flex items-end justify-between gap-6">
        <div>
          <p className="eyebrow mb-4">The workbench</p>
          <h2 className="font-display text-[clamp(38px,5vw,72px)] leading-[1] text-[var(--ink-strong)]">
            Try it on a document.
          </h2>
        </div>
        {response && (
          <button
            type="button"
            onClick={() => {
              reset();
              setFile(null);
            }}
            className="text-[13px] tracking-wide text-[var(--ink-soft)] underline decoration-[var(--rule)] decoration-1 underline-offset-4 hover:text-[var(--ink)] hover:decoration-[var(--ink)]"
          >
            Start over
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-14 lg:grid-cols-[1fr_1fr] lg:gap-20">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <Dropzone
            file={file}
            docType={docType}
            setFile={setFile}
            setDocType={setDocType}
            onExtract={doExtract}
            onSample={() => {
              // If a sample was picked, kick off extraction automatically.
              setTimeout(doExtract, 200);
            }}
            busy={busy}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{
            duration: 0.8,
            delay: 0.15,
            ease: [0.16, 1, 0.3, 1],
          }}
        >
          <ResultsPanel status={status} response={response} error={error} />
        </motion.div>
      </div>
    </section>
  );
}
