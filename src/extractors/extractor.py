"""Main extraction orchestrator.

    from src.extractors import DocumentExtractor
    ex = DocumentExtractor()
    result, metrics = ex.extract(file_bytes, "invoice.pdf", doc_type="invoice")
    # result is ExtractionResult[Invoice]
    # metrics has tokens, cost, latency
"""
from __future__ import annotations

from typing import Any

from src.extractors.document_loader import LoadedDocument, load_document
from src.extractors.envelope import compute_overall_confidence, make_envelope
from src.extractors.openai_client import OpenAIExtractionClient
from src.extractors.prompts import get_prompt
from src.extractors.section_chunker import chunk_filing
from src.schemas import ExtractionResult
from src.schemas.registry import get_schema
from src.utils.cost_tracker import ExtractionMetrics
from src.utils.logging import logger


class DocumentExtractor:
    """Public entry point for extraction.

    Stateless-ish: holds a shared OpenAI client + default model, no per-request state.
    Safe to reuse across many extractions.
    """

    def __init__(
        self,
        client: OpenAIExtractionClient | None = None,
        default_model: str | None = None,
    ):
        self._client = client or OpenAIExtractionClient(model=default_model)

    # ------------------------------------------------------------------

    def extract(
        self,
        file_bytes: bytes,
        filename: str,
        doc_type: str,
        *,
        model_override: str | None = None,
        render_images: bool = True,
        reasoning_effort: str | None = None,
    ) -> tuple[ExtractionResult, ExtractionMetrics]:
        """Extract a doc into an ExtractionResult[T] plus per-call metrics.

        - `doc_type` looks up both the schema (via registry) and the prompt.
        - `model_override` lets the caller swap models for benchmarking.
        - `render_images=False` skips vision (text-only) for cheap extractions.
        """
        # 1. Look up schema + prompt.
        schema_cls = get_schema(doc_type)
        system_prompt = get_prompt(doc_type)
        envelope_cls = make_envelope(schema_cls)

        # 2. Load the document.
        loaded = load_document(file_bytes, filename, render_images=render_images)
        if loaded.source_type == "empty":
            raise ValueError(f"Could not load document {filename!r} (unknown or corrupt format).")

        # 3. Build the messages. Filings use a section-aware path — a full 10-K
        #    is ~150K tokens; we ship only cover + Item 8 + Item 1A to keep
        #    per-call cost + latency reasonable and reduce distractor text.
        if doc_type.strip().lower() == "filing":
            messages = self._build_filing_messages(system_prompt, loaded)
        else:
            messages = self._build_messages(system_prompt, loaded)

        # 4. Call the model.
        envelope, metrics = self._client.parse_structured(
            response_format=envelope_cls,
            messages=messages,
            model=model_override,
            reasoning_effort=reasoning_effort,
        )

        # 5. Wrap into ExtractionResult.
        result = ExtractionResult(
            document_type=doc_type,
            data=envelope.data,
            field_confidences=envelope.field_confidences,
            overall_confidence=compute_overall_confidence(envelope.field_confidences),
            warnings=envelope.warnings,
            raw_text_snippet=loaded.text[:2000] if loaded.text else None,
        )

        logger.info(
            f"Extracted {doc_type} from {filename}: "
            f"overall_confidence={result.overall_confidence:.2f}, "
            f"warnings={len(result.warnings)}, cost=${metrics.cost_usd:.5f}"
        )
        return result, metrics

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(system_prompt: str, loaded: LoadedDocument) -> list[dict[str, Any]]:
        """Assemble the OpenAI messages list from the loaded document."""
        user_content: list[dict[str, Any]] = []

        if loaded.text:
            user_content.append(
                {
                    "type": "text",
                    "text": (
                        "Extract the structured data from this document. "
                        "The document text follows (and page images may also be attached):\n\n"
                        f"---BEGIN DOCUMENT TEXT---\n{loaded.text}\n---END DOCUMENT TEXT---"
                    ),
                }
            )
        else:
            user_content.append(
                {
                    "type": "text",
                    "text": (
                        "Extract the structured data from this document. "
                        "Only page images are provided (no text was extractable)."
                    ),
                }
            )

        for img_b64 in loaded.images_b64:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_b64}",
                        "detail": "high",
                    },
                }
            )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    # ------------------------------------------------------------------
    # Filing path
    # ------------------------------------------------------------------

    # Per-section byte caps. Real 10-K sections rarely exceed ~40 KB; 60 KB
    # gives us headroom for verbose filers (JPM's Item 1A runs long) while
    # keeping total prompt size ~30-40K tokens — well inside gpt-5-nano's cost
    # sweet spot.
    _FILING_COVER_BYTES = 6_000
    _FILING_ITEM_1A_BYTES = 60_000
    _FILING_ITEM_8_BYTES = 60_000

    def _build_filing_messages(
        self,
        system_prompt: str,
        loaded: LoadedDocument,
    ) -> list[dict[str, Any]]:
        """Message builder for the 10-K path.

        Slices the loaded text into cover + Item 8 (financials) + Item 1A
        (risk factors) and hands each to the model as a clearly-labeled block.
        Filings are text-first — vision isn't used here (10-K images are
        usually chart infographics, not extraction targets).
        """
        text = loaded.text or ""
        chunked = chunk_filing(text, cover_bytes=self._FILING_COVER_BYTES)

        cover = chunked.cover[: self._FILING_COVER_BYTES]
        item_8 = chunked.get_text("8", default="(Item 8 not found in this filing.)")[
            : self._FILING_ITEM_8_BYTES
        ]
        item_1a = chunked.get_text("1A", default="(Item 1A not found in this filing.)")[
            : self._FILING_ITEM_1A_BYTES
        ]

        logger.info(
            f"[filing] chunked: cover={len(cover)}B, "
            f"item_8={len(item_8)}B (present={chunked.has('8')}), "
            f"item_1a={len(item_1a)}B (present={chunked.has('1A')}), "
            f"total_items={len(chunked.item_ids)}"
        )

        user_text = (
            "Extract the structured filing data. Three relevant sections of the "
            "10-K are provided below. Do NOT hallucinate values from other "
            "sections not shown.\n\n"
            "---COVER SECTION---\n"
            f"{cover}\n"
            "---END COVER SECTION---\n\n"
            "---FINANCIAL SECTION (Item 8)---\n"
            f"{item_8}\n"
            "---END FINANCIAL SECTION---\n\n"
            "---RISK FACTORS SECTION (Item 1A)---\n"
            f"{item_1a}\n"
            "---END RISK FACTORS SECTION---"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": [{"type": "text", "text": user_text}]},
        ]
