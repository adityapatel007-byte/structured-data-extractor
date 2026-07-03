"""Schema discovery routes.

GET /schemas               -> list of registered document types
GET /schemas/{doc_type}    -> full JSON Schema for that type

The JSON Schema is what OpenAI's structured outputs uses internally — exposing
it lets clients validate uploads client-side, or auto-generate forms.
"""
from __future__ import annotations

from fastapi import APIRouter

from src.api.errors import UnsupportedDocType
from src.schemas.registry import get_json_schema, list_doc_types

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.get("")
def list_schemas() -> dict:
    """Return all registered document type keys."""
    return {"doc_types": list_doc_types()}


@router.get("/{doc_type}")
def get_schema_json(doc_type: str) -> dict:
    """Return the JSON Schema for one document type."""
    try:
        return get_json_schema(doc_type)
    except KeyError as e:
        raise UnsupportedDocType(str(e), details={"doc_type": doc_type}) from e
