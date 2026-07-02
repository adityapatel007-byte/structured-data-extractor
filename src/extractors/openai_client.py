"""Thin wrapper around OpenAI's structured-outputs API with retries + metrics.

We use `client.beta.chat.completions.parse` which:
- Takes a Pydantic model as `response_format`
- Handles JSON Schema translation + strict-mode transformation automatically
- Returns a validated Pydantic instance (`.choices[0].message.parsed`)
"""
from __future__ import annotations

from typing import Any

from openai import APIError, OpenAI, RateLimitError
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.utils.config import get_settings
from src.utils.cost_tracker import ExtractionMetrics, Timer
from src.utils.logging import logger

# --- Retry policy -----------------------------------------------------------
# Retry on rate limits + transient API errors. Do NOT retry on validation or
# 4xx auth errors — those won't fix themselves.
_RETRYABLE = (RateLimitError, APIError)


class OpenAIExtractionClient:
    """Wraps the OpenAI client. One instance per app (created at startup)."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        s = get_settings()
        self._client = OpenAI(
            api_key=api_key or s.openai_api_key,
            timeout=s.openai_request_timeout,
        )
        self._default_model = model or s.openai_model
        self._max_retries = s.openai_max_retries

    # ------------------------------------------------------------------

    def parse_structured(
        self,
        *,
        response_format: type[BaseModel],
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[BaseModel, ExtractionMetrics]:
        """Call OpenAI with structured outputs; return (parsed_object, metrics).

        - `response_format` is a Pydantic model class (envelope schema).
        - `messages` is standard OpenAI messages list, may include vision content.
        - `temperature=0` for reproducibility on extraction workloads.
        """
        active_model = model or self._default_model

        @retry(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(_RETRYABLE),
            reraise=True,
        )
        def _call():
            return self._client.beta.chat.completions.parse(
                model=active_model,
                messages=messages,
                response_format=response_format,
                temperature=temperature,
            )

        with Timer() as t:
            response = _call()

        parsed = response.choices[0].message.parsed
        if parsed is None:
            # Model refused or returned unparseable — surface the refusal.
            refusal = getattr(response.choices[0].message, "refusal", None)
            raise RuntimeError(
                f"Model returned no parsed output (model={active_model}). "
                f"Refusal: {refusal!r}"
            )

        usage = response.usage
        metrics = ExtractionMetrics(
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=t.elapsed_ms,
            model=active_model,
        )

        logger.info(
            f"OpenAI call OK: model={active_model} "
            f"tokens={metrics.input_tokens}+{metrics.output_tokens} "
            f"latency={metrics.latency_ms:.0f}ms cost=${metrics.cost_usd:.5f}"
        )
        return parsed, metrics
