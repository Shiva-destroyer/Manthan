"""A2: the prompt runner scores all trials in a judging phase, after the generation models unload."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from manthan.core.config import RootConfig
from manthan.core.judge.ensemble import JudgeEnsemble
from manthan.core.judge.refusal import RefusalJudge
from manthan.core.model import MockBackend
from manthan.core.store import Store
from manthan.modules.prompt.runner import run_prompt


class PhaseRecorder:
    """Stands in for ModelSlotScheduler: records phase order and the phase now active."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.current: str | None = None

    @contextmanager
    def phase(self, name: str):
        prev, self.current = self.current, name
        self.order.append(name)
        try:
            yield self
        finally:
            self.current = prev


@pytest.mark.integration
def test_judge_calls_happen_only_in_the_judging_phase():
    sched = PhaseRecorder()
    judged_in: list[str | None] = []
    generated_in: list[str | None] = []

    class SpyEnsemble(JudgeEnsemble):
        def score(self, transcript):
            judged_in.append(sched.current)
            return super().score(transcript)

    class SpyBackend(MockBackend):
        def chat(self, model, messages, **kw):
            generated_in.append(sched.current)
            return super().chat(model, messages, **kw)

    cfg = RootConfig()
    cfg.models.backend = "mock"
    store = Store.in_memory()
    cid = store.add_campaign("prompt", cfg.config_hash(), cfg.seed)
    summary = run_prompt(
        cfg,
        SpyBackend(0),
        store,
        cid,
        ensemble=SpyEnsemble([RefusalJudge()]),
        scheduler=sched,
        smoke=True,
    )
    assert judged_in and set(judged_in) == {"judging"}
    assert generated_in and set(generated_in) == {"generation"}
    assert sched.order[:2] == ["generation", "judging"]
    assert len(store.findings_for_campaign(cid)) == summary["n_findings"] > 0


@pytest.mark.integration
def test_strategies_keep_their_per_turn_refusal_check_in_generation(monkeypatch):
    """The in-loop 0-RAM heuristic stays inside the attack loop; only the ensemble moves."""
    from manthan.modules.prompt.strategies.crescendo import Crescendo

    sched = PhaseRecorder()
    checked_in: list[str | None] = []
    orig = Crescendo._is_refusal

    def spy(self, response):
        checked_in.append(sched.current)
        return orig(self, response)

    monkeypatch.setattr(Crescendo, "_is_refusal", spy)
    cfg = RootConfig()
    cfg.models.backend = "mock"
    cfg.prompt.strategies = ["crescendo"]
    store = Store.in_memory()
    cid = store.add_campaign("prompt", cfg.config_hash(), cfg.seed)
    run_prompt(cfg, MockBackend(0), store, cid, ensemble=JudgeEnsemble([RefusalJudge()]),
               scheduler=sched, smoke=True)  # fmt: skip
    assert checked_in and set(checked_in) == {"generation"}
