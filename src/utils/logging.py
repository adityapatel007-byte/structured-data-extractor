"""Loguru-based structured logging."""
from __future__ import annotations

import sys

from loguru import logger

from src.utils.config import get_settings


def setup_logging() -> None:
    """Configure loguru — call once at app startup."""
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )


__all__ = ["logger", "setup_logging"]
