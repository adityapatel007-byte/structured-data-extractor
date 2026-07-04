"""Unit tests for the extraction layer.

All OpenAI calls are mocked — these tests run offline in <1s and never spend money.
Real end-to-end tests belong in tests/integration/ and require OPENAI_API_KEY.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.extractors import DocumentExtractor, compute_overall_confidence, make_envelope
from src.extractors.prompts import PROMPTS, get_prompt
from src.schemas import (
    ExtractionResult,
    ExtractionWarning,
    FieldConfidence,
    Invoice,
    Party,
    Receipt,
)

# --- Prompt registry -------------------------------------------------------


def test_prompt_registry_has_expected_types():
    assert "invoice" in PROMPTS
    assert "receipt" in PROMPTS


def test_get_prompt_invoice_mentions_key_rules():
    p = get_prompt("invoice")
    assert "CRITICAL EXTRACTION RULES" in p
    assert "ISO 8601" in p
    assert "ISO 4217" in p
    assert "field_confidences" in p


def test_get_prompt_unknown_raises():
    with pytest.raises(KeyError):
        get_prompt("bogus")


# --- Envelope factory ------------------------------------------------------


def test_make_envelope_invoice_shape():
    env_cls = make_envelope(Invoice)
    fields = env_cls.model_fields
    assert "data" in fields
    assert "field_confidences" in fields
    assert "warnings" in fields
    # Can instantiate
    env = env_cls(
        data=Invoice(
            invoice_number="INV-1",
            vendor=Party(name="Acme"),
            total=10.00,
            currency="USD",
        ),
        field_confidences=[FieldConfidence(field="total", score=0.95)],
    )
    assert env.data.invoice_number == "INV-1"


def test_make_envelope_is_cached():
    """Envelope classes are cached per domain to avoid re-generating on every call."""
    a = make_envelope(Invoice)
    b = make_envelope(Invoice)
    assert a is b


def test_compute_overall_confidence_mean():
    confs = [
        FieldConfidence(field="a", score=1.0),
        FieldConfidence(field="b", score=0.8),
        FieldConfidence(field="c", score=0.6),
    ]
    assert compute_overall_confidence(confs) == 0.8


def test_compute_overall_confidence_empty_is_zero():
    assert compute_overall_confidence([]) == 0.0


# --- Extractor end-to-end (mocked) -----------------------------------------


def _mock_openai_call_returning(envelope_cls, envelope_instance):
    """Build a MagicMock imitating the OpenAI beta.parse response shape."""
    usage = MagicMock(prompt_tokens=800, completion_tokens=200)
    message = MagicMock(parsed=envelope_instance, refusal=None)
    choice = MagicMock(message=message)
    return MagicMock(choices=[choice], usage=usage)


@patch("src.extractors.openai_client.OpenAI")
def test_extractor_invoice_end_to_end_mocked(mock_openai_cls):
    """DocumentExtractor.extract wires loader -> LLM -> ExtractionResult correctly."""
    # Build a fake envelope response the mocked LLM will "return".
    env_cls = make_envelope(Invoice)
    envelope_instance = env_cls(
        data=Invoice(
            invoice_number="INV-42",
            vendor=Party(name="Widgets Ltd"),
            invoice_date=date(2026, 6, 15),
            total=125.50,
            subtotal=115.00,
            tax=10.50,
            currency="USD",
        ),
        field_confidences=[
            FieldConfidence(field="invoice_number", score=0.98),
            FieldConfidence(field="total", score=0.95),
            FieldConfidence(field="vendor.name", score=0.99),
        ],
        warnings=[
            ExtractionWarning(field="customer", message="Customer not present on doc", severity="info")
        ],
    )

    # Wire the OpenAI client mock end-to-end.
    fake_response = _mock_openai_call_returning(env_cls, envelope_instance)
    fake_client = MagicMock()
    fake_client.beta.chat.completions.parse.return_value = fake_response
    mock_openai_cls.return_value = fake_client

    # Feed a tiny fake "PDF" — loader will fail gracefully (source_type=empty).
    # So we patch the loader too, to inject a fake LoadedDocument.
    with patch("src.extractors.extractor.load_document") as mock_load:
        from src.extractors.document_loader import LoadedDocument

        mock_load.return_value = LoadedDocument(
            text="INVOICE INV-42 from Widgets Ltd. Total: $125.50",
            images_b64=[],
            source_type="text_pdf",
            page_count=1,
            filename="invoice.pdf",
        )

        extractor = DocumentExtractor()
        result, metrics = extractor.extract(
            b"%PDF-fake", filename="invoice.pdf", doc_type="invoice"
        )

    # Assertions on the result
    assert isinstance(result, ExtractionResult)
    assert result.document_type == "invoice"
    assert result.data.invoice_number == "INV-42"
    assert result.data.total == 125.50
    assert 0.9 <= result.overall_confidence <= 1.0
    assert len(result.warnings) == 1
    assert result.raw_text_snippet.startswith("INVOICE INV-42")

    # Assertions on metrics
    assert metrics.input_tokens == 800
    assert metrics.output_tokens == 200
    assert metrics.cost_usd > 0


@patch("src.extractors.openai_client.OpenAI")
def test_extractor_receipt_end_to_end_mocked(mock_openai_cls):
    """Same shape check for the receipt schema."""
    env_cls = make_envelope(Receipt)
    envelope_instance = env_cls(
        data=Receipt(
            merchant="Corner Coffee",
            transaction_date=date(2026, 6, 20),
            total=4.75,
            currency="USD",
        ),
        field_confidences=[
            FieldConfidence(field="merchant", score=0.99),
            FieldConfidence(field="total", score=0.97),
        ],
        warnings=[],
    )

    fake_response = _mock_openai_call_returning(env_cls, envelope_instance)
    fake_client = MagicMock()
    fake_client.beta.chat.completions.parse.return_value = fake_response
    mock_openai_cls.return_value = fake_client

    with patch("src.extractors.extractor.load_document") as mock_load:
        from src.extractors.document_loader import LoadedDocument

        mock_load.return_value = LoadedDocument(
            text="Corner Coffee\nTotal: $4.75",
            source_type="text_pdf",
            page_count=1,
            filename="receipt.pdf",
        )

        extractor = DocumentExtractor()
        result, _ = extractor.extract(
            b"%PDF-fake", filename="receipt.pdf", doc_type="receipt"
        )

    assert result.document_type == "receipt"
    assert result.data.merchant == "Corner Coffee"
    assert result.data.total == 4.75


@patch("src.extractors.openai_client.OpenAI")
def test_extractor_rejects_unknown_doc_type(_mock):
    extractor = DocumentExtractor()
    with pytest.raises(KeyError):
        extractor.extract(b"", filename="x.pdf", doc_type="bogus")
