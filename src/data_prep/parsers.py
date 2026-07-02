"""Robust parsers for the messy strings you find in receipt / invoice ground truth.

Public dataset ground truth is dirty: money values arrive as "$12.99", "12,99",
"12.99 USD", or even "1299" (missing decimal). Dates come in "DD/MM/YYYY",
"MM-DD-YY", "20250615", "Jun 15, 2025", etc.

These parsers do best-effort normalization and return None on failure — the
caller decides whether that's an error.
"""
from __future__ import annotations

import re
from datetime import date, datetime

# --- Money ------------------------------------------------------------------

# Strip anything that isn't a digit, decimal point, or minus sign.
# Handles "$12.99", "12,99 USD", "SGD 45.00", "£10", etc.
_MONEY_STRIP_RE = re.compile(r"[^\d.,\-]")


def parse_money(value: str | float | int | None) -> float | None:
    """Parse a monetary string/number to a float. Returns None on failure.

    Handles:
      "$12.99" -> 12.99
      "12,99"  -> 12.99   (European decimal)
      "1,299.50" -> 1299.50
      "1.299,50" -> 1299.50  (EU format with thousands)
      1299     -> 1299.0
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)

    s = _MONEY_STRIP_RE.sub("", str(value)).strip()
    if not s:
        return None

    # Detect European format: last separator is a comma AND (no dot OR dot is a thousands sep)
    last_comma = s.rfind(",")
    last_dot = s.rfind(".")

    try:
        if last_comma > last_dot:
            # European: "1.299,50" — dots are thousands, comma is decimal
            s = s.replace(".", "").replace(",", ".")
        else:
            # US / international: commas are thousands, dot is decimal
            s = s.replace(",", "")
        return round(float(s), 2)
    except ValueError:
        return None


# --- Dates ------------------------------------------------------------------

# Try formats in this order — first match wins. Order matters: put more
# specific (with delimiters) formats before ambiguous ones.
_DATE_FORMATS = (
    "%Y-%m-%d",         # 2026-06-15
    "%Y/%m/%d",
    "%d-%m-%Y",         # 15-06-2026
    "%d/%m/%Y",
    "%m-%d-%Y",         # 06-15-2026
    "%m/%d/%Y",
    "%d-%m-%y",
    "%d/%m/%y",
    "%b %d, %Y",        # Jun 15, 2026
    "%B %d, %Y",        # June 15, 2026
    "%d %b %Y",         # 15 Jun 2026
    "%d %B %Y",         # 15 June 2026
    "%Y%m%d",           # 20260615
)


def parse_date(value: str | date | None) -> date | None:
    """Parse a date string using a family of common formats. None on failure."""
    if value is None:
        return None
    if isinstance(value, date):
        return value

    s = str(value).strip()
    if not s:
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# --- Free-text cleanup ------------------------------------------------------


def clean_text(value: str | None) -> str | None:
    """Collapse whitespace, strip. Returns None if the result is empty."""
    if not value:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None
