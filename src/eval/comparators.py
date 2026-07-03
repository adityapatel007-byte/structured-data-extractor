"""Per-field comparators.

Each returns (match: bool, score: float) where `score` is a 0-1 similarity
(useful for debugging + partial-credit later). `match` is the boolean the
metrics aggregator counts as TP.

Design choices:
    - Text: rapidfuzz `token_set_ratio` >= 85. Handles reordered tokens, extra
      whitespace, capitalization. Merchant names on receipts are the classic
      motivator (e.g. "TAN WOON YANN" vs "Tan Woon Yann Sdn Bhd").
    - Money: absolute 0.01 OR relative 0.5% — either passes. Real-world receipts
      have rounding on tax, so 0.5% covers subtotal/tax legitimate drift, and
      0.01 handles the common integer-cent case exactly.
    - Date/time: ISO-format equality. Both sides are already parsed (Pydantic on
      the model side; JSON round-trip on ground truth) so a string == suffices.
    - Exact: case- and whitespace-insensitive string equality. Used for
      currency codes, SKUs, invoice numbers, phones.
    - Number: exact numeric equality with tiny float tolerance.
"""
from __future__ import annotations

from datetime import date, time
from typing import Any

from rapidfuzz import fuzz

# --- Thresholds ------------------------------------------------------------

TEXT_FUZZ_THRESHOLD = 85            # rapidfuzz score out of 100
MONEY_ABS_TOL = 0.01                # $0.01 or 1¢
MONEY_REL_TOL = 0.005               # 0.5%
NUMBER_ABS_TOL = 1e-6


# --- Helpers ---------------------------------------------------------------

def _both_none(a: Any, b: Any) -> bool:
    return a is None and b is None


def _one_none(a: Any, b: Any) -> bool:
    return (a is None) ^ (b is None)


def _norm_str(v: Any) -> str:
    return str(v).strip().lower()


# --- Comparators -----------------------------------------------------------

def match_text(pred: Any, truth: Any) -> tuple[bool, float]:
    """Fuzzy text match — for free-text fields (names, descriptions)."""
    if _both_none(pred, truth):
        return True, 1.0
    if _one_none(pred, truth):
        return False, 0.0
    p, t = _norm_str(pred), _norm_str(truth)
    if not p and not t:
        return True, 1.0
    score = fuzz.token_set_ratio(p, t) / 100.0
    return score >= (TEXT_FUZZ_THRESHOLD / 100.0), score


def match_exact(pred: Any, truth: Any) -> tuple[bool, float]:
    """Case- and whitespace-insensitive equality — for codes/IDs/currency."""
    if _both_none(pred, truth):
        return True, 1.0
    if _one_none(pred, truth):
        return False, 0.0
    return (_norm_str(pred) == _norm_str(truth)), 1.0 if _norm_str(pred) == _norm_str(truth) else 0.0


def match_money(pred: Any, truth: Any) -> tuple[bool, float]:
    """Money: 0.01 absolute OR 0.5% relative tolerance. Either passes."""
    if _both_none(pred, truth):
        return True, 1.0
    if _one_none(pred, truth):
        return False, 0.0
    try:
        p, t = float(pred), float(truth)
    except (TypeError, ValueError):
        return False, 0.0
    diff = abs(p - t)
    ok = diff <= MONEY_ABS_TOL or (t != 0 and (diff / abs(t)) <= MONEY_REL_TOL)
    # score = 1 - normalized error, floored at 0
    denom = max(abs(t), 1.0)
    score = max(0.0, 1.0 - diff / denom)
    return ok, score


def match_number(pred: Any, truth: Any) -> tuple[bool, float]:
    """Numeric equality with tiny float tolerance. For qty, tax_rate, list sizes."""
    if _both_none(pred, truth):
        return True, 1.0
    if _one_none(pred, truth):
        return False, 0.0
    try:
        p, t = float(pred), float(truth)
    except (TypeError, ValueError):
        return False, 0.0
    ok = abs(p - t) <= NUMBER_ABS_TOL
    return ok, 1.0 if ok else 0.0


def match_date(pred: Any, truth: Any) -> tuple[bool, float]:
    """ISO date equality. Accepts date objects or ISO strings on either side."""
    if _both_none(pred, truth):
        return True, 1.0
    if _one_none(pred, truth):
        return False, 0.0
    p = pred.isoformat() if isinstance(pred, date) else str(pred)
    t = truth.isoformat() if isinstance(truth, date) else str(truth)
    ok = p == t
    return ok, 1.0 if ok else 0.0


def match_time(pred: Any, truth: Any) -> tuple[bool, float]:
    """ISO time equality."""
    if _both_none(pred, truth):
        return True, 1.0
    if _one_none(pred, truth):
        return False, 0.0
    p = pred.isoformat() if isinstance(pred, time) else str(pred)
    t = truth.isoformat() if isinstance(truth, time) else str(truth)
    ok = p == t
    return ok, 1.0 if ok else 0.0


# --- Dispatch --------------------------------------------------------------

_DISPATCH = {
    "text": match_text,
    "exact": match_exact,
    "money": match_money,
    "number": match_number,
    "date": match_date,
    "time": match_time,
}


def compare(pred: Any, truth: Any, field_type: str) -> tuple[bool, float]:
    """Dispatch to the right comparator by field type."""
    fn = _DISPATCH.get(field_type, match_exact)
    return fn(pred, truth)
