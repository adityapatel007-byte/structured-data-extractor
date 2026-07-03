import type { Config } from "tailwindcss";

/**
 * Tailwind is used strictly for utility layout + spacing.
 * All colors, typography, and design tokens live in CSS variables (theme.css)
 * so dark/light mode is one attribute flip on <html data-theme="...">.
 * We reference variables via arbitrary values: text-[var(--ink)] etc.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Instrument Serif"', "serif"],
        sans: ['"Geist"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      transitionTimingFunction: {
        // The house easing — expo out. Everything eases like this.
        editorial: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
} satisfies Config;
