"""Middleware: request IDs + structured access logs.

RequestIDMiddleware attaches a UUID4 to every request as `X-Request-ID`. Both
the response header and the log line carry it so a user reporting an error can
give you the ID and you can find the log.

StructuredLoggingMiddleware logs one JSON line per request with method, path,
status, latency, and the request ID.
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.utils.logging import logger

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign each request a UUID and echo it in the response header."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = rid
        response: Response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """One log line per request with method, path, status, latency, request_id."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000
        rid = getattr(request.state, "request_id", "-")
        logger.info(
            f"[api] method={request.method} path={request.url.path} "
            f"status={response.status_code} latency_ms={latency_ms:.1f} rid={rid}"
        )
        return response
