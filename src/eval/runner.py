"""Eval runner: iterate JSONL ground truth, call extractor, score, aggregate.

Design note — extractor is injectable:
    The runner takes any `Callable[[dict], tuple[ExtractionResult, ExtractionMetrics]]`.
    This keeps the runner testable without hitting the OpenAI API: tests pass
    a fake callable that returns pre-baked results. The CLI passes a real
    extractor closure that loads document bytes and calls DocumentExtractor.
"""
from __future__ import annotations

import time as _time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from pydantic import BaseModel

from src.eval.flatten import flatten_model
from src.eval.metrics import DocStat, FieldStat, aggregate, micro_macro, score_doc
from src.schemas import ExtractionResult
from src.schemas.registry import get_schema
from src.utils.cost_tracker import ExtractionMetrics
from src.utils.logging import logger

# --- Types -----------------------------------------------------------------

# (record_dict) -> (ExtractionResult, ExtractionMetrics)
ExtractorFn = Callable[[dict], tuple[ExtractionResult, ExtractionMetrics]]


@dataclass
class EvalReport:
    """Everything you need to write CSV + markdown reports."""

    doc_type: str
    model: str
    n_docs: int
    n_errors: int
    field_stats: dict[str, FieldStat]
    doc_stats: list[DocStat]
    aggregate: dict[str, float]
    doc_exact_match_rate: float
    mean_latency_ms: float
    mean_cost_usd: float
    total_cost_usd: float
    wall_time_s: float

    def summary(self) -> dict[str, Any]:
        """One-line resume-worthy summary."""
        return {
            "model": self.model,
            "doc_type": self.doc_type,
            "n_docs": self.n_docs,
            "errors": self.n_errors,
            "micro_f1": self.aggregate.get("micro_f1", 0.0),
            "macro_f1": self.aggregate.get("macro_f1", 0.0),
            "doc_exact_match": round(self.doc_exact_match_rate, 4),
            "mean_latency_ms": round(self.mean_latency_ms, 1),
            "mean_cost_usd": round(self.mean_cost_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "wall_time_s": round(self.wall_time_s, 2),
        }


def run_eval(
    records: Sequence[dict],
    extractor: ExtractorFn,
    doc_type: str,
    *,
    model_label: str = "unknown",
    limit: int | None = None,
) -> EvalReport:
    """Run the full eval loop.

    - `records`: JSONL rows, each a dict with keys "id" and "ground_truth".
    - `extractor(record)` must return (ExtractionResult, ExtractionMetrics).
    - `doc_type`: "invoice" | "receipt" — selects the schema for flattening.
    - `model_label`: purely for the report header; extractor decides real model.
    - `limit`: cap number of records (handy for quick smoke runs).
    """
    schema_cls: type[BaseModel] = get_schema(doc_type)
    if limit:
        records = list(records)[:limit]

    per_doc_counts: list[dict[str, tuple[int, int, int, int]]] = []
    doc_stats: list[DocStat] = []
    field_types: dict[str, str] = {}
    latencies: list[float] = []
    costs: list[float] = []
    errors = 0

    wall_start = _time.perf_counter()

    for i, rec in enumerate(records):
        doc_id = rec.get("id", f"doc_{i}")
        truth_dict = rec.get("ground_truth", {})
        truth_flat = flatten_model(truth_dict, schema_cls)

        try:
            result, metrics = extractor(rec)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[eval] extractor failed for {doc_id}: {e}")
            errors += 1
            doc_stats.append(DocStat(doc_id=doc_id, error=str(e)))
            # Count every truth field as FN so recall reflects the failure.
            per_doc_counts.append({p: (0, 0, 1, 0) for p, (v, _) in truth_flat.items() if v is not None})
            for p, (_v, t) in truth_flat.items():
                field_types.setdefault(p, t)
            continue

        pred_flat = flatten_model(result.data, schema_cls)
        # Merge type info from both sides (truth wins on conflict).
        for p, (_v, t) in pred_flat.items():
            field_types.setdefault(p, t)
        for p, (_v, t) in truth_flat.items():
            field_types[p] = t

        doc_stat, counts = score_doc(doc_id, pred_flat, truth_flat)
        doc_stat.latency_ms = metrics.latency_ms
        doc_stat.cost_usd = metrics.cost_usd
        doc_stats.append(doc_stat)
        per_doc_counts.append(counts)
        latencies.append(metrics.latency_ms)
        costs.append(metrics.cost_usd)

    wall = _time.perf_counter() - wall_start

    field_stats = aggregate(per_doc_counts, field_types)
    agg = micro_macro(field_stats)

    scored_docs = [d for d in doc_stats if d.error is None]
    exact_rate = (
        sum(1 for d in scored_docs if d.exact_match) / len(scored_docs)
        if scored_docs
        else 0.0
    )

    return EvalReport(
        doc_type=doc_type,
        model=model_label,
        n_docs=len(records),
        n_errors=errors,
        field_stats=field_stats,
        doc_stats=doc_stats,
        aggregate=agg,
        doc_exact_match_rate=exact_rate,
        mean_latency_ms=mean(latencies) if latencies else 0.0,
        mean_cost_usd=mean(costs) if costs else 0.0,
        total_cost_usd=sum(costs),
        wall_time_s=wall,
    )
