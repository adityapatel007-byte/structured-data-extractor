"""Write normalized ground-truth records to JSONL for the eval harness.

Output format (one line per record):
    {"id": "...", "source": "sroie|cord", "ground_truth": {...Receipt JSON...}}

The eval harness reads this back, runs each record through the extractor, and
compares against `ground_truth`.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from src.schemas import Receipt
from src.utils.logging import logger


def write_jsonl(
    records: Iterable[tuple[str, Receipt]],
    output_path: str | Path,
    source: str,
) -> int:
    """Write (id, Receipt) pairs to JSONL. Returns the count written."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w", encoding="utf-8") as f:
        for record_id, receipt in records:
            line = {
                "id": record_id,
                "source": source,
                "ground_truth": receipt.model_dump(mode="json"),
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            count += 1

    logger.info(f"Wrote {count} records to {output_path}")
    return count


def read_jsonl(path: str | Path) -> list[dict]:
    """Read a JSONL ground-truth file. Returns list of record dicts."""
    path = Path(path)
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
