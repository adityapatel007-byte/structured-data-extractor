---
title: Structured Data Extractor
emoji: 📄
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Receipts + invoices to validated JSON, GPT-5 nano
---

# Structured Data Extraction Service

> Multi-domain document extraction — turn invoices, receipts, and SEC filings into schema-validated JSON with confidence scoring, multi-model benchmarking, and quantified accuracy.

[![CI](https://github.com/adityapatel007-byte/structured-data-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/adityapatel007-byte/structured-data-extractor/actions/workflows/ci.yml)
[![HF Space](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Live%20demo-yellow)](https://huggingface.co/spaces/aditya0103/structured-data-extractor)
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![OpenAI](https://img.shields.io/badge/LLM-GPT--5%20nano-green)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

---

## What this does

Upload any invoice, receipt, or SEC filing (10-K / 10-Q). Get back clean, validated JSON matching a Pydantic schema — plus a per-field confidence score, a cost breakdown, and latency metrics.

```
PDF / Image / Scan  ─►  Router  ─►  {Invoice | Receipt | Filing} Pipeline  ─►  JSON + Confidence
                                        │
                                        └─►  Evaluation Harness  ─►  Precision / Recall / F1
```

## Why this project exists

Enterprise doc extraction is one of the highest-demand LLM use cases in 2026. This repo demonstrates the production skills that hiring managers screen for:

- Schema-driven extraction with **OpenAI structured outputs** + Pydantic validation
- **Vision-language handling** for scanned/image PDFs (GPT-5 nano vision)
- **Long-document handling** for 10-K / 10-Q filings (400K context, minimal chunking)
- **Multi-model benchmarking** — empirically compared gpt-5-nano vs gpt-5-mini vs gpt-5 on the same 10-record eval; nano is Pareto-optimal (micro F1 0.896 at $0.012/doc)
- **Evaluation harness** with precision / recall / F1 on public ground truth (SROIE, CORD)
- **Cost + latency observability** — every extraction logs tokens and $
- Full-stack: **FastAPI** backend, **React + Motion + R3F** UI, **Docker**, GitHub Actions **CI**
- **CI/CD** with GitHub Actions running tests + lint on every push

## Live demo

The full stack is on Hugging Face Spaces:

> **[huggingface.co/spaces/aditya0103/structured-data-extractor](https://huggingface.co/spaces/aditya0103/structured-data-extractor)** — always-on, free tier

Locally: `docker compose up --build` after cloning; hit [http://localhost:5173](http://localhost:5173).

## Deploy your own to HF Spaces

1. Create a new [HF Space](https://huggingface.co/new-space) → **Docker SDK**, blank template.
2. Add `OPENAI_API_KEY` under **Settings → Repository secrets**.
3. Point the Space at this repo (or push a fork). HF reads the YAML frontmatter
   at the top of this README (`sdk: docker`, `app_port: 7860`), builds the root
   `Dockerfile`, and exposes it on your Space URL. First build ~5-8 min; every
   redeploy ~2-3 min thanks to layer caching.

## Quantified results

Live evaluation on **gpt-5-nano** with `reasoning_effort="minimal"`. 10 receipt
records derived from public SROIE + CORD ground truth. Reports (per-record CSV,
JSON summary, markdown) land in `evaluation/reports/<timestamp>/` after each run.

| Domain   | Dataset (n=)      | Micro F1  | Macro F1  | Doc Exact | Cost / doc | Mean Latency |
|----------|-------------------|-----------|-----------|-----------|------------|--------------|
| Receipts | SROIE (5)         | **0.938** | **1.000** | 0.20      | **$0.012** | 6.3 s        |
| Receipts | CORD (5)          | **0.914** | 0.839     | **0.80**  | **$0.012** | 8.2 s        |
| Filings  | SEC 10-K (n=5)    | _v2 pipeline built — live numbers pending_ | | | | |

**Read the numbers:**
- **Micro F1 ≈ 0.92** across both datasets — the model gets ~92% of individual
  fields correct on ground-truth-derived text.
- **Doc-level exact match** is stricter (100% of fields right on one doc) and
  swings by dataset: CORD receipts (short, simple line items) hit 0.80; SROIE
  (freer-form Malaysian/Singaporean receipts with more optional fields) hits
  0.20 — a single missing field kills the metric on those.
- **$0.012 / doc** is the reasoning-tokens-included cost at `reasoning_effort=minimal`.
  Default (non-minimal) reasoning was **$0.042 / doc, 30 s / doc** — the minimal
  flag is a ~3.5× cost cut and ~4× latency cut with no measured quality loss
  on this schema.
- **Total spend for a full run: ~$0.12** — cheap enough to re-run on every
  significant prompt/schema change.

Reproduce locally:

```bash
python scripts/run_eval.py \
  --dataset evaluation/smoke_sroie_sample.jsonl \
  --doc-type receipt \
  --mode live \
  --model gpt-5-nano \
  --reasoning-effort minimal
```

### Multi-model comparison (2026-07-05)

Same 10 records, same prompts, same schemas — only the model changes. All runs
use `reasoning_effort="minimal"`. Reports land under `evaluation/benchmarks/<timestamp>/`.

| Model         | Micro F1  | Macro F1  | Doc-exact | Latency  | Cost / doc |
|---------------|-----------|-----------|-----------|----------|------------|
| `gpt-5-nano`  | **0.896** | 0.885     | 40 %      | 5.1 s    | **$0.0116** |
| `gpt-5-mini`  | 0.864     | 0.927     | 40 %      | 6.1 s    | $0.0127    |
| `gpt-5`       | 0.884     | **0.939** | 30 %      | 5.4 s    | $0.0118    |

**Read the numbers:**
- **`gpt-5-nano` is Pareto-optimal on this workload** — highest micro F1 at the
  lowest cost and lowest latency. Bigger tiers don't buy quality on high-support
  fields.
- **`gpt-5` and `gpt-5-mini` lead on macro F1** — they're measurably better on
  the rarer fields (macro weights every field equally regardless of support).
  If your extraction schema is long-tailed, the ~7 % macro-F1 lift may be worth
  the small extra spend.
- **Doc-exact stays 30-40 % across all three** — an artifact of a strict metric
  and a schema with many optional fields. Micro F1 tracks real quality here.
- **Total benchmark spend: $0.36** to definitively answer "which model should
  ship in prod?" — this is the kind of question worth measuring instead of
  guessing at, and it's cheap enough to re-run whenever the prompt or schema
  moves.

Reproduce:

```bash
python scripts/run_multimodel_benchmark.py
# or with a custom matrix:
python scripts/run_multimodel_benchmark.py gpt-5-nano:minimal gpt-5-mini:minimal gpt-4o-mini
```

Next: real image PDFs from the SROIE test split for a stricter, OCR-inclusive
number, then the SEC 10-K schema for the long-doc / dual-domain story.

## Architecture

```
┌──────────────┐      ┌───────────────┐      ┌────────────────────┐
│  React UI    │─────►│    FastAPI    │─────►│   Extractor        │
│      UI      │◄─────│   /extract    │◄─────│  (GPT-5 nano+vision)│
└──────────────┘      └───────────────┘      └────────────────────┘
                                                       │
                             ┌─────────────────────────┼─────────────────────┐
                             ▼                         ▼                     ▼
                    ┌────────────────┐        ┌──────────────┐      ┌──────────────┐
                    │ Pydantic       │        │ Confidence   │      │  Cost /      │
                    │ Schemas        │        │ Scorer       │      │  Latency Log │
                    └────────────────┘        └──────────────┘      └──────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Evaluation    │
                    │  Harness       │
                    │  (P/R/F1)      │
                    └────────────────┘
```

**Long-document handling (10-K path).** SEC filings are 50-250 pages and would
cost ~$0.60/doc if we shipped the whole thing to the model on every call. So
the filing path runs the document through a section chunker
(`src/extractors/section_chunker.py`) that finds each `Item 1.`, `Item 1A.`,
`Item 7.`, `Item 8.` heading via regex, deduplicates against the Table of
Contents (keeping the last occurrence — the real section), and slices the
plaintext into named chunks. Only the cover, Item 8 (financials), and Item 1A
(risk factors) are stitched into the prompt — everything else is skipped.
Result: ~30–40K prompt tokens per 10-K instead of ~150K, on the same
gpt-5-nano @ minimal reasoning-effort configuration.

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| LLM | OpenAI GPT-5 nano (default) + benchmarked vs GPT-5 mini + GPT-5 full | 400K context, vision, structured outputs, ~50x cheaper than GPT-4o |
| Schema | Pydantic v2 | Runtime validation + JSON schema for OpenAI |
| PDF text | pdfplumber, PyMuPDF | Fast, robust, handles most layouts |
| PDF images | pdf2image + Pillow | For scanned/image-heavy PDFs → vision model |
| Backend | FastAPI | Async, auto OpenAPI docs, batteries included |
| Frontend | React + Vite + Tailwind + Motion + React Three Fiber | Editorial "Paper & Ink" aesthetic — 3D paper sheet in the hero, kinetic type, dark/light mode. No generic AI-SaaS look. |
| Eval | rapidfuzz, scikit-learn | Fuzzy text matching + P/R/F1 |
| Container | Docker (multi-stage) | Portable, reproducible |
| Deploy | Hugging Face Spaces | Free, AI-community-recognized |
| CI | GitHub Actions | Tests + lint on every push |

## Quick start

```bash
# 1. Clone + install
git clone https://github.com/adityapatel007-byte/structured-data-extractor.git
cd structured-data-extractor
python -m venv .venv && source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Set your OpenAI key
cp .env.example .env
# edit .env → paste your OPENAI_API_KEY

# 3. Run the API
uvicorn src.api.main:app --reload

# 4. Run the UI — Paper & Ink React + Motion + R3F frontend
#    (in another terminal, from ui/)
cd ui && npm install && npm run dev
# then open http://localhost:5173

# 5. (Optional) Evaluate against the committed sample ground truth.
#    `selfcheck` mode uses a mock extractor to validate the eval pipeline (F1=1.0).
python scripts/run_eval.py --dataset data/samples/sroie_sample.jsonl \
    --doc-type receipt --mode selfcheck

# 6. Benchmark a real model on your own ground-truth JSONL:
python scripts/run_eval.py --dataset evaluation/ground_truth/sroie.jsonl \
    --doc-type receipt --mode live --model gpt-5-nano
```

Reports (per-record CSV + summary JSON + resume-ready markdown) land in
`evaluation/reports/<UTC-timestamp>/`.

### 10-K (SEC filings) quick start

```bash
# 1. Download the 5-issuer watchlist (Apple, JPM, ExxonMobil, Pfizer, Walmart).
#    Files land in data/raw/10k/ — plaintext, sidecar JSON, and XBRL companyfacts.
python scripts/download_edgar.py

# 2. Build a ground-truth JSONL from the sidecars + XBRL.
python scripts/build_filings_gt.py

# 3. Run the eval against a real model.
python scripts/run_eval.py \
    --dataset evaluation/smoke_filings_sample.jsonl \
    --doc-type filing \
    --mode live \
    --model gpt-5-nano \
    --reasoning-effort minimal
```

The filing extractor uses section-based chunking to keep per-doc cost around
$0.05–0.15 instead of $0.60+ at whole-document context.

## Project structure

```
04-structured-data-extraction/
├── src/
│   ├── schemas/         # Pydantic schemas per doc type
│   ├── extractors/      # LLM extraction logic
│   ├── api/             # FastAPI backend
│   └── utils/           # cost tracking, logging, config
├── ui/                  # React + Motion + R3F frontend (Paper & Ink)
│   ├── src/components/  # Hero, PaperScene (3D), Dropzone, ResultsPanel, ...
│   ├── src/styles/      # theme.css (dark/light tokens) + globals.css
│   └── package.json
├── tests/
│   ├── unit/
│   └── integration/
├── data/
│   ├── raw/             # downloaded datasets (gitignored)
│   ├── processed/       # normalized ground truth
│   └── samples/         # small demo files (committed)
├── evaluation/
│   ├── ground_truth/    # labeled gold data
│   └── reports/         # eval run outputs
├── docker/              # Dockerfile + compose
├── .github/workflows/   # CI
├── requirements.txt
├── .env.example
└── README.md
```

## Roadmap

- [x] **v1 — Invoices & Receipts pipeline + multi-model benchmark**
- [x] **v2 — SEC 10-K pipeline** (schema + section chunker + EDGAR downloader, live eval pending)
- [ ] v3 — Streaming extraction + async batch API
- [ ] v4 — Fine-tuning experiment vs. base GPT-5 nano

## License

MIT
