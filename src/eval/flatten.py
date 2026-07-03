"""Flatten a Pydantic model (or dict) to a {dotted.path: (value, field_type)} map.

Why:
    Field-level metrics need every leaf field addressable by a stable key. Nested
    models become "vendor.address.city", lists become "line_items[0].description".

Field types drive comparator choice in `comparators.py`:
    - "money"  -> float fields that hold monetary amounts (total, tax, unit_price)
    - "date"   -> datetime.date fields
    - "time"   -> datetime.time fields
    - "number" -> other numeric fields (quantity, tax_rate)
    - "text"   -> free-text string fields (merchant name, description)
    - "exact"  -> short/normalized strings (currency, sku, phone, tax_id)

The type classifier uses Pydantic's field annotations plus a small set of
name-based hints for the money/exact split (both are `float`/`str` at the type
level but need different comparators).
"""
from __future__ import annotations

from datetime import date, time
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

# --- Field-name hints -------------------------------------------------------
# Any float field whose name matches these is treated as MONEY (0.01 tolerance,
# 0.5% relative tolerance). Line-item quantities / tax rates fall through to
# "number" (exact match).
_MONEY_FIELD_NAMES = {
    "total", "subtotal", "tax", "tip", "discount", "shipping",
    "unit_price", "price", "amount",
}

# String fields whose name matches these are compared as EXACT (case/whitespace
# insensitive), not fuzzy text.
_EXACT_STRING_FIELD_NAMES = {
    "currency", "sku", "invoice_number", "purchase_order_number",
    "receipt_number", "tax_id", "postal_code", "country", "phone",
    "merchant_phone", "payment_method",
}


FieldMap = dict[str, tuple[Any, str]]


def _unwrap_optional(annotation: Any) -> Any:
    """Return the non-None type inside Optional[X] / X | None."""
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation


def _classify(field_name: str, annotation: Any) -> str:
    """Pick a comparator bucket for a single leaf field."""
    ann = _unwrap_optional(annotation)

    if ann is date:
        return "date"
    if ann is time:
        return "time"
    if ann is bool:
        return "exact"
    if ann is int:
        return "number"
    if ann is float:
        return "money" if field_name in _MONEY_FIELD_NAMES else "number"
    if ann is str:
        return "exact" if field_name in _EXACT_STRING_FIELD_NAMES else "text"
    # Fallback for enums / unusual types.
    return "exact"


def flatten_model(
    model_or_dict: BaseModel | dict[str, Any] | None,
    schema_cls: type[BaseModel],
    prefix: str = "",
) -> FieldMap:
    """Flatten a Pydantic model instance OR a raw dict against `schema_cls`.

    Ground-truth data comes in as dict (from JSONL); extractor output comes in
    as Pydantic. This function handles both by using `schema_cls` as the shape
    reference and looking up values in whichever form was passed.
    """
    out: FieldMap = {}
    if model_or_dict is None:
        return out

    # Normalize input to a dict-ish accessor.
    def _get(name: str) -> Any:
        if isinstance(model_or_dict, BaseModel):
            return getattr(model_or_dict, name, None)
        return model_or_dict.get(name)

    for field_name, field_info in schema_cls.model_fields.items():
        path = f"{prefix}{field_name}"
        value = _get(field_name)
        annotation = _unwrap_optional(field_info.annotation)
        origin = get_origin(annotation)

        # Case 1: nested Pydantic model
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            out.update(flatten_model(value, annotation, prefix=f"{path}."))
            continue

        # Case 2: list[NestedModel] — flatten each element by index
        if origin is list:
            inner = get_args(annotation)[0]
            inner = _unwrap_optional(inner)
            if isinstance(inner, type) and issubclass(inner, BaseModel):
                items = value or []
                # Record list length under a synthetic key so eval can
                # detect missing/extra items even when both sides are empty.
                out[f"{path}[]"] = (len(items), "number")
                for i, item in enumerate(items):
                    out.update(flatten_model(item, inner, prefix=f"{path}[{i}]."))
                continue
            # list of primitives — treat as one bucket
            out[path] = (value, "exact")
            continue

        # Case 3: leaf field
        out[path] = (value, _classify(field_name, field_info.annotation))

    return out
