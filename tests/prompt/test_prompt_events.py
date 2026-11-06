"""Prompt runner event log: stage/run binding, verdict timing, guard-pass link (plan Task 4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from manthan.core import events
from manthan.core.config import RootConfig
from manthan.core.judge.guard import MockGuard
from manthan.core.model import MockBackend
from manthan.core.model.recording import RecordingBackend
from manthan.core.store import Store
from manthan.modules.prompt.runner import run_prompt


@pytest.fixture
def prompt_run(tmp_path: Path) -> tuple[Store, list[dict[str, Any]]]:
    cfg = RootConfig()
    cfg.models.backend = "mock"
    cfg.prompt.strategies = ["crescendo"]
    cfg.prompt.objectives = ["obfuscated-injection"]  # always meets the guard (runner.py)
    cfg.prompt.use_defended_target = True
    store = Store(tmp_path / "m.db")
    cid = store.add_campaign("prompt", cfg.config_hash(), cfg.seed)
    log = tmp_path / "e.jsonl"
    events.start(log)
    run_prompt(cfg, RecordingBackend(MockBackend(0)), store, cid, guard=MockGuard(), smoke=True)
    events.stop()
    return store, events.read_events(log)[0]


def test_every_attack_event_names_a_stored_run(prompt_run) -> None:
    store, evs = prompt_run
    run_ids = {r["id"] for r in store.conn.execute("SELECT id FROM run")}
    attack = [e for e in evs if e.get("stage") == "attack" and e["kind"].startswith("model.")]
    assert attack and all(e["run_id"] in run_ids for e in attack)


def test_verdicts_have_times_and_run_ids(prompt_run) -> None:
    _, evs = prompt_run
    vs = [e for e in evs if e["kind"] == "verdict"]
    assert vs and all(e["started_at"] and e["duration_s"] >= 0 and e["run_id"] for e in vs)
    assert all(e["stage"] == "judging" for e in vs)


def test_guard_pass_links_to_first_pass(prompt_run) -> None:
    store, evs = prompt_run
    links = [e for e in evs if e["kind"] == "guard_pass.link"]
    assert links
    for e in links:
        g = store.conn.execute("SELECT target_label FROM run WHERE id=?", (e["run_id"],)).fetchone()
        p = store.conn.execute(
            "SELECT target_label FROM run WHERE id=?", (e["parent_run_id"],)
        ).fetchone()
        assert g[0].endswith("+guard") and not p[0].endswith("+guard")


def test_guard_score_event_has_threshold(prompt_run) -> None:
    _, evs = prompt_run
    gs = [e for e in evs if e["kind"] == "guard.score"]
    assert gs and all(e["threshold"] == 0.5 and isinstance(e["blocked"], bool) for e in gs)
