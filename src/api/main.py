"""FastAPI application factory + module-level `app` for uvicorn.

Run:
    uvicorn src.api.main:app --reload

Design notes:
- App is created by a factory (`create_app`) so tests can instantiate a fresh
  app with overrides — no shared mutable state across test cases.
- CORS is wide-open by default for local Streamlit; tighten for prod.
- All exceptions funnel through the ErrorEnvelope handler for consistent shape.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.errors import APIError, ErrorDetail, ErrorEnvelope
from src.api.middleware import AccessLogMiddleware, RequestIDMiddleware
from src.api.routers import batch as batch_router
from src.api.routers import extract as extract_router
from src.api.routers import health as health_router
from src.api.routers import schemas as schemas_router
from src.api.routers import stream as stream_router
from src.utils.logging import logger


def create_app() -> FastAPI:
    app = FastAPI(
        title="Structured Data Extraction API",
        description=(
            "Multi-domain document extraction — invoices, receipts, and (v2) SEC filings — "
            "returned as schema-validated JSON with confidence scoring, cost, and latency."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- Middleware (outer -> inner order) ---------------------------------
    # CORS must be outermost so it can add headers to error responses too.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # --- Routers -----------------------------------------------------------
    app.include_router(health_router.router)
    app.include_router(schemas_router.router)
    app.include_router(extract_router.router)
    app.include_router(stream_router.router)   # POST /extract/stream (SSE)      — v3
    app.include_router(batch_router.router)    # POST /extract/batch + GET /...  — v3

    # --- Error handlers ----------------------------------------------------
    @app.exception_handler(APIError)
    async def _api_error_handler(request: Request, exc: APIError):
        rid = getattr(request.state, "request_id", None)
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code=exc.code, message=exc.message, request_id=rid, details=exc.details
            )
        )
        return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", None)
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code="validation_error",
                message="Request failed validation.",
                request_id=rid,
                details={"errors": exc.errors()},
            )
        )
        return JSONResponse(status_code=422, content=envelope.model_dump())

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", None)
        logger.exception(f"[api] Unhandled exception (rid={rid}): {exc}")
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code="internal_error",
                message="An unexpected error occurred.",
                request_id=rid,
            )
        )
        return JSONResponse(status_code=500, content=envelope.model_dump())

    return app


# Module-level instance for `uvicorn src.api.main:app`.
app = create_app()
