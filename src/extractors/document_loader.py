"""Load documents (PDF / PNG / JPG) into text + page images for extraction.

Strategy:
1. For PDFs, try text extraction first via pdfplumber. If the doc has meaningful
   text, we use it directly (fast, cheap).
2. Always also render page images via PyMuPDF — GPT-5 nano vision handles layout
   information that pure text misses (tables, spatial context on receipts).
3. Standalone images (PNG/JPG) skip text extraction and go straight to vision.

The extractor decides how to use text vs images based on `source_type`.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber
from PIL import Image

from src.utils.logging import logger

# --- Config knobs ------------------------------------------------------------

# If extracted text is shorter than this, treat the PDF as scanned/image-based.
_MIN_TEXT_CHARS_FOR_TEXT_PDF = 100

# Max pages we render as images (guards against absurdly long PDFs pre-v2).
_MAX_PAGES_TO_RENDER = 5

# DPI for rendering — higher = clearer OCR but slower + bigger payload.
# 200 DPI is a good sweet spot for receipts + invoices.
_RENDER_DPI = 200

# Max side length before we downscale — GPT-5 nano vision handles up to 2048.
_MAX_IMAGE_SIDE = 2048


@dataclass
class LoadedDocument:
    """The output of the loader — text and/or images ready for the LLM."""

    text: str = ""
    images_b64: list[str] = field(default_factory=list)
    source_type: str = "unknown"  # "text_pdf" | "image_pdf" | "image" | "empty"
    page_count: int = 0
    filename: str = ""


# --- Helpers ---------------------------------------------------------------


def _image_to_b64(img: Image.Image) -> str:
    """PIL Image -> base64-encoded PNG string suitable for OpenAI vision."""
    # Downscale if needed
    if max(img.size) > _MAX_IMAGE_SIDE:
        ratio = _MAX_IMAGE_SIDE / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _render_pdf_pages(pdf_bytes: bytes, max_pages: int = _MAX_PAGES_TO_RENDER) -> list[str]:
    """Render each PDF page to a base64 PNG using PyMuPDF."""
    images_b64: list[str] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=_RENDER_DPI)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images_b64.append(_image_to_b64(img))
    return images_b64


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from all pages via pdfplumber. Empty string on failure."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            parts: list[str] = []
            for page in pdf.pages[:_MAX_PAGES_TO_RENDER]:
                text = page.extract_text() or ""
                if text.strip():
                    parts.append(text)
            return "\n\n".join(parts).strip()
    except Exception as e:
        logger.warning(f"pdfplumber text extraction failed: {e}")
        return ""


# --- Public API ------------------------------------------------------------


def load_document(
    file_bytes: bytes,
    filename: str = "document",
    *,
    render_images: bool = True,
) -> LoadedDocument:
    """Turn raw file bytes into a LoadedDocument.

    - `render_images=False` skips image rendering for cost savings on text-heavy PDFs.
      The extractor can decide based on doc size / cost budget.
    """
    ext = Path(filename).suffix.lower()

    # --- Standalone images -> straight to vision -----------------------------
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}:
        try:
            img = Image.open(io.BytesIO(file_bytes))
            return LoadedDocument(
                text="",
                images_b64=[_image_to_b64(img)],
                source_type="image",
                page_count=1,
                filename=filename,
            )
        except Exception as e:
            logger.error(f"Failed to load image {filename}: {e}")
            return LoadedDocument(source_type="empty", filename=filename)

    # --- PDFs ---------------------------------------------------------------
    if ext == ".pdf" or file_bytes[:4] == b"%PDF":
        text = _extract_pdf_text(file_bytes)
        has_text = len(text) >= _MIN_TEXT_CHARS_FOR_TEXT_PDF

        images_b64: list[str] = []
        if render_images or not has_text:
            try:
                images_b64 = _render_pdf_pages(file_bytes)
            except Exception as e:
                logger.warning(f"PDF image rendering failed: {e}")

        source_type = "text_pdf" if has_text else "image_pdf"

        # Get page count for logging
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                page_count = len(doc)
        except Exception:
            page_count = len(images_b64)

        logger.info(
            f"Loaded {filename}: source_type={source_type}, pages={page_count}, "
            f"text_chars={len(text)}, images={len(images_b64)}"
        )
        return LoadedDocument(
            text=text,
            images_b64=images_b64,
            source_type=source_type,
            page_count=page_count,
            filename=filename,
        )

    # --- Unknown format -----------------------------------------------------
    logger.warning(f"Unknown file extension {ext!r} for {filename}. Treating as empty.")
    return LoadedDocument(source_type="empty", filename=filename)
