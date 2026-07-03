"""FastAPI dependencies + upload constraints.

Why a `Depends`-based extractor:
    FastAPI's dependency injection lets tests override the extractor via
    `app.dependency_overrides[get_extractor] = fake_extractor`, so we can
    hit the endpoints in tests without an OpenAI key. In production the
    lru_cache means we build one DocumentExtractor per worker process.
"""
from __future__ import annotations

from functools import lru_cache

from src.extractors.extractor import DocumentExtractor
from src.schemas.registry import list_doc_types

# --- Upload constraints ----------------------------------------------------

# 10 MB by default. Set to something small for tests via monkeypatch if needed.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# MIME allowlist. Also accept common browser variants. `application/octet-stream`
# is accepted because some clients (and Streamlit) send it for images.
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "application/octet-stream",
    "text/plain",  # for inline text extraction convenience
}

# Extensions we can actually load (mirrors document_loader.py).
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".txt"}


# --- Dependencies ----------------------------------------------------------

@lru_cache(maxsize=1)
def get_extractor() -> DocumentExtractor:
    """Singleton DocumentExtractor. Overridden in tests via dependency_overrides."""
    return DocumentExtractor()


def get_allowed_doc_types() -> list[str]:
    """List of registered document type strings — used by /schemas."""
    return list_doc_types()
