"""Dynamically build an envelope schema that wraps a domain schema for extraction.

We can't ask the model to output the full ExtractionResult directly — some of
its fields (`overall_confidence`, `raw_text_snippet`, `document_type`) are
computed by our code, not the model. Instead we ask the model to output an
envelope containing only what IT should produce, then we build the
ExtractionResult around that.

Envelope shape (per domain):
    {
      "data": { ...domain schema... },
      "field_confidences": [ { field, score, reasoning }, ... ],
      "warnings":         [ { field, message, severity }, ... ]
    }
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, create_model

from src.schemas.base import ExtractionWarning, FieldConfidence


@lru_cache(maxsize=32)
def make_envelope(domain_schema_cls: type[BaseModel]) -> type[BaseModel]:
    """Create (and cache) an envelope Pydantic model wrapping the given domain schema.

    The envelope is generated once per domain class and reused. Cache size is
    conservative — we only expect a handful of doc types.
    """
    envelope_name = f"{domain_schema_cls.__name__}Envelope"

    envelope_cls = create_model(
        envelope_name,
        __config__=ConfigDict(extra="forbid"),
        data=(domain_schema_cls, Field(description=f"Extracted {domain_schema_cls.__name__} data.")),
        field_confidences=(
            list[FieldConfidence],
            Field(
                default_factory=list,
                description="Per-field confidence scores. Include at least the required fields.",
            ),
        ),
        warnings=(
            list[ExtractionWarning],
            Field(
                default_factory=list,
                description="Non-fatal issues surfaced during extraction.",
            ),
        ),
    )
    return envelope_cls


def compute_overall_confidence(field_confidences: list[FieldConfidence]) -> float:
    """Roll per-field scores into a single 0-1 score. Mean of scores.

    Returns 0.0 if the list is empty (defensively — model should always return some).
    """
    if not field_confidences:
        return 0.0
    total = sum(fc.score for fc in field_confidences)
    return round(total / len(field_confidences), 3)
