"""Shared building-block types used across invoice and receipt schemas."""
from __future__ import annotations

from pydantic import Field, field_validator

from src.schemas.base import StrictModel


class Address(StrictModel):
    """A postal address. All fields optional to handle partial extractions."""

    line1: str | None = Field(default=None, description="Street address line 1.")
    line2: str | None = Field(default=None, description="Suite / apartment / unit.")
    city: str | None = None
    region: str | None = Field(default=None, description="State / province / region.")
    postal_code: str | None = None
    country: str | None = Field(
        default=None, description="ISO 3166-1 alpha-2 country code when derivable, else free text."
    )


class Party(StrictModel):
    """A named entity on an invoice — vendor, customer, or bill-to party."""

    name: str = Field(description="Legal or trade name of the entity.")
    address: Address | None = Field(
        default=None, description="Postal address if present on the document."
    )
    tax_id: str | None = Field(
        default=None, description="VAT / GST / EIN / other tax identifier if present."
    )
    email: str | None = None
    phone: str | None = None


# --- Currency helpers -------------------------------------------------------

# ISO 4217 three-letter codes we commonly see on receipts/invoices.
# Not exhaustive — the model may return other valid codes.
COMMON_CURRENCIES = {
    "USD", "EUR", "GBP", "INR", "CAD", "AUD", "JPY", "CNY", "CHF",
    "SEK", "NOK", "DKK", "SGD", "HKD", "MXN", "BRL", "ZAR", "AED",
}


def normalize_currency(value: str | None) -> str | None:
    """Uppercase and strip; leave unknown codes alone (log-and-pass)."""
    if value is None:
        return None
    v = value.strip().upper()
    return v or None


# --- Monetary amount ---
# We use `float` (not Decimal) at the schema layer because OpenAI structured
# outputs enforces strict JSON Schema — 'number' round-trips cleanly. A
# validator rounds to 2 decimals to prevent drift. If your domain requires
# Decimal correctness (e.g. accounting book-of-record), convert at the app
# layer after extraction.
MoneyAmount = float


def round_money(v: float | None) -> float | None:
    """Round monetary amounts to 2 decimals, preserving None."""
    return None if v is None else round(float(v), 2)


class MoneyMixin(StrictModel):
    """Mixin providing a shared validator for monetary fields.

    Subclasses list monetary field names in `_money_fields` and this mixin
    ensures they are rounded to 2 decimals on assignment.
    """

    _money_fields: tuple[str, ...] = ()

    @field_validator("*", mode="before")
    @classmethod
    def _round_money_fields(cls, v, info):
        if info.field_name in cls._money_fields and v is not None:
            try:
                return round(float(v), 2)
            except (TypeError, ValueError):
                return v
        return v
