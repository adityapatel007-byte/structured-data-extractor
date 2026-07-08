"""SROIE dataset loader + normalizer.

SROIE (ICDAR 2019 Robust Reading Challenge on Scanned Receipts Information
Extraction) has ~1000 scanned Singapore-region receipts with ground truth for
four fields: company, address, date, total.

Datasets change over time — we default to `darentang/sroie` on Hugging Face,
which mirrors the ICDAR test set. If that ID has moved by the time you run
this, pass `--dataset-id` to override.

Reference: https://rrc.cvc.uab.es/?ch=13
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from src.data_prep.parsers import clean_text, parse_date, parse_money
from src.schemas import Address, Receipt
from src.utils.logging import logger

# Default Hugging Face dataset ID + fallbacks. Updated 2026-07 — override
# via the CLI if it has moved again.
DEFAULT_DATASET_IDS = (
    "darentang/sroie",
    "mychen76/invoices-and-receipts_ocr_v1",
)


def load_sroie_split(split: str = "test", dataset_id: str | None = None):
    """Load a SROIE split from Hugging Face. Requires `datasets` package.

    Returns a HuggingFace Dataset object — iterable of dicts.
    """
    from datasets import load_dataset

    ids_to_try = (dataset_id,) if dataset_id else DEFAULT_DATASET_IDS
    last_err: Exception | None = None

    for ds_id in ids_to_try:
        try:
            logger.info(f"Loading SROIE split={split!r} from Hugging Face id={ds_id!r}")
            return load_dataset(ds_id, split=split)
        except Exception as e:
            logger.warning(f"Failed to load {ds_id}: {e}")
            last_err = e

    raise RuntimeError(
        f"Could not load any SROIE dataset. Last error: {last_err}. "
        f"Try passing --dataset-id explicitly. Check huggingface.co for a working ID."
    ) from last_err


def normalize_sroie_record(record: dict[str, Any]) -> Receipt | None:
    """Convert a raw SROIE record into our Receipt schema.

    Handles both common shapes:
      A) flat: {"company": ..., "date": ..., "address": ..., "total": ...}
      B) nested: {"parsed_data": {"company": ..., ...}}

    Returns None if we can't extract the minimum required fields (merchant + total).
    """
    # Unwrap common nesting patterns. HF datasets sometimes store the annotation
    # as a JSON *string* (parquet doesn\'t love nested dicts), so try to parse
    # string values before treating them as opaque.
    import json as _json
    _raw = record.get("parsed_data") or record.get("ground_truth") or record
    if isinstance(_raw, str):
        try:
            _raw = _json.loads(_raw)
        except Exception:
            return None    # unparseable — skip this record rather than crash
    if not isinstance(_raw, dict):
        return None
    src = _raw

    company = clean_text(src.get("company") or src.get("merchant"))
    address = clean_text(src.get("address"))
    date_str = src.get("date")
    total_str = src.get("total") or src.get("amount")

    if not company:
        logger.debug(f"SROIE record missing company field; skipping. record keys={list(src.keys())}")
        return None

    total = parse_money(total_str)
    if total is None:
        logger.debug(f"SROIE record {company!r} missing parseable total ({total_str!r}); skipping.")
        return None

    try:
        return Receipt(
            merchant=company,
            merchant_address=Address(line1=address) if address else None,
            transaction_date=parse_date(date_str),
            total=total,
            # SROIE is largely Singapore/Malaysia — SGD is the safer default than USD.
            currency="SGD",
        )
    except Exception as e:
        logger.warning(f"Failed to build Receipt from SROIE record {company!r}: {e}")
        return None


def iter_normalized(dataset) -> Iterator[tuple[str, Receipt]]:
    """Iterate a HF Dataset, yielding (record_id, Receipt) pairs.

    Skips records that fail normalization.
    """
    for idx, rec in enumerate(dataset):
        record_id = str(rec.get("id") or rec.get("image_id") or f"sroie_{idx:05d}")
        normalized = normalize_sroie_record(rec)
        if normalized is not None:
            yield record_id, normalized
