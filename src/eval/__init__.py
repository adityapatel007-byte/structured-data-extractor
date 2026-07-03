"""Evaluation harness for structured document extraction.

This package turns the extractor into a measurable system:
- Runs a JSONL ground-truth file through DocumentExtractor
- Compares per-field with type-appropriate comparators (text/money/date/exact)
- Aggregates field-level precision/recall/F1 and document-level exact match
- Emits per-record CSV + resume-worthy markdown summary
- Supports multi-model benchmark runs via --model flag

Public entry points:
    run_eval(records, extractor, doc_type, ...) -> EvalReport
    write_reports(report, out_dir) -> (csv_path, md_path)
"""
from src.eval.runner import EvalReport, run_eval
from src.eval.report import write_reports

__all__ = ["run_eval", "EvalReport", "write_reports"]
