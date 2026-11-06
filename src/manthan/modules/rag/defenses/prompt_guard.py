"""Defense layer 2 — query-side & chunk injection screening (PRD §11, FR-R4).

Uses the input guard (DeBERTa by default, MockGuard in CI) to screen the query
and the retrieved chunks for injection, dropping flagged chunks and optionally
blocking an injected query.
"""

from __future__ import annotations

from manthan.core.judge.guard import Guard
from manthan.modules.rag.pipeline import Retrieved


def query_blocked(query: str, guard: Guard, threshold: float = 0.5) -> bool:
    """True if the query itself trips the injection guard."""
    return guard.classify(query) >= threshold


def screen_contexts(
    retrieved: list[Retrieved],
    guard: Guard,
    threshold: float = 0.5,
) -> list[Retrieved]:
    """Drop retrieved chunks the guard flags as injection."""
    return [r for r in retrieved if guard.classify(r.document.text) < threshold]
