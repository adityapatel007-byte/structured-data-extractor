"""Tests for the evaluation harness.

We test each layer independently plus one end-to-end run with a mocked
extractor. No OpenAI calls are made — the runner accepts any callable that
returns (ExtractionResult, ExtractionMetrics), which is what makes this
testable offline.

Layers covered: comparators, flatten, doc-scoring, aggregation, runner, reports.
Version tag v2 (forces bytecode invalidation on mounted filesystems).
"""
from __future__ import annotations

from datetime import date

from src.data_prep.writer import read_jsonl
from src.eval.comparators import (
    compare,
    match_date,
    match_exact,
    match_money,
    match_number,
    match_text,
)
from src.eval.flatten import flatten_model
from src.eval.metrics import aggregate, micro_macro, score_doc
from src.eval.runner import run_eval
from src.schemas import ExtractionResult, Receipt
from src.utils.cost_tracker import ExtractionMetrics

# --- Comparators -----------------------------------------------------------

class TestComparators:
    def test_text_fuzzy_match(self):
        assert match_text("TAN WOON YANN", "Tan Woon Yann")[0]
        assert match_text("TAN WOON YANN SDN BHD", "TAN WOON YANN")[0]
        assert match_text("Starbucks", "McDonalds")[0] is False

    def test_text_null_handling(self):
        assert match_text(None, None) == (True, 1.0)
        assert match_text("x", None)[0] is False
        assert match_text(None, "x")[0] is False

    def test_money_within_tolerance(self):
        # Absolute tolerance: 0.01
        assert match_money(72.00, 72.01)[0] is True
        # Relative tolerance: 0.5% of 1000 = 5.00, so 4.00 delta passes
        assert match_money(1000.00, 1004.00)[0] is True

    def test_money_outside_tolerance(self):
        # Small values where 0.5% rel is tiny and abs 0.01 is exceeded
        assert match_money(1.00, 1.05)[0] is False
        # 100 vs 102 -> abs 2 > 0.01, rel 2% > 0.5%
        assert match_money(100.00, 102.00)[0] is False

    def test_money_null(self):
        assert match_money(None, None)[0] is True
        assert match_money(0.0, None)[0] is False

    def test_number_exact(self):
        assert match_number(3, 3)[0] is True
        assert match_number(3, 3.0000001)[0] is True
        assert match_number(3, 4)[0] is False

    def test_date_iso(self):
        assert match_date(date(2018, 6, 25), "2018-06-25")[0] is True
        assert match_date(date(2018, 6, 25), date(2018, 6, 25))[0] is True
        assert match_date(date(2018, 6, 25), "2018-06-26")[0] is False

    def test_exact_normalizes(self):
        assert match_exact("USD", " usd ")[0] is True
        assert match_exact("USD", "EUR")[0] is False

    def test_dispatch(self):
        assert compare("Hello world", "hello world", "text")[0]
        assert compare(1.00, 1.005, "money")[0]
        assert compare(date(2020, 1, 1), "2020-01-01", "date")[0]
        assert compare("USD", "usd", "exact")[0]
        assert compare(3, 3, "number")[0]


# --- Flattener -------------------------------------------------------------

class TestFlatten:
    def test_receipt_flatten_basic(self):
        r = Receipt(merchant="ACME", total=10.00, currency="USD")
        flat = flatten_model(r, Receipt)
        assert flat["merchant"] == ("ACME", "text")
        assert flat["total"] == (10.00, "money")
        assert flat["currency"] == ("USD", "exact")

    def test_receipt_flatten_nested_address(self):
        r = Receipt(
            merchant="X",
            total=1.0,
            currency="USD",
            merchant_address={"line1": "123 Main St", "city": "NYC"},
        )
        flat = flatten_model(r, Receipt)
        assert flat["merchant_address.line1"][0] == "123 Main St"
        assert flat["merchant_address.city"] == ("NYC", "text")
        assert flat["merchant_address.postal_code"] == (None, "exact")

    def test_flatten_line_items(self):
        r = Receipt(
            merchant="X",
            total=5.0,
            currency="USD",
            line_items=[{"description": "coffee", "quantity": 1, "total": 5.0}],
        )
        flat = flatten_model(r, Receipt)
        assert flat["line_items[]"] == (1, "number")
        assert flat["line_items[0].description"] == ("coffee", "text")
        assert flat["line_items[0].unit_price"] == (None, "money")
        assert flat["line_items[0].total"] == (5.0, "money")

    def test_flatten_dict_and_model_symmetric(self):
        gt = {
            "merchant": "ACME", "total": 10.00, "currency": "USD",
            "merchant_address": None, "merchant_phone": None,
            "transaction_date": None, "transaction_time": None,
            "receipt_number": None, "line_items": [], "subtotal": None,
            "tax": None, "tip": None, "payment_method": None,
        }
        pred = Receipt(merchant="ACME", total=10.00, currency="USD")
        assert set(flatten_model(gt, Receipt)) == set(flatten_model(pred, Receipt))


# --- Doc-level scoring -----------------------------------------------------

class TestScoring:
    def _pair(self, gt, pred):
        return score_doc("doc_1", flatten_model(pred, Receipt), flatten_model(gt, Receipt))

    def test_perfect_match(self):
        r = Receipt(merchant="ACME", total=10.00, currency="USD")
        stat, counts = self._pair(r, r)
        assert stat.exact_match
        for tp, fp, fn, _tn in counts.values():
            assert fp == 0 and fn == 0

    def test_wrong_merchant_is_mismatch(self):
        gt = Receipt(merchant="ACME", total=10.0, currency="USD")
        pred = Receipt(merchant="BETA STORE", total=10.0, currency="USD")
        stat, counts = self._pair(gt, pred)
        assert stat.exact_match is False
        assert counts["merchant"] == (0, 1, 1, 0)
        assert counts["total"] == (1, 0, 0, 0)

    def test_missing_field_is_fn(self):
        gt = Receipt(merchant="ACME", total=10.0, currency="USD", tax=1.0)
        pred = Receipt(merchant="ACME", total=10.0, currency="USD")
        _stat, counts = self._pair(gt, pred)
        assert counts["tax"] == (0, 0, 1, 0)

    def test_hallucinated_field_is_fp(self):
        gt = Receipt(merchant="ACME", total=10.0, currency="USD")
        pred = Receipt(merchant="ACME", total=10.0, currency="USD", tax=1.0)
        _stat, counts = self._pair(gt, pred)
        assert counts["tax"] == (0, 1, 0, 0)


# --- Aggregation -----------------------------------------------------------

class TestAggregation:
    def test_micro_macro_perfect(self):
        counts = [
            {"merchant": (1, 0, 0, 0), "total": (1, 0, 0, 0)},
            {"merchant": (1, 0, 0, 0), "total": (1, 0, 0, 0)},
        ]
        stats = aggregate(counts, {"merchant": "text", "total": "money"})
        summary = micro_macro(stats)
        assert summary["micro_f1"] == 1.0
        assert summary["macro_f1"] == 1.0

    def test_micro_macro_partial(self):
        counts = [
            {"merchant": (1, 0, 0, 0), "total": (1, 0, 0, 0)},
            {"merchant": (0, 1, 1, 0), "total": (1, 0, 0, 0)},
        ]
        stats = aggregate(counts, {"merchant": "text", "total": "money"})
        assert stats["merchant"].precision == 0.5
        assert stats["merchant"].recall == 0.5
        assert stats["merchant"].f1 == 0.5
        assert stats["total"].f1 == 1.0
        assert micro_macro(stats)["macro_f1"] == 0.75

    def test_micro_macro_all_wrong(self):
        counts = [{"merchant": (0, 1, 1, 0)}]
        stats = aggregate(counts, {"merchant": "text"})
        assert micro_macro(stats)["micro_f1"] == 0.0


# --- End-to-end runner -----------------------------------------------------

class TestRunner:
    def _fake_extractor(self, mutator=None):
        def _extract(record):
            gt = record["ground_truth"]
            data = Receipt.model_validate(gt)
            if mutator is not None:
                data = mutator(data)
            return (
                ExtractionResult(
                    document_type="receipt",
                    data=data,
                    field_confidences=[],
                    overall_confidence=1.0,
                    warnings=[],
                ),
                ExtractionMetrics(
                    input_tokens=100, output_tokens=50, latency_ms=250.0, model="fake"
                ),
            )
        return _extract

    def test_perfect_run_on_samples(self):
        records = read_jsonl("data/samples/sroie_sample.jsonl")
        report = run_eval(records, self._fake_extractor(), doc_type="receipt")
        s = report.summary()
        assert s["n_docs"] == len(records)
        assert s["errors"] == 0
        assert s["micro_f1"] == 1.0
        assert s["macro_f1"] == 1.0
        assert s["doc_exact_match"] == 1.0

    def test_run_with_extractor_error(self):
        def broken(_rec):
            raise RuntimeError("api down")

        records = read_jsonl("data/samples/sroie_sample.jsonl")[:2]
        report = run_eval(records, broken, doc_type="receipt")
        assert report.n_errors == len(records)
        assert report.aggregate["micro_f1"] == 0.0

    def test_run_with_wrong_merchant(self):
        def wrong_merchant(r: Receipt) -> Receipt:
            return r.model_copy(update={"merchant": "TOTALLY WRONG NAME"})

        records = read_jsonl("data/samples/sroie_sample.jsonl")
        report = run_eval(
            records, self._fake_extractor(mutator=wrong_merchant), doc_type="receipt"
        )
        assert report.field_stats["merchant"].f1 == 0.0
        assert 0.0 < report.aggregate["micro_f1"] < 1.0
        assert report.doc_exact_match_rate == 0.0


# --- Reports ---------------------------------------------------------------

class TestReports:
    def test_write_reports_creates_all_three(self, tmp_path):
        from src.eval.report import write_reports

        records = [
            {
                "id": "smoke",
                "ground_truth": {
                    "merchant": "ACME", "total": 1.0, "currency": "USD",
                    "merchant_address": None, "merchant_phone": None,
                    "transaction_date": None, "transaction_time": None,
                    "receipt_number": None, "line_items": [], "subtotal": None,
                    "tax": None, "tip": None, "payment_method": None,
                },
            }
        ]

        def extractor(record):
            data = Receipt.model_validate(record["ground_truth"])
            return (
                ExtractionResult(
                    document_type="receipt",
                    data=data,
                    field_confidences=[],
                    overall_confidence=1.0,
                    warnings=[],
                ),
                ExtractionMetrics(
                    input_tokens=1, output_tokens=1, latency_ms=1.0, model="fake"
                ),
            )

        report = run_eval(records, extractor, doc_type="receipt", model_label="fake")
        paths = write_reports(report, tmp_path)

        assert paths["csv"].exists()
        assert paths["json"].exists()
        assert paths["markdown"].exists()
        md = paths["markdown"].read_text()
        assert "Micro F1" in md
        assert "1.0000" in md
