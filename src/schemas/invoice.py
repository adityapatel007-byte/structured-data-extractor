"""Invoice schema — for B2B invoices with structured line items, tax, and parties."""
from __future__ import annotations

from datetime import date

from pydantic import Field, field_validator, model_validator

from src.schemas.base import StrictModel
from src.schemas.common import MoneyAmount, Party, normalize_currency, round_money


class LineItem(StrictModel):
    """A single row on the invoice — product/service with quantity and price."""

    description: str = Field(description="Human-readable description of the item or service.")
    sku: str | None = Field(default=None, description="Product code / SKU / catalog number, if present.")
    quantity: float | None = Field(
        default=None, ge=0, description="Number of units. Null if not on the document."
    )
    unit_price: MoneyAmount | None = Field(
        default=None, description="Price per unit in the invoice's currency."
    )
    tax_rate: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Tax rate applied to this line as a decimal (0.08 = 8%). Null if not itemized.",
    )
    total: MoneyAmount | None = Field(
        default=None,
        description="Line total (quantity * unit_price, or as stated on the document).",
    )

    @field_validator("unit_price", "total", mode="before")
    @classmethod
    def _round(cls, v):
        return round_money(v) if v is not None else v


class Invoice(StrictModel):
    """A B2B invoice.

    Required fields (`invoice_number`, `vendor`, `total`, `currency`) reflect
    the minimum you can meaningfully call an invoice. Everything else is
    Optional to handle partial or malformed source documents.
    """

    # Identifiers
    invoice_number: str = Field(description="The vendor's invoice number, as printed.")
    purchase_order_number: str | None = Field(
        default=None, description="Customer's PO number if referenced on the invoice."
    )

    # Dates
    invoice_date: date | None = Field(
        default=None, description="Date the invoice was issued (ISO 8601)."
    )
    due_date: date | None = Field(default=None, description="Payment due date (ISO 8601).")
    service_period_start: date | None = None
    service_period_end: date | None = None

    # Parties
    vendor: Party = Field(description="The party issuing the invoice — who is being paid.")
    customer: Party | None = Field(
        default=None, description="The party being billed, if identifiable."
    )

    # Line items and totals
    line_items: list[LineItem] = Field(
        default_factory=list,
        description="Individual line items. Empty list is allowed but strongly discouraged.",
    )
    subtotal: MoneyAmount | None = Field(
        default=None, description="Sum of line items before tax and discounts."
    )
    discount: MoneyAmount | None = Field(
        default=None, description="Total discount amount (positive number)."
    )
    tax: MoneyAmount | None = Field(default=None, description="Total tax amount.")
    shipping: MoneyAmount | None = Field(
        default=None, description="Shipping / freight / handling fees, if line-itemized."
    )
    total: MoneyAmount = Field(description="Grand total the customer owes.")

    # Currency + payment
    currency: str = Field(
        description="ISO 4217 currency code (e.g. USD, EUR). Extractor should normalize."
    )
    payment_terms: str | None = Field(
        default=None, description="Free-text terms, e.g. 'Net 30' or 'Due on receipt'."
    )
    payment_instructions: str | None = Field(
        default=None, description="Bank / ACH / other payment routing details."
    )

    # --- Validators ---

    @field_validator("subtotal", "discount", "tax", "shipping", "total", mode="before")
    @classmethod
    def _round_money(cls, v):
        return round_money(v) if v is not None else v

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, v):
        return normalize_currency(v)

    @model_validator(mode="after")
    def _sanity_check_totals(self) -> Invoice:
        """Sanity-check: if subtotal + tax + shipping ~= total, we're consistent.

        We don't reject on mismatch (the model may have transcribed one field
        wrong), but we surface it via the ExtractionResult warnings layer.
        For now, just enforce total >= 0.
        """
        if self.total < 0:
            raise ValueError(f"Invoice total cannot be negative: {self.total}")
        return self
