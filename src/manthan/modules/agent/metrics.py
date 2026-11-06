"""Agent metrics: ASR/class, utility-under-attack, aggregate detection P/R.

Thin helpers over the shared core (PRD §10.4, §14).
"""

from __future__ import annotations

from manthan.core.metrics.detection import (
    DetectionResult,
    detection_scores,
    utility_under_attack,
)
from manthan.modules.agent.detect.runtime_monitor import MonitorResult

__all__ = ["aggregate_monitor", "utility_under_attack"]


def aggregate_monitor(results: list[MonitorResult]) -> DetectionResult:
    """Pool confusion-matrix counts across trajectories into one P/R/F1/FPR."""
    tp = fp = fn = tn = 0
    for r in results:
        tp += r.scores.tp
        fp += r.scores.fp
        fn += r.scores.fn
        tn += r.scores.tn
    return detection_scores(tp=tp, fp=fp, fn=fn, tn=tn)
