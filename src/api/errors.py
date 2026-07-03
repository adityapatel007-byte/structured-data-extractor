"""API-facing error envelope and typed exceptions.

Every 4xx / 5xx response from this service returns the same JSON shape:

    {
      "error": {
        "code": "unsupported_doc_type",
        "message": "Human-readable explanation.",
        "request_id": "abc-123",
        "details": {...optional...}
      }
    }

Consistent shape makes clients (Streamlit, curl, external integrations) easier
to write than raw FastAPI HTTPException details.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class APIError(Exception):
    """Base class — subclass rather than raising HTTPException directly."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedDocType(APIError):
    status_code = 400
    code = "unsupported_doc_type"


class UnsupportedFileType(APIError):
    status_code = 415
    code = "unsupported_media_type"


class FileTooLarge(APIError):
    status_code = 413
    code = "file_too_large"


class EmptyDocument(APIError):
    status_code = 422
    code = "empty_document"


class ExtractionFailed(APIError):
    status_code = 502
    code = "extraction_failed"
