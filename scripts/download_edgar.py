"""Download the most recent 10-K for a small watchlist of large-cap issuers.

Purpose
-------
Give the eval pipeline five real 10-K filings to run against, with
auto-scrapable ground-truth metadata already pulled from SEC EDGAR's
structured feeds. Filings are saved as plaintext under `data/raw/10k/`
so `src/eval/cli.py --mode live` can read them via the loader's `.txt` path.

Approach
--------
SEC EDGAR exposes a JSON submissions feed per issuer at
    https://data.sec.gov/submissions/CIK{cik10}.json
which lists every filing (form, accession, date, primary document). We:
    1. For each ticker in WATCHLIST, resolve ticker -> CIK via the tickers file.
    2. Fetch the submissions feed and pick the most recent 10-K.
    3. Download the primary document (HTML).
    4. Strip HTML -> plaintext (via BeautifulSoup) and save.
    5. Also fetch companyfacts.json for XBRL-driven ground truth.

SEC's rules
-----------
- Identify yourself in the User-Agent header (they rate-limit anonymous UAs).
- Cap traffic at <= 10 req/s. A 250 ms sleep between requests is well under.

Usage
-----
    python scripts/download_edgar.py                    # default watchlist
    python scripts/download_edgar.py AAPL MSFT NVDA     # custom tickers
    python scripts/download_edgar.py --dry-run          # print plan only
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "10k"

# One large-cap per sector — diverse writing styles, real ground truth.
WATCHLIST_DEFAULT = ["AAPL", "JPM", "XOM", "PFE", "WMT"]

# SEC requires an identifying User-Agent. Change the email if you fork.
USER_AGENT = "structured-data-extractor (Aditya Patel, adityapatel1801@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
SLEEP_SEC = 0.25   # <= 10 req/s per SEC's fair-use policy


def _get(url: str, timeout: int = 30) -> requests.Response:
    """Throttled GET with SEC-mandated headers."""
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    time.sleep(SLEEP_SEC)
    return r


def load_ticker_index() -> dict:
    """Return a dict of TICKER -> 10-digit CIK, downloaded from SEC."""
    r = _get("https://www.sec.gov/files/company_tickers.json")
    payload = r.json()
    out = {}
    for row in payload.values():
        out[str(row["ticker"]).upper()] = str(row["cik_str"]).zfill(10)
    return out


def latest_10k_metadata(cik10: str) -> dict:
    """Return { accession, primary_doc, filing_date, ... } for the most recent 10-K."""
    r = _get(f"https://data.sec.gov/submissions/CIK{cik10}.json")
    payload = r.json()
    recent = payload["filings"]["recent"]
    # SEC submissions feed carries a top-level exchanges array + state_of_incorporation.
    # Both live *outside* the recent-filings block, so they carry per-issuer, not per-filing.
    exchanges = payload.get("exchanges") or []
    for i, form in enumerate(recent["form"]):
        if form == "10-K":
            return {
                "cik10": cik10,
                "company_name": payload.get("name", ""),
                "form": form,
                "accession": recent["accessionNumber"][i],
                "filing_date": recent["filingDate"][i],
                "reporting_period_end": recent["reportDate"][i],
                "primary_doc": recent["primaryDocument"][i],
                # NEW in v2.2 — used by build_filings_gt.py to backfill cover ground truth.
                "exchange": exchanges[0] if exchanges else None,   # e.g. "Nasdaq"
                "state_of_incorporation": payload.get("stateOfIncorporation") or None,
                "state_of_incorporation_desc": payload.get("stateOfIncorporationDescription") or None,
            }
    raise RuntimeError(f"No 10-K found in recent filings for CIK {cik10}")


def download_10k_html(meta: dict) -> str:
    accession_nodash = meta["accession"].replace("-", "")
    cik_nozero = str(int(meta["cik10"]))
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_nozero}/"
        f"{accession_nodash}/{meta['primary_doc']}"
    )
    r = _get(url, timeout=60)
    return r.text


def html_to_text(html: str) -> str:
    """Strip HTML -> plaintext, preserving section headings so the chunker can find them."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.rstrip() for ln in text.splitlines()]
    out = []
    blank = 0
    for ln in lines:
        if ln.strip() == "":
            blank += 1
            if blank <= 1:
                out.append("")
        else:
            blank = 0
            out.append(ln)
    return "\n".join(out).strip() + "\n"


def download_companyfacts(cik10: str) -> dict:
    """Return the XBRL companyfacts JSON — used for auto-ground-truth."""
    r = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json")
    return r.json()


def save_filing(ticker: str, meta: dict, text: str, facts: dict | None) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{ticker.upper()}_{meta['reporting_period_end']}_10k"
    txt_path = RAW_DIR / f"{stem}.txt"
    meta_path = RAW_DIR / f"{stem}.meta.json"

    txt_path.write_text(text, encoding="utf-8")

    sidecar = {
        "ticker": ticker.upper(),
        "cik10": meta["cik10"],
        "company_name": meta["company_name"],
        "form": meta["form"],
        "accession": meta["accession"],
        "filing_date": meta["filing_date"],
        "reporting_period_end": meta["reporting_period_end"],
        "primary_doc": meta["primary_doc"],
        "source_url": (
            f"https://www.sec.gov/Archives/edgar/data/{int(meta['cik10'])}/"
            f"{meta['accession'].replace('-', '')}/{meta['primary_doc']}"
        ),
        "text_bytes": len(text),
        "has_companyfacts": facts is not None,
    }
    meta_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    if facts is not None:
        (RAW_DIR / f"{stem}.facts.json").write_text(
            json.dumps(facts, separators=(",", ":")), encoding="utf-8"
        )
    return txt_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tickers", nargs="*", default=WATCHLIST_DEFAULT,
                    help=f"Ticker symbols. Default: {' '.join(WATCHLIST_DEFAULT)}")
    ap.add_argument("--dry-run", action="store_true", help="Print plan + exit.")
    ap.add_argument("--skip-facts", action="store_true",
                    help="Skip companyfacts.json download (faster, loses auto-GT).")
    args = ap.parse_args(argv)

    tickers = [t.upper() for t in args.tickers]
    print(f"Watchlist:  {tickers}")
    print(f"Output dir: {RAW_DIR}")
    if args.dry_run:
        return 0

    print("Loading SEC ticker index ...", flush=True)
    ticker_index = load_ticker_index()

    for ticker in tickers:
        try:
            cik10 = ticker_index[ticker]
        except KeyError:
            print(f"[!] {ticker} not in SEC ticker index — skipping.")
            continue

        print(f"\n=== {ticker}  (CIK {cik10}) ===")
        try:
            meta = latest_10k_metadata(cik10)
            print(f"    latest 10-K: accession={meta['accession']} filed {meta['filing_date']}")
            html = download_10k_html(meta)
            print(f"    primary doc: {meta['primary_doc']}  ({len(html):,} HTML bytes)")
            text = html_to_text(html)
            print(f"    plaintext:   {len(text):,} chars")
            facts = None
            if not args.skip_facts:
                facts = download_companyfacts(cik10)
                print(f"    companyfacts: {len(facts.get('facts', {}))} taxonomies")
            path = save_filing(ticker, meta, text, facts)
            print(f"    -> {path.relative_to(ROOT)}")
        except requests.HTTPError as e:
            print(f"[!] {ticker} HTTP error: {e}")
        except Exception as e:
            print(f"[!] {ticker} failed: {type(e).__name__}: {e}")

    print(f"\nDone. Files in {RAW_DIR.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
