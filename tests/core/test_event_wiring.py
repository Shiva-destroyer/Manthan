"""Campaigns write an ordered event log when asked to (plan Task 3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from manthan.core import events
from manthan.core.cli import orchestrator
from manthan.core.cli.orchestrator import run_campaign
from manthan.core.config import RootConfig
from manthan.core.store import Store


def _mock_cfg() -> RootConfig:
    c = RootConfig()
    c.models.backend = "mock"
    return c


def test_campaign_writes_ordered_log(tmp_path: Path) -> None:
    store = Store(tmp_path / "m.db")
    man = run_campaign(_mock_cfg(), ["prompt"], store, smoke=True, events_dir=tmp_path)
    evs, _ = events.read_events(tmp_path / man.campaign_id / "events.jsonl")
    kinds = [e["kind"] for e in evs]
    assert kinds[0] == "campaign.start" and kinds[-1] == "campaign.end"
    assert evs[0]["pid"] > 0 and evs[-1]["status"] == "ok"
    assert {
        "domain.start",
        "phase.start",
        "model.request",
        "model.reply",
        "run.stored",
        "finding.stored",
        "metric.stored",
    } <= set(kinds)
    assert {e["role"] for e in evs if e["kind"] == "model.request"} >= {"attacker", "target"}


def test_campaign_end_written_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("x")

    monkeypatch.setattr(orchestrator, "_run_domain", boom)
    with pytest.raises(RuntimeError):
        run_campaign(
            _mock_cfg(), ["prompt"], Store(tmp_path / "m.db"), smoke=True, events_dir=tmp_path
        )
    (folder,) = [d for d in tmp_path.iterdir() if d.is_dir()]
    last = events.read_events(folder / "events.jsonl")[0][-1]
    assert (last["kind"], last["status"]) == ("campaign.end", "error")
    assert events.active() is None


def test_sigterm_writes_stopped_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def term(*a: object, **k: object) -> None:
        raise SystemExit(143)

    monkeypatch.setattr(orchestrator, "_run_domain", term)
    with pytest.raises(SystemExit):
        run_campaign(
            _mock_cfg(), ["prompt"], Store(tmp_path / "m.db"), smoke=True, events_dir=tmp_path
        )
    (folder,) = [d for d in tmp_path.iterdir() if d.is_dir()]
    assert events.read_events(folder / "events.jsonl")[0][-1]["status"] == "stopped"


def test_no_events_dir_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_campaign(_mock_cfg(), ["prompt"], Store.in_memory(), smoke=True)
    assert not list(tmp_path.rglob("events.jsonl"))
