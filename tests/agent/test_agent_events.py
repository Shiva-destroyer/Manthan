"""Agent runner event log: trial events bound to stored runs (plan Task 5)."""

from __future__ import annotations

from pathlib import Path

from manthan.core import events
from manthan.core.config import RootConfig
from manthan.core.model import MockBackend
from manthan.core.model.recording import RecordingBackend
from manthan.core.store import Store
from manthan.modules.agent.runner import run_agent


def test_agent_trial_events_bound_to_stored_run(tmp_path: Path) -> None:
    cfg = RootConfig()
    cfg.models.backend = "mock"
    store = Store(tmp_path / "m.db")
    cid = store.add_campaign("agent", cfg.config_hash(), cfg.seed)
    log = tmp_path / "e.jsonl"
    events.start(log)
    run_agent(cfg, RecordingBackend(MockBackend(0)), store, cid, smoke=True)
    events.stop()
    evs = events.read_events(log)[0]
    run_ids = {r["id"] for r in store.conn.execute("SELECT id FROM run")}
    trial = [e for e in evs if e["kind"] == "run.stored" and e.get("attack_class")]
    assert trial and {e["run_id"] for e in trial} <= run_ids
