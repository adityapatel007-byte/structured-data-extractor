"""Section-aware chunker for SEC 10-K annual reports.

Why this exists
---------------
A 10-K is 50-250 pages. Even at gpt-5's 400K-token context, feeding the whole
thing on every extraction is wasteful — a filing weighs ~150K tokens and each
call costs ~$0.60. Worse, the model has to skim past long stretches of
irrelevant text to find the fields you asked for.

The 10-K format is our friend: every filing structures its content into
numbered Items. The three we care about for v2:

    Item 1     — Business (skipped for now)
    Item 1A    — Risk Factors            → RiskFactor extraction
    Item 7     — MD&A                    → macroeconomic + strategy context
    Item 8     — Financial Statements    → FilingFinancials extraction

The cover page (registrant name, CIK, fiscal year, ticker, exchange) lives in
the first ~2 KB before Item 1 kicks in, so we grab it as an implicit
"cover" chunk.

Method
------
Regex over the plaintext for headings that look like `ITEM 1A.` /
`Item 1A.` / `Item 1A —` / `ITEM 1A — RISK FACTORS`. We build a list of
(item_id, start_offset) hits, sort them, and slice the text into (item_id →
text) chunks. The last item runs to end-of-document.

We match generously (case-insensitive; Roman-numeral or "PART II" prefixes
tolerated) because real 10-K formatting is inconsistent across filers and
years. Downstream code should never assume every item is present — a filer
might omit Item 1A when it's not material.

Not in scope for v2
-------------------
- HTML-to-text (already handled upstream by pdfplumber / bs4 in the loader).
- Table-of-contents skipping: the TOC often lists all items, and our regex
  will match them. We mitigate this by keeping only the *last* occurrence of
  each item id — which is the actual section, not the TOC entry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Ordered list of items we recognize. Order matters — the chunker returns
# sections in filing order for humans reading a report side-by-side.
KNOWN_ITEMS: tuple[str, ...] = (
    "1",   "1A",  "1B",  "1C",
    "2",   "3",   "4",
    "5",   "6",   "7",   "7A",
    "8",   "9",   "9A",  "9B",
    "10",  "11",  "12",  "13",  "14",  "15",
)


# The regex allows:
#   ITEM 1A.  |  Item 1A —  |  ITEM 1A -  |  Item 1A:
# case-insensitive, with optional PART header prefix stripped by callers.
_ITEM_ID_ALT = "|".join(re.escape(x) for x in KNOWN_ITEMS)
_ITEM_HEADING = re.compile(
    rf"""
    (?:^|\n)                          # anchor to start of line (permissive)
    \s{{0,6}}                         # a few leading spaces okay
    ITEM\s+                           # the word ITEM
    (?P<item>{_ITEM_ID_ALT})          # captures 1, 1A, 7, 8, ...
    \b                                # word boundary
    \s*[\.\-–—:\)]?         # optional punctuation: . - – — : )
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class SectionChunk:
    """One chunk of a 10-K aligned to a specific Item heading."""
    item: str          # normalized item id, e.g. "1A", "7", "8"
    heading: str       # the raw matched heading text, e.g. "Item 1A. RISK FACTORS"
    text: str          # the chunk body (from just after the heading to the next heading or EOF)
    start: int         # byte offset in the original document
    end: int


@dataclass
class ChunkedFiling:
    """A 10-K sliced into cover + Item chunks. Access via `.get('1A')` etc."""
    cover: str
    sections: list[SectionChunk]

    def get(self, item: str) -> SectionChunk | None:
        """Return the section for a given item id, or None if absent."""
        want = item.upper().strip()
        for s in self.sections:
            if s.item == want:
                return s
        return None

    def get_text(self, item: str, default: str = "") -> str:
        s = self.get(item)
        return s.text if s else default

    def has(self, item: str) -> bool:
        return self.get(item) is not None

    @property
    def item_ids(self) -> list[str]:
        return [s.item for s in self.sections]


# --- API -------------------------------------------------------------------

def chunk_filing(text: str, cover_bytes: int = 4000) -> ChunkedFiling:
    """Slice a 10-K text into cover + per-Item chunks.

    Args:
        text: The full 10-K plaintext (from pdfplumber, bs4, or similar).
        cover_bytes: How much of the doc to treat as the cover chunk. Cover
            pages are usually ~1-3 KB; 4000 is a safe upper bound.

    Returns:
        A ChunkedFiling. If no Item headings are found (rare — malformed doc
        or non-10-K input), returns a single "sections" entry with the whole
        text under item="0".
    """
    if not text or not text.strip():
        return ChunkedFiling(cover="", sections=[])

    hits = _find_all_item_headings(text)

    # No Item headings — return everything as one blob and let the caller decide.
    if not hits:
        return ChunkedFiling(
            cover=text[:cover_bytes],
            sections=[SectionChunk(item="0", heading="(no headings)", text=text, start=0, end=len(text))],
        )

    # Deduplicate: keep only the LAST occurrence of each item id — the earlier
    # ones are almost always the Table of Contents entries.
    last_by_item: dict[str, tuple[str, str, int, int]] = {}
    for m in hits:
        item = m["item"]
        last_by_item[item] = (item, m["heading"], m["start"], m["heading_end"])

    # Now order by start offset (filing order).
    ordered = sorted(last_by_item.values(), key=lambda x: x[2])

    # Compute end offsets — each section ends where the next one starts.
    sections: list[SectionChunk] = []
    for i, (item, heading, start, heading_end) in enumerate(ordered):
        end = ordered[i + 1][2] if i + 1 < len(ordered) else len(text)
        sections.append(
            SectionChunk(item=item, heading=heading, text=text[heading_end:end], start=start, end=end)
        )

    cover_end = min(cover_bytes, ordered[0][2])
    return ChunkedFiling(cover=text[:cover_end], sections=sections)


# --- Internals -------------------------------------------------------------

def _find_all_item_headings(text: str) -> list[dict]:
    """Return every regex match as a dict, normalized item id + offsets."""
    out: list[dict] = []
    for m in _ITEM_HEADING.finditer(text):
        item = m.group("item").upper()
        # Grab the rest of the line as the "heading" for debugging.
        line_end = text.find("\n", m.end())
        if line_end == -1:
            line_end = min(m.end() + 120, len(text))
        heading = text[m.start(): line_end].strip()
        out.append({
            "item": item,
            "heading": heading,
            "start": m.start(),
            "heading_end": line_end,
        })
    return out
