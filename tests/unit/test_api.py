"""FastAPI endpoint tests using TestClient + dependency_overrides.

No OpenAI key is required — `get_extractor` is overridden with a fake that
returns a hand-built ExtractionResult. This tests the API layer in isolation
from the extractor.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_extractor
from src.api.main import create_app
from src.schemas import ExtractionResult, Receipt
from src.utils.cost_tracker import ExtractionMetrics

# --- Fake extractor --------------------------------------------------------

class _FakeExtractor:
    """Stand-in for DocumentExtractor — no network. Records last call for asserts."""

    def __init__(self):
        self.last_call: dict = {}

    def extract(self, file_bytes, filename, doc_type, *, model_override=None, render_images=True):
        self.last_call = {
            "filename": filename,
            "doc_type": doc_type,
            "size": len(file_bytes),
            "model_override": model_override,
        }
        data = Receipt(merchant="ACME COFFEE", total=4.50, currency="USD")
        result = ExtractionResult(
            document_type=doc_type,
            data=data,
            field_confidences=[],
            overall_confidence=0.95,
            warnings=[],
            raw_text_snippet="ACME COFFEE\nTotal: $4.50",
        )
        metrics = ExtractionMetrics(
            input_tokens=100, output_tokens=50, latency_ms=123.4,
            model=model_override or "gpt-5-nano",
        )
        return result, metrics


@pytest.fixture
def fake_extractor():
    return _FakeExtractor()


@pytest.fixture
def client(fake_extractor):
    app = create_app()
    app.dependency_overrides[get_extractor] = lambda: fake_extractor
    with TestClient(app) as c:
        yield c


# --- Root / health ---------------------------------------------------------

class TestHealth:
    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["service"] == "structured-data-extraction"
        assert "version" in body

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_request_id_header_echoed(self, client):
        r = client.get("/health", headers={"X-Request-ID": "test-rid-123"})
        assert r.headers["X-Request-ID"] == "test-rid-123"

    def test_request_id_generated_when_absent(self, client):
        r = client.get("/health")
        assert r.headers.get("X-Request-ID")


# --- Schemas ---------------------------------------------------------------

class TestSchemas:
    def test_list_schemas(self, client):
        r = client.get("/schemas")
        assert r.status_code == 200
        body = r.json()
        assert "invoice" in body["doc_types"]
        assert "receipt" in body["doc_types"]

    def test_get_receipt_schema(self, client):
        r = client.get("/schemas/receipt")
        assert r.status_code == 200
        schema = r.json()
        assert schema["type"] == "object"
        # Receipt has 'merchant' and 'total' as required-ish leaves
        assert "properties" in schema
        assert "merchant" in schema["properties"]
        assert "total" in schema["properties"]

    def test_unknown_doc_type_returns_400_envelope(self, client):
        r = client.get("/schemas/spaceship_manual")
        assert r.status_code == 400
        env = r.json()
        assert env["error"]["code"] == "unsupported_doc_type"
        assert env["error"]["request_id"]


# --- Extract ---------------------------------------------------------------

class TestExtract:
    def _upload(self, client, *, filename="receipt.png", content=b"\x89PNG\r\n\x1a\n" + b"x" * 128,
                content_type="image/png", doc_type="receipt", model=None):
        files = {"file": (filename, io.BytesIO(content), content_type)}
        data = {"doc_type": doc_type}
        if model is not None:
            data["model"] = model
        return client.post("/extract", files=files, data=data)

    def test_extract_happy_path(self, client, fake_extractor):
        r = self._upload(client)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["result"]["document_type"] == "receipt"
        assert body["result"]["data"]["merchant"] == "ACME COFFEE"
        assert body["result"]["data"]["total"] == 4.5
        assert body["metrics"]["input_tokens"] == 100
        assert body["metrics"]["model"] == "gpt-5-nano"
        # Extractor received what we uploaded
        assert fake_extractor.last_call["doc_type"] == "receipt"
        assert fake_extractor.last_call["filename"] == "receipt.png"

    def test_extract_model_override_flows_through(self, client, fake_extractor):
        r = self._upload(client, model="gpt-5.4")
        assert r.status_code == 200
        assert r.json()["metrics"]["model"] == "gpt-5.4"
        assert fake_extractor.last_call["model_override"] == "gpt-5.4"

    def test_unknown_doc_type_400(self, client):
        r = self._upload(client, doc_type="spaceship_manual")
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "unsupported_doc_type"

    def test_unsupported_extension_415(self, client):
        r = self._upload(client, filename="malware.exe", content=b"MZ" + b"x" * 100,
                         content_type="application/octet-stream")
        assert r.status_code == 415
        assert r.json()["error"]["code"] == "unsupported_media_type"

    def test_missing_file_422(self, client):
        r = client.post("/extract", data={"doc_type": "receipt"})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"

    def test_missing_doc_type_422(self, client):
        files = {"file": ("x.png", io.BytesIO(b"\x89PNG"), "image/png")}
        r = client.post("/extract", files=files)
        assert r.status_code == 422

    def test_empty_file_422(self, client):
        r = self._upload(client, content=b"")
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "empty_document"

    def test_oversized_file_413(self, client, monkeypatch):
        # Shrink the cap so we don't have to actually upload 10MB
        monkeypatch.setattr("src.api.routers.extract.MAX_UPLOAD_BYTES", 32)
        r = self._upload(client, content=b"\x89PNG" + b"x" * 200)
        assert r.status_code == 413
        env = r.json()
        assert env["error"]["code"] == "file_too_large"
        assert env["error"]["details"]["max_bytes"] == 32

    def test_extractor_failure_502(self, client, fake_extractor):
        def _raise(*_a, **_k):
            raise RuntimeError("openai unreachable")

        fake_extractor.extract = _raise
        r = self._upload(client)
        assert r.status_code == 502
        assert r.json()["error"]["code"] == "extraction_failed"


# --- Error envelope shape --------------------------------------------------

class TestErrorEnvelope:
    def test_envelope_has_all_fields(self, client):
        r = client.get("/schemas/nope")
        body = r.json()
        assert set(body.keys()) == {"error"}
        assert set(body["error"].keys()) >= {"code", "message", "request_id", "details"}
