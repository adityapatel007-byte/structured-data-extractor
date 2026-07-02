"""CORD dataset loader + normalizer.

CORD (Consolidated Receipt Dataset, Naver Clova) has ~1000 receipts with rich
ground truth including line items, subtotal, tax, and total — much richer
than SROIE.

Reference: https://github.com/clovaai/cord
"""
from __future__ import annotations

from typing import Any, Iterator

from src.data_prep.parsers import clean_text, parse_money
from src.schemas import Receipt, ReceiptLineItem
from src.utils.logging import logger

DEFAULT_DATASET_IDS = (
    "naver-clova-ix/cord-v2",
    "katanaml-org/invoices-donut-data-v1",  # occasional CORD mirror
)


def load_cord_split(split: str = "test", dataset_id: str | None = None):
    """Load a CORD split from Hugging Face."""
    from datasets import load_dataset

    ids_to_try = (dataset_id,) if dataset_id else DEFAULT_DATASET_IDS
    last_err: Exception | None = None

    for ds_id in ids_to_try:
        try:
            logger.info(f"Loading CORD split={split!r} from Hugging Face id={ds_id!r}")
            return load_dataset(ds_id, split=split)
        except Exception as e:
            logger.warning(f"Failed to load {ds_id}: {e}")
            last_err = e

    raise RuntimeError(
        f"Could not load any CORD dataset. Last error: {last_err}"
    ) from last_err


def _extract_menu_items(menu: list[dict[str, Any]]) -> list[ReceiptLineItem]:
    """Parse CORD's `menu` list into ReceiptLineItem objects.

    CORD menu items look like:
      {"nm": "product name", "cnt": "1", "price": "5.00", "unitprice": "5.00"}
    """
    items: list[ReceiptLineItem] = []
    for m in menu:
        description = clean_text(m.get("nm"))
        if not description:
            continue
        try:
            qty_raw = m.get("cnt")
            qty = float(qty_raw) if qty_raw not in (None, "") else None
        except (TypeError, ValueError):
            qty = None

        items.append(
            ReceiptLineItem(
                description=description,
                quantity=qty,
                unit_price=parse_money(m.get("unitprice") or m.get("price")),
                total=parse_money(m.get("price")),
            )
        )
    return items


def normalize_cord_ground_truth(gt: dict[str, Any]) -> Receipt | None:
    """Normalize a CORD ground_truth JSON block into our Receipt schema.

    CORD `gt_parse` structure (top-level keys):
      {
        "menu": [ {...}, ... ],
        "sub_total": { "subtotal_price": "...", "tax_price": "...", ... },
        "total": { "total_price": "...", "cashprice": "...", ... }
      }
    """
    # CORD often nests everything under "gt_parse" or similar; unwrap if needed.
    src = gt.get("gt_parse") or gt.get("valid_line") or gt

    menu = src.get("menu")
    if isinstance(menu, dict):
        # Some CORD variants have a single menu dict instead of a list.
        menu = [menu]
    if not isinstance(menu, list):
        menu = []

    line_items = _extract_menu_items(menu)

    sub_total_block = src.get("sub_total") or {}
    total_block = src.get("total") or {}

    subtotal = parse_money(sub_total_block.get("subtotal_price"))
    tax = parse_money(sub_total_block.get("tax_price"))
    total = parse_money(total_block.get("total_price") or total_block.get("cashprice"))

    if total is None:
        logger.debug(f"CORD record missing total; keys={list(src.keys())}")
        return None

    # CORD receipts often don't include merchant name in the structured GT.
    # We fall back to "Unknown merchant" — evaluation still works on the fields
    # that CORD does provide (line items, subtotal, tax, total).
    merchant = clean_text(src.get("merchant") or src.get("nm")) or "Unknown merchant"

    try:
        return Receipt(
            merchant=merchant,
            line_items=line_items,
            subtotal=subtotal,
            tax=tax,
            total=total,
            # CORD is Korean receipts by origin. Use KRW as default.
            currency="KRW",
        )
    except Exception as e:
        logger.warning(f"Failed to build Receipt from CORD record: {e}")
        return None


def iter_normalized(dataset) -> Iterator[tuple[str, Receipt]]:
    """Iterate a HF CORD Dataset, yielding (record_id, Receipt) pairs."""
    import json as _json

    for idx, rec in enumerate(dataset):
        record_id = str(rec.get("id") or f"cord_{idx:05d}")
        # CORD ground truth is usually stored as a JSON string under `ground_truth`.
        gt_raw = rec.get("ground_truth") or rec.get("gt_parse") or rec
        if isinstance(gt_raw, str):
            try:
                gt = _json.loads(gt_raw)
            except _json.JSONDecodeError:
                logger.debug(f"Could not JSON-decode CORD ground_truth for record {record_id}")
                continue
        else:
            gt = gt_raw

        normalized = normalize_cord_ground_truth(gt)
        if normalized is not None:
            yield record_id, normalized
