"""Upload the FT dataset + launch an OpenAI fine-tuning job.

Two steps:
    1. `client.files.create(purpose="fine-tune", ...)` for train + val files.
    2. `client.fine_tuning.jobs.create(...)` on the base model.

Prints the job id and a poll command. The user waits ~10-30 min for OpenAI
to train, then uses the resulting model id in `compare_finetune.py`.

Cost planning
-------------
gpt-4o-mini fine-tuning is currently ~$3.00 per 1M training tokens (the
default is 3 epochs). A typical receipt example runs ~600-1000 tokens end
to end, so 100 examples * 800 tokens * 3 epochs = 240K tokens ≈ $0.72 to
train. Inference is ~$0.30/$1.20 per 1M in/out tokens (roughly 2x base
gpt-4o-mini). Real quality gain depends on your data. See the README\'s
"v4 fine-tuning" section for the tradeoff discussion.

Default target model
--------------------
`gpt-4o-mini-2024-07-18` — the workhorse fine-tune target. Widely
supported, cheapest reliable base. Override with `--base-model` for
gpt-4o or (if available in your org) gpt-5-nano. Skip GPT-3.5 — it\'s
being retired.

Usage
-----
    python scripts/launch_finetune.py --train data/ft/sroie_train.jsonl \
                                       --val   data/ft/sroie_val.jsonl \
                                       --suffix receipts-2026
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_openai():
    """Import lazily so `--dry-run` / `--help` don\'t require openai installed."""
    from openai import OpenAI

    from src.utils.config import get_settings
    settings = get_settings()
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY not set. Add it to .env or export it.", file=sys.stderr)
        raise SystemExit(2)
    return OpenAI(api_key=settings.openai_api_key)


def upload(client, path: Path):
    """Upload a file for fine-tuning. Returns the file object."""
    print(f"  uploading {path.name} ({path.stat().st_size:,} bytes) ...", flush=True)
    with path.open("rb") as f:
        return client.files.create(file=f, purpose="fine-tune")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train", required=True, help="Path to <name>_train.jsonl from prep_ft_dataset.py")
    ap.add_argument("--val",   required=True, help="Path to <name>_val.jsonl from prep_ft_dataset.py")
    ap.add_argument("--base-model", default="gpt-4o-mini-2024-07-18",
                    help="Base model to fine-tune. Default: gpt-4o-mini-2024-07-18.")
    ap.add_argument("--suffix", default="receipts",
                    help="Suffix baked into the resulting model id (e.g. ft:gpt-4o-mini:you:receipts:...)")
    ap.add_argument("--n-epochs", type=int, default=None,
                    help="Number of training epochs. Default: OpenAI auto-picks (usually 3).")
    ap.add_argument("--dry-run", action="store_true", help="Print plan + exit — no uploads, no charges.")
    args = ap.parse_args(argv)

    train_path = ROOT / args.train if not Path(args.train).is_absolute() else Path(args.train)
    val_path   = ROOT / args.val   if not Path(args.val).is_absolute()   else Path(args.val)
    for p in (train_path, val_path):
        if not p.exists():
            print(f"ERROR: not found: {p}", file=sys.stderr)
            return 2

    n_train = sum(1 for _ in train_path.open())
    n_val   = sum(1 for _ in val_path.open())

    print("Plan:")
    print(f"  base model:  {args.base_model}")
    print(f"  suffix:      {args.suffix}")
    print(f"  train file:  {train_path.relative_to(ROOT)}  ({n_train} rows)")
    print(f"  val file:    {val_path.relative_to(ROOT)}    ({n_val} rows)")
    print(f"  epochs:      {args.n_epochs or 'auto'}")

    if n_train < 10:
        print(
            f"[!] Only {n_train} training rows. OpenAI requires >= 10 for most base "
            f"models. Consider running `python scripts/prep_datasets.py all` first "
            f"to pull the full SROIE/CORD training splits.",
            file=sys.stderr,
        )
        if not args.dry_run:
            print("Refusing to launch — run with --dry-run if you really want to see the plan.")
            return 2

    if args.dry_run:
        return 0

    client = _load_openai()

    print("\nUploading files ...")
    tr = upload(client, train_path)
    vl = upload(client, val_path)
    print(f"  train file id: {tr.id}")
    print(f"  val   file id: {vl.id}")

    print("\nCreating fine-tuning job ...")
    kwargs = {
        "training_file":   tr.id,
        "validation_file": vl.id,
        "model":           args.base_model,
        "suffix":          args.suffix,
    }
    if args.n_epochs is not None:
        kwargs["hyperparameters"] = {"n_epochs": args.n_epochs}
    job = client.fine_tuning.jobs.create(**kwargs)

    print(f"\n>>> Job created: {job.id}")
    print(f"    Status:      {job.status}")
    print(f"    Base model:  {job.model}")
    print(f"    Suffix:      {args.suffix}")
    print("\nPoll:")
    poll_snippet = (
        f"python -c \"from openai import OpenAI; "
        f"j = OpenAI().fine_tuning.jobs.retrieve(\'{job.id}\'); "
        f"print(j.status, j.fine_tuned_model)\""
    )
    print(f"    {poll_snippet}")
    print("\nOr wait interactively (Ctrl-C to detach):")
    print("    (polling every 30 sec)")

    # Simple polling loop — Ctrl-C exits cleanly.
    try:
        while True:
            time.sleep(30)
            j = client.fine_tuning.jobs.retrieve(job.id)
            ts = time.strftime("%H:%M:%S")
            tt = getattr(j, "trained_tokens", None)
            fm = getattr(j, "fine_tuned_model", None)
            print(f"    [{ts}] status={j.status}  trained_tokens={tt}  model={fm}")
            if j.status in ("succeeded", "failed", "cancelled"):
                print(f"\n>>> Job finished: {j.status}")
                if j.status == "succeeded":
                    print(f">>> Fine-tuned model id: {j.fine_tuned_model}")
                    print("\nNext: python scripts/compare_finetune.py \\")
                    print(f"           --ft-model {j.fine_tuned_model}")
                return 0
    except KeyboardInterrupt:
        print("\n(detached — job continues on OpenAI\'s side. Poll with the command above.)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
