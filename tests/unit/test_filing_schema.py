"""Filing schema tests — pure Python, no OpenAI. Covers the required-field,
validator, currency, and CIK-padding contracts."""
from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from src.schemas import Filing, FilingCover, FilingFinancials, RiskFactor
from src.schemas.registry import get_schema, list_doc_types


def _cover(**overrides) -> FilingCover:
    return FilingCover(company_name="Apple Inc.", **overrides)


def _fin(**overrides) -> FilingFinancials:
    return FilingFinancials(**overrides)


# --- Cover ----------------------------------------------------------------

def test_cover_requires_company_name_only():
    c = FilingCover(company_name="Northwind Software, Inc.")
    assert c.company_name == "Northwind Software, Inc."
    assert c.form_type == "10-K"
    assert c.cik is None
    assert c.ticker is None


def test_cover_ticker_uppercased_and_stripped():
    c = _cover(ticker="aapl")
    assert c.ticker == "AAPL"
    c2 = _cover(ticker="  msft  ")
    assert c2.ticker == "MSFT"


def test_cover_ticker_blank_becomes_none():
    c = _cover(ticker="   ")
    assert c.ticker is None


def test_cik_gets_zero_padded_from_str_int():
    assert _cover(cik="320193").cik == "0000320193"
    assert _cover(cik=320193).cik == "0000320193"
    # A CIK already at 10 digits stays the same.
    assert _cover(cik="0000320193").cik == "0000320193"


def test_cik_non_numeric_passes_through_untouched():
    # Belt-and-suspenders: if the LLM returns something weird, don't crash.
    assert _cover(cik="CIK-320193").cik == "CIK-320193"


def test_cover_dates_parsed_from_iso_strings():
    c = _cover(fiscal_year_end="2024-09-28", filing_date="2024-11-01")
    assert c.fiscal_year_end == date(2024, 9, 28)
    assert c.filing_date == date(2024, 11, 1)


# --- Financials -----------------------------------------------------------

def test_financials_defaults_currency_to_usd():
    assert FilingFinancials().currency == "USD"


def test_financials_currency_normalized():
    assert _fin(currency="usd").currency == "USD"
    assert _fin(currency="  eur  ").currency == "EUR"


def test_financials_currency_blank_falls_back_to_usd():
    # Model returning "" or spaces shouldn't produce an invalid currency.
    assert _fin(currency="").currency == "USD"
    assert _fin(currency="   ").currency == "USD"


def test_financials_money_rounds_to_two_decimals():
    f = _fin(revenue=391035000000.123456, net_income=93736000000.789)
    assert f.revenue == 391035000000.12
    assert f.net_income == 93736000000.79


def test_financials_fiscal_year_range_enforced():
    _fin(fiscal_year=2024)  # OK
    with pytest.raises(ValidationError):
        _fin(fiscal_year=1500)
    with pytest.raises(ValidationError):
        _fin(fiscal_year=2200)


def test_financials_all_money_fields_optional():
    # Building with no fields shouldn't raise — 10-K may omit any of them.
    f = FilingFinancials()
    assert f.revenue is None
    assert f.total_debt is None
    assert f.free_cash_flow is None


# --- Risk factors + top-level Filing -------------------------------------

def test_risk_factor_requires_both_theme_and_summary():
    RiskFactor(theme="supply chain", summary="Depends on China manufacturing.")
    with pytest.raises(ValidationError):
        RiskFactor(theme="supply chain")  # missing summary


def test_filing_composes_all_three_subschemas():
    f = Filing(
        cover=_cover(cik="0000320193", ticker="AAPL", fiscal_year_end="2024-09-28"),
        financials=_fin(fiscal_year=2024, revenue=391035000000, net_income=93736000000, eps_diluted=6.11),
        top_risk_factors=[
            RiskFactor(theme="supply chain concentration", summary="China dependency."),
            RiskFactor(theme="FX exposure",                 summary="Non-US sales volatility."),
        ],
    )
    assert f.cover.ticker == "AAPL"
    assert f.financials.revenue == 391035000000.0
    assert len(f.top_risk_factors) == 2


def test_top_risk_factors_capped_at_five():
    with pytest.raises(ValidationError):
        Filing(
            cover=_cover(),
            financials=_fin(),
            top_risk_factors=[
                RiskFactor(theme=str(i), summary="x") for i in range(6)  # 6 > max_length=5
            ],
        )


def test_top_risk_factors_default_empty_list():
    # A 10-K with no risk section shouldn't fail extraction.
    f = Filing(cover=_cover(), financials=_fin())
    assert f.top_risk_factors == []


def test_filing_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Filing.model_validate({
            "cover": {"company_name": "X"},
            "financials": {},
            "top_risk_factors": [],
            "extra_field": "nope",  # extra="forbid" should reject this
        })


# --- Registry hookup ------------------------------------------------------

def test_filing_registered_and_returned_by_get_schema():
    assert get_schema("filing") is Filing


def test_list_doc_types_includes_filing():
    assert "filing" in list_doc_types()


def test_filing_case_insensitive_lookup():
    # get_schema lowercases the input.
    assert get_schema("FILING") is Filing
    assert get_schema("Filing") is Filing
