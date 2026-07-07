"""In-memory async job store for batch extraction.

Design intent
-------------
Batch extraction submits N documents in one request, returns a job_id
immediately, and lets the caller poll for status. To keep the architecture
simple (no Redis, no RQ, no external state), the job store is an in-process
dict guarded by an asyncio lock. That means:

- Jobs live in the memory of one uvicorn worker. Restart wipes them. That is
  the tradeoff we\'ve accepted at this scale — jobs finish in seconds to
  minutes, and losing an in-flight job to a restart is acceptable for a
  portfolio project. Prod would swap this for Redis without touching the API.
- The concurrency cap is enforced by a single asyncio.Semaphore initialized
  at import time. We deliberately size it small (default 5) to stay well
  under OpenAI\'s per-org rate limits while multiple jobs run in parallel.

Public API
----------
    store   = get_job_store()
    job     = await store.create_job(items)      # returns Job with id + pending status
    await store.mark_running(job_id, index)
    await store.set_result(job_id, index, result_dict)
    await store.set_error(job_id, index, err_str)
    job     = await store.get(job_id)            # snapshot for the GET endpoint
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

# How many extractions run concurrently across all jobs. Small on purpose —
# OpenAI structured-outputs strict mode is billed on tokens, and we already
# saw ~5s latency per call; five in flight is enough parallelism for a
# batch of 100 to finish in ~100s.
BATCH_CONCURRENCY = 5


ItemStatus = Literal["pending", "running", "done", "error"]
JobStatus  = Literal["pending", "running", "done"]


@dataclass
class BatchItem:
    """One document inside a batch job."""
    index:    int
    filename: str
    status:   ItemStatus = "pending"
    result:   dict[str, Any] | None = None
    metrics:  dict[str, Any] | None = None
    error:    str | None = None


@dataclass
class Job:
    """A batch job — a collection of items processed with bounded concurrency."""
    id:         str
    doc_type:   str
    model:      str | None
    items:      list[BatchItem]
    created_at: str
    status:     JobStatus = "pending"

    @property
    def progress(self) -> dict[str, int]:
        return {
            "total":   len(self.items),
            "done":    sum(1 for i in self.items if i.status == "done"),
            "errors":  sum(1 for i in self.items if i.status == "error"),
            "pending": sum(1 for i in self.items if i.status == "pending"),
            "running": sum(1 for i in self.items if i.status == "running"),
        }

    def snapshot(self) -> dict[str, Any]:
        """Serialize the job for the GET endpoint — small, safe, JSON-friendly."""
        return {
            "job_id":    self.id,
            "doc_type":  self.doc_type,
            "model":     self.model,
            "status":    self.status,
            "progress":  self.progress,
            "created_at": self.created_at,
            "items": [
                {
                    "index":    it.index,
                    "filename": it.filename,
                    "status":   it.status,
                    "error":    it.error,
                    "result":   it.result,   # may be None for pending/running
                    "metrics":  it.metrics,
                }
                for it in self.items
            ],
        }


class JobStore:
    """Async-safe in-memory store. One instance per process."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()
        # Bounded concurrency across ALL jobs — OpenAI rate limits are per-org,
        # not per-job. Lazily materialised so the semaphore lives on the correct
        # event loop.
        self._semaphore: asyncio.Semaphore | None = None

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)
        return self._semaphore

    async def create_job(
        self,
        items: list[tuple[str, bytes]],  # (filename, bytes) pairs
        doc_type: str,
        model: str | None,
    ) -> Job:
        job_id = uuid.uuid4().hex[:16]
        items_list = [
            BatchItem(index=i, filename=fn) for i, (fn, _b) in enumerate(items)
        ]
        job = Job(
            id=job_id,
            doc_type=doc_type,
            model=model,
            items=items_list,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        async with self._lock:
            self._jobs[job_id] = job
        return job

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def mark_running(self, job_id: str, index: int) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.items[index].status = "running"
            job.status = "running"

    async def set_result(
        self,
        job_id: str,
        index: int,
        result: dict[str, Any],
        metrics: dict[str, Any],
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            item = job.items[index]
            item.status = "done"
            item.result = result
            item.metrics = metrics
            self._maybe_finalize(job)

    async def set_error(self, job_id: str, index: int, error: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            item = job.items[index]
            item.status = "error"
            item.error = error
            self._maybe_finalize(job)

    def _maybe_finalize(self, job: Job) -> None:
        # Called while holding the lock — flip the job to \"done\" once every item is settled.
        if all(i.status in ("done", "error") for i in job.items):
            job.status = "done"


_STORE: JobStore | None = None


def get_job_store() -> JobStore:
    """Singleton JobStore. Overridden in tests via dependency_overrides."""
    global _STORE
    if _STORE is None:
        _STORE = JobStore()
    return _STORE


def reset_job_store() -> None:
    """Only for tests — drop the singleton so each test gets a fresh store."""
    global _STORE
    _STORE = None
