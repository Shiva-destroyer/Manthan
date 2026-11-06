"""P3 (session 4): RAG reuses the judge ensemble (FR-R6) and runs retrieval manipulation (FR-R3)."""

from __future__ import annotations

import pytest

from manthan.core.config import RootConfig
from manthan.core.judge import MockGuard
from manthan.core.judge.ensemble import JudgeEnsemble
from manthan.core.judge.refusal import RefusalJudge
from manthan.core.model import MockBackend
from manthan.core.store import Store
from manthan.modules.rag.pipeline import MockRagPipeline
from manthan.modules.rag.runner import run_rag


def _run(monkeypatch=None, indexed=None):
    cfg = RootConfig()
    cfg.models.backend = "mock"
    cfg.rag.n_trials = 1
    cfg.rag.attack.n_poison_max = 1
    store = Store.in_memory()
    cid = store.add_campaign("rag", cfg.config_hash(), cfg.seed)
    if monkeypatch is not None:
        real = MockRagPipeline.index

        def spy(self, docs):
            indexed.append([d.id for d in docs])
            return real(self, docs)

        monkeypatch.setattr(MockRagPipeline, "index", spy)
    ens = JudgeEnsemble([RefusalJudge()])
    run_rag(cfg, MockBackend(0), store, cid, guard=MockGuard(), ensemble=ens)
    return store, cid


@pytest.mark.integration
def test_rag_stores_ensemble_verdicts_on_answer_turns():
    store, cid = _run()
    rows = store.conn.execute(
        "SELECT t.role, v.judge_name FROM verdict v JOIN turn t ON t.id = v.turn_id"
        " JOIN run r ON r.id = t.run_id WHERE r.campaign_id = ? AND r.domain = 'rag'",
        (cid,),
    ).fetchall()
    assert rows and {r[0] for r in rows} == {"assistant"}
    assert {r[1] for r in rows} == {"refusal_baseline"}
    answers = store.conn.execute(
        "SELECT count(*) FROM turn t JOIN run r ON r.id = t.run_id"
        " WHERE r.campaign_id = ? AND r.domain = 'rag' AND t.role = 'assistant'"
        " AND r.objective_id NOT LIKE 'rag-qa-benign-%'",  # benign QA is scored by accuracy
        (cid,),
    ).fetchone()[0]
    assert len(rows) == answers  # one verdict per attack and leak answer
    m = {x["name"]: x["value"] for x in store.metrics_for_campaign(cid)}
    assert 0.0 <= m["rag_judge_agreement"] <= 1.0


@pytest.mark.integration
def test_rag_indexes_retrieval_manip_docs_and_stores_both_f1(monkeypatch):
    indexed: list[list[str]] = []
    store, cid = _run(monkeypatch, indexed)
    assert any(any(i.startswith("manip-") for i in ids) for ids in indexed)
    m = {x["name"]: x["value"] for x in store.metrics_for_campaign(cid)}
    assert {"retrieval_f1_clean", "retrieval_f1_manip"} <= set(m)
    f = [x for x in store.findings_for_campaign(cid) if x["strategy"] == "retrieval_manip"]
    assert len(f) == 1
    tags = {t["atlas_id"] for t in store.tags_for_campaign(cid) if t["finding_id"] == f[0]["id"]}
    assert tags == {"AML.T0066"}
