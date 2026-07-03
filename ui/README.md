# Ledger UI

The Paper & Ink frontend for the structured-data-extraction API.

## Stack

- **Vite + React + TypeScript** — fast dev loop, small bundle.
- **Tailwind** — utility layout only. All colors, typography, and design
  tokens live as CSS variables in `src/styles/theme.css`, so dark/light mode
  is a single attribute flip on `<html data-theme="...">`.
- **Motion** (`motion/react`) — component-level animation.
- **React Three Fiber + drei + three** — the 3D paper sheet in the hero.
- **Google Fonts** — Instrument Serif (display), Geist (UI), JetBrains Mono
  (code). All free.

## Run locally

```bash
# 1. Install
cd ui
npm install

# 2. Point at the API (in another terminal, from the repo root):
uvicorn src.api.main:app --reload

# 3. Start the dev server
npm run dev

# open http://localhost:5173
```

Vite proxies `/api/*` to `http://localhost:8000`, so no CORS needed in dev.

## Configuration

- `VITE_API_BASE` (optional) — override the API origin for prod builds.
  Defaults to `/api`.

## Design tokens

Everything visual is in `src/styles/theme.css`:

- `--bg`, `--surface`, `--surface-2`, `--rule` — surfaces + dividers
- `--ink`, `--ink-strong`, `--ink-soft`, `--ink-mute` — text weights
- `--accent`, `--accent-hover`, `--accent-soft` — coral
- `--sage`, `--mustard` — confidence tiers + warnings

To try a color, edit the variable — both modes update simultaneously.

## Project shape

```
ui/
├── index.html                  # font preload + theme priming (no-flash)
├── src/
│   ├── main.tsx                # ReactDOM render
│   ├── App.tsx                 # page composition
│   ├── styles/
│   │   ├── theme.css           # design tokens (light + dark)
│   │   └── globals.css         # base + grain overlay + focus/cursor
│   ├── components/
│   │   ├── TopNav.tsx          # logo + theme toggle
│   │   ├── ThemeToggle.tsx     # hand-drawn sun/moon
│   │   ├── CustomCursor.tsx    # spring-lag ink dot
│   │   ├── Hero.tsx            # kinetic headline + stats + 3D scene
│   │   ├── PaperScene.tsx      # R3F: floating paper w/ mouse parallax
│   │   ├── ExtractSection.tsx  # workbench (dropzone + results)
│   │   ├── Dropzone.tsx        # drop + browse + doc-type + samples
│   │   ├── ResultsPanel.tsx    # composes the below
│   │   ├── ConfidenceInkwell.tsx # confidence as an ink vessel
│   │   ├── MetricsStrip.tsx    # cost/latency/tokens/model
│   │   ├── JsonView.tsx        # syntax-highlighted JSON
│   │   ├── WarningsList.tsx    # model-flagged concerns
│   │   ├── HowItWorks.tsx      # three chapters
│   │   ├── Numbers.tsx         # magazine-style data page
│   │   └── Footer.tsx          # signature line
│   ├── hooks/
│   │   ├── useTheme.ts         # dark/light + localStorage
│   │   └── useExtract.ts       # upload lifecycle
│   ├── lib/
│   │   ├── api.ts              # thin fetch client + typed error envelope
│   │   └── samples.ts          # committed sample docs
│   └── types.ts                # mirrors src/schemas server-side
└── public/samples/             # sample_receipt.png, sample_invoice.pdf
```
