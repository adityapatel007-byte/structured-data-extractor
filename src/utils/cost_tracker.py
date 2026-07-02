"""Track token usage + cost per extraction."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from src.utils.config import get_settings


@dataclass
class ExtractionMetrics:
    """Metrics for a single extraction call."""

    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    model: str = ""
    cost_usd: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        s = get_settings()
        self.cost_usd = (
            (self.input_tokens / 1000) * s.cost_per_1k_input
            + (self.output_tokens / 1000) * s.cost_per_1k_output
        )

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "latency_ms": round(self.latency_ms, 1),
            "cost_usd": round(self.cost_usd, 6),
            "model": self.model,
        }


class Timer:
    """Context manager for measuring wall-clock latency in ms."""

    def __enter__(self) -> "Timer":
        self._start = perf_counter()
        self.elapsed_ms = 0.0
        return self

    def __exit__(self, *_exc) -> None:
        self.elapsed_ms = (perf_counter() - self._start) * 1000
