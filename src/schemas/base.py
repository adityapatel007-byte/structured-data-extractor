"""Base schema types and the ExtractionResult wrapper.

Every extraction returns an ExtractionResult[T] where T is the domain schema
(Invoice, Receipt, or a filing schema in v2). The wrapper carries the extracted
data plus per-field confidence, warnings, and provenance so downstream code
never has to reach into the LLM response directly.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Type variable for the domain schema ---
T = TypeVar("T", bound=BaseModel)


class StrictModel(BaseModel):
    """Base model with strict config — matches OpenAI structured-outputs requirements."""

    model_config = ConfigDict(
        extra="forbid",         # no extra fields (matches OpenAI strict mode)
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class FieldConfidence(StrictModel):
    """Model-reported confidence for a single extracted field."""

    field: str = Field(description="Dotted path to the field, e.g. 'total' or 'line_items[0].price'.")
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Model's self-reported confidence for this field (0.0 = uncertain, 1.0 = certain).",
    )
    reasoning: str | None = Field(
        default=None,
        description="Brief explanation of why confidence is not 1.0 (only present when score < 0.9).",
    )


class ExtractionWarning(StrictModel):
    """A warning surfaced during extraction — non-fatal, human-reviewable."""

    field: str | None = Field(default=None, description="Field the warning applies to, if applicable.")
    message: str = Field(description="Human-readable warning.")
    severity: str = Field(
        default="info",
        description="One of: info, warning, error. 'error' means the field could not be extracted.",
    )

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, v: str) -> str:
        if v not in {"info", "warning", "error"}:
            raise ValueError(f"severity must be info/warning/error, got {v!r}")
        return v


class ExtractionResult(StrictModel, Generic[T]):
    """Wrapper around any extracted domain schema.

    - `data` is the strongly-typed domain object (Invoice, Receipt, etc.)
    - `field_confidences` gives per-field confidence
    - `overall_confidence` is a single 0-1 rollup for quick UI display
    - `warnings` surfaces low-confidence or missing fields to the caller
    - `raw_text_snippet` keeps a slice of the source for debugging / traceability
    """

    document_type: str = Field(description="Identifier of the domain schema used (e.g. 'invoice').")
    data: T = Field(description="The extracted, schema-validated domain object.")
    field_confidences: list[FieldConfidence] = Field(
        default_factory=list,
        description="Per-field confidence scores. Empty list is acceptable but discouraged.",
    )
    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="Rollup confidence across all fields (mean of scores)."
    )
    warnings: list[ExtractionWarning] = Field(
        default_factory=list, description="Non-fatal issues surfaced during extraction."
    )
    raw_text_snippet: str | None = Field(
        default=None,
        max_length=2000,
        description="First 2K chars of source text for debugging. None for pure-image inputs.",
    )
