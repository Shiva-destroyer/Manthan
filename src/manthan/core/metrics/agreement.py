"""Inter-rater agreement: Cohen's κ (pairwise) and Fleiss' κ (collective).

Implemented from first principles so the core stays lean (no scikit-learn).
Used by the judge ensemble to quantify how much the judges agree (PRD §8.2,
§14). κ > 0.6 is the "substantial agreement" target.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


def cohen_kappa(a: Sequence[Any], b: Sequence[Any]) -> float:
    """Cohen's κ between two equal-length label sequences."""
    if len(a) != len(b):
        raise ValueError("rater sequences must be the same length")
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca = Counter(a)
    cb = Counter(b)
    labels = set(ca) | set(cb)
    pe = sum((ca.get(k, 0) / n) * (cb.get(k, 0) / n) for k in labels)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def pairwise_kappa_matrix(
    raters: Mapping[str, Sequence[Any]],
) -> dict[tuple[str, str], float]:
    """Cohen's κ for every ordered-unique pair of raters."""
    names = list(raters)
    out: dict[tuple[str, str], float] = {}
    for i, ni in enumerate(names):
        for nj in names[i + 1 :]:
            out[(ni, nj)] = cohen_kappa(raters[ni], raters[nj])
    return out


def _counts_table(ratings: Sequence[Sequence[Any]], categories: list[Any]) -> list[list[int]]:
    table: list[list[int]] = []
    cat_index = {c: i for i, c in enumerate(categories)}
    for subject in ratings:
        row = [0] * len(categories)
        for label in subject:
            row[cat_index[label]] += 1
        table.append(row)
    return table


def fleiss_kappa(ratings: Sequence[Sequence[Any]], categories: list[Any] | None = None) -> float:
    """Fleiss' κ for ``ratings`` = one list of category labels per subject.

    Every subject must have the same number of ratings (judges).
    """
    ratings = [list(r) for r in ratings if len(list(r)) > 0]
    n_subjects = len(ratings)
    if n_subjects == 0:
        return 0.0
    n_raters = len(ratings[0])
    if n_raters <= 1:
        return 0.0
    if any(len(r) != n_raters for r in ratings):
        raise ValueError("every subject must have the same number of ratings for Fleiss' κ")
    if categories is None:
        categories = sorted({lab for subj in ratings for lab in subj}, key=str)
    table = _counts_table(ratings, categories)

    # Proportion of all assignments to each category.
    total = n_subjects * n_raters
    p_j = [sum(table[i][j] for i in range(n_subjects)) / total for j in range(len(categories))]
    # Agreement per subject.
    p_i = [
        (sum(c * c for c in table[i]) - n_raters) / (n_raters * (n_raters - 1))
        for i in range(n_subjects)
    ]
    p_bar = sum(p_i) / n_subjects
    pe_bar = sum(p * p for p in p_j)
    if pe_bar >= 1.0:
        return 1.0 if p_bar >= 1.0 else 0.0
    return (p_bar - pe_bar) / (1.0 - pe_bar)
