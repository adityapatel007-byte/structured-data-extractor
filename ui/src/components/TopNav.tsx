/**
 * TopNav — logo mark on the left, GitHub + theme toggle on the right.
 * Deliberately quiet — no full navigation, no CTAs. The site is one page.
 */
import { ThemeToggle } from "./ThemeToggle";

const GITHUB_URL = "https://github.com/adityapatel007-byte/structured-data-extractor";

export function TopNav() {
  return (
    <header className="relative z-30 mx-auto flex w-full max-w-[1240px] items-center justify-between px-6 py-6 md:px-10">
      <a href="#top" className="flex items-center gap-3">
        <LogoMark />
        <span className="font-display text-[22px] leading-none tracking-tight">
          Ledger
        </span>
        <span className="hidden text-[11px] uppercase tracking-[0.18em] text-[var(--ink-mute)] md:inline-block">
          / structured extraction
        </span>
      </a>

      <nav className="flex items-center gap-3">
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noreferrer"
          className="hidden text-[13px] tracking-wide text-[var(--ink-soft)] transition-colors duration-300 hover:text-[var(--ink)] md:inline"
        >
          Source ↗
        </a>
        <ThemeToggle />
      </nav>
    </header>
  );
}

function LogoMark() {
  // A minimal ink glyph — a page corner folded over. Two strokes, that's it.
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden>
      <path
        d="M5 3.5h11.5L21 8v14.5H5V3.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path
        d="M16.5 3.5V8H21"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}
