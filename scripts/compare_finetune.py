"""Compare a fine-tuned model against the base gpt-5-nano baseline.

Runs the exact same 10-record smoke eval used in `run_multimodel_benchmark.py`
against two models — the production baseline (gpt-5-nano @ minimal) and the
fine-tuned model whose id you pass with `--ft-model`. Produces a side-by-side
comparison table.

The interesting output is not just "which one has higher F1" — it\'s also the
cost delta. Fine-tuned models bill at higher per-token rates than base
(gpt-4o-mini fine-tunes cost ~$0.30/$1.20 per 1M in/out tokens vs. $0.15/$0.60
for base). If the base beats the fine-tune on F1, or ties within the noise
band, the fine-tune isn\'t worth shipping.

Usage
-----
    python scripts/compare_finetune.py --ft-model ft:gpt-4o-mini:aditya-p:receipts:abc123
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATASETS = [
    ("receipt", ROOT / "evaluation" / "smoke_sroie_sample.jsonl", "sroie"),
    ("receipt", ROOT / "evaluation" / "smoke_cord_sample.jsonl",  "cord"),
]


def run_one_eval(model: str, doc_type: str, dataset: Path, out_dir: Path,
                 reasoning_effort: str | None = None) -> dict:
    """Fire the eval CLI once. Returns the summary dict."""
    cmd = [
        sys.executable, "-m", "src.eval.cli",
        "--dataset", str(dataset),
        "--doc-type", doc_type,
        "--mode", "live",
        "--model", model,
        "--output-dir", str(out_dir),
    ]
    if reasoning_effort:
        cmd += ["--reasoning-effort", reasoning_effort]

    cmd_str = " ".join(cmd)
    print(f"    $ {cmd_str}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"eval CLI failed: rc={r.returncode}")

    summary_paths = sorted(out_dir.glob("*_summary.json"))
    if not summary_paths:
        raise RuntimeError(f"no summary.json in {out_dir}")
    with summary_paths[-1].open() as f:
        return json.load(f)["summary"]


def aggregate(rows: list[dict]) -> dict:
    """Weighted aggregate of per-dataset runs into one row."""
    n = sum(r["n_docs"] for r in rows)
    if n == 0:
        return {}
    def w(k): return sum(r[k] * r["n_docs"] for r in rows) / n
    return {
        "n_docs":          n,
        "errors":          sum(r["errors"] for r in rows),
        "micro_f1":        round(w("micro_f1"), 4),
        "macro_f1":        round(w("macro_f1"), 4),
        "doc_exact_match": round(w("doc_exact_match"), 4),
        "mean_latency_ms": round(w("mean_latency_ms"), 0),
        "mean_cost_usd":   round(w("mean_cost_usd"), 6),
        "total_cost_usd":  round(sum(r["total_cost_usd"] for r in rows), 4),
    }


def write_markdown(rows: list[dict], out: Path) -> Path:
    lines = [
        "# Fine-tuning comparison",
        "",
        f"_Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_",
        "",
        "10 receipts (5 SROIE + 5 CORD), same prompts, same schemas, same",
        "eval harness. Only the model changes.",
        "",
        "| Model | Micro F1 | Macro F1 | Doc-exact | Latency | Cost / doc |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        label = r["label"]
        mf1   = r["micro_f1"]
        mac   = r["macro_f1"]
        de    = r["doc_exact_match"]
        lat   = r["mean_latency_ms"]
        cd    = r["mean_cost_usd"]
        lines.append(
            f"| `{label}` | {mf1:.3f} | {mac:.3f} | {de:.0%} | {lat:.0f} ms | ${cd:.5f} |"
        )
    lines.append("")
    lines.append("**Read the numbers:** if the fine-tuned F1 is within noise (a few points)")
    lines.append("of the base and its cost/doc is higher, do NOT ship the fine-tune —")
    lines.append("ongoing cost + schema lock-in isn\'t justified. If F1 is materially")
    lines.append("higher and cost is comparable, the fine-tune is a real win.")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ft-model", required=True,
                    help="Fine-tuned model id, e.g. ft:gpt-4o-mini:you:receipts:abc123")
    ap.add_argument("--base-model", default="gpt-5-nano",
                    help="Baseline model. Default: gpt-5-nano (our production choice).")
    ap.add_argument("--base-effort", default="minimal",
                    help="Reasoning effort for the base model. Default: minimal.")
    args = ap.parse_args(argv)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_root = ROOT / "evaluation" / "finetuning" / stamp
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"Fine-tuning comparison  ({out_root.relative_to(ROOT)})")
    print(f"  base:  {args.base_model} (effort={args.base_effort})")
    print(f"  fine-tune: {args.ft_model}")
    print()

    matrix = [
        (args.base_model, args.base_effort, args.base_model),
        (args.ft_model,   None,             "fine-tuned"),
    ]

    rollup: list[dict] = []
    for model, effort, label in matrix:
        print(f"=== {label}  ({model}) ===")
        per_dataset: list[dict] = []
        for doc_type, dataset, tag in DATASETS:
            run_dir = out_root / f"{label}_{tag}"
            run_dir.mkdir(parents=True, exist_ok=True)
            summary = run_one_eval(model, doc_type, dataset, run_dir, reasoning_effort=effort)
            per_dataset.append(summary)
            mf1 = summary["micro_f1"]
            cd = summary["mean_cost_usd"]
            print(f"    [{tag}] micro_f1={mf1:.3f}  cost/doc=${cd:.5f}")
        agg = aggregate(per_dataset)
        agg["label"] = label
        rollup.append(agg)
        print()

    # Roll-up files.
    (out_root / "comparison.json").write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "base_model":   args.base_model,
            "ft_model":     args.ft_model,
            "rows":         rollup,
        }, indent=2)
    )

    with (out_root / "comparison.csv").open("w", newline="") as f:
        cols = ["label", "micro_f1", "macro_f1", "doc_exact_match",
                "mean_latency_ms", "mean_cost_usd", "total_cost_usd", "n_docs"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rollup:
            w.writerow({c: r.get(c, "") for c in cols})

    write_markdown(rollup, out_root / "comparison.md")

    print(f"Done. Comparison in {out_root.relative_to(ROOT)}/comparison.{{md,csv,json}}")
    print("\n" + (out_root / "comparison.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
