"""Health + root routes.

GET /         -> service banner (name, version, docs link)
GET /health   -> {"status": "ok"} — probe target for orchestrators
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])

SERVICE_NAME = "structured-data-extraction"
SERVICE_VERSION = "0.1.0"


@router.get("/")
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
