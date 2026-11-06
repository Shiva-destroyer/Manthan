"""RAG metrics: retrieval F1, leak rate (PRD §11, §14).

ASR/CI and detection P/R/F1 come from the shared core; these helpers add the
retrieval-quality and leak-rate measures specific to the RAG module.
"""

from __future__ import annotations

from manthan.core.metrics.detection import DetectionResult, detection_scores
from manthan.modules.rag.pipeline import Retrieved


def retrieval_scores(
    retrieved: list[Retrieved],
    relevant_ids: set[str],
    total_relevant: int | None = None,
) -> DetectionResult:
    """Precision/recall/F1 treating poison or off-topic chunks as false positives."""
    retrieved_ids = [r.document.id for r in retrieved]
    tp = sum(1 for rid in retrieved_ids if rid in relevant_ids)
    fp = len(retrieved_ids) - tp
    total_rel = total_relevant if total_relevant is not None else len(relevant_ids)
    fn = max(0, total_rel - tp)
    # tn is not meaningful for ranked retrieval; use 0 (precision/recall/F1 unaffected).
    return detection_scores(tp=tp, fp=fp, fn=fn, tn=0)


def leak_rate(leaked: int, trials: int) -> float:
    return leaked / trials if trials else 0.0
