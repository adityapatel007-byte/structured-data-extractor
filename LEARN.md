# LEARN — a working knowledge of what you built

> If a hiring manager pulls this project up in a screen and asks you to walk
> them through it, this doc is the map you narrate from. Every design
> decision, every trade-off, every "why not the other thing" is captured
> here. Read it end to end once. Reread the section for whichever thing they
> poke at.

---

## Table of contents

1. [The one-liner (what it is, why it exists)](#1-the-one-liner)
2. [The end-to-end request flow](#2-the-end-to-end-request-flow)
3. [Every layer, one at a time](#3-every-layer-one-at-a-time)
   - 3.1 Pydantic schemas + the strict-mode constraint
   - 3.2 The extractor + the envelope pattern
   - 3.3 The document loader
   - 3.4 The OpenAI client (why `temperature=None`, why `reasoning_effort="minimal"`)
   - 3.5 Section chunker for 10-Ks
   - 3.6 FastAPI backend + dependency injection for tests
   - 3.7 Evaluation harness — the P/R/F1 machinery
   - 3.8 UI (Paper & Ink, React + Motion + R3F)
   - 3.9 Docker + HF Spaces single-container deploy
   - 3.10 GitHub Actions CI
4. [The 14 design decisions you should be able to defend](#4-the-14-design-decisions-you-should-be-able-to-defend)
5. [The roadmap explained — v1 v2 v3 v4](#5-the-roadmap-explained)
6. [Interview cheat sheet](#6-interview-cheat-sheet)
7. [File map — what lives where](#7-file-map)

---

## 1. The one-liner

**A production-grade LLM service that turns unstructured business documents
(invoices, receipts, SEC 10-K filings) into schema-validated JSON with
per-field confidence, cost accounting, and a reproducible evaluation harness.**

The point of the project isn't the extraction. Every LLM demo does that. The
point is everything *around* it — schemas, evaluation, cost tracking, multi-
model benchmarking, section chunking for long documents, tests, CI, a real
frontend, Docker, and a live public URL. That's the shape of shipped LLM
software, and it's what hiring managers screen for.

**Who would use this**: a fintech that gets 10,000 vendor invoices a month and
needs to auto-populate their AP system. A hedge fund analyst who wants 10-K
financials in Snowflake. A small business owner who wants receipts categorized
into QuickBooks. All three use the same API — different `doc_type`, different
schema, same envelope.

---

## 2. The end-to-end request flow

Here's what happens when a user drops a PDF into the UI. Follow this sequence
carefully — every layer earns its keep.

```
┌────────────┐   1. multipart POST   ┌──────────────┐   2. dispatch on doc_type    ┌───────────────┐
│  React UI  │──────────────────────►│   FastAPI    │─────────────────────────────►│  Extractor    │
│ (Dropzone) │◄──────────────────────│  /extract    │◄─── 6. ExtractionResult ─────│ orchestrator  │
└────────────┘                       └──────────────┘                              └───────┬───────┘
                                                                                          │
                                                                                          │ 3. load
                                                                                          ▼
                                                                                  ┌───────────────┐
                                                                                  │ document      │
                                                                                  │ loader        │
                                                                                  │ (pdf/img/txt) │
                                                                                  └───────┬───────┘
                                                                                          │
                                                                                          │ text + images
                                                                                          │
                                    ┌─────────────────────────────────────────────────────┤
                                    │  4. filing? → chunk into cover + Item 1A + Item 8   │
                                    │     invoice/receipt? → send whole doc               │
                                    ▼                                                     ▼
                             ┌─────────────┐                                    ┌──────────────────┐
                             │ system      │                                    │  OpenAI          │
                             │ prompt      │──── messages ─────────────────────►│ chat.completions │
                             │ (per type)  │                                    │      .parse      │
                             └─────────────┘                                    └────────┬─────────┘
                                                                                         │
                                              5. envelope validated ◄──────── strict JSON│
                                              by Pydantic v2                             │
                                              (extra=forbid)                             ▼
                                                                                ┌──────────────────┐
                                                                                │ ExtractionResult │
                                                                                │ + metrics        │
                                                                                └──────────────────┘
```

**Steps 1-6 in words:**

1. **UI POSTs `file + doc_type + optional model` to `/extract`.** The React
   Dropzone builds the multipart request. `doc_type` is one of
   `receipt | invoice | filing`. The optional `model` flag is what powers the
   multi-model benchmark.

2. **FastAPI receives, dispatches to `DocumentExtractor.extract()`.** The
   router (`src/api/routers/extract.py`) validates the file size (413 error
   over 10 MB), the content type (415), the doc_type (400), and injects the
   extractor via `Depends(get_extractor)`. That dependency injection is
   important — it lets tests swap in a fake extractor.

3. **Document loader parses the bytes.** `document_loader.py` sniffs the
   filename and dispatches. PDFs go through pdfplumber for text; if
   text-density is under 100 chars per page it falls back to PyMuPDF page
   rendering → PNG → vision. Images pass straight through as base64. `.txt`
   / `.md` decode as UTF-8. Returns a `LoadedDocument(text, images_b64,
   source_type)`.

4. **Dispatch on `doc_type`.** For invoices/receipts, one system prompt + the
   full document text + images → one OpenAI call. For filings, the section
   chunker runs first, slicing the doc into cover + Item 8 + Item 1A blocks,
   and the message builder stitches those into three labeled sections. This is
   the trick that makes 10-Ks affordable (~$0.06/doc instead of ~$0.60/doc if
   you ship the whole 150K-token document).

5. **OpenAI `chat.completions.parse` with a Pydantic response format.** This
   is the game-changer. Instead of asking for JSON in a prompt and hoping,
   we hand OpenAI the *envelope schema* — Pydantic v2 → JSON Schema —
   and OpenAI's strict mode guarantees the return matches. No JSON parsing
   errors, no missing fields, no extra fields. If the model can't comply,
   the API returns 400 instead of garbage.

6. **Response gets wrapped in `ExtractionResult`.** The extractor computes
   `overall_confidence` from the per-field scores, attaches the raw text
   snippet for debugging, and returns `(result, metrics)`. Metrics include
   tokens, cost, latency, and the model used — every request is fully
   accounted for.

---

## 3. Every layer, one at a time

### 3.1 Pydantic schemas + the strict-mode constraint

`src/schemas/{base,common,invoice,receipt,filing,registry}.py`.

**The base**: `StrictModel` has `extra="forbid"`. This one config choice
cascades through everything. It means:

- The model cannot invent fields. If it hallucinates `internal_note`, Pydantic
  rejects the whole response.
- OpenAI's structured-outputs strict mode requires `additionalProperties:
  false` on every object in the schema — which is exactly what `extra="forbid"`
  produces.
- Adding a new field means adding it to the schema. There's no other place it
  can come from.

**The registry pattern**: `src/schemas/registry.py` maps `"invoice" | "receipt"
| "filing"` to schema classes. Adding a new domain (e.g. purchase orders)
is a one-line change here plus a new schema file. Downstream code — the API,
the eval CLI, the extractor, the envelope factory — all look up via
`get_schema(doc_type)`. No hardcoded branches anywhere.

**Money as `float`, not `Decimal`**. Read this carefully because it's a
question you *will* be asked. OpenAI structured outputs represent `Decimal`
as `string` in JSON Schema — which pushes the numeric parsing back onto the
model as a string task and reduces precision. `float` is `number` in JSON
Schema, which the model handles natively. We round to 2 decimals on assignment
via a validator. If this were an accounting system-of-record, we'd use
`Decimal` at the *application* layer *after* extraction — but at the LLM
boundary, `float` is correct.

### 3.2 The extractor + the envelope pattern

`src/extractors/extractor.py` orchestrates. `src/extractors/envelope.py`
handles the Pydantic gymnastics.

The **envelope pattern** answers a subtle question: what does the LLM
return? Not `ExtractionResult` directly, because some of that (like
`overall_confidence`, computed as mean-of-scores) is our code's job, not the
model's. Instead we generate — dynamically per doc type — an envelope class:

```python
Envelope = create_model(
    "InvoiceEnvelope",
    data=(Invoice, ...),
    field_confidences=(list[FieldConfidence], ...),
    warnings=(list[ExtractionWarning], ...),
)
```

The model outputs the envelope, our code wraps it in `ExtractionResult` and
adds the computed pieces. Envelopes are LRU-cached so they're created once
per doc type.

### 3.3 The document loader

`src/extractors/document_loader.py`. Dispatches on filename + magic bytes:

- `.pdf` → try pdfplumber first. If text density is under 100 chars/page,
  fall back to PyMuPDF page rendering → PNG → send images to vision.
- `.png / .jpg / .jpeg / .webp / .tiff / .bmp` → base64 encode, ship as
  vision input.
- `.txt / .md / .log / .text` → UTF-8 decode, ship as text.
- Anything else → `source_type="empty"`, extractor raises.

The text/image branch matters because a scanned receipt with no OCR layer
looks empty to pdfplumber. The rendering fallback lets vision do the work.

### 3.4 The OpenAI client

`src/extractors/openai_client.py`. Two non-obvious details:

**`temperature=None` (not 0.0)**. The gpt-5 family only accepts the default
temperature; passing `0.0` returns a 400. We use a nullable field and only
send it if the caller explicitly requests one. This bit us early — the
original code hardcoded `temperature=0.0` and every gpt-5-nano call failed.

**`reasoning_effort="minimal"`**. gpt-5 models have an internal chain-of-
thought that's billed to you as reasoning tokens. On our schema, the default
effort costs $0.042/doc and takes 30 seconds. `minimal` costs $0.012/doc and
takes 7 seconds with no measured quality loss. The flag is exposed all the
way through the CLI so the benchmark can compare.

**Tenacity retry**. The client retries on `RateLimitError` and `APIError` with
exponential backoff. Nothing exotic — just a decorator.

### 3.5 Section chunker for 10-Ks

`src/extractors/section_chunker.py`. This one's pretty:

A 10-K is 50-250 pages. Even at gpt-5's 400K token context, feeding the whole
thing costs ~$0.60/doc. But 10-Ks have structured Items — `Item 1A. Risk
Factors`, `Item 7. MD&A`, `Item 8. Financial Statements` — that the chunker
finds via regex.

The regex tolerates every real-world variant: `ITEM 1A.`, `Item 1A —`,
`item 1a:`. It runs across the whole document and returns every hit, then
**keeps only the last occurrence of each item ID** — because every 10-K
mentions each Item at least twice (Table of Contents + real section), and the
last one is always the real body.

Cover slice = first 4KB before the first Item. Section bodies = from just
after the heading to the start of the next heading. Result: a `ChunkedFiling`
with `.get("1A")`, `.has("8")`, `.get_text("1A", default="…")`.

Downstream, the extractor stitches cover + Item 8 + Item 1A into three
labeled blocks in one prompt. Prompt tokens drop from ~150K to ~30-40K,
cost drops from ~$0.60/doc to ~$0.06/doc, and the model has less distractor
text to sift through.

### 3.6 FastAPI backend

`src/api/main.py`, `routers/`, `middleware.py`, `errors.py`.

- **Endpoints**: `GET /` (banner), `GET /health` (probe for Docker),
  `GET /schemas` (list doc types), `GET /schemas/{doc_type}` (JSON Schema),
  `POST /extract` (the money endpoint).
- **Dependency injection**: `get_extractor` returns a singleton
  `DocumentExtractor` via `lru_cache`. In tests, `app.dependency_overrides`
  swaps it for a fake — so the whole test suite runs without an OpenAI key.
- **Middleware**: `RequestIDMiddleware` attaches an `X-Request-ID` header;
  `AccessLogMiddleware` emits one structured JSON log line per request.
- **Error envelope**: every 4xx/5xx returns `{"error": {code, message,
  request_id, details}}`. Consistent shape for the frontend to render.
- **CORS**: wide open. Fine for a portfolio; you'd lock this down in prod.

### 3.7 Evaluation harness

`src/eval/{flatten,comparators,metrics,runner,report,cli}.py`.

This is the piece I'm proudest of. Given a JSONL of ground-truth records
and an extractor function, it produces per-record CSV, JSON summary, and
resume-worthy markdown — all reproducible from `python scripts/run_eval.py`.

**Flattener** walks a Pydantic model + dicts recursively and produces
`{"total": 12.99, "line_items[0].description": "Coffee", ...}`. So nested
schemas score the same way flat ones do.

**Type classifier** looks at each field's Python type and JSON value:
- `float` fields with `money` in the name → money comparator (0.01 absolute
  OR 0.5% relative tolerance — either passes)
- other `float` / `int` → number comparator (exact)
- `str` with currency/SKU/phone/ID hints → exact comparator
- other `str` → fuzzy comparator (rapidfuzz `token_set_ratio ≥ 85`)
- `date` / `time` → ISO equality

**Metrics** compute per-field TP/FP/FN/TN, then **micro F1** (weighted by
field support), **macro F1** (mean of per-field F1 across every field with
non-zero support), and **doc-exact-match** (fraction of docs where every
field is right).

**Runner** takes an *injected* extractor function (`ExtractorFn` protocol),
so `--mode selfcheck` uses a mock that returns ground truth verbatim
(validates the eval pipeline itself always hits F1=1.0), and `--mode live`
uses `DocumentExtractor`. Same code path.

The CLI accepts `--model` and `--reasoning-effort` — which is what makes the
multi-model benchmark a one-command sweep.

### 3.8 UI — Paper & Ink

`ui/src/`. React + Vite + TypeScript + Tailwind + Motion + React Three Fiber.

Deliberate choice: **do not look like a generic AI-SaaS demo**. Editorial
aesthetic. Cream paper + deep ink navy in light mode; warm charcoal +
parchment in dark. Instrument Serif italic for the display face. Grain
overlay via inline SVG turbulence.

**Hero**: a 3D paper sheet with mouse parallax (React Three Fiber), procedural
canvas texture (no glTF file), that folds a corner and turns green when the
extraction succeeds. Reduced-motion respected.

**Dropzone**: drag-drop or browse, sample buttons for a real receipt PNG and
invoice PDF that ship in `ui/public/samples/`. Doc-type picker with `Receipt
| Invoice | 10-K`. Confidence rendered as an ink well that fills from the
bottom; cost as a wax-stamped number.

**API contract** in `ui/src/lib/api.ts`. Types mirror the FastAPI response
shape 1:1.

### 3.9 Docker + HF Spaces single-container deploy

Root `Dockerfile` is three-stage:

1. `node:20-alpine` builds the UI → `dist/`.
2. `python:3.11-slim` installs the Python venv.
3. Runtime: nginx + uvicorn + tini as PID 1. `docker/nginx.hf.conf` listens
   on 7860 (HF's required port), serves `dist/` at `/`, proxies `/api/*` to
   `127.0.0.1:8000`. Entrypoint launches uvicorn in the background, polls
   `/health` for up to 30s so nginx never serves 502s during boot, then
   exec's nginx in the foreground with a SIGTERM trap.

`docker/api.Dockerfile` + `docker/ui.Dockerfile` + `docker-compose.yml` are
the two-container local-dev variant. Same code, different packaging.

HF Space YAML frontmatter (`sdk: docker`, `app_port: 7860`) tells HF to build
the root `Dockerfile`. `OPENAI_API_KEY` is a Space secret.

### 3.10 GitHub Actions CI

`.github/workflows/ci.yml`. Three parallel jobs on every push:

1. **python-lint-and-test** — ruff + pytest across 126 unit tests (no OpenAI
   key needed, thanks to the injected extractor).
2. **ui-typecheck-and-build** — tsc + vite build.
3. **docker-build** — buildx multi-arch build with GHA cache, gated on both
   lint jobs.

---

## 4. The 14 design decisions you should be able to defend

If asked "why did you do X instead of Y," here's the honest answer for each.

| # | Decision | Alternative | Why we chose ours |
|---|----------|-------------|-------------------|
| 1 | Pydantic v2 with `extra="forbid"` | dataclasses, Marshmallow, JSON Schema alone | OpenAI's structured-outputs strict mode maps directly onto Pydantic's config. Free validation + JSON Schema generation. |
| 2 | Money as `float` with rounder validator | `Decimal` | OpenAI structured outputs render `Decimal` as `string` in JSON Schema — model has to parse. `float` is native `number`. Round on assignment. Convert to `Decimal` at the app layer if needed. |
| 3 | Envelope pattern (dynamically generated) | Model outputs full `ExtractionResult` | Some fields (`overall_confidence`, `raw_text_snippet`) are our code's job. Envelope is the LLM contract; ExtractionResult is the app contract. |
| 4 | Registry for doc types | `if/elif` on doc_type | One place to add a new domain. Downstream code is generic. |
| 5 | `client.beta.chat.completions.parse` | Prompt-then-JSON.loads | Native structured outputs eliminate a whole class of parsing errors and hallucinated schemas. |
| 6 | `reasoning_effort="minimal"` on gpt-5 | Default effort | 3.5× cheaper, 4× faster, no measurable quality drop on structured extraction. Verified with the eval harness. |
| 7 | `temperature=None` (opt-in) | `temperature=0.0` hardcoded | gpt-5 family rejects `temperature=0.0`. Had to be discovered by breakage. |
| 8 | Section chunking for 10-Ks | Whole-doc single call | ~10× cost reduction ($0.60→$0.06) with equal-or-better signal ratio. |
| 9 | Regex chunker, "keep last occurrence" | Full parser (unstructured, llama_index) | Real 10-Ks mention each Item at least twice (TOC + body). Keep-last is deterministic and works. |
| 10 | Injected extractor in eval + API | Real extractor everywhere | Test suite runs without OpenAI. CI stays deterministic and free. |
| 11 | Rapidfuzz `token_set_ratio ≥ 85` for text | Exact string match | Merchant names print as "SANYU STATIONERY" vs `"Sanyu Stationery Shop"`; those are the same merchant. |
| 12 | Money tolerance: 0.01 abs OR 0.5% rel | Exact match | Real receipts round differently. Both prevent silly-false-negatives. |
| 13 | React + Motion + R3F for UI | Streamlit / Gradio | Portfolio project. Recruiters can tell in 5 seconds whether the UI was thrown together. Editorial aesthetic on purpose. |
| 14 | Single Docker container on HF Spaces | HF SDK Gradio, or Vercel + Railway | HF Spaces is the AI-community-recognized host, single container = one URL, one deploy, one health check. |

---

## 5. The roadmap explained

The README roadmap has four checkboxes. Here's what each one actually means
in concrete engineering terms.

### v1 — Invoices & Receipts pipeline + multi-model benchmark ✅

**Shipped 2026-07-04 → 2026-07-05.** Full stack: schemas, extractor,
FastAPI, React UI, Docker, HF Spaces, 96 tests, CI green. Live eval on
gpt-5-nano hit **0.94 F1 on receipts at $0.012/doc, 6s latency**. Multi-model
benchmark swept nano vs mini vs full at reasoning-effort=minimal on the same
10 records; **nano was Pareto-optimal (0.896 micro F1 at $0.0116/doc)** —
larger tiers led on macro F1 only.

### v2 — SEC 10-K pipeline ✅

**Shipped 2026-07-05 → 2026-07-06.** Adds the `filing` doc type end-to-end:
`FilingCover` + `FilingFinancials` + `RiskFactor` Pydantic schemas, regex-based
section chunker for Items 1A/8, filing-specific system prompt with unit-of-
measure normalization rules, EDGAR downloader script that respects SEC's
10 req/s + User-Agent policy, XBRL-driven auto-ground-truth builder. First
live eval: **0.56 micro F1 at $0.06/doc**. v2.2 attempted three targeted
fixes (prompt worked examples, FIN_MAP expansion for banks, cover backfill)
— per-field improvements on revenue/total_equity/operating_income, aggregate
stayed flat because filing_date regressed and total_debt didn't move. Full
diagnose→try→measure narrative in the README. **30 new tests, 126 total.**

### v3 — Streaming extraction + async batch API 🔜

**Two orthogonal features that ship together because they both change the
API shape.**

**Streaming extraction.** Right now `/extract` waits 5-8 seconds for the full
completion, then returns the whole `ExtractionResult`. That's fine for one
doc, poor UX for a big 10-K. Streaming means the API returns
**Server-Sent Events**: as OpenAI streams tokens, we forward chunks to the
client, which shows fields "appearing" one at a time in the UI.

Concretely:
- `POST /extract/stream` → `Content-Type: text/event-stream`, one JSON event
  per field, terminated with `event: done`.
- FastAPI uses `StreamingResponse` + `sse-starlette`.
- OpenAI SDK: `client.chat.completions.parse(stream=True)` iterates chunks.
- The UI hook `useExtract` becomes an `EventSource` consumer; the
  `ResultsPanel` renders fields as they arrive.
- Complication: `parse(stream=True)` doesn't give partial validated objects
  — you get raw JSON text you have to accumulate + parse yourself. That's
  where a token-safe streaming parser (`json-stream`, `ijson`) earns its
  keep.

**Async batch API.** For enterprise use — imagine uploading 500 vendor
invoices at once. Client submits, gets a job ID, polls or subscribes for
results.

Concretely:
- `POST /extract/batch` with a list of file URLs (or a zip) → returns `job_id`.
- `GET /extract/batch/{job_id}` → status + partial results.
- Backend: an `asyncio.Queue` fanning docs out to N concurrent extractors
  (Semaphore-limited to respect OpenAI rate limits). No Redis / RQ needed —
  the docs are small, the state fits in memory. If we scaled beyond one
  container we'd swap in Redis + RQ.
- Cost tracking rolls up to per-batch totals.

**Why this matters on your resume**: streaming + batching are the two things
that separate "LLM demo" from "LLM product." Hiring managers see this and
think you've been in production.

**Estimated work**: 1-2 sessions. No new API cost — same extractor, different
wrapper.

### v4 — Fine-tuning experiment vs. base GPT-5 nano 🔜

**Fine-tune a copy of gpt-5-nano (or gpt-4o-mini as the cheaper baseline) on
~200-500 receipt / invoice examples pulled from SROIE and CORD training
splits. Benchmark against the base model on the same 10-record eval you've
been using.**

Concretely:
- Fine-tuning is OpenAI's hosted service. You upload a JSONL of examples in
  chat-completion format: `{"messages": [{system}, {user, file+prompt},
  {assistant, expected JSON}]}`. OpenAI trains a copy. You call it via a
  custom model ID (`ft:gpt-5-nano:your-org:receipts-2026:abc123`).
- **What to expect**: the fine-tuned model will score *higher* F1 on this
  specific schema (probably 0.94 → 0.97+ on receipts) but is billed at a
  higher per-token rate. And it only knows your schema — a schema change
  means retraining.
- **What you'd actually write about**: not "look, F1 went up," but "here's
  when you should fine-tune vs. when you should prompt-tune." Most schemas
  don't need fine-tuning; ours got 0.94 F1 with prompting alone. The
  interesting answer to a hiring manager is "I tried fine-tuning and
  measured that the marginal quality gain wasn't worth the ongoing cost +
  schema lock-in for this workload."

**Estimated work**: 2-3 sessions. **Cost**: ~$5-20 for the training run
depending on example count and epochs.

**Why this matters on your resume**: fine-tuning is a keyword hiring
managers screen for, but "I fine-tuned and F1 went up" is a junior answer.
"I fine-tuned, measured, and chose *not* to ship it because the cost model
didn't work for this schema" is a senior answer.

---

## 6. Interview cheat sheet

### "Walk me through your project."

Take 90 seconds. Don't start with the stack. Start with the story:

> I built a service that turns three kinds of business documents — invoices,
> receipts, SEC 10-Ks — into schema-validated JSON. The interesting part
> isn't the extraction itself; it's everything around it. Pydantic v2 with
> `extra="forbid"` gives OpenAI's structured-outputs strict mode a schema
> to enforce, so the model can't hallucinate fields. There's an evaluation
> harness that computes per-field precision, recall, and F1 against public
> ground truth. I used that harness to benchmark three GPT-5 tiers and
> proved that nano is Pareto-optimal on this workload. For 10-Ks I built a
> regex-based section chunker so we only ship Item 8 and Item 1A to the
> model — that drops cost from $0.60/doc to $0.06/doc. Deployed on Hugging
> Face Spaces via a single Docker container. Full stack: FastAPI backend,
> React + Motion + R3F frontend, GitHub Actions CI running 126 tests.

### "Why Pydantic?"

Runtime validation + JSON Schema generation for free. And its `extra="forbid"`
config maps 1:1 onto OpenAI's strict mode requirement of
`additionalProperties: false`. If I hadn't used Pydantic I'd have written
that JSON Schema by hand and validated the response manually.

### "How do you handle model errors or hallucinations?"

Three layers. First, `extra="forbid"` means the model *cannot* invent fields —
OpenAI's strict mode rejects those before we ever see them. Second, per-field
confidence scores let us surface uncertainty to the UI. Third, the eval
harness measures F1 against ground truth so we know *empirically* which
fields the model gets wrong — you can't catch what you don't measure.

### "How do you evaluate quality?"

Per-field precision, recall, F1 with type-appropriate comparators — money
uses a 0.01 absolute or 0.5% relative tolerance; text uses rapidfuzz's
token-set ratio at 85; dates use ISO equality. Then micro F1 for overall,
macro F1 for how rare fields do, and doc-level exact-match as the strictest
metric.

### "What was the hardest part?"

Two things. **One**: 10-K unit-of-measure — "in millions" means multiply
by a million and the model kept forgetting. I did a diagnose→try→measure
loop where I added worked examples to the prompt. Revenue precision doubled;
some other fields regressed. Real ML/eng work. **Two**: the streaming
consideration — I punted it to v3 because getting partial validated Pydantic
objects out of a token stream is a whole architectural rethink; the current
`.parse()` API only gives you the object at completion.

### "What would you do differently?"

Two-pass extract-then-verify for money fields. First call extracts as we do
now; second call is prompted with "here's what you just returned — verify
each dollar figure against the scale header in the source." Empirically that
kind of self-review pattern is where the next 15-20 F1 points on 10-K
financials live.

### "How did you deploy?"

Single-container Docker on Hugging Face Spaces. Multi-stage build: node
builds the UI to `dist/`, python installs the venv, runtime image has nginx
+ uvicorn + tini. Entrypoint launches uvicorn in the background, polls
`/health` for up to 30 seconds so nginx never serves 502s while boot is
in progress, then exec's nginx as PID 1. Space secret carries the OpenAI
key.

### "Why not just use LangChain?"

For this use case it would add complexity without helping. LangChain's
value is when you need agents, tool use, RAG. Structured extraction with
a Pydantic response format is one API call — LangChain would be a wrapper
over what I already have. If v3 grows an agent-style tool-use pattern
(e.g. "look up this vendor in our CRM") I'd reconsider.

### "How much did all this cost you to build?"

Under $2 in OpenAI API cost total. Multi-model benchmark was $0.36. Two
10-K eval runs were $0.30 each. Everything else is free — HF Spaces free
tier, GitHub free-tier CI, the sandbox for dev.

---

## 7. File map

```
04-structured-data-extraction/
├── src/                          # Backend Python
│   ├── schemas/                  # Pydantic schemas + registry
│   │   ├── base.py               # StrictModel, ExtractionResult, FieldConfidence, ExtractionWarning
│   │   ├── common.py             # Address, Party, MoneyMixin, currency helpers
│   │   ├── invoice.py            # Invoice, LineItem
│   │   ├── receipt.py            # Receipt, ReceiptLineItem
│   │   ├── filing.py             # Filing, FilingCover, FilingFinancials, RiskFactor  ← v2
│   │   └── registry.py           # doc_type → schema class
│   ├── extractors/
│   │   ├── document_loader.py    # PDF/image/txt → LoadedDocument
│   │   ├── prompts.py            # SYSTEM_PROMPT_{INVOICE,RECEIPT,FILING} + common rules
│   │   ├── envelope.py           # Dynamic envelope Pydantic model, per-schema LRU cached
│   │   ├── openai_client.py      # OpenAI wrapper, retry, reasoning_effort, temperature=None
│   │   ├── section_chunker.py    # Regex-based 10-K Item splitter, TOC dedup            ← v2
│   │   └── extractor.py          # Top-level DocumentExtractor, dispatches on doc_type
│   ├── api/
│   │   ├── main.py               # FastAPI app + CORS + middleware wiring
│   │   ├── deps.py               # get_extractor dependency (LRU-cached singleton)
│   │   ├── errors.py             # APIError subclasses, exception handler
│   │   ├── middleware.py         # RequestID + AccessLog middleware
│   │   └── routers/
│   │       ├── health.py         # GET /, /health
│   │       ├── schemas.py        # GET /schemas, /schemas/{doc_type}
│   │       └── extract.py        # POST /extract (multipart)
│   ├── data_prep/                # SROIE + CORD normalizers, JSONL writer
│   ├── eval/
│   │   ├── flatten.py            # Nested Pydantic → flat dotted-path dict
│   │   ├── comparators.py        # money / number / text / exact / date comparators
│   │   ├── metrics.py            # TP/FP/FN/TN, micro F1, macro F1, doc-exact
│   │   ├── runner.py             # run_eval(records, extractor_fn, doc_type) → EvalReport
│   │   ├── report.py             # write CSV, JSON summary, markdown
│   │   └── cli.py                # argparse entry point (--mode, --model, --reasoning-effort)
│   └── utils/                    # config (dotenv), cost_tracker, logging (loguru)
├── ui/                           # React + Vite + TS + Tailwind + Motion + R3F
│   ├── src/
│   │   ├── App.tsx               # Page composition
│   │   ├── main.tsx              # Vite entry
│   │   ├── components/
│   │   │   ├── Hero.tsx          # Kinetic-headline + 3D paper
│   │   │   ├── PaperScene.tsx    # R3F Canvas, procedural paper texture
│   │   │   ├── ExtractSection.tsx# Workbench (Dropzone + ResultsPanel)
│   │   │   ├── Dropzone.tsx      # File upload + doc-type picker + samples
│   │   │   ├── ResultsPanel.tsx  # JSON view + confidence + cost
│   │   │   ├── ConfidenceInkwell.tsx, JsonView.tsx, MetricsStrip.tsx, WarningsList.tsx
│   │   │   ├── HowItWorks.tsx, Numbers.tsx, TopNav.tsx, Footer.tsx
│   │   │   ├── ThemeToggle.tsx   # dark/light one-attribute flip
│   │   │   └── CustomCursor.tsx  # ink-dot cursor with spring lag
│   │   ├── hooks/                # useExtract, useTheme
│   │   ├── lib/                  # api.ts (fetch client), samples.ts (Coffee/Software)
│   │   ├── styles/               # theme.css (tokens), globals.css (grain, cursor)
│   │   └── types.ts              # DocType, ExtractResponse mirror the API
│   ├── public/samples/           # coffee_receipt.png + software_invoice.pdf (real files!)
│   ├── package.json, tsconfig.json, vite.config.ts, tailwind.config.js
├── scripts/                      # CLI tools
│   ├── prep_datasets.py          # Download + normalize SROIE/CORD
│   ├── run_eval.py               # Thin wrapper over src/eval/cli.py
│   ├── run_multimodel_benchmark.py  # Matrix sweep → comparison.{md,csv,json}
│   ├── download_edgar.py         # 5-issuer 10-K download from SEC EDGAR      ← v2
│   └── build_filings_gt.py       # XBRL companyfacts → ground truth JSONL     ← v2
├── tests/
│   └── unit/                     # 126 tests, no OpenAI key required
│       ├── test_schemas.py       # Invoice/Receipt schema
│       ├── test_filing_schema.py # Filing schema — 20 tests                    ← v2
│       ├── test_section_chunker.py # Section chunker — 10 tests                ← v2
│       ├── test_extractor.py     # DocumentExtractor with FakeClient
│       ├── test_eval.py          # Flatten, comparators, metrics
│       ├── test_data_prep.py     # SROIE + CORD normalizers
│       └── test_api.py           # FastAPI TestClient + dependency override
├── data/
│   ├── samples/                  # Committed 10 hand-crafted samples
│   └── raw/10k/                  # Downloaded 10-Ks (gitignored by default)   ← v2
├── evaluation/
│   ├── smoke_sroie_sample.jsonl  # 5 receipts (SROIE, live eval)
│   ├── smoke_cord_sample.jsonl   # 5 receipts (CORD, live eval)
│   ├── smoke_filings_sample.jsonl # 5 10-Ks (live eval)                        ← v2
│   ├── reports/<timestamp>/      # Per-run reports
│   └── benchmarks/<timestamp>/   # Multi-model comparison rollups
├── docker/
│   ├── api.Dockerfile            # Two-container local dev
│   ├── ui.Dockerfile             # Two-container local dev
│   ├── nginx.conf                # Two-container proxy config
│   ├── nginx.hf.conf             # HF Space single-container config (port 7860)
│   └── hf-entrypoint.sh          # tini + uvicorn + nginx orchestration
├── Dockerfile                    # Single-container HF build (3-stage)
├── docker-compose.yml            # Two-container local dev
├── .github/workflows/ci.yml      # 3 parallel jobs
├── requirements.txt              # Python deps
├── pyproject.toml                # ruff + black + pytest config
├── .env.example                  # OPENAI_API_KEY placeholder
├── .gitignore, .gitattributes
├── README.md                     # The narrative + numbers
├── SHIPPING.md                   # Resume bullet + LinkedIn draft
└── LEARN.md                      # This document
```

---

**Read this once. Skim it before any interview. Every design decision has an
answer here — no hand-waving needed.**
