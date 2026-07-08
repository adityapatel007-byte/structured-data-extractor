"""Convert receipt/invoice ground-truth JSONL into OpenAI fine-tuning format.

Purpose
-------
Take one of our smoke datasets (JSONL with `text` + `ground_truth`) and produce
a `.jsonl` in OpenAI\'s chat-completions fine-tuning format:

    {"messages": [
      {"role": "system",    "content": SYSTEM_PROMPT_RECEIPT},
      {"role": "user",      "content": "Extract... <document text>"},
      {"role": "assistant", "content": "<envelope JSON matching ExtractionResult>"}
    ]}

The `system` and `user` blocks match what our production extractor sends, so
the fine-tuned model learns the *exact* input-output pair we\'ll invoke it with.
The `assistant` content is the envelope wrapping the ground-truth data with an
empty `field_confidences` + empty `warnings` list — since ground truth is by
definition confident and warning-free.

Split
-----
Randomized 80/20 train/val split, deterministic per `--seed`.

Usage
-----
    # Quick — use the 5-record smoke set (fine-tuning will only complete if
    # OpenAI relaxes its ~10-example minimum; consider augmenting first).
    python scripts/prep_ft_dataset.py \
        --input evaluation/smoke_sroie_sample.jsonl \
        --doc-type receipt

    # Real — after `python scripts/prep_datasets.py all` has pulled full SROIE:
    python scripts/prep_ft_dataset.py \
        --input data/processed/sroie.jsonl \
        --doc-type receipt \
        --out data/ft/sroie
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _rel(p: Path) -> str:
    try:
        return str(p)
    except ValueError:
        return str(p)
sys.path.insert(0, str(ROOT))

from src.extractors.prompts import get_prompt  # noqa: E402


def _envelope_from_gt(ground_truth: dict) -> dict:
    """Wrap the ground truth in the envelope shape the model must learn to emit."""
    return {
        "data": ground_truth,
        "field_confidences": [],
        "warnings": [],
    }


def _make_user_message(text: str) -> str:
    """Match the exact user-message shape the production extractor sends.

    See `DocumentExtractor._build_messages()` — anything the model saw during
    fine-tuning that doesn\'t match production input will hurt inference-time F1.
    """
    return (
        "Extract the structured data from this document. "
        "The document text follows (and page images may also be attached):\n\n"
        f"---BEGIN DOCUMENT TEXT---\n{text}\n---END DOCUMENT TEXT---"
    )


def build_row(record: dict, system_prompt: str) -> dict:
    """Convert one smoke-dataset row into one fine-tuning row."""
    rec_id = record.get("id") or "unknown"
    text = record.get("text") or ""
    gt   = record.get("ground_truth") or {}
    if not text:
        raise ValueError(f"record {rec_id} has no text field — required for fine-tuning")
    if not gt:
        raise ValueError(f"record {rec_id} has empty ground_truth")

    envelope = _envelope_from_gt(gt)
    return {
        "messages": [
            {"role": "system",    "content": system_prompt},
            {"role": "user",      "content": _make_user_message(text)},
            {"role": "assistant", "content": json.dumps(envelope, separators=(",", ":"))},
        ],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",    required=True, nargs="+", help="One or more input JSONL files — each must have text + ground_truth. Multiple files are concatenated.")
    ap.add_argument("--doc-type", default="receipt", choices=["invoice", "receipt", "filing"])
    ap.add_argument("--out",      default="data/ft/receipt", help="Output prefix (writes _train.jsonl + _val.jsonl).")
    ap.add_argument("--val-frac", type=float, default=0.20, help="Fraction held out for validation.")
    ap.add_argument("--seed",     type=int,   default=42)
    args = ap.parse_args(argv)

    in_paths = [Path(p) for p in args.input]
    for ip in in_paths:
        if not ip.exists():
            print(f"ERROR: input not found: {ip}", file=sys.stderr)
            return 2

    system_prompt = get_prompt(args.doc_type)

    # Load + convert every row across every input file. Skip bad rows loudly.
    rows = []
    for ip in in_paths:
        n_before = len(rows)
        with ip.open() as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    rows.append(build_row(rec, system_prompt))
                except Exception as e:
                    print(f"[!] {ip.name} line {i} skipped: {e}", file=sys.stderr)
        print(f"loaded {len(rows) - n_before} rows from {ip.name}")

    if not rows:
        print("ERROR: no usable rows.", file=sys.stderr)
        return 2

    # Deterministic shuffle + split.
    rng = random.Random(args.seed)
    rng.shuffle(rows)

    if args.val_frac <= 0:
        # No validation split — every row goes to training. OpenAI accepts
        # fine-tune jobs without a val file. Useful for tiny datasets.
        val_rows, train_rows = [], rows
    else:
        n_val = max(1, int(round(len(rows) * args.val_frac)))
        val_rows, train_rows = rows[:n_val], rows[n_val:]

    # Warn early — OpenAI requires >= 10 training examples for most models.
    if len(train_rows) < 10:
        print(
            f"[!] {len(train_rows)} train rows — OpenAI requires >= 10 for fine-tuning. "
            f"Run `python scripts/prep_datasets.py all` to pull real SROIE/CORD first, "
            f"then re-run this against the fuller dataset.",
            file=sys.stderr,
        )

    _o = Path(args.out)
    out_prefix = _o if _o.is_absolute() else ROOT / _o
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    train_path = out_prefix.with_name(out_prefix.name + "_train.jsonl")
    val_path   = out_prefix.with_name(out_prefix.name + "_val.jsonl")

    with train_path.open("w") as f:
        for r in train_rows:
            f.write(json.dumps(r) + "\n")
    if val_rows:
        with val_path.open("w") as f:
            for r in val_rows:
                f.write(json.dumps(r) + "\n")

    print(f"train: {len(train_rows)} rows -> {_rel(train_path)}")
    if val_rows:
        print(f"val:   {len(val_rows)} rows -> {_rel(val_path)}")
    else:
        print("val:   0 rows (skipped — --val-frac was 0)")
    print("\nNext: python scripts/launch_finetune.py \\")
    print(f"           --train {_rel(train_path)} \\")
    if val_rows:
        print(f"           --val   {_rel(val_path)}")
    else:
        print("           --val   \'\'    # omit --val entirely if you like")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
