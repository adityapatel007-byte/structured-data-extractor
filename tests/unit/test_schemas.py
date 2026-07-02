"""Sanity tests for the schema layer — verifies validators, defaults, and the registry.

These are pure-Python tests (no LLM calls) so they run in milliseconds.
"""
from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from src.schemas import (
    ExtractionResult,
    FieldConfidence,
    Invoice,
    LineItem,
    Party,
    Receipt,
    ReceiptLineItem,
    get_schema,
    list_doc_types,
)


# --- Invoice ----------------------------------------------------------------


def test_invoice_minimum_required_fields():
    """An invoice needs vendor, invoice_number, total, currency — nothing else."""
    inv = Invoice(
        invoice_number="INV-001",
        vendor=Party(name="Acme Corp"),
        total=100.00,
        currency="USD",
    )
    assert inv.invoice_number == "INV-001"
    assert inv.total == 100.00
    assert inv.currency == "USD"
    assert inv.line_items == []


def test_invoice_rounds_money_to_2_decimals():
    inv = Invoice(
        invoice_number="INV-002",
        vendor=Party(name="Acme"),
        total=99.999,        # should round to 100.00
        subtotal=87.4444,    # should round to 87.44
        currency="usd",      # should normalize to USD
    )
    assert inv.total == 100.00
    assert inv.subtotal == 87.44
    assert inv.currency == "USD"


def test_invoice_rejects_negative_total():
    with pytest.raises(ValidationError):
        Invoice(
            invoice_number="INV-003",
            vendor=Party(name="Acme"),
            total=-10.00,
            currency="USD",
        )


def test_invoice_with_line_items():
    inv = Invoice(
        invoice_number="INV-004",
        vendor=Party(name="Widgets Inc"),
        invoice_date=date(2026, 6, 15),
        line_items=[
            LineItem(description="Widget", quantity=3, unit_price=9.99, total=29.97),
            LineItem(description="Sprocket", quantity=1, unit_price=15.00, total=15.00),
        ],
        subtotal=44.97,
        tax=3.60,
        total=48.57,
        currency="USD",
    )
    assert len(inv.line_items) == 2
    assert inv.line_items[0].total == 29.97


# --- Receipt ----------------------------------------------------------------


def test_receipt_minimum_required_fields():
    r = Receipt(merchant="Corner Coffee", total=4.50, currency="USD")
    assert r.merchant == "Corner Coffee"
    assert r.total == 4.50


def test_receipt_rejects_negative_total():
    with pytest.raises(ValidationError):
        Receipt(merchant="X", total=-1.00, currency="USD")


def test_receipt_with_items_and_tip():
    r = Receipt(
        merchant="Diner",
        transaction_date=date(2026, 6, 20),
        line_items=[
            ReceiptLineItem(description="Burger", quantity=1, total=12.00),
            ReceiptLineItem(description="Fries", quantity=1, total=4.00),
        ],
        subtotal=16.00,
        tax=1.28,
        tip=3.00,
        total=20.28,
        currency="USD",
    )
    assert r.tip == 3.00
    assert len(r.line_items) == 2


# --- Registry ---------------------------------------------------------------


def test_registry_lookup():
    assert get_schema("invoice") is Invoice
    assert get_schema("receipt") is Receipt
    assert get_schema("INVOICE") is Invoice   # case-insensitive


def test_registry_unknown_raises():
    with pytest.raises(KeyError):
        get_schema("bogus")


def test_list_doc_types():
    types = list_doc_types()
    assert "invoice" in types
    assert "receipt" in types


# --- ExtractionResult wrapper ----------------------------------------------


def test_extraction_result_wraps_invoice():
    inv = Invoice(
        invoice_number="INV-999",
        vendor=Party(name="Acme"),
        total=50.00,
        currency="USD",
    )
    result = ExtractionResult[Invoice](
        document_type="invoice",
        data=inv,
        field_confidences=[
            FieldConfidence(field="invoice_number", score=0.99),
            FieldConfidence(field="total", score=0.95),
        ],
        overall_confidence=0.97,
        raw_text_snippet="INVOICE INV-999...",
    )
    assert result.data.invoice_number == "INV-999"
    assert result.overall_confidence == 0.97
    assert len(result.field_confidences) == 2


def test_extraction_result_rejects_bad_confidence():
    inv = Invoice(
        invoice_number="INV-1",
        vendor=Party(name="A"),
        total=1.0,
        currency="USD",
    )
    with pytest.raises(ValidationError):
        ExtractionResult[Invoice](
            document_type="invoice",
            data=inv,
            overall_confidence=1.5,   # > 1.0
        )
