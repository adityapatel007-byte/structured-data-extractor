/**
 * ThemeToggle — a moon/sun rendered as ink strokes, not a Material icon.
 * Deliberately hand-drawn feel: the moon has a slight crescent bite, the sun
 * has four short rays. Both drawn with strokeLinecap="round".
 */
import { motion } from "motion/react";

import { useTheme } from "@/hooks/useTheme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${dark ? "light" : "dark"} mode`}
      className="group relative h-9 w-9 rounded-full border border-[var(--rule)] bg-[var(--surface)] transition-colors duration-500 ease-editorial hover:border-[var(--ink)]"
    >
      <motion.span
        key={theme}
        initial={{ rotate: -30, opacity: 0 }}
        animate={{ rotate: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="pointer-events-none absolute inset-0 flex items-center justify-center"
      >
        {dark ? <Moon /> : <Sun />}
      </motion.span>
    </button>
  );
}

function Sun() {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="3.4" stroke="currentColor" strokeWidth="1.2" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => {
        const rad = (deg * Math.PI) / 180;
        const x1 = 10 + Math.cos(rad) * 6;
        const y1 = 10 + Math.sin(rad) * 6;
        const x2 = 10 + Math.cos(rad) * 7.8;
        const y2 = 10 + Math.sin(rad) * 7.8;
        return (
          <line
            key={deg}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="currentColor"
            strokeWidth="1.2"
            strokeLinecap="round"
          />
        );
      })}
    </svg>
  );
}

function Moon() {
  // A crescent drawn as one path — feels like a pen stroke, not an icon.
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M15 12.5A6 6 0 0 1 7.5 5c0-.5.06-.98.17-1.44A6 6 0 1 0 16.44 12.33c-.46.11-.94.17-1.44.17Z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
