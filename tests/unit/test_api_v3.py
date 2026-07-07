"""Tests for the v3 API surface — POST /extract/stream (SSE) and
POST /extract/batch + GET /extract/batch/{id}.

Same fake-extractor pattern as test_api.py — no OpenAI key needed.
"""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi.testclient import TestClient

from src.api.batch_store import reset_job_store
from src.api.deps import get_extractor
from src.api.main import create_app
from src.schemas import ExtractionResult, Receipt
from src.utils.cost_tracker import ExtractionMetrics

# --- Fakes ---------------------------------------------------------------

class _FakeExtractor:
    """Fake extractor. Sleep hook lets us test progress ordering."""

    def __init__(self, sleep_ms: int = 0, raise_type: type[Exception] | None = None):
        self.sleep_ms = sleep_ms
        self.raise_type = raise_type
        self.calls = 0

    def extract(self, file_bytes, filename, doc_type, *, model_override=None, render_images=True):
        self.calls += 1
        if self.sleep_ms:
            time.sleep(self.sleep_ms / 1000.0)
        if self.raise_type is not None:
            raise self.raise_type("simulated failure")
        data = Receipt(merchant=f"MERCHANT-{filename}", total=1.23, currency="USD")
        result = ExtractionResult(
            document_type=doc_type,
            data=data,
            field_confidences=[],
            overall_confidence=0.9,
            warnings=[],
            raw_text_snippet=None,
        )
        metrics = ExtractionMetrics(
            input_tokens=100, output_tokens=50, latency_ms=10.0,
            model=model_override or "fake-model",
        )
        return result, metrics


def _build_client(fake) -> TestClient:
    reset_job_store()  # fresh in-memory store per test
    app = create_app()
    app.dependency_overrides[get_extractor] = lambda: fake
    return TestClient(app)


def _fake_pdf_bytes() -> bytes:
    # A real-enough PDF header so content-type sniffing accepts it.
    return b"%PDF-1.4\n%fake pdf bytes for tests\n"


# --- SSE parser ----------------------------------------------------------

def _parse_sse(body: bytes) -> list[dict[str, Any]]:
    """Parse a Server-Sent-Events body into a list of {event, data}."""
    events: list[dict[str, Any]] = []
    for block in body.decode("utf-8").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = None
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        payload = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append({"event": event, "data": payload})
    return events


# =========================================================================
# /extract/stream
# =========================================================================

def test_stream_emits_progress_result_and_done_in_order():
    client = _build_client(_FakeExtractor())
    resp = client.post(
        "/extract/stream",
        files={"file": ("r.pdf", _fake_pdf_bytes(), "application/pdf")},
        data={"doc_type": "receipt"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.content)

    names = [e["event"] for e in events]
    assert names[0] == "progress"
    assert names[-1] == "done"
    assert "result" in names
    # Progress must appear at least twice — starting + model_call at minimum.
    assert names.count("progress") >= 2


def test_stream_result_carries_full_extraction_result_and_metrics():
    client = _build_client(_FakeExtractor())
    resp = client.post(
        "/extract/stream",
        files={"file": ("x.pdf", _fake_pdf_bytes(), "application/pdf")},
        data={"doc_type": "receipt"},
    )
    events = _parse_sse(resp.content)
    result_events = [e for e in events if e["event"] == "result"]
    assert len(result_events) == 1
    payload = result_events[0]["data"]
    assert "result" in payload and "metrics" in payload
    assert payload["result"]["data"]["merchant"].startswith("MERCHANT-")
    assert payload["metrics"]["model"] == "fake-model"


def test_stream_rejects_unknown_doc_type_with_400():
    client = _build_client(_FakeExtractor())
    resp = client.post(
        "/extract/stream",
        files={"file": ("r.pdf", _fake_pdf_bytes(), "application/pdf")},
        data={"doc_type": "hieroglyph"},
    )
    # Validation happens *before* the stream opens, so we get a real HTTP status.
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "unsupported_doc_type"


def test_stream_reports_extractor_failure_via_sse_error_event():
    client = _build_client(_FakeExtractor(raise_type=RuntimeError))
    resp = client.post(
        "/extract/stream",
        files={"file": ("r.pdf", _fake_pdf_bytes(), "application/pdf")},
        data={"doc_type": "receipt"},
    )
    # SSE has already started -> 200 OK, error is in-band.
    assert resp.status_code == 200
    events = _parse_sse(resp.content)
    err_events = [e for e in events if e["event"] == "error"]
    assert len(err_events) == 1
    assert err_events[0]["data"]["code"] == "extraction_failed"
    # Even on error, the stream must close with a `done` event.
    assert events[-1]["event"] == "done"


# =========================================================================
# /extract/batch  +  /extract/batch/{id}
# =========================================================================

def test_batch_returns_202_and_job_id():
    client = _build_client(_FakeExtractor())
    resp = client.post(
        "/extract/batch",
        files=[
            ("files", ("a.pdf", _fake_pdf_bytes(), "application/pdf")),
            ("files", ("b.pdf", _fake_pdf_bytes(), "application/pdf")),
            ("files", ("c.pdf", _fake_pdf_bytes(), "application/pdf")),
        ],
        data={"doc_type": "receipt"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["progress"]["total"] == 3


def test_batch_polls_progress_and_reports_done():
    client = _build_client(_FakeExtractor())
    resp = client.post(
        "/extract/batch",
        files=[
            ("files", ("a.pdf", _fake_pdf_bytes(), "application/pdf")),
            ("files", ("b.pdf", _fake_pdf_bytes(), "application/pdf")),
        ],
        data={"doc_type": "receipt"},
    )
    job_id = resp.json()["job_id"]

    # TestClient runs BackgroundTasks synchronously after the response —
    # the follow-up GET should already see the job as done.
    snap = client.get(f"/extract/batch/{job_id}").json()
    assert snap["status"] == "done"
    assert snap["progress"]["done"] == 2
    assert snap["progress"]["errors"] == 0
    assert all(item["status"] == "done" for item in snap["items"])
    # Each item carries a validated result + metrics.
    for item in snap["items"]:
        assert item["result"]["data"]["merchant"].startswith("MERCHANT-")
        assert item["metrics"]["model"] == "fake-model"


def test_batch_records_per_item_errors_without_failing_the_job():
    """If one extractor call raises, the item is marked errored — others must still finish."""
    client = _build_client(_FakeExtractor(raise_type=RuntimeError))
    resp = client.post(
        "/extract/batch",
        files=[
            ("files", ("bad.pdf", _fake_pdf_bytes(), "application/pdf")),
        ],
        data={"doc_type": "receipt"},
    )
    job_id = resp.json()["job_id"]
    snap = client.get(f"/extract/batch/{job_id}").json()
    assert snap["status"] == "done"
    assert snap["progress"]["errors"] == 1
    err_item = snap["items"][0]
    assert err_item["status"] == "error"
    assert "RuntimeError" in err_item["error"]


def test_batch_get_returns_404_for_unknown_job_id():
    client = _build_client(_FakeExtractor())
    resp = client.get("/extract/batch/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "job_not_found"


def test_batch_rejects_unknown_doc_type_up_front():
    client = _build_client(_FakeExtractor())
    resp = client.post(
        "/extract/batch",
        files=[("files", ("a.pdf", _fake_pdf_bytes(), "application/pdf"))],
        data={"doc_type": "napkin"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_doc_type"


def test_batch_rejects_unsupported_extension_with_415():
    client = _build_client(_FakeExtractor())
    resp = client.post(
        "/extract/batch",
        files=[("files", ("resume.docx", b"binary", "application/octet-stream"))],
        data={"doc_type": "receipt"},
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "unsupported_media_type"


def test_batch_snapshot_shape_matches_contract():
    """Guardrail against accidental field drift in the JSON snapshot."""
    client = _build_client(_FakeExtractor())
    resp = client.post(
        "/extract/batch",
        files=[("files", ("a.pdf", _fake_pdf_bytes(), "application/pdf"))],
        data={"doc_type": "receipt", "model": "gpt-5-nano"},
    )
    job_id = resp.json()["job_id"]
    snap = client.get(f"/extract/batch/{job_id}").json()

    # Top-level keys we\'ve documented in LEARN.md / the code.
    for k in ("job_id", "doc_type", "model", "status", "progress", "created_at", "items"):
        assert k in snap, f"missing top-level key {k!r}"
    assert snap["doc_type"] == "receipt"
    assert snap["model"] == "gpt-5-nano"

    # Progress keys.
    for k in ("total", "done", "errors", "pending", "running"):
        assert k in snap["progress"], f"missing progress key {k!r}"

    # Item shape.
    it = snap["items"][0]
    for k in ("index", "filename", "status", "error", "result", "metrics"):
        assert k in it, f"missing item key {k!r}"


def test_batch_stores_model_override_on_the_job():
    client = _build_client(_FakeExtractor())
    resp = client.post(
        "/extract/batch",
        files=[("files", ("a.pdf", _fake_pdf_bytes(), "application/pdf"))],
        data={"doc_type": "receipt", "model": "gpt-5-mini"},
    )
    job_id = resp.json()["job_id"]
    snap = client.get(f"/extract/batch/{job_id}").json()
    assert snap["model"] == "gpt-5-mini"
    assert snap["items"][0]["metrics"]["model"] == "gpt-5-mini"
