"""Run the same evaluation across several models + write a comparison table.

Baseline is gpt-5-nano @ minimal effort (already validated on 2026-07-04).
This script sweeps a small matrix of (model, reasoning_effort) combos over
the committed smoke datasets (5 SROIE + 5 CORD receipts) and produces:

    evaluation/benchmarks/<UTC-timestamp>/comparison.json
    evaluation/benchmarks/<UTC-timestamp>/comparison.csv
    evaluation/benchmarks/<UTC-timestamp>/comparison.md

The markdown table drops straight into the README.

Usage
-----
    # Default matrix (gpt-5 nano/mini/full @ minimal)
    python scripts/run_multimodel_benchmark.py

    # Custom matrix: pass any number of MODEL[:effort] specs
    python scripts/run_multimodel_benchmark.py gpt-5-nano:minimal gpt-4o-mini

    # Dry-run to check what would fire without hitting the API
    python scripts/run_multimodel_benchmark.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = [
    ("receipt", ROOT / "evaluation" / "smoke_sroie_sample.jsonl", "sroie"),
    ("receipt", ROOT / "evaluation" / "smoke_cord_sample.jsonl", "cord"),
]

DEFAULT_MATRIX = [
    ("gpt-5-nano", "minimal"),
    ("gpt-5-mini", "minimal"),
    ("gpt-5",      "minimal"),
]


@dataclass
class Combo:
    model: str
    effort: str | None

    @property
    def label(self) -> str:
        return f"{self.model}" + (f"@{self.effort}" if self.effort else "")


def parse_spec(spec: str) -> Combo:
    if ":" in spec:
        m, e = spec.split(":", 1)
        return Combo(model=m.strip(), effort=e.strip() or None)
    return Combo(model=spec.strip(), effort=None)


def run_one_eval(combo: Combo, doc_type: str, dataset: Path, out_dir: Path) -> dict:
    """Fire the eval CLI for one (combo, dataset) and load the JSON summary."""
    cmd = [
        sys.executable, "-m", "src.eval.cli",
        "--dataset", str(dataset),
        "--doc-type", doc_type,
        "--mode", "live",
        "--model", combo.model,
        "--output-dir", str(out_dir),
    ]
    if combo.effort:
        cmd += ["--reasoning-effort", combo.effort]

    print(f"    $ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"eval CLI failed: rc={r.returncode}")

    # Find the summary JSON just written (there's exactly one _summary.json per run).
    matches = sorted(out_dir.glob("*_summary.json"))
    if not matches:
        raise RuntimeError(f"no summary.json in {out_dir}")
    with matches[-1].open() as f:
        return json.load(f)["summary"]


def aggregate(rows: list[dict]) -> dict:
    """Weighted aggregate of per-dataset runs into one row per (model, effort)."""
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
        "wall_time_s":     round(sum(r["wall_time_s"] for r in rows), 2),
    }


def write_markdown(combos: list[Combo], results: dict[str, dict], out: Path) -> Path:
    lines = [
        "# Multi-model benchmark",
        "",
        f"_Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_",
        "",
        "10 receipts (5 SROIE + 5 CORD), synthetic text derived from public ground truth.",
        "All runs use the same prompts, schemas, and post-processing — the only variable is the model.",
        "",
        "| Model | Effort | Micro F1 | Macro F1 | Doc-exact | Latency (ms) | Cost / doc | Total cost |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for c in combos:
        r = results.get(c.label)
        if not r:
            lines.append(f"| `{c.model}` | {c.effort or '—'} | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| `{c.model}` | {c.effort or '—'} | "
            f"{r['micro_f1']:.3f} | {r['macro_f1']:.3f} | {r['doc_exact_match']:.0%} | "
            f"{r['mean_latency_ms']:.0f} | ${r['mean_cost_usd']:.5f} | ${r['total_cost_usd']:.4f} |"
        )
    lines.append("")
    lines.append("_Field-level breakdowns live in each combo's per-run report under `evaluation/reports/`._")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_csv(combos: list[Combo], results: dict[str, dict], out: Path) -> Path:
    fields = ["model", "reasoning_effort", "micro_f1", "macro_f1", "doc_exact_match",
              "mean_latency_ms", "mean_cost_usd", "total_cost_usd", "wall_time_s", "n_docs", "errors"]
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for c in combos:
            r = results.get(c.label, {})
            row = {"model": c.model, "reasoning_effort": c.effort or ""}
            row.update({k: r.get(k, "") for k in fields[2:]})
            w.writerow(row)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("specs", nargs="*", help="Optional model specs (model[:effort]).")
    ap.add_argument("--dry-run", action="store_true", help="Print matrix + exit.")
    args = ap.parse_args(argv)

    combos = [parse_spec(s) for s in args.specs] if args.specs else [Combo(m, e) for m, e in DEFAULT_MATRIX]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bench_root = ROOT / "evaluation" / "benchmarks" / stamp
    bench_root.mkdir(parents=True, exist_ok=True)

    print(f"Benchmark run: {bench_root}")
    print("Matrix:")
    for c in combos:
        print(f"  - {c.label}")
    print(f"Datasets: {len(DATASETS)} ({sum(1 for _ in DATASETS)} runs per model)")
    if args.dry_run:
        return 0

    # Sanity-check: OPENAI_API_KEY must be set (dotenv is loaded by src.utils.config).
    from dotenv import dotenv_values
    env_file = ROOT / ".env"
    if not env_file.exists():
        print("ERROR: .env not found — add OPENAI_API_KEY there or export it.", file=sys.stderr)
        return 2
    if not (dotenv_values(env_file).get("OPENAI_API_KEY") or "").strip():
        print("ERROR: OPENAI_API_KEY missing/blank in .env", file=sys.stderr)
        return 2

    results: dict[str, dict] = {}
    for c in combos:
        print(f"\n=== {c.label} ===")
        per_dataset: list[dict] = []
        for doc_type, dataset, tag in DATASETS:
            run_dir = bench_root / f"{c.model.replace('/', '_')}_{c.effort or 'default'}_{tag}"
            run_dir.mkdir(parents=True, exist_ok=True)
            summary = run_one_eval(c, doc_type, dataset, run_dir)
            per_dataset.append(summary)
            print(f"    [{tag}] micro_f1={summary['micro_f1']:.3f}  "
                  f"cost/doc=${summary['mean_cost_usd']:.5f}  "
                  f"lat={summary['mean_latency_ms']:.0f}ms")
        results[c.label] = aggregate(per_dataset)

    # Emit the three roll-up files.
    (bench_root / "comparison.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(),
         "matrix": [{"model": c.model, "reasoning_effort": c.effort} for c in combos],
         "results": results},
        indent=2))
    write_csv(combos, results, bench_root / "comparison.csv")
    write_markdown(combos, results, bench_root / "comparison.md")

    print(f"\nDone.  Comparison written to {bench_root}/comparison.{{json,csv,md}}")
    print("\n" + (bench_root / "comparison.md").read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
