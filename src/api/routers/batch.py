"""POST /extract/batch, GET /extract/batch/{job_id} — async batch extraction.

Use case
--------
An enterprise integration that wants to submit 100 invoices at once. Instead
of 100 sequential POST /extract calls (~10 minutes wall time), the caller
submits one batch request, gets a job_id, and polls for results while the
server processes them with bounded concurrency.

Semantics
---------
- POST /extract/batch is multipart with N files + doc_type + optional model.
  Returns 202 Accepted, {job_id, status: "pending"} — nothing has run yet.
  Actual extraction happens in a background task.
- GET /extract/batch/{job_id} returns the current snapshot: overall status,
  per-item status, and per-item results/errors as they land. Poll every 1-3s.
- Concurrency is capped globally at BATCH_CONCURRENCY (5) via an asyncio
  semaphore — sized to stay well under OpenAI rate limits even if multiple
  jobs run simultaneously.

Not implemented (deliberate)
----------------------------
- No persistent storage (Redis/DB). Jobs live in-process; restart wipes them.
- No auth, no per-user quotas.
- No webhook completion callbacks (the caller polls). Streaming completion
  updates would be the natural next step — but SSE for job progress is
  covered by the /extract/stream endpoint for the single-doc case.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from src.api.batch_store import JobStore, get_job_store
from src.api.deps import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_BYTES,
    get_extractor,
)
from src.api.errors import (
    FileTooLarge,
    UnsupportedDocType,
    UnsupportedFileType,
)
from src.extractors.extractor import DocumentExtractor
from src.schemas.registry import get_schema
from src.utils.logging import logger

router = APIRouter(prefix="/extract", tags=["extract-batch"])


# --- POST /extract/batch --------------------------------------------------

@router.post("/batch", status_code=202)
async def create_batch(
    background: BackgroundTasks,
    files:    list[UploadFile] = File(..., description="List of documents to extract."),
    doc_type: str    = Form(..., description="Registered doc type (invoice|receipt|filing)."),
    model:    str | None = Form(None, description="Optional model override."),
    extractor: DocumentExtractor = Depends(get_extractor),
    store:     JobStore = Depends(get_job_store),
) -> JSONResponse:
    # Reject unknown doc types up front — one 400 for the whole batch.
    try:
        get_schema(doc_type)
    except KeyError as e:
        raise UnsupportedDocType(str(e), details={"doc_type": doc_type}) from e

    if not files:
        # Return an empty done job rather than 400 — the semantics are clear.
        job = await store.create_job([], doc_type=doc_type, model=model)
        return JSONResponse(
            status_code=202,
            content={"job_id": job.id, "status": "done", "progress": job.progress},
        )

    # Read + validate each file *before* enqueueing so a bad file fails fast.
    items: list[tuple[str, bytes]] = []
    for uf in files:
        fn  = uf.filename or "upload"
        ext = Path(fn).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileType(
                f"Extension {ext!r} is not supported for {fn!r}.",
                details={"filename": fn, "extension": ext},
            )
        if uf.content_type and uf.content_type not in ALLOWED_MIME_TYPES:
            raise UnsupportedFileType(
                f"MIME type {uf.content_type!r} not accepted for {fn!r}.",
                details={"content_type": uf.content_type, "filename": fn},
            )
        payload = await uf.read()
        if len(payload) > MAX_UPLOAD_BYTES:
            raise FileTooLarge(
                f"{fn!r} is {len(payload)} bytes; max is {MAX_UPLOAD_BYTES}.",
                details={"filename": fn, "size_bytes": len(payload)},
            )
        items.append((fn, payload))

    job = await store.create_job(items, doc_type=doc_type, model=model)
    logger.info(f"[batch] created job {job.id} with {len(items)} items ({doc_type}, model={model})")

    # Fan out into background tasks. FastAPI runs BackgroundTasks after the
    # response is returned — so the caller gets an immediate 202.
    for i, (fn, payload) in enumerate(items):
        background.add_task(
            _run_item, store, extractor, job.id, i, fn, payload, doc_type, model
        )

    return JSONResponse(
        status_code=202,
        content={
            "job_id":   job.id,
            "status":   job.status,
            "progress": job.progress,
        },
    )


# --- GET /extract/batch/{job_id} -----------------------------------------

@router.get("/batch/{job_id}")
async def get_batch(
    job_id: str,
    store:  JobStore = Depends(get_job_store),
) -> dict:
    job = await store.get(job_id)
    if job is None:
        # 404 as a plain JSON envelope — this happens after a restart wipes memory.
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "job_not_found", "message": f"No job with id {job_id!r}."}},
        )
    return job.snapshot()


# --- Worker --------------------------------------------------------------

async def _run_item(
    store: JobStore,
    extractor: DocumentExtractor,
    job_id: str,
    index: int,
    filename: str,
    payload: bytes,
    doc_type: str,
    model: str | None,
) -> None:
    """Run a single item under the global concurrency semaphore.

    The semaphore caps ALL concurrent extractions across every in-flight job.
    OpenAI rate limits are per-org, so job-scoped limits wouldn\'t protect us.
    """
    async with store.semaphore:
        await store.mark_running(job_id, index)
        try:
            # DocumentExtractor.extract() is sync + CPU/IO-bound (openai SDK is
            # synchronous under .parse). Push it to a thread so the event loop
            # keeps servicing status polls + other batches.
            result, metrics = await asyncio.to_thread(
                extractor.extract,
                payload,
                filename=filename,
                doc_type=doc_type,
                model_override=model,
            )
            await store.set_result(
                job_id, index,
                result=result.model_dump(mode="json"),
                metrics=metrics.to_dict(),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[batch] job={job_id} item={index} failed: {e}")
            await store.set_error(job_id, index, f"{type(e).__name__}: {e}")
