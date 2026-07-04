# ============================================================================
# Structured Data Extraction — API image
#
# Multi-stage build: builder installs Python deps into a venv, runtime is a
# slim image with only the venv + source code. Cuts final image size roughly
# in half vs a single-stage build (no pip cache, no build toolchain).
# ============================================================================

# ---------- Stage 1: builder --------------------------------------------------
FROM python:3.11-slim AS builder

# System build tools — only present in the builder stage, not runtime.
# Needed because pymupdf / Pillow may compile C extensions on some archs.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated venv so the runtime stage can just copy /opt/venv.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------- Stage 2: runtime --------------------------------------------------
FROM python:3.11-slim AS runtime

# poppler-utils supports pdf2image; libglib is a pymupdf runtime dep.
RUN apt-get update && apt-get install -y --no-install-recommends \
      poppler-utils \
      libglib2.0-0 \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the venv from the builder — no dev deps, no pip cache.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Non-root user — hardens against container escapes. FastAPI needs no privs.
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app

# Copy only what the API needs at runtime. src/ contains the entire python
# package; pyproject.toml is present for tooling that reads project metadata.
COPY --chown=app:app src/ ./src/
COPY --chown=app:app pyproject.toml ./

USER app

EXPOSE 8000

# Container healthcheck — Docker + docker-compose will use this to gate startup
# of dependent services (the UI waits on `service_healthy`).
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# uvicorn's --host 0.0.0.0 makes the port reachable from other compose services.
# Single worker keeps the FastAPI dependency singleton (DocumentExtractor)
# consistent; if we ever need horizontal scale we'll switch to gunicorn.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
