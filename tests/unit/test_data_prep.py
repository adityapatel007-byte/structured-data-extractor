"""Unit tests for parsers, normalizers, and the JSONL writer.

No network calls — tests use synthetic dataset records that mirror the shape
of SROIE and CORD.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.data_prep.cord import normalize_cord_ground_truth
from src.data_prep.parsers import clean_text, parse_date, parse_money
from src.data_prep.sroie import normalize_sroie_record
from src.data_prep.writer import read_jsonl, write_jsonl
from src.schemas import Receipt


# --- Money parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("$12.99", 12.99),
        ("12.99", 12.99),
        (12.999, 13.00),
        ("SGD 45.00", 45.00),
        ("1,299.50", 1299.50),
        ("1.299,50", 1299.50),      # EU thousands + comma decimal
        ("12,99", 12.99),           # EU decimal
        ("£10", 10.00),
        (None, None),
        ("", None),
        ("total:", None),
        ("abc", None),
        (1299, 1299.00),
    ],
)
def test_parse_money(raw, expected):
    assert parse_money(raw) == expected


# --- Date parsing ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-06-15", date(2026, 6, 15)),
        ("15/06/2026", date(2026, 6, 15)),
        ("06-15-2026", date(2026, 6, 15)),
        ("Jun 15, 2026", date(2026, 6, 15)),
        ("15 June 2026", date(2026, 6, 15)),
        ("20260615", date(2026, 6, 15)),
        (None, None),
        ("", None),
        ("nonsense", None),
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


def test_clean_text_collapses_whitespace():
    assert clean_text("  hello   world\n\t") == "hello world"
    assert clean_text("") is None
    assert clean_text(None) is None


# --- SROIE normalization ---------------------------------------------------


def test_normalize_sroie_flat_shape():
    """SROIE flat-format record → Receipt."""
    rec = {
        "company": "TAN WOON YANN",
        "address": "789 KING STREET, TAMAN DAYA, 81100 JOHOR BAHRU",
        "date": "25/06/2018",
        "total": "$72.00",
    }
    receipt = normalize_sroie_record(rec)
    assert receipt is not None
    assert receipt.merchant == "TAN WOON YANN"
    assert receipt.total == 72.00
    assert receipt.transaction_date == date(2018, 6, 25)
    assert receipt.currency == "SGD"


def test_normalize_sroie_nested_shape():
    """SROIE with parsed_data wrapper (mychen76 dataset variant)."""
    rec = {
        "id": "X001",
        "image": None,
        "parsed_data": {
            "company": "AEON CO",
            "date": "2018-11-30",
            "address": "AEON MALURI",
            "total": "39.20",
        },
    }
    receipt = normalize_sroie_record(rec)
    assert receipt is not None
    assert receipt.merchant == "AEON CO"
    assert receipt.total == 39.20


def test_normalize_sroie_missing_total_returns_none():
    rec = {"company": "Some Shop", "date": "2020-01-01", "address": "X"}
    assert normalize_sroie_record(rec) is None


def test_normalize_sroie_missing_merchant_returns_none():
    rec = {"date": "2020-01-01", "total": "10.00"}
    assert normalize_sroie_record(rec) is None


# --- CORD normalization ----------------------------------------------------


def test_normalize_cord_with_menu_and_totals():
    gt = {
        "menu": [
            {"nm": "Iced Americano", "cnt": "1", "price": "4500", "unitprice": "4500"},
            {"nm": "Muffin", "cnt": "2", "price": "6000", "unitprice": "3000"},
        ],
        "sub_total": {"subtotal_price": "10500", "tax_price": "1050"},
        "total": {"total_price": "11550"},
    }
    receipt = normalize_cord_ground_truth(gt)
    assert receipt is not None
    assert receipt.total == 11550.00
    assert receipt.subtotal == 10500.00
    assert receipt.tax == 1050.00
    assert len(receipt.line_items) == 2
    assert receipt.line_items[0].description == "Iced Americano"
    assert receipt.line_items[1].quantity == 2.0
    assert receipt.currency == "KRW"


def test_normalize_cord_missing_total_returns_none():
    gt = {"menu": [{"nm": "X", "cnt": "1", "price": "1000"}], "sub_total": {}, "total": {}}
    assert normalize_cord_ground_truth(gt) is None


def test_normalize_cord_wrapped_in_gt_parse():
    """CORD often ships ground truth under a `gt_parse` key."""
    gt = {
        "gt_parse": {
            "menu": [{"nm": "Coffee", "cnt": "1", "price": "3000"}],
            "sub_total": {"subtotal_price": "3000"},
            "total": {"total_price": "3300"},
        }
    }
    receipt = normalize_cord_ground_truth(gt)
    assert receipt is not None
    assert receipt.total == 3300.00


# --- JSONL round-trip ------------------------------------------------------


def test_jsonl_write_and_read(tmp_path: Path):
    r1 = Receipt(merchant="A", total=1.00, currency="USD")
    r2 = Receipt(merchant="B", total=2.00, currency="USD")
    out = tmp_path / "sample.jsonl"

    n = write_jsonl([("id1", r1), ("id2", r2)], out, source="test")
    assert n == 2

    records = read_jsonl(out)
    assert len(records) == 2
    assert records[0]["id"] == "id1"
    assert records[0]["source"] == "test"
    assert records[0]["ground_truth"]["merchant"] == "A"
    assert records[1]["ground_truth"]["total"] == 2.00


# --- Sample data present ---------------------------------------------------


def test_sample_data_exists_and_parses():
    """The committed sample JSONL should always be readable and valid."""
    for name in ("sroie_sample.jsonl", "cord_sample.jsonl"):
        p = Path("data/samples") / name
        assert p.exists(), f"Missing sample dataset: {p}"
        records = read_jsonl(p)
        assert len(records) >= 5, f"{p} should have at least 5 samples"
        # Every record must round-trip through Receipt validation.
        for rec in records:
            Receipt.model_validate(rec["ground_truth"])
