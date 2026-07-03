/**
 * Footer — a signature line, not a link farm.
 */
const GITHUB_URL = "https://github.com/adityapatel007-byte/structured-data-extractor";

export function Footer() {
  return (
    <footer className="mx-auto w-full max-w-[1240px] border-t border-[var(--rule)] px-6 py-10 md:px-10">
      <div className="flex flex-col items-start justify-between gap-4 text-[12px] tracking-wide text-[var(--ink-mute)] md:flex-row md:items-center">
        <p>
          Built by{" "}
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="text-[var(--ink-soft)] underline decoration-[var(--rule)] decoration-1 underline-offset-4 transition-colors hover:text-[var(--ink)] hover:decoration-[var(--ink)]"
          >
            ASP
          </a>
          {" · "}open source · MIT
        </p>
        <p className="font-mono">v0.1.0 · 2026</p>
      </div>
    </footer>
  );
}
