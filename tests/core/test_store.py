"""Store tests — round-trip, heatmap counts, JSONL export."""

from __future__ import annotations

import pytest

from manthan.core.judge.base import Verdict
from manthan.core.model.base import Transcript
from manthan.core.store import Finding, Store, export_jsonl


def _populate(store: Store) -> str:
    cid = store.add_campaign("prompt", "hash1", 1337, label="t")
    rid = store.add_run(cid, "reveal-system-prompt", "qwen2.5:7b", domain="prompt")
    tr = Transcript("reveal-system-prompt", "qwen2.5:7b", strategy="crescendo")
    tr.add("user", "probe")
    tr.add("assistant", "CANARY leaked")
    tids = store.add_transcript(rid, tr)
    store.add_verdicts(tids[-1], [Verdict("rubric", "success", 1.0, 0.9)])
    store.add_finding(
        Finding(
            run_id=rid,
            success=True,
            strategy="crescendo",
            objective_id="reveal-system-prompt",
            owasp=["LLM07"],
            atlas=["AML.T0051.000", "AML.T0054"],
        )
    )
    store.add_metric(rid, "asr", 1.0, 0.2, 1.0, method="wilson", seed=1337)
    return cid


@pytest.mark.unit
def test_store_round_trip_and_queries():
    s = Store.in_memory()
    cid = _populate(s)
    assert len(s.campaigns()) == 1
    assert s.get_campaign(cid)["config_hash"] == "hash1"
    runs = s.runs_for(cid)
    assert len(runs) == 1
    assert len(s.findings_for_campaign(cid)) == 1
    assert len(s.metrics_for_campaign(cid)) == 1
    assert len(s.turns_for_run(runs[0]["id"])) == 2
    assert len(s.verdicts_for_run(runs[0]["id"])) == 1


@pytest.mark.unit
def test_heatmap_counts_cross_product():
    s = Store.in_memory()
    cid = _populate(s)
    counts = s.heatmap_counts(cid)
    # one finding with 1 owasp x 2 atlas -> two heatmap cells
    assert counts[("LLM07", "AML.T0051.000")] == 1
    assert counts[("LLM07", "AML.T0054")] == 1


@pytest.mark.unit
def test_export_jsonl(tmp_path):
    s = Store.in_memory()
    cid = _populate(s)
    rid = s.runs_for(cid)[0]["id"]
    path = export_jsonl(s, rid, out_root=tmp_path)
    assert path.exists()
    lines = path.read_text().splitlines()
    assert len(lines) == 2  # two turns
    assert "verdicts" in lines[1]


@pytest.mark.unit
def test_store_file_backed(tmp_path):
    db = tmp_path / "x.db"
    s = Store(db)
    _populate(s)
    s.close()
    assert db.exists()
    s2 = Store(db)
    assert len(s2.campaigns()) == 1
    s2.close()
