"""Inter-rater agreement tests — Cohen & Fleiss κ (hand-checked)."""

from __future__ import annotations

import pytest

from manthan.core.metrics.agreement import (
    cohen_kappa,
    fleiss_kappa,
    pairwise_kappa_matrix,
)


@pytest.mark.unit
def test_cohen_kappa_perfect_and_hand_value():
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1.0)
    # Hand calc: po=0.75, pe=0.5 -> kappa=0.5
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(0.5)


@pytest.mark.unit
def test_cohen_kappa_empty_and_length_mismatch():
    assert cohen_kappa([], []) == 0.0
    with pytest.raises(ValueError):
        cohen_kappa([1, 2], [1])


@pytest.mark.unit
def test_cohen_kappa_all_same_label_pe_one():
    # Both raters always say the same single label -> pe==1 path.
    assert cohen_kappa(["a", "a", "a"], ["a", "a", "a"]) == 1.0
    assert cohen_kappa(["a", "a", "a"], ["a", "a", "b"]) == 0.0


@pytest.mark.unit
def test_fleiss_kappa_perfect_and_partial():
    assert fleiss_kappa([["a", "a", "a"], ["b", "b", "b"]]) == pytest.approx(1.0)
    k = fleiss_kappa([["a", "a", "a"], ["b", "b", "b"], ["a", "a", "b"]])
    assert -1.0 <= k <= 1.0
    assert fleiss_kappa([]) == 0.0
    assert fleiss_kappa([["a"]]) == 0.0  # single rater


@pytest.mark.unit
def test_fleiss_kappa_mismatched_rater_counts():
    with pytest.raises(ValueError):
        fleiss_kappa([["a", "a"], ["b"]])


@pytest.mark.unit
def test_pairwise_matrix():
    m = pairwise_kappa_matrix({"a": [1, 0, 1], "b": [1, 0, 1], "c": [0, 1, 0]})
    assert m[("a", "b")] == pytest.approx(1.0)
    assert ("a", "c") in m and ("b", "c") in m
