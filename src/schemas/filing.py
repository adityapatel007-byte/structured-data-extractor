"""SEC filing schema — for 10-K annual reports (v2).

Design intent
-------------
A 10-K is a very different beast from a receipt: 50-250 pages, structured into
Items (1, 1A, 7, 8, ...), with a mix of long-form narrative (business
description, risk factors) and dense financial tables (income statement,
balance sheet, cash flow).

Rather than model the whole document, we extract the three highest-signal
slices for downstream analysis and evaluation:

    1. **Cover page**    — identity + registration metadata (CIK, fiscal year,
       ticker, exchange). These are canonical, auto-scrapable from EDGAR, and
       make excellent ground-truth targets.
    2. **Financials**    — the top-line income statement + balance-sheet
       figures a human analyst would extract for a quick take: revenue, net
       income, EPS, cash, debt, equity. All in the filing's reporting currency
       (almost always USD), normalized to *absolute* dollars (i.e. the
       extractor must undo "in millions"/"in thousands" scaling).
    3. **Top risk factors** — the extractor summarizes Item 1A into up to 5
       themed risk factors. This is the qualitative story a portfolio project
       needs — it shows the LLM doing unstructured → structured reduction, not
       just field-picking.

Conventions kept in line with receipt/invoice schemas
------------------------------------------------------
- `StrictModel` base (extra="forbid" for OpenAI structured-outputs strict mode).
- `MoneyAmount = float` (never Decimal — see common.py for the tradeoff).
- All fields on the sub-models are Optional except a small "required core"
  (company name, form type). Real 10-Ks omit fields; we shouldn't fail on that.
"""
from __future__ import annotations

from datetime import date

from pydantic import Field, field_validator

from src.schemas.base import StrictModel
from src.schemas.common import Address, MoneyAmount, normalize_currency, round_money

# ---------------------------------------------------------------------------
# 1) COVER PAGE
# ---------------------------------------------------------------------------

class FilingCover(StrictModel):
    """Registrant + filing metadata from the 10-K cover page.

    All of this is scrapable from EDGAR's structured header, so it's a strong
    ground-truth target for evaluation. A well-tuned extractor should hit
    ~100% F1 on this section — the interesting question is whether it does.
    """

    company_name: str = Field(description="Full legal name of the registrant as it appears on the cover.")

    cik: str | None = Field(
        default=None,
        description=(
            "SEC Central Index Key — 10-digit numeric string with leading zeros preserved "
            "(e.g. '0000320193' for Apple). Extract as printed if visible; else null."
        ),
    )
    ticker: str | None = Field(
        default=None, description="Primary trading symbol, e.g. 'AAPL'. Uppercase."
    )
    exchange: str | None = Field(
        default=None,
        description=(
            "Registered exchange (e.g. 'NASDAQ Global Select Market', 'New York Stock Exchange'). "
            "Verbatim from the cover — do NOT abbreviate 'NASDAQ Global Select Market' to 'NASDAQ'."
        ),
    )

    form_type: str = Field(
        default="10-K",
        description="Filing form (10-K, 10-K/A, 10-Q, etc.) as printed on the cover.",
    )

    fiscal_year_end: date | None = Field(
        default=None,
        description=(
            "Last day of the fiscal year the filing covers (ISO 8601). "
            "Not the filing date — the *reporting period end* date."
        ),
    )
    filing_date: date | None = Field(
        default=None,
        description=(
            "Date the 10-K was filed with the SEC (ISO 8601). Sometimes only "
            "the report date is on the cover; this may need to be inferred from the header."
        ),
    )

    state_of_incorporation: str | None = Field(
        default=None,
        description="US state (two-letter) or country of incorporation. Uppercase.",
    )
    address: Address | None = Field(
        default=None,
        description="Principal executive offices address if listed on the cover.",
    )

    @field_validator("ticker", "state_of_incorporation", mode="before")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.strip().upper() if isinstance(v, str) and v.strip() else None

    @field_validator("cik", mode="before")
    @classmethod
    def _cik(cls, v):
        """Left-pad CIK to 10 digits if the model returns 320193 not 0000320193."""
        if v is None:
            return None
        s = str(v).strip()
        return s.zfill(10) if s.isdigit() else s


# ---------------------------------------------------------------------------
# 2) FINANCIALS
# ---------------------------------------------------------------------------

class FilingFinancials(StrictModel):
    """Top-line financial figures from the income statement, balance sheet,
    and cash-flow statement (Item 8).

    Every monetary field is in **absolute** currency units (dollars, not
    millions). The extraction prompt instructs the model to multiply back
    up when the source states "(in millions)" or "(in thousands)". Getting
    the units right is one of the harder eval targets — a factor-of-1000
    error is easy to make and easy to catch.
    """

    currency: str = Field(
        default="USD",
        description="ISO 4217 code for the reporting currency (almost always USD).",
    )
    fiscal_year: int | None = Field(
        default=None,
        ge=1900,
        le=2100,
        description="The 4-digit fiscal year these financials correspond to (e.g. 2025).",
    )

    # --- Income statement -----------------------------------------------
    revenue: MoneyAmount | None = Field(
        default=None,
        description=(
            "Total net revenue (top line) in absolute currency units. "
            "For Apple FY2024 this would be 391_035_000_000 (=$391.035B), NOT 391035."
        ),
    )
    cost_of_revenue: MoneyAmount | None = Field(
        default=None, description="Cost of goods/services sold. Absolute units."
    )
    gross_profit: MoneyAmount | None = Field(default=None)
    operating_income: MoneyAmount | None = Field(default=None)
    net_income: MoneyAmount | None = Field(
        default=None, description="Net income attributable to the parent company."
    )

    # --- Per-share ------------------------------------------------------
    eps_basic: float | None = Field(
        default=None, description="Basic earnings per share (e.g. 6.11 for $6.11)."
    )
    eps_diluted: float | None = Field(default=None, description="Diluted EPS.")

    # --- Balance sheet ---------------------------------------------------
    cash_and_equivalents: MoneyAmount | None = Field(
        default=None,
        description="Cash and cash equivalents (excluding marketable securities).",
    )
    total_debt: MoneyAmount | None = Field(
        default=None,
        description=(
            "Total debt = short-term + long-term borrowings. If the filing separates "
            "'current portion of long-term debt' from long-term debt, sum them."
        ),
    )
    total_assets: MoneyAmount | None = Field(default=None)
    total_equity: MoneyAmount | None = Field(
        default=None, description="Total stockholders' equity attributable to the parent."
    )

    # --- Cash flow -------------------------------------------------------
    operating_cash_flow: MoneyAmount | None = Field(
        default=None, description="Net cash provided by operating activities."
    )
    free_cash_flow: MoneyAmount | None = Field(
        default=None,
        description=(
            "Free cash flow = operating_cash_flow - capex. If not explicitly reported, "
            "leave null rather than compute it — many 10-Ks don't state it."
        ),
    )

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, v):
        return normalize_currency(v) or "USD"

    @field_validator(
        "revenue", "cost_of_revenue", "gross_profit", "operating_income",
        "net_income", "cash_and_equivalents", "total_debt",
        "total_assets", "total_equity",
        "operating_cash_flow", "free_cash_flow",
        mode="before",
    )
    @classmethod
    def _money(cls, v):
        return round_money(v) if v is not None else v


# ---------------------------------------------------------------------------
# 3) RISK FACTORS (Item 1A)
# ---------------------------------------------------------------------------

class RiskFactor(StrictModel):
    """A single themed risk distilled from Item 1A.

    Item 1A in a real 10-K is 20-80 pages of prose. The model reduces it to
    at most ~5 named themes with 1-3 sentence summaries — the "TL;DR" a
    quant would want on a first pass. `theme` is fuzzy-matchable (eval uses
    rapidfuzz); `summary` is scored more leniently.
    """

    theme: str = Field(
        description=(
            "Short (2-6 word) label for the risk — e.g. 'supply chain concentration', "
            "'foreign-exchange exposure', 'regulatory / antitrust'."
        ),
    )
    summary: str = Field(
        description=(
            "1-3 sentence plain-English summary of the risk. Use the filer's own language "
            "where possible; do not editorialize."
        ),
    )


# ---------------------------------------------------------------------------
# TOP-LEVEL FILING
# ---------------------------------------------------------------------------

class Filing(StrictModel):
    """A structured extract of a single SEC 10-K annual report.

    Composed of the three sub-schemas above. The top-level model stays flat
    to keep the JSON output easy to consume in a downstream analytics
    pipeline (Snowflake, DuckDB, a dashboard).
    """

    cover: FilingCover = Field(description="Registrant identity + filing metadata.")
    financials: FilingFinancials = Field(
        description="Top-line income statement, balance sheet, and cash flow figures."
    )
    top_risk_factors: list[RiskFactor] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "Up to 5 themed risk factors distilled from Item 1A. "
            "Order = the extractor's ranking of importance. Empty list allowed for filings "
            "with unusually short or missing risk sections."
        ),
    )
