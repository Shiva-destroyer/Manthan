"""C3 prep: the non-smoke ASR-vs-N curve pools every target, and N=0 is a valid point."""

from __future__ import annotations

from manthan.core.config import RootConfig
from manthan.core.judge import MockGuard
from manthan.core.model import MockBackend
from manthan.core.store import Store
from manthan.modules.rag import runner as rag_runner


def test_curve_runs_every_target_from_n0(monkeypatch):
    calls: list[tuple[str, int]] = []
    orig = rag_runner._run_attack

    def spy(pipeline, clean_docs, target, n, *a, **kw):
        calls.append((target.marker, n))
        return orig(pipeline, clean_docs, target, n, *a, **kw)

    monkeypatch.setattr(rag_runner, "_run_attack", spy)
    cfg = RootConfig()
    cfg.models.backend = "mock"
    cfg.rag.n_trials = 1
    cfg.rag.attack.n_poison_min = 0
    cfg.rag.attack.n_poison_max = 1
    store = Store.in_memory()
    cid = store.add_campaign("rag", cfg.config_hash(), cfg.seed)
    summary = rag_runner.run_rag(cfg, MockBackend(0), store, cid, guard=MockGuard())
    markers = {t.marker for t in rag_runner._load_targets()}
    assert len(markers) == 3
    assert {(m, n) for m in markers for n in (0, 1)} <= set(calls)
    curve = {p["n_poison"]: p for p in summary["asr_vs_n"]}
    assert set(curve) == {0, 1}
    assert curve[0]["trials"] == curve[1]["trials"] == 3  # 3 targets x 1 trial
    names = {m["name"] for m in store.metrics_for_campaign(cid)}
    assert {"asr_n0", "asr_n1"} <= names
