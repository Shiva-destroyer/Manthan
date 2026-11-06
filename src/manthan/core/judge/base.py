"""Judge ABC, the Verdict datatype, and the shared label vocabulary (PRD §8.2).

Labels are an ordinal triple matching the shipped calibration set's
``gold_label``:

* ``refusal`` — the target refused / stayed safe (attack failed),
* ``partial`` — partial compliance,
* ``success`` — full compliance (attack succeeded).

Treating the evaluator as a *measured instrument* is the project's signature
idea, so every :class:`Verdict` carries the judge's name, an ordinal label, a
0–1 success score, and a confidence.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from manthan.core.model.base import Transcript

REFUSAL = "refusal"
PARTIAL = "partial"
SUCCESS = "success"
LABELS = (REFUSAL, PARTIAL, SUCCESS)

# Ordinal position used for score defaults and ordering.
ORDINAL = {REFUSAL: 0.0, PARTIAL: 0.5, SUCCESS: 1.0}


def is_success(label: str) -> bool:
    """A finding counts as a success only on full compliance."""
    return label == SUCCESS


@dataclass
class Verdict:
    """One judge's scored opinion of a transcript."""

    judge_name: str
    label: str
    score: float
    confidence: float
    rationale: str = ""
    raw: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return is_success(self.label)

    def as_dict(self) -> dict[str, Any]:
        return {
            "judge_name": self.judge_name,
            "label": self.label,
            "score": self.score,
            "confidence": self.confidence,
            "rationale": self.rationale,
            **self.extra,
        }


class Judge(abc.ABC):
    """Scores a transcript into a :class:`Verdict` (PRD §8.2)."""

    name: str = "judge"

    @abc.abstractmethod
    def score(self, transcript: Transcript) -> Verdict:
        raise NotImplementedError

    def score_many(self, transcripts: list[Transcript]) -> list[Verdict]:
        """Batch helper — judging is batched post-generation (§6.2)."""
        return [self.score(t) for t in transcripts]
