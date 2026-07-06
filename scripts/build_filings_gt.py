"""Build filings ground-truth JSONL from downloaded EDGAR data.

Reads the sidecars + XBRL companyfacts written by `download_edgar.py` and
produces `evaluation/smoke_filings_sample.jsonl` — the file the eval CLI
reads in `--mode live --doc-type filing` runs.

Each JSONL row has:
    id, source, text (full 10-K plaintext), ground_truth (Filing schema dict)

Cover fields come from the sidecar (auto). Financials come from XBRL
companyfacts using the most-common US-GAAP concepts (see FIN_MAP below).
Risk factors are left EMPTY in the auto-generated ground truth — they're
free text and there's no canonical source. Backfill by hand for a stricter
qualitative eval.

Usage
-----
    python scripts/build_filings_gt.py
    python scripts/build_filings_gt.py --raw-dir data/raw/10k --out evaluation/smoke_filings_sample.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# US-GAAP concept name -> our schema field.
# Values are lists of candidate concept names in order of preference — real
# filers use different names for the same line ("Revenues", "SalesRevenueNet",
# "RevenueFromContractWithCustomerExcludingAssessedTax"...).
# US-GAAP concept mapping. Values are ordered lists of candidate concept
# names — the first one that has an FP='FY' entry for the target fiscal-year
# end date wins. `total_debt` is special: we SUM all matching concepts because
# real filers split debt across many line items (short-term borrowings +
# long-term debt current portion + long-term debt noncurrent + notes payable).
#
# v2.2 expansions:
# - Added Deposits + LongTermBorrowings so banks (JPM) get real total_debt.
# - Added StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest
#   as first choice for total_equity (matches how large filers actually report).
# - Added several revenue variants (retail filers use SalesRevenueGoodsNet, etc.).
# - Added short-term debt concepts (ShortTermBorrowings, etc.) into total_debt sum.
FIN_MAP = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss", "IncomeLossFromContinuingOperations"],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAttributableToParent",
    ],
    "eps_basic":   ["EarningsPerShareBasic",   "IncomeLossFromContinuingOperationsPerBasicShare"],
    "eps_diluted": ["EarningsPerShareDiluted", "IncomeLossFromContinuingOperationsPerDilutedShare"],
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
    "total_assets": ["Assets"],
    "total_equity": [
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "StockholdersEquity",
    ],
    "total_debt": [  # SUM of every matching concept — filers split debt many ways
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "LongTermDebtCurrent",
        "LongTermBorrowings",   # banks (JPM, Citi) use this instead of LongTermDebt
        "ShortTermBorrowings",
        "CommercialPaper",
        "DebtCurrent",
        "DebtLongtermAndShorttermCombinedAmount",
        "Deposits",             # bank funding — treat as debt for a bank
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
}


def _pick_fy_value(concept_data: dict, fy_end: str) -> float | None:
    """Return the concept value for the fiscal year ending `fy_end` (ISO date).

    XBRL companyfacts nests values by unit (USD, USD/shares, pure). We take
    the first unit that produces a match. Match rule: same `end` date + form
    starting with '10-K' + `fp == 'FY'`.
    """
    units = concept_data.get("units", {})
    for _unit, entries in units.items():
        for e in entries:
            if e.get("end") == fy_end and e.get("form", "").startswith("10-K") and e.get("fp") == "FY":
                try:
                    return float(e["val"])
                except (KeyError, ValueError, TypeError):
                    continue
    return None


def build_financials(facts: dict, fy_end: str) -> dict:
    """Populate as many FilingFinancials fields as possible from XBRL."""
    us_gaap = (facts.get("facts", {}) or {}).get("us-gaap", {}) or {}
    fin: dict = {"currency": "USD", "fiscal_year": int(fy_end[:4])}

    for field, candidates in FIN_MAP.items():
        val = None
        collected: list[float] = []
        for concept in candidates:
            data = us_gaap.get(concept)
            if not data:
                continue
            v = _pick_fy_value(data, fy_end)
            if v is None:
                continue
            if field == "total_debt":
                # Sum across all matching debt concepts (short-term + long-term).
                collected.append(v)
            else:
                val = v
                break
        if field == "total_debt" and collected:
            val = sum(collected)
        if val is not None:
            fin[field] = val

    return fin


def build_row(txt_path: Path) -> dict | None:
    """Produce one ground-truth row for the JSONL, or None if metadata is missing."""
    stem = txt_path.name[:-len(".txt")]
    meta_path = txt_path.parent / f"{stem}.meta.json"
    facts_path = txt_path.parent / f"{stem}.facts.json"
    if not meta_path.exists():
        print(f"[!] no sidecar for {txt_path.name} — skipping")
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    facts = json.loads(facts_path.read_text(encoding="utf-8")) if facts_path.exists() else None

    fy_end = meta["reporting_period_end"]
    # Backfill exchange + state_of_incorporation from the SEC submissions feed
    # (both were added to the sidecar in download_edgar.py v2.2). If they're
    # missing (older sidecar without the field), fall back to None — the
    # schema field is Optional so this doesn't fail extraction.
    exchange = meta.get("exchange")
    # Prefer the two-letter code (matches the schema validator that uppercases + strips).
    state = meta.get("state_of_incorporation") or meta.get("state_of_incorporation_desc")

    cover = {
        "company_name": meta["company_name"],
        "cik": meta["cik10"],
        "ticker": meta["ticker"],
        "form_type": meta["form"],
        "fiscal_year_end": fy_end,
        "filing_date": meta["filing_date"],
    }
    if exchange:
        cover["exchange"] = exchange
    if state:
        cover["state_of_incorporation"] = state
    financials = build_financials(facts, fy_end) if facts else {"currency": "USD", "fiscal_year": int(fy_end[:4])}

    return {
        "id": f"filing_{meta['ticker']}_{fy_end}",
        "source": "sec_edgar",
        "text": txt_path.read_text(encoding="utf-8"),
        "ground_truth": {
            "cover": cover,
            "financials": financials,
            "top_risk_factors": [],   # backfill by hand for qualitative eval
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", default="data/raw/10k")
    ap.add_argument("--out", default="evaluation/smoke_filings_sample.jsonl")
    args = ap.parse_args(argv)

    raw = ROOT / args.raw_dir
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)

    txts = sorted(raw.glob("*_10k.txt"))
    if not txts:
        print(f"[!] no *_10k.txt files under {raw} — run download_edgar.py first.")
        return 2

    n_written = 0
    with out.open("w", encoding="utf-8") as f:
        for p in txts:
            row = build_row(p)
            if not row:
                continue
            f.write(json.dumps(row) + "\n")
            n_written += 1
            fin = row["ground_truth"]["financials"]
            print(f"  {row['id']:36s} revenue={fin.get('revenue')} net_income={fin.get('net_income')}")

    print(f"\n-> {out}  ({n_written} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
