"""$0 telemetry — wall-clock, tokens/sec, peak RSS. **No dollar accounting.**

Where the source blueprint tracked dollars, Manthan tracks time, throughput,
and memory (PRD §7.6, §8.3). The budget guard counts tokens and time, never
money, and the report's headline reads "Runtime cost: ₹0 / $0".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any


def _rss_mb() -> float:
    try:
        import psutil

        proc = psutil.Process()
        total = proc.memory_info().rss
        for child in proc.children(recursive=True):
            try:
                total += child.memory_info().rss
            except Exception:
                pass
        return total / (1024**2)
    except Exception:  # pragma: no cover
        return 0.0


@dataclass
class TelemetryResult:
    wall_clock_s: float = 0.0
    tokens: int = 0
    peak_rss_mb: float = 0.0
    cost_usd: float = 0.0  # always 0.0 — fully local, offline, CPU-only
    cost_inr: float = 0.0  # always 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens_per_sec(self) -> float:
        return self.tokens / self.wall_clock_s if self.wall_clock_s > 0 else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "wall_clock_s": round(self.wall_clock_s, 4),
            "tokens": self.tokens,
            "tokens_per_sec": round(self.tokens_per_sec, 3),
            "peak_rss_mb": round(self.peak_rss_mb, 2),
            "cost_usd": 0.0,
            "cost_inr": 0.0,
            **self.extra,
        }


class Telemetry:
    """Context manager that times a campaign and tracks tokens + peak RSS."""

    def __init__(self) -> None:
        self.result = TelemetryResult()
        self._start: float | None = None

    def __enter__(self) -> Telemetry:
        self._start = time.perf_counter()
        self.sample_rss()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.sample_rss()
        if self._start is not None:
            self.result.wall_clock_s = time.perf_counter() - self._start

    def add_tokens(self, n: int) -> None:
        self.result.tokens += max(0, int(n))

    def sample_rss(self) -> float:
        rss = _rss_mb()
        if rss > self.result.peak_rss_mb:
            self.result.peak_rss_mb = rss
        return rss


class BudgetExhausted(RuntimeError):
    """Raised between trials once the time or token budget is spent."""


class BudgetGuard:
    """Checks ``budget.yaml`` limits; callers call ``check()`` before each trial."""

    def __init__(self, max_wall_clock_min: float, max_tokens: int, backend: Any) -> None:
        self.max_wall_clock_min = max_wall_clock_min
        self.max_tokens = max_tokens
        self.backend = backend
        self.deadline = time.monotonic() + max_wall_clock_min * 60

    def check(self) -> None:
        if time.monotonic() >= self.deadline:
            raise BudgetExhausted(f"max_wall_clock_min={self.max_wall_clock_min} reached")
        used = getattr(self.backend, "tokens_used", 0)
        if used > self.max_tokens:
            raise BudgetExhausted(f"max_tokens={self.max_tokens} exceeded ({used} used)")


def estimate_tokens(text: str) -> int:
    """Cheap, offline token estimate (~4 chars/token). No tokenizer download."""
    if not text:
        return 0
    return max(1, len(text) // 4)
