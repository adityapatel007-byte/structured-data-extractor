"""CSV + markdown reporters for EvalReport."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from src.eval.runner import EvalReport

# --- CSV -------------------------------------------------------------------

def write_per_record_csv(report: EvalReport, out_path: str | Path) -> Path:
    """One row per (doc, field) with predicted, truth, outcome, score."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "doc_id", "field", "field_type", "predicted", "truth",
            "outcome", "score", "latency_ms", "cost_usd",
        ])
        for doc in report.doc_stats:
            if doc.error:
                w.writerow([doc.doc_id, "__error__", "", "", "", "ERROR", 0.0, "", ""])
                continue
            for row in doc.per_field:
                w.writerow([
                    doc.doc_id,
                    row["field"],
                    row["field_type"],
                    row["predicted"],
                    row["truth"],
                    row["outcome"],
                    row["score"],
                    round(doc.latency_ms, 1),
                    round(doc.cost_usd, 6),
                ])
    return out_path


def write_summary_json(report: EvalReport, out_path: str | Path) -> Path:
    """Machine-readable summary — feeds the multi-model benchmark table."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": report.summary(),
        "aggregate": report.aggregate,
        "field_stats": {k: s.to_dict() for k, s in report.field_stats.items()},
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


# --- Markdown --------------------------------------------------------------

def write_markdown_summary(report: EvalReport, out_path: str | Path) -> Path:
    """Resume-worthy markdown: headline metrics + top/bottom field table."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    s = report.summary()
    lines: list[str] = []
    lines.append(f"# Evaluation Report — `{report.doc_type}` on `{report.model}`")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Documents evaluated | {s['n_docs']} |")
    lines.append(f"| Extractor errors    | {s['errors']} |")
    lines.append(f"| **Micro F1**        | **{s['micro_f1']:.4f}** |")
    lines.append(f"| **Macro F1**        | **{s['macro_f1']:.4f}** |")
    lines.append(f"| Doc exact-match rate| {s['doc_exact_match']:.2%} |")
    lines.append(f"| Mean latency        | {s['mean_latency_ms']:.0f} ms |")
    lines.append(f"| Mean cost / doc     | ${s['mean_cost_usd']:.6f} |")
    lines.append(f"| Total cost          | ${s['total_cost_usd']:.4f} |")
    lines.append(f"| Wall time           | {s['wall_time_s']:.2f} s |")
    lines.append("")

    lines.append("## Per-field performance")
    lines.append("")
    lines.append("| Field | Type | Support | Precision | Recall | F1 |")
    lines.append("|---|---|---:|---:|---:|---:|")
    ordered = sorted(
        report.field_stats.values(),
        key=lambda st: (-st.support, -st.f1, st.field),
    )
    for st in ordered:
        if st.support == 0 and st.fp == 0:
            continue  # skip fields never seen
        lines.append(
            f"| `{st.field}` | {st.field_type} | {st.support} | "
            f"{st.precision:.3f} | {st.recall:.3f} | {st.f1:.3f} |"
        )
    lines.append("")

    if report.n_errors:
        lines.append("## Errors")
        lines.append("")
        for d in report.doc_stats:
            if d.error:
                lines.append(f"- `{d.doc_id}`: {d.error}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# --- Convenience -----------------------------------------------------------

def write_reports(report: EvalReport, out_dir: str | Path) -> dict[str, Path]:
    """Write CSV, JSON summary, and markdown into `out_dir`. Returns all paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{report.doc_type}_{report.model.replace('/', '_')}"
    return {
        "csv": write_per_record_csv(report, out_dir / f"{tag}_per_record.csv"),
        "json": write_summary_json(report, out_dir / f"{tag}_summary.json"),
        "markdown": write_markdown_summary(report, out_dir / f"{tag}_summary.md"),
    }
