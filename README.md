# Structured Data Extraction Service

> Multi-domain document extraction — turn invoices, receipts, and SEC filings into schema-validated JSON with confidence scoring, multi-model benchmarking, and quantified accuracy.

[![CI](https://img.shields.io/badge/CI-pending-yellow)]()
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
- **Multi-model benchmarking** — quantifies GPT-5 nano vs GPT-5.4 vs GPT-5.5 cost/quality tradeoffs
- **Evaluation harness** with precision / recall / F1 on public ground truth (SROIE, CORD)
- **Cost + latency observability** — every extraction logs tokens and $
- Full-stack: **FastAPI** backend, **Streamlit** UI, **Docker**, deployed on **HF Spaces**
- **CI/CD** with GitHub Actions running tests + lint on every push

## Live demo

_v1 (invoices) — coming soon on HF Spaces._

## Quantified results

_Will be filled in after v1 evaluation run:_

| Domain | Dataset | Field-level F1 | Doc-level Accuracy | Cost / doc | Median Latency |
|--------|---------|---------------|-------------------|-----------|---------------|
| Receipts | SROIE (test) | _pending_ | _pending_ | _pending_ | _pending_ |
| Receipts | CORD (test) | _pending_ | _pending_ | _pending_ | _pending_ |
| Filings | SEC 10-K sample | _pending_ | _pending_ | _pending_ | _pending_ |

## Architecture

```
┌──────────────┐      ┌───────────────┐      ┌────────────────────┐
│  Streamlit   │─────►│    FastAPI    │─────►│   Extractor        │
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

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| LLM | OpenAI GPT-5 nano (default) + benchmarking against GPT-5.4 / GPT-5.5 | 400K context, vision, structured outputs, ~50x cheaper than GPT-4o |
| Schema | Pydantic v2 | Runtime validation + JSON schema for OpenAI |
| PDF text | pdfplumber, PyMuPDF | Fast, robust, handles most layouts |
| PDF images | pdf2image + Pillow | For scanned/image-heavy PDFs → vision model |
| Backend | FastAPI | Async, auto OpenAPI docs, batteries included |
| Frontend | Streamlit | Fastest path to a demo-worthy UI |
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

# 4. Run the UI (in another terminal)
streamlit run src/ui/app.py
```

## Project structure

```
04-structured-data-extraction/
├── src/
│   ├── schemas/         # Pydantic schemas per doc type
│   ├── extractors/      # LLM extraction logic
│   ├── api/             # FastAPI backend
│   ├── ui/              # Streamlit frontend
│   └── utils/           # cost tracking, logging, config
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

- [x] **v1 — Invoices & Receipts pipeline + multi-model benchmark** _(in progress)_
- [ ] v2 — SEC Filings pipeline (10-K / 10-Q, long-doc handling)
- [ ] v3 — Streaming extraction + async batch API
- [ ] v4 — Fine-tuning experiment vs. base GPT-5 nano

## License

MIT
