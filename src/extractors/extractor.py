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

        # 3. Build the messages.
        messages = self._build_messages(system_prompt, loaded)

        # 4. Call the model.
        envelope, metrics = self._client.parse_structured(
            response_format=envelope_cls,
            messages=messages,
            model=model_override,
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
