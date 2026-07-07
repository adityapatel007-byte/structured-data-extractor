"""POST /extract/stream — Server-Sent Events for progress-aware extraction.

Why this shape (progress events, not partial JSON)
--------------------------------------------------
Streaming a strict-mode structured-output response as *partial validated
Pydantic objects* is currently not supported by openai-python. `.parse()`
with `stream=True` yields raw token deltas — you\'d have to run your own
streaming JSON parser (ijson / json-stream) that can tolerate mid-value
boundaries, then re-validate the accumulated object against the envelope
schema. That gets fragile, particularly on nested arrays of line items or
risk factors.

Instead we ship the honest thing: a progress stream. Each server-sent
event carries a JSON payload with a `stage` and a `message`. The UI shows
"loading document", "calling model", "validating schema", and the final
`result` event carries the full validated ExtractionResult. The user gets
the same UX (something is happening, then the answer arrives) without the
JSON-stream headaches.

If OpenAI ships object-level streaming for structured outputs later, we can
extend this endpoint to emit field-level `partial` events on top of the
progress events — the SSE format is fine with both.

Event schema (SSE)
------------------
    event: progress
    data:  {"stage": "loading", "elapsed_ms": 12}

    event: progress
    data:  {"stage": "model_call", "elapsed_ms": 4820}

    event: result
    data:  {"result": <ExtractionResult>, "metrics": <ExtractionMetrics>}

    event: done
    data:  {}

    event: error
    data:  {"code": "extraction_failed", "message": "..."}

Errors mid-stream come back as an SSE `event: error` rather than an HTTP
error code — the HTTP 200 has already been sent by then. Clients that
speak SSE handle this naturally.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from src.api.deps import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_BYTES,
    get_extractor,
)
from src.api.errors import (
    EmptyDocument,
    FileTooLarge,
    UnsupportedDocType,
    UnsupportedFileType,
)
from src.extractors.extractor import DocumentExtractor
from src.schemas.registry import get_schema

router = APIRouter(tags=["extract-stream"])


def _sse(event: str, data: dict) -> bytes:
    """Format one SSE frame — event name + JSON data + terminator blank line."""
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n".encode()


@router.post("/extract/stream")
async def extract_stream(
    file:     UploadFile = File(..., description="PDF or image."),
    doc_type: str        = Form(..., description="invoice|receipt|filing"),
    model:    str | None = Form(None, description="Optional model override."),
    extractor: DocumentExtractor = Depends(get_extractor),
) -> StreamingResponse:
    # --- Validate up front so the HTTP status code carries a real error. ---
    try:
        get_schema(doc_type)
    except KeyError as e:
        raise UnsupportedDocType(str(e), details={"doc_type": doc_type}) from e

    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileType(
            f"Extension {ext!r} not supported. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            details={"filename": filename, "extension": ext},
        )
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise UnsupportedFileType(
            f"MIME type {file.content_type!r} not accepted for {filename!r}.",
            details={"content_type": file.content_type},
        )

    payload = await file.read()
    if not payload:
        raise EmptyDocument("Uploaded file is empty.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise FileTooLarge(
            f"File is {len(payload)} bytes; max allowed is {MAX_UPLOAD_BYTES}.",
            details={"size_bytes": len(payload), "max_bytes": MAX_UPLOAD_BYTES},
        )

    async def event_stream() -> AsyncIterator[bytes]:
        t0 = time.perf_counter()

        def elapsed_ms() -> int:
            return int((time.perf_counter() - t0) * 1000)

        # Emit an immediate "starting" so the client sees the connection open.
        yield _sse("progress", {"stage": "starting", "elapsed_ms": elapsed_ms(),
                                "filename": filename, "doc_type": doc_type})

        # Loader phase — cheap. Emit before running so the UI can render even
        # if loading takes non-trivial time (large multi-page PDFs).
        yield _sse("progress", {"stage": "loading",   "elapsed_ms": elapsed_ms()})
        # Force a tiny sleep so the frame ships before the CPU-bound work starts.
        await asyncio.sleep(0)

        # Model call phase.
        yield _sse("progress", {"stage": "model_call", "elapsed_ms": elapsed_ms()})

        try:
            # The extractor runs synchronously (openai-python .parse is sync);
            # push it off the event loop so we can keep serving SSE frames.
            result, metrics = await asyncio.to_thread(
                extractor.extract,
                payload,
                filename=filename,
                doc_type=doc_type,
                model_override=model,
            )
        except ValueError as e:
            # Loader reports "could not load" for unknown/corrupt formats.
            yield _sse("error", {"code": "empty_document", "message": str(e)})
            yield _sse("done", {})
            return
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {
                "code": "extraction_failed",
                "message": f"{type(e).__name__}: {e}",
            })
            yield _sse("done", {})
            return

        # Emit validation success + full payload.
        yield _sse("progress", {"stage": "validated", "elapsed_ms": elapsed_ms()})
        yield _sse("result", {
            "result":  result.model_dump(mode="json"),
            "metrics": metrics.to_dict(),
        })
        yield _sse("done", {"elapsed_ms": elapsed_ms()})

    # Note: text/event-stream is the SSE content-type. Cache-Control: no-cache
    # is critical — otherwise nginx or a browser cache buffers the whole stream.
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",   # nginx: disable proxy buffering
        },
    )
