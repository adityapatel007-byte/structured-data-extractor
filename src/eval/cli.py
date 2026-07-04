"""CLI entry point for the evaluation harness.

Usage examples:
    # Sanity-check the eval pipeline itself against the committed samples
    # (uses a self-consistent extractor — no OpenAI call, always F1=1.0)
    python -m src.eval.cli --dataset data/samples/sroie_sample.jsonl \\
        --doc-type receipt --mode selfcheck

    # Real evaluation with a live model (each record must provide a file_path
    # or an inline text field for the extractor to consume)
    python -m src.eval.cli --dataset evaluation/ground_truth/sroie.jsonl \\
        --doc-type receipt --mode live --model gpt-5-nano

    # Multi-model benchmark (repeat --mode live with different --model tags)

Outputs land in `evaluation/reports/<timestamp>/<doc_type>_<model>_*.{csv,md,json}`.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from src.data_prep.writer import read_jsonl
from src.eval.report import write_reports
from src.eval.runner import ExtractorFn, run_eval
from src.schemas import ExtractionResult
from src.schemas.registry import get_schema
from src.utils.cost_tracker import ExtractionMetrics
from src.utils.logging import logger

# ---------------------------------------------------------------------------
# Extractor factories: pluggable strategies for how a JSONL record becomes an
# (ExtractionResult, ExtractionMetrics) pair.
# ---------------------------------------------------------------------------

def make_selfcheck_extractor(doc_type: str) -> ExtractorFn:
    """Extractor that returns ground truth verbatim — validates the eval pipeline.

    Guaranteed F1=1.0 doc_exact_match=1.0. Useful for CI + first-time setup.
    """
    schema_cls: type[BaseModel] = get_schema(doc_type)

    def _extract(record: dict) -> tuple[ExtractionResult, ExtractionMetrics]:
        data = schema_cls.model_validate(record["ground_truth"])
        result = ExtractionResult(
            document_type=doc_type,
            data=data,
            field_confidences=[],
            overall_confidence=1.0,
            warnings=[],
            raw_text_snippet=None,
        )
        return result, ExtractionMetrics(input_tokens=0, output_tokens=0, latency_ms=0.0, model="selfcheck")

    return _extract


def make_live_extractor(doc_type: str, model: str | None) -> ExtractorFn:
    """Real extractor. Each record must provide either `file_path` or `text`.

    Deferred import: keeps `--mode selfcheck` runs from requiring OpenAI creds.
    """
    from src.extractors.extractor import DocumentExtractor

    ex = DocumentExtractor(default_model=model)

    def _extract(record: dict) -> tuple[ExtractionResult, ExtractionMetrics]:
        # Prefer an on-disk file if we have one.
        fp = record.get("file_path")
        if fp:
            p = Path(fp)
            if not p.exists():
                raise FileNotFoundError(f"file_path not found for record {record.get('id')}: {fp}")
            file_bytes = p.read_bytes()
            filename = p.name
        elif record.get("text"):
            # Fallback: use inline text as if it were a .txt document.
            file_bytes = record["text"].encode("utf-8")
            filename = f"{record.get('id', 'inline')}.txt"
        else:
            raise ValueError(
                f"Record {record.get('id')!r} has neither 'file_path' nor 'text' — "
                f"live extraction needs one of them."
            )

        return ex.extract(file_bytes, filename, doc_type=doc_type, model_override=model)

    return _extract


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Structured-extraction evaluation harness")
    p.add_argument("--dataset", required=True, help="JSONL ground-truth file.")
    p.add_argument(
        "--doc-type",
        default="receipt",
        choices=["invoice", "receipt"],
        help="Domain schema to evaluate against.",
    )
    p.add_argument(
        "--mode",
        default="selfcheck",
        choices=["selfcheck", "live"],
        help=(
            "selfcheck: mock extractor returns ground truth (validates pipeline). "
            "live: run real DocumentExtractor (needs OPENAI_API_KEY + source docs)."
        ),
    )
    p.add_argument("--model", default=None, help="Model override for live mode (e.g. gpt-5-nano).")
    p.add_argument("--limit", type=int, default=None, help="Cap on records for quick runs.")
    p.add_argument(
        "--output-dir",
        default=None,
        help="Where to write reports. Defaults to evaluation/reports/<UTC-timestamp>/.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"ERROR: dataset not found: {dataset_path}", file=sys.stderr)
        return 2

    records = read_jsonl(dataset_path)
    logger.info(f"Loaded {len(records)} records from {dataset_path}")

    # Pick extractor strategy
    if args.mode == "selfcheck":
        extractor = make_selfcheck_extractor(args.doc_type)
        model_label = "selfcheck"
    else:
        extractor = make_live_extractor(args.doc_type, args.model)
        model_label = args.model or "default"

    report = run_eval(
        records,
        extractor=extractor,
        doc_type=args.doc_type,
        model_label=model_label,
        limit=args.limit,
    )

    # Console summary
    s = report.summary()
    print("\n=== Evaluation summary ===")
    for k, v in s.items():
        print(f"  {k:20s} {v}")

    # Write reports
    out_dir = args.output_dir or f"evaluation/reports/{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
    paths = write_reports(report, out_dir)
    print("\nReports written:")
    for k, p in paths.items():
        print(f"  {k:10s} {p}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
