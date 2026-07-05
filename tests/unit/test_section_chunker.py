"""Tests for the 10-K section chunker."""
from __future__ import annotations

import textwrap

import pytest

from src.extractors.section_chunker import chunk_filing


SYNTHETIC_10K = textwrap.dedent("""\
    APPLE INC.
    FORM 10-K
    Annual Report Pursuant to Section 13 or 15(d) of the Securities Exchange Act of 1934

    Common Stock, $0.00001 par value per share
    NASDAQ Global Select Market
    Central Index Key: 0000320193
    State of Incorporation: California

    TABLE OF CONTENTS
    Item 1.  Business ..................... 3
    Item 1A. Risk Factors ................. 12
    Item 7.  MD&A ......................... 34
    Item 8.  Financial Statements ......... 42

    PART I

    Item 1. Business

    Apple Inc. designs, manufactures, and markets smartphones, personal
    computers, tablets, wearables, and accessories.

    Item 1A. Risk Factors

    The company faces intense competition and the following risks could
    materially affect the business.

    Supply chain — heavy dependence on manufacturing in China.
    Foreign exchange — a substantial portion of net sales from non-US markets.

    PART II

    Item 7. Management's Discussion and Analysis of Financial Condition

    Net sales grew 3% year over year, driven by Services growth.

    Item 8. Financial Statements and Supplementary Data

    Revenue: $391,035 million
    Net income: $93,736 million
    Diluted EPS: $6.11
    Cash and cash equivalents: $29,943 million
    Total assets: $364,980 million
""")


def test_finds_the_four_headline_items_in_order():
    c = chunk_filing(SYNTHETIC_10K)
    assert c.item_ids == ["1", "1A", "7", "8"]


def test_toc_entries_deduped_last_wins():
    """A synthetic 10-K has each Item mentioned twice (TOC + real section).
    We keep the LAST occurrence — the real section, not the TOC entry.
    """
    c = chunk_filing(SYNTHETIC_10K)
    # If we'd kept the TOC entry, Item 1A's text would start with '. Risk Factors'
    # from the TOC. Real section starts with actual body.
    body = c.get_text("1A").lstrip()
    assert body.startswith("The company faces intense competition"), body[:80]


def test_cover_captured_before_first_item():
    c = chunk_filing(SYNTHETIC_10K)
    assert "APPLE INC." in c.cover
    assert "Central Index Key: 0000320193" in c.cover
    # The cover ends where the FIRST Item heading starts — so the actual
    # "Item 1. Business" section body must NOT be in it.
    assert "Apple Inc. designs, manufactures" not in c.cover


def test_section_bodies_do_not_leak_into_neighbors():
    c = chunk_filing(SYNTHETIC_10K)
    # Item 1A's chunk should have risk-factor content, not Item 7 MD&A content.
    body_1a = c.get_text("1A")
    assert "Supply chain" in body_1a
    assert "Net sales grew 3%" not in body_1a
    # Item 8's chunk holds financials, not MD&A.
    body_8 = c.get_text("8")
    assert "Revenue: $391,035" in body_8
    assert "Net sales grew 3%" not in body_8


def test_has_and_get_are_case_insensitive():
    c = chunk_filing(SYNTHETIC_10K)
    assert c.has("1a") is True   # lowercase input
    assert c.has("1A") is True
    assert c.get("1a") is not None


def test_missing_item_returns_none():
    c = chunk_filing(SYNTHETIC_10K)
    assert c.get("15") is None
    assert c.get_text("15", default="—") == "—"


def test_empty_input_returns_empty_result():
    c = chunk_filing("")
    assert c.cover == ""
    assert c.sections == []
    c2 = chunk_filing("   \n\n   ")
    assert c2.sections == []


def test_no_headings_returns_single_blob():
    """A plain document with no Item headings shouldn't crash — degrades gracefully."""
    text = "This document does not follow SEC 10-K structure."
    c = chunk_filing(text)
    assert len(c.sections) == 1
    assert c.sections[0].item == "0"
    assert c.sections[0].text == text


def test_variant_heading_punctuation_still_matches():
    # 10-Ks in the wild use "Item 1A -", "Item 1A —", "Item 1A:"
    for sep in [". ", " - ", " — ", ": "]:
        text = f"cover\n\nItem 1A{sep}Risk Factors\n\nThe risks are as follows."
        c = chunk_filing(text)
        assert c.has("1A"), f"failed on separator {sep!r}"


def test_case_variants_in_source_still_match():
    # ITEM 1A. and item 1a. are both valid in real filings.
    for form in ["Item 1A.", "ITEM 1A.", "item 1a."]:
        text = f"cover\n\n{form} Risk Factors\n\nRisks."
        c = chunk_filing(text)
        assert c.has("1A"), f"failed on form {form!r}"
