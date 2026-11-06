"""Core metrics tests — ASR CIs (AT-CORE1), detection, evasion, telemetry."""

from __future__ import annotations

import pytest

from manthan.core.metrics import (
    Telemetry,
    asr,
    detection_scores,
    estimate_tokens,
    evasion_score,
    scores_from_labels,
    utility_under_attack,
)
from manthan.core.metrics.asr import bootstrap_interval, wilson_interval


@pytest.mark.unit
def test_wilson_ci_brackets_point():
    r = asr(7, 10)  # wilson default
    assert r.method == "wilson"
    assert r.ci_low <= r.point <= r.ci_high
    assert 0.0 <= r.ci_low and r.ci_high <= 1.0


@pytest.mark.unit
def test_at_core1_bootstrap_ci_and_seed_reproduces():
    """AT-CORE1: CI brackets the point estimate; seed reproduces exactly."""
    r1 = asr(7, 10, method="bootstrap", seed=42)
    r2 = asr(7, 10, method="bootstrap", seed=42)
    assert r1.ci_low <= r1.point <= r1.ci_high
    assert (r1.ci_low, r1.ci_high) == (r2.ci_low, r2.ci_high)  # reproducible
    # a different seed may differ, but still brackets the point
    r3 = asr(7, 10, method="bootstrap", seed=7)
    assert r3.ci_low <= r3.point <= r3.ci_high


@pytest.mark.unit
def test_asr_edges_and_zero_trials():
    assert asr(0, 0).point == 0.0
    r0 = asr(0, 10)
    assert r0.point == 0.0 and r0.ci_low == 0.0
    r1 = asr(10, 10)
    assert r1.point == 1.0 and r1.ci_high == 1.0
    assert bootstrap_interval(0, 5) == (0.0, 0.0)  # degenerate -> point
    assert wilson_interval(0, 0) == (0.0, 1.0)


@pytest.mark.unit
def test_asr_invalid_counts():
    with pytest.raises(ValueError):
        asr(11, 10)
    with pytest.raises(ValueError):
        asr(1, 2, method="nope")


@pytest.mark.unit
def test_detection_scores_hand_values():
    d = detection_scores(tp=8, fp=2, fn=1, tn=9)
    assert d.precision == pytest.approx(8 / 10)
    assert d.recall == pytest.approx(8 / 9)
    assert d.fpr == pytest.approx(2 / 11)
    assert d.accuracy == pytest.approx(17 / 20)
    # zero-denominator guards
    z = detection_scores(0, 0, 0, 0)
    assert z.precision == 0.0 and z.f1 == 0.0


@pytest.mark.unit
def test_scores_from_labels_and_helpers():
    d = scores_from_labels([True, True, False, False], [True, False, True, False])
    assert d.tp == 1 and d.fp == 1 and d.fn == 1 and d.tn == 1
    assert evasion_score(3, 6) == 0.5
    assert utility_under_attack(10, 4) == 0.4
    assert utility_under_attack(0, 4) == 0.0


@pytest.mark.unit
def test_telemetry_no_money_tokens_and_rss():
    with Telemetry() as t:
        t.add_tokens(100)
        t.add_tokens(50)
    assert t.result.tokens == 150
    assert t.result.cost_usd == 0.0 and t.result.cost_inr == 0.0
    assert t.result.wall_clock_s >= 0.0
    assert t.result.peak_rss_mb >= 0.0
    assert estimate_tokens("abcd" * 4) >= 1
    assert estimate_tokens("") == 0
