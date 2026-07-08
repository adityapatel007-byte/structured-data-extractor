# Shipping — resume / LinkedIn copy for Project 4

> Everything below is copy-paste ready. Quantified. Honest. No fluff.

---

## One-line resume bullet (tune length to your resume format)

**Preferred (single line, ~35 words):**

> Built a production-grade document-extraction service (invoices, receipts, SEC 10-Ks) — FastAPI + Pydantic + GPT-5 with schema-driven structured outputs, streaming SSE + async batch API, and a fine-tuning experimentation pipeline; 0.94 F1 on receipts at $0.012/doc, benchmarked 3 model tiers, deployed to Hugging Face Spaces.

**Alt (two lines, if you have room):**

> Built a production-grade LLM document-extraction service handling invoices, receipts, and SEC 10-K filings. FastAPI + Pydantic v2 + OpenAI structured outputs; React + R3F frontend; Docker + GitHub Actions CI.
> Benchmarked gpt-5-nano / mini / full on 10 records with a self-consistent P/R/F1 harness — nano is Pareto-optimal (0.896 micro F1, $0.012/doc). 96 tests. [Live demo](https://huggingface.co/spaces/aditya0103/structured-data-extractor) · [Code](https://github.com/adityapatel007-byte/structured-data-extractor).

---

## LinkedIn post (~230 words — the diagnose loop is the hook)

I just shipped a 3-week LLM project I actually want to talk about: an end-to-end
document extraction service (invoices, receipts, SEC 10-K filings → schema-validated
JSON).

The interesting part isn't the "it works" — it's the measurement.

Once the pipeline was live I built a small P/R/F1 evaluation harness. First run
on receipts: **micro F1 0.94, $0.012 per document, 6 seconds latency** on
gpt-5-nano. Solid baseline.

Then I benchmarked gpt-5-nano vs gpt-5-mini vs gpt-5 (full) at the same
reasoning-effort setting. Nano won on micro F1 — the bigger tiers only lead on
macro F1 (rarer fields). **Pareto-optimal at $0.36 total spend.** That's a
number I can defend in a review meeting.

10-Ks were the hard part. First live eval: F1 0.56 — well below receipts. The
per-field breakdown pointed at unit-of-measure ("in millions" → absolute
dollars) as the biggest miss. I wrote a targeted prompt fix with worked
examples, re-ran, watched the numbers.

Result: **revenue F1 doubled (0.25 → 0.50). total_equity went from 0.00 to 0.29.
Aggregate F1 flat — because filing_date regressed.**

That's the story I care about. Not "the model got better." The story is: I have
a harness that tells me exactly which of my hypotheses paid off and which
didn't, so v2.3 gets chosen from data instead of instinct.

**Stack**: FastAPI · Pydantic v2 · OpenAI structured outputs · React · Motion ·
Three.js · Docker · GitHub Actions · Hugging Face Spaces.

Live: [huggingface.co/spaces/aditya0103/structured-data-extractor](https://huggingface.co/spaces/aditya0103/structured-data-extractor)
Code: [github.com/adityapatel007-byte/structured-data-extractor](https://github.com/adityapatel007-byte/structured-data-extractor)

#LLM #MLOps #Python #FastAPI #Hiring

---

## Two-paragraph project blurb (for a portfolio site / cover letter)

**Structured Data Extraction Service.** A production-grade LLM pipeline that
turns unstructured business documents — invoices, receipts, SEC 10-K filings —
into schema-validated JSON with per-field confidence, cost accounting, and a
reproducible evaluation harness. Built on FastAPI + Pydantic v2 + OpenAI
structured outputs; frontend in React + Motion + React Three Fiber ("Paper &
Ink" aesthetic, no generic AI-SaaS look); deployed to Hugging Face Spaces via
a single-container Docker build with a health-check-gated nginx front end.

**Why it's in my portfolio.** The eval harness is the point. On receipts, I
hit **micro F1 0.94 at $0.012/doc**, benchmarked three GPT-5 tiers and found
nano was Pareto-optimal (total spend $0.36 to definitively answer "which model
ships"). On 10-Ks, the first run came back at 0.56 — I diagnosed the failure
modes from the per-field table, made three targeted fixes, and watched some
of them pay off (revenue F1 doubled) and some regress (filing_date). That
iteration loop — hypothesis → intervention → measurement — is the shape of the
work I want to keep doing. 96 unit tests, GitHub Actions CI, section-based
chunking for long documents, and a genuinely usable UI.

---

## Suggested next social/portfolio drop (once v2.3 lands)

If two-pass extract-then-verify ships:

> Update on my document-extraction project — I shipped v2.3, a two-pass verifier
> that reads its own output and re-checks each money field against the source
> "in millions" header. Micro F1 went 0.56 → X.XX with zero new model calls
> per doc (verifier runs in the same completion). Details + code linked below.

Empty for now. Fill in when v2.3 numbers exist.
