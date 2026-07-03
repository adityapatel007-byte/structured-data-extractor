"""Metrics aggregation: TP/FP/FN counters, precision/recall/F1.

Field-level classification per (doc, field):
    - TP: both non-null AND comparator matches
    - FP: prediction non-null AND (truth is null OR comparator fails)
    - FN: truth non-null AND (prediction is null OR comparator fails)
    - TN: both null                                (NOT counted — trivial)

Note: a "wrong" prediction counts as BOTH FP and FN by convention. This
matches how NER / structured-extraction leaderboards score mismatches
(over-count once as a wrong prediction and once as a missed truth).

At the document level, `exact_match` is True iff every field in the doc is
TP or TN.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.eval.comparators import compare
from src.eval.flatten import FieldMap


@dataclass
class FieldStat:
    """Aggregate stats for one field across all docs."""

    field: str
    field_type: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def support(self) -> int:
        """Number of docs where truth was non-null (denominator for recall)."""
        return self.tp + self.fn

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "field_type": self.field_type,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
            "support": self.support,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class DocStat:
    """Per-document stats."""

    doc_id: str
    fields_correct: int = 0
    fields_total: int = 0
    exact_match: bool = False
    per_field: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    error: str | None = None


def score_doc(
    doc_id: str,
    predicted: FieldMap,
    truth: FieldMap,
) -> tuple[DocStat, dict[str, tuple[int, int, int, int]]]:
    """Score one document. Returns (DocStat, {field -> (tp, fp, fn, tn)})."""
    # Union of paths — every field either side reported.
    all_paths = sorted(set(predicted) | set(truth))
    per_field_counts: dict[str, tuple[int, int, int, int]] = {}
    stat = DocStat(doc_id=doc_id)

    fields_ok = 0
    fields_scored = 0
    exact = True

    for path in all_paths:
        p_val, p_type = predicted.get(path, (None, "exact"))
        t_val, t_type = truth.get(path, (None, "exact"))
        field_type = t_type if path in truth else p_type

        p_null = p_val is None
        t_null = t_val is None

        if p_null and t_null:
            per_field_counts[path] = (0, 0, 0, 1)  # TN — trivial
            continue

        fields_scored += 1
        matched, score = compare(p_val, t_val, field_type)

        if matched and not p_null and not t_null:
            per_field_counts[path] = (1, 0, 0, 0)
            fields_ok += 1
            outcome = "TP"
        elif p_null and not t_null:
            per_field_counts[path] = (0, 0, 1, 0)
            exact = False
            outcome = "FN"
        elif t_null and not p_null:
            per_field_counts[path] = (0, 1, 0, 0)
            exact = False
            outcome = "FP"
        else:
            # both non-null but comparator says no
            per_field_counts[path] = (0, 1, 1, 0)
            exact = False
            outcome = "MISMATCH"

        stat.per_field.append(
            {
                "field": path,
                "field_type": field_type,
                "predicted": _stringify(p_val),
                "truth": _stringify(t_val),
                "outcome": outcome,
                "score": round(score, 3),
            }
        )

    stat.fields_correct = fields_ok
    stat.fields_total = fields_scored
    stat.exact_match = exact and fields_scored > 0
    return stat, per_field_counts


def aggregate(
    per_doc_counts: list[dict[str, tuple[int, int, int, int]]],
    field_types: dict[str, str],
) -> dict[str, FieldStat]:
    """Sum per-doc counts into FieldStat objects keyed by field path."""
    stats: dict[str, FieldStat] = {}
    for doc_counts in per_doc_counts:
        for path, (tp, fp, fn, tn) in doc_counts.items():
            if path not in stats:
                stats[path] = FieldStat(field=path, field_type=field_types.get(path, "exact"))
            s = stats[path]
            s.tp += tp
            s.fp += fp
            s.fn += fn
            s.tn += tn
    return stats


def micro_macro(stats: dict[str, FieldStat]) -> dict[str, float]:
    """Compute micro-F1 (pool all counts) and macro-F1 (mean of per-field F1)."""
    if not stats:
        return {"micro_precision": 0, "micro_recall": 0, "micro_f1": 0, "macro_f1": 0}

    tp = sum(s.tp for s in stats.values())
    fp = sum(s.fp for s in stats.values())
    fn = sum(s.fn for s in stats.values())
    micro_p = tp / (tp + fp) if (tp + fp) else 0.0
    micro_r = tp / (tp + fn) if (tp + fn) else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) else 0.0

    supported = [s for s in stats.values() if s.support > 0]
    macro_f1 = sum(s.f1 for s in supported) / len(supported) if supported else 0.0

    return {
        "micro_precision": round(micro_p, 4),
        "micro_recall": round(micro_r, 4),
        "micro_f1": round(micro_f1, 4),
        "macro_f1": round(macro_f1, 4),
    }


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return str(v)
