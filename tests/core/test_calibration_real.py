"""P2 (session 4): the real labeled set drawn from stored campaign replies."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from manthan.core.cli.main import app
from manthan.core.judge.base import LABELS
from manthan.core.judge.ensemble import (
    REAL_LABELED_SET,
    _item_to_transcript,
    compute_calibration,
    load_labeled_set,
)


@pytest.fixture(scope="module")
def rows():
    return load_labeled_set(REAL_LABELED_SET)


def test_real_set_rows_carry_gold_split_provenance(rows):
    assert len(rows) == 88
    for r in rows:
        assert r["gold_label"] in LABELS
        assert r["split"] in ("dev", "test")
        assert r["labeler"] == "claude"
        assert {"db", "run", "turn"} <= set(r["provenance"])
        tr = _item_to_transcript(r)
        assert tr.messages[-1].content == r["transcript"]["messages"][-1]["content"]
        assert "success_marker" not in tr.metadata  # judges never see the marker


def test_real_set_splits_are_disjoint_by_conversation(rows):
    dev = {r["group"] for r in rows if r["split"] == "dev"}
    test = {r["group"] for r in rows if r["split"] == "test"}
    assert dev and test and not dev & test
    replies = {}
    for r in rows:  # an identical reply never sits on both sides
        replies.setdefault(r["transcript"]["messages"][-1]["content"].strip(), set()).add(
            r["split"]
        )
    assert all(len(s) == 1 for s in replies.values())


def test_calibration_on_hand_checked_slice(rows):
    by_id = {r["id"]: r for r in rows}
    ids = ["p8-6aa58835", "p8-e737de95", "p8-615b5850", "p8-da36e411", "p8-3823cff5",
           "postfix-4e525bf6"]  # fmt: skip
    gold = [by_id[i]["gold_label"] for i in ids]
    assert gold == ["success", "partial", "refusal", "success", "refusal", "success"]
    a = ["success", "success", "refusal", "success", "refusal", "refusal"]
    rep = compute_calibration({"a": a, "b": list(gold)}, gold)
    assert rep.per_judge["a"].fpr == pytest.approx(1 / 3)  # 1 FP of 3 negatives
    assert rep.per_judge["a"].tpr == pytest.approx(2 / 3)
    assert rep.per_judge["b"].fpr == 0.0
    assert rep.pairwise_kappa["a|b"] == pytest.approx(3 / 7)  # po=4/6, pe=15/36
    assert rep.fleiss_kappa == pytest.approx(17 / 41)  # P=96/144, Pe=62/144


def test_calibrate_cli_reads_real_set_test_split():
    res = CliRunner().invoke(
        app, ["calibrate", "--labeled", str(REAL_LABELED_SET), "--split", "test"]
    )
    assert res.exit_code == 0, res.output
    assert "n=48" in res.output
