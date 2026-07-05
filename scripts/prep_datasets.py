"""CLI: download and normalize public receipt datasets into eval-ready JSONL.

Examples:
    # Prep the SROIE test split (fastest way to get real eval data):
    python scripts/prep_datasets.py sroie --split test --output data/processed/sroie_test.jsonl

    # Prep CORD dev split (has rich line items):
    python scripts/prep_datasets.py cord  --split validation --output data/processed/cord_val.jsonl

    # Prep everything at once:
    python scripts/prep_datasets.py all

Once you've run these, the eval harness (Task #5) reads the JSONL directly.

Notes:
- Hugging Face dataset IDs occasionally move. If the default ID fails, override
  with `--dataset-id <new-id>`.
- The first run downloads the dataset to your HF cache (~500 MB for SROIE + CORD).
- No API calls to OpenAI are made here; this is pure data prep.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make src importable when running as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import cord as cord_loader  # noqa: E402
from src.data_prep import sroie as sroie_loader  # noqa: E402
from src.data_prep.writer import write_jsonl  # noqa: E402
from src.utils.logging import logger, setup_logging  # noqa: E402


def prep_sroie(split: str, output: str, dataset_id: str | None, limit: int | None) -> int:
    ds = sroie_loader.load_sroie_split(split=split, dataset_id=dataset_id)
    records = sroie_loader.iter_normalized(ds)
    if limit:
        records = (r for i, r in enumerate(records) if i < limit)
    return write_jsonl(records, output, source="sroie")


def prep_cord(split: str, output: str, dataset_id: str | None, limit: int | None) -> int:
    ds = cord_loader.load_cord_split(split=split, dataset_id=dataset_id)
    records = cord_loader.iter_normalized(ds)
    if limit:
        records = (r for i, r in enumerate(records) if i < limit)
    return write_jsonl(records, output, source="cord")


def _run_all(args) -> None:
    """Run SROIE test + CORD validation into data/processed/."""
    processed = Path("data/processed")
    processed.mkdir(parents=True, exist_ok=True)
    n_sroie = prep_sroie("test", str(processed / "sroie_test.jsonl"), None, args.limit)
    n_cord = prep_cord("validation", str(processed / "cord_val.jsonl"), None, args.limit)
    logger.info(f"Done. SROIE: {n_sroie} records | CORD: {n_cord} records")


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(description="Download + normalize receipt datasets.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Shared args
    def add_common(p):
        p.add_argument("--split", default="test", help="Dataset split (train/validation/test).")
        p.add_argument("--output", required=True, help="Output JSONL path.")
        p.add_argument("--dataset-id", default=None, help="Override HF dataset ID.")
        p.add_argument("--limit", type=int, default=None, help="Max records (for a quick sample).")

    p_sroie = sub.add_parser("sroie", help="Prep SROIE receipts dataset.")
    add_common(p_sroie)

    p_cord = sub.add_parser("cord", help="Prep CORD receipts dataset.")
    add_common(p_cord)

    p_all = sub.add_parser("all", help="Prep both SROIE and CORD default splits.")
    p_all.add_argument("--limit", type=int, default=None)

    args = parser.parse_args()

    if args.cmd == "sroie":
        n = prep_sroie(args.split, args.output, args.dataset_id, args.limit)
        logger.info(f"Wrote {n} SROIE records to {args.output}")
    elif args.cmd == "cord":
        n = prep_cord(args.split, args.output, args.dataset_id, args.limit)
        logger.info(f"Wrote {n} CORD records to {args.output}")
    elif args.cmd == "all":
        _run_all(args)


if __name__ == "__main__":
    main()
