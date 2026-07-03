/**
 * HowItWorks — three editorial "chapters" instead of icon cards.
 * Each chapter has a chapter number, a serif headline, and a short body.
 * The numbers scale up on scroll into view — subtle, not showy.
 */
import { motion } from "motion/react";

const CHAPTERS = [
  {
    n: "I",
    title: "Read the document",
    body: "PyMuPDF renders each page; pdfplumber extracts text; the loader auto-detects text vs image PDFs so we spend vision tokens only when we need them.",
  },
  {
    n: "II",
    title: "Parse into a schema",
    body: "The prompt requests strict JSON in a Pydantic-defined envelope. OpenAI’s structured outputs handle the schema translation — the model literally cannot invent fields.",
  },
  {
    n: "III",
    title: "Score, benchmark, ship",
    body: "The eval harness compares extracted fields against ground truth with type-appropriate matching (fuzzy text, money tolerance, ISO dates). Micro-F1 rolls up into a resume-worthy number.",
  },
];

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="mx-auto w-full max-w-[1240px] border-t border-[var(--rule)] px-6 py-24 md:px-10"
    >
      <p className="eyebrow mb-16">The pipeline</p>

      <div className="grid grid-cols-1 gap-16 md:grid-cols-3 md:gap-12">
        {CHAPTERS.map((c, i) => (
          <motion.div
            key={c.n}
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{
              duration: 0.8,
              delay: i * 0.1,
              ease: [0.16, 1, 0.3, 1],
            }}
            className="flex flex-col gap-4"
          >
            <div className="font-display-italic text-[92px] leading-[0.9] text-[var(--accent)]">
              {c.n}
            </div>
            <h3 className="font-display text-[32px] leading-[1] text-[var(--ink-strong)]">
              {c.title}
            </h3>
            <p className="max-w-[380px] text-[14.5px] leading-[1.65] text-[var(--ink-soft)]">
              {c.body}
            </p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
