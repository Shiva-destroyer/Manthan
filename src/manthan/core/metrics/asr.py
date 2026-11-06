"""Attack Success Rate with confidence intervals (PRD §8.3, §14).

Default CI is the **Wilson score interval** — robust for a binomial proportion
including small N and the 0% / 100% edges. A **seeded percentile bootstrap**
(``scipy.stats.bootstrap``) is offered for distributional reporting and for
non-proportion statistics. Every rate carries the method and seed used, so a
run reproduces exactly (FR-C6, NFR-5).
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import stats


@dataclass
class RateResult:
    """A proportion with a confidence interval and full provenance."""

    point: float
    ci_low: float
    ci_high: float
    method: str
    confidence: float
    successes: int
    trials: int
    seed: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "point": self.point,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "method": self.method,
            "confidence": self.confidence,
            "successes": self.successes,
            "trials": self.trials,
            "seed": self.seed,
            **self.extra,
        }

    def __str__(self) -> str:
        return (
            f"{self.point:.3f} "
            f"[{self.ci_low:.3f}, {self.ci_high:.3f}] "
            f"({self.method}, {int(self.confidence * 100)}% CI, n={self.trials})"
        )


def _z(confidence: float) -> float:
    return float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))


def wilson_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if trials <= 0:
        return (0.0, 1.0)
    z = _z(confidence)
    p = successes / trials
    denom = 1.0 + z * z / trials
    center = (p + z * z / (2 * trials)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    low = max(0.0, center - half)
    high = min(1.0, center + half)
    # Snap tiny floating-point drift at the boundaries (e.g. 0.9999999999999999
    # for successes==trials) so the closed interval ends exactly at 0.0 / 1.0.
    if abs(high - 1.0) < 1e-9:
        high = 1.0
    if abs(low) < 1e-9:
        low = 0.0
    return (low, high)


def bootstrap_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
    seed: int = 0,
    n_resamples: int = 2000,
) -> tuple[float, float]:
    """Seeded percentile bootstrap CI over the 0/1 outcome vector."""
    if trials <= 0:
        return (0.0, 1.0)
    data = np.array([1] * successes + [0] * (trials - successes), dtype=float)
    if np.all(data == data[0]):
        # Degenerate (all 0 or all 1): bootstrap CI collapses to the point.
        p = float(data[0])
        return (p, p)
    rng = np.random.default_rng(seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = stats.bootstrap(
            (data,),
            np.mean,
            confidence_level=confidence,
            n_resamples=n_resamples,
            method="percentile",
            random_state=rng,
        )
    low = float(res.confidence_interval.low)
    high = float(res.confidence_interval.high)
    return (max(0.0, low), min(1.0, high))


def asr(
    successes: int,
    trials: int,
    method: str = "wilson",
    confidence: float = 0.95,
    seed: int = 0,
    n_resamples: int = 2000,
) -> RateResult:
    """Attack Success Rate as a :class:`RateResult` with a 95% CI by default."""
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError(f"invalid counts: successes={successes}, trials={trials}")
    point = successes / trials if trials else 0.0
    method = method.lower()
    if method == "wilson":
        low, high = wilson_interval(successes, trials, confidence)
        used_seed: int | None = None
    elif method == "bootstrap":
        low, high = bootstrap_interval(successes, trials, confidence, seed, n_resamples)
        used_seed = seed
    else:
        raise ValueError(f"unknown CI method: {method!r} (expected 'wilson' or 'bootstrap')")
    return RateResult(
        point=point,
        ci_low=low,
        ci_high=high,
        method=method,
        confidence=confidence,
        successes=successes,
        trials=trials,
        seed=used_seed,
    )


def rate_from_bools(outcomes: list[bool], **kw: Any) -> RateResult:
    """Convenience: ASR from a list of boolean outcomes."""
    trials = len(outcomes)
    successes = sum(1 for o in outcomes if o)
    return asr(successes, trials, **kw)
