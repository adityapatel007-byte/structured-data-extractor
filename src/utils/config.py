"""Centralized configuration loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    """Application settings — loaded once at startup."""

    # OpenAI
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-5-nano"))
    openai_vision_model: str = Field(
        default_factory=lambda: os.getenv("OPENAI_VISION_MODEL", "gpt-5-nano")
    )
    openai_max_retries: int = Field(
        default_factory=lambda: int(os.getenv("OPENAI_MAX_RETRIES", "3"))
    )
    openai_request_timeout: int = Field(
        default_factory=lambda: int(os.getenv("OPENAI_REQUEST_TIMEOUT", "60"))
    )

    # App
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    api_host: str = Field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = Field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    streamlit_port: int = Field(
        default_factory=lambda: int(os.getenv("STREAMLIT_PORT", "8501"))
    )

    # Pricing (gpt-5-nano defaults; override in .env when swapping models)
    cost_per_1k_input: float = Field(
        default_factory=lambda: float(os.getenv("COST_PER_1K_INPUT_TOKENS", "0.00005"))
    )
    cost_per_1k_output: float = Field(
        default_factory=lambda: float(os.getenv("COST_PER_1K_OUTPUT_TOKENS", "0.00040"))
    )

    # SEC (v2)
    sec_user_agent: str = Field(
        default_factory=lambda: os.getenv(
            "SEC_USER_AGENT", "ASP Research adityapatel1801@gmail.com"
        )
    )

    def validate_ready(self) -> None:
        """Raise if the app isn't ready to run — call at startup."""
        if not self.openai_api_key or self.openai_api_key.startswith("sk-your-key"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and paste your key."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton — call this everywhere instead of instantiating Settings."""
    return Settings()
