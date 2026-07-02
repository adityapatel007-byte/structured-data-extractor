"""Schema registry — maps document-type strings to Pydantic schemas.

The API endpoint uses this to look up which schema to extract into based on
the `doc_type` argument the caller provides. Adding a new domain (e.g. filings
in v2) is a matter of registering it here.
"""
from __future__ import annotations

from pydantic import BaseModel

from src.schemas.invoice import Invoice
from src.schemas.receipt import Receipt

# Registry: doc_type string -> Pydantic schema class
_REGISTRY: dict[str, type[BaseModel]] = {
    "invoice": Invoice,
    "receipt": Receipt,
    # v2 additions will land here:
    # "sec_10k": Filing10K,
    # "sec_10q": Filing10Q,
}


def get_schema(doc_type: str) -> type[BaseModel]:
    """Look up a schema class by document type. Raises KeyError if unknown."""
    key = doc_type.strip().lower()
    if key not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown doc_type {doc_type!r}. Available: {available}")
    return _REGISTRY[key]


def list_doc_types() -> list[str]:
    """Return all registered document types (used by GET /schemas)."""
    return sorted(_REGISTRY.keys())


def get_json_schema(doc_type: str) -> dict:
    """Return the JSON Schema for a doc type — used by the API and by OpenAI structured outputs."""
    schema_cls = get_schema(doc_type)
    return schema_cls.model_json_schema()
