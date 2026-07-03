"""POST /extract — the main extraction endpoint.

Multipart form:
    file      : uploaded document (required)
    doc_type  : "invoice" | "receipt" (required)
    model     : optional model override (e.g. "gpt-5-nano", "gpt-5.4") for benchmarking

Returns:
    {
      "result": ExtractionResult[T] JSON,
      "metrics": {input_tokens, output_tokens, latency_ms, cost_usd, model}
    }
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.api.deps import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_BYTES,
    get_extractor,
)
from src.api.errors import (
    EmptyDocument,
    ExtractionFailed,
    FileTooLarge,
    UnsupportedDocType,
    UnsupportedFileType,
)
from src.extractors.extractor import DocumentExtractor
from src.schemas.registry import get_schema

router = APIRouter(tags=["extract"])


@router.post("/extract")
async def extract(
    file: UploadFile = File(..., description="PDF or image to extract from."),
    doc_type: str = Form(..., description="One of the registered doc types (see GET /schemas)."),
    model: str | None = Form(None, description="Optional model override (e.g. gpt-5-nano)."),
    extractor: DocumentExtractor = Depends(get_extractor),
) -> dict:
    # --- Validate doc_type
    try:
        get_schema(doc_type)  # raises KeyError if unknown
    except KeyError as e:
        raise UnsupportedDocType(str(e), details={"doc_type": doc_type}) from e

    # --- Validate file extension + content-type
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileType(
            f"Extension {ext!r} is not supported. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            details={"filename": filename, "extension": ext},
        )
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise UnsupportedFileType(
            f"MIME type {file.content_type!r} not accepted for {filename}.",
            details={"content_type": file.content_type},
        )

    # --- Read + size-check
    payload = await file.read()
    if len(payload) == 0:
        raise EmptyDocument("Uploaded file is empty.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise FileTooLarge(
            f"File is {len(payload)} bytes; max allowed is {MAX_UPLOAD_BYTES}.",
            details={"size_bytes": len(payload), "max_bytes": MAX_UPLOAD_BYTES},
        )

    # --- Run extraction
    try:
        result, metrics = extractor.extract(
            payload, filename=filename, doc_type=doc_type, model_override=model
        )
    except ValueError as e:
        # Loader reports "could not load" for unknown/corrupt formats.
        raise EmptyDocument(str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise ExtractionFailed(f"Model extraction failed: {e}") from e

    return {
        "result": result.model_dump(mode="json"),
        "metrics": metrics.to_dict(),
    }
