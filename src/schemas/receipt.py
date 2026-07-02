"""Receipt schema — for consumer receipts (retail, restaurant, gas, etc.).

Receipts are simpler than invoices: no PO, no billing party, no payment terms.
Typically we care about merchant, transaction time, line items, and totals.
"""
from __future__ import annotations

from datetime import date, time

from pydantic import Field, field_validator

from src.schemas.base import StrictModel
from src.schemas.common import Address, MoneyAmount, normalize_currency, round_money


class ReceiptLineItem(StrictModel):
    """A row on a consumer receipt — usually less structured than an invoice line."""

    description: str = Field(description="What was purchased.")
    quantity: float | None = Field(default=None, ge=0)
    unit_price: MoneyAmount | None = None
    total: MoneyAmount | None = None

    @field_validator("unit_price", "total", mode="before")
    @classmethod
    def _round(cls, v):
        return round_money(v) if v is not None else v


class Receipt(StrictModel):
    """A consumer-facing receipt.

    Required fields: merchant name, total, currency. Everything else optional
    since many receipts omit fields (e.g. gas receipts often lack line items).
    """

    # Merchant
    merchant: str = Field(description="Merchant / business name as printed on the receipt.")
    merchant_address: Address | None = Field(
        default=None, description="Structured address of the merchant if legible."
    )
    merchant_phone: str | None = None

    # Transaction
    transaction_date: date | None = Field(
        default=None, description="Date of the transaction (ISO 8601)."
    )
    transaction_time: time | None = Field(
        default=None, description="Time of day (24h, ISO 8601)."
    )
    receipt_number: str | None = Field(
        default=None, description="Receipt / transaction / order number, if present."
    )

    # Items and totals
    line_items: list[ReceiptLineItem] = Field(
        default_factory=list, description="Purchased items. Empty is allowed for e.g. lump-sum receipts."
    )
    subtotal: MoneyAmount | None = None
    tax: MoneyAmount | None = None
    tip: MoneyAmount | None = Field(default=None, description="Gratuity, if applicable (restaurants).")
    total: MoneyAmount = Field(description="Grand total charged.")

    # Payment
    currency: str = Field(description="ISO 4217 currency code (e.g. USD).")
    payment_method: str | None = Field(
        default=None,
        description="Free text: 'Visa **** 1234', 'Cash', 'Apple Pay', etc.",
    )

    # --- Validators ---

    @field_validator("subtotal", "tax", "tip", "total", mode="before")
    @classmethod
    def _round_money(cls, v):
        return round_money(v) if v is not None else v

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, v):
        return normalize_currency(v)

    @field_validator("total")
    @classmethod
    def _total_nonneg(cls, v):
        if v < 0:
            raise ValueError(f"Receipt total cannot be negative: {v}")
        return v
