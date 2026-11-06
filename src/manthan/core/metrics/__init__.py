"""Metrics: ASR+CIs, κ, detection P/R/F1, evasion, telemetry ($0)."""

from manthan.core.metrics.agreement import (
    cohen_kappa,
    fleiss_kappa,
    pairwise_kappa_matrix,
)
from manthan.core.metrics.asr import (
    RateResult,
    asr,
    bootstrap_interval,
    rate_from_bools,
    wilson_interval,
)
from manthan.core.metrics.detection import (
    DefenseLayerResult,
    DetectionResult,
    detection_scores,
    evasion_score,
    false_positive_rate,
    scores_from_labels,
    utility_under_attack,
)
from manthan.core.metrics.telemetry import Telemetry, TelemetryResult, estimate_tokens

__all__ = [
    "asr",
    "RateResult",
    "wilson_interval",
    "bootstrap_interval",
    "rate_from_bools",
    "cohen_kappa",
    "fleiss_kappa",
    "pairwise_kappa_matrix",
    "detection_scores",
    "scores_from_labels",
    "DetectionResult",
    "DefenseLayerResult",
    "false_positive_rate",
    "evasion_score",
    "utility_under_attack",
    "Telemetry",
    "TelemetryResult",
    "estimate_tokens",
]
