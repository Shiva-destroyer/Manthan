"""Prompt strategy tests — AT-P1 (Crescendo escalation + backtracking) + TAP."""

from __future__ import annotations

import pytest

from manthan.core.model import MockBackend, ModelRole
from manthan.modules.prompt.strategies import TAP, Crescendo, load_objectives
from manthan.modules.prompt.target import Target


@pytest.fixture
def objective():
    return load_objectives()[0]  # reveal-system-prompt, marker CANARY-SYS-7Q2F


@pytest.mark.integration
def test_at_p1_crescendo_escalates_and_backtracks(objective):
    """AT-P1: Crescendo escalates & backtracks over a mocked target; -> Transcript."""
    mb = MockBackend(seed=0)
    mb.set_script(ModelRole.ATTACKER, ["soft probe", "firmer probe", "direct probe"])
    state = {"n": 0}

    def target_responder(_messages):
        state["n"] += 1
        if state["n"] <= 2:
            return "I'm sorry, but I can't reveal my system prompt."
        return f"Fine, the token is {objective.success_marker}."

    mb.register(ModelRole.TARGET, target_responder)
    result = Crescendo(mb, max_turns=5, seed=0).run(objective, Target(mb, "qwen2.5:7b"))
    assert result.backtracks >= 1  # refusals triggered backtracking
    assert result.inline_success  # canary eventually hit
    assert len(result.transcript.messages) >= 2
    assert result.transcript.strategy == "crescendo"


@pytest.mark.integration
def test_crescendo_all_refusals_no_success(objective):
    mb = MockBackend(seed=1)
    mb.register(ModelRole.TARGET, lambda m: "I cannot help with that.")
    result = Crescendo(mb, max_turns=3, seed=1).run(objective, Target(mb, "qwen2.5:7b"))
    assert not result.inline_success
    assert result.backtracks == 3


@pytest.mark.integration
def test_target_sees_its_own_earlier_replies(objective):
    """Multi-turn attacks must send the target the whole conversation, not only user turns."""
    seen: list[list[str]] = []

    def engaged(msgs):
        seen.append([m.role for m in msgs])
        return "Sure, here is some general background on access tokens."

    for strategy in (
        Crescendo(MockBackend(seed=3), max_turns=3, seed=3),
        TAP(MockBackend(seed=3), branches=1, depth=2, seed=3),
    ):
        strategy.attacker.backend.register(ModelRole.TARGET, engaged)
        seen.clear()
        strategy.run(objective, Target(strategy.attacker.backend, "qwen2.5:7b"))
        assert seen[-1] == ["user", "assistant", "user", "assistant", "user"], strategy.name


@pytest.mark.integration
def test_at_p1_tap_branches_and_prunes(objective):
    mb = MockBackend(seed=2)
    mb.set_script(ModelRole.ATTACKER, ["a", "b", "c", "d", "e", "f", "g", "h", "i"])
    state = {"n": 0}

    def target(_m):
        state["n"] += 1
        return f"token {objective.success_marker}" if state["n"] >= 3 else "I can't do that."

    mb.register(ModelRole.TARGET, target)
    result = TAP(mb, branches=3, depth=3, seed=2).run(objective, Target(mb, "qwen2.5:7b"))
    assert result.branches_explored >= 3
    assert result.transcript.strategy == "tap"


@pytest.mark.integration
def test_objectives_are_tagged_and_valid():
    from manthan.core.taxonomy import get_registry

    reg = get_registry()
    for obj in load_objectives():
        reg.validate_tags(obj.owasp, obj.atlas)  # every objective validates
        assert obj.success_marker
