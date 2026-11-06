"""Final-review fixes: liveness stamp, stream end event, stop grace, cid and offset checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from manthan.core import events
from manthan.core.cli.orchestrator import run_campaign
from manthan.core.config import RootConfig
from manthan.core.store import Store
from manthan.ui import actions, data
from manthan.ui.actions import ActionRunner


def _log(path: Path, **start: object) -> Path:
    path.write_text(
        json.dumps({"seq": 1, "kind": "campaign.start", **start}) + "\n", encoding="utf-8"
    )
    return path


def test_zombie_pid_is_not_running(tmp_path: Path) -> None:
    child = subprocess.Popen([sys.executable, "-c", "pass"])  # exits, not reaped: a zombie
    try:
        for _ in range(100):
            if Path(f"/proc/{child.pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
                break
            time.sleep(0.05)
        assert data.campaign_status(_log(tmp_path / "e.jsonl", pid=child.pid)) == "incomplete"
    finally:
        child.wait()


def test_reused_pid_is_not_running(tmp_path: Path) -> None:
    me = events.proc_stamp(os.getpid())
    assert me is not None
    same = _log(tmp_path / "a.jsonl", pid=os.getpid(), **me)
    other = _log(
        tmp_path / "b.jsonl", pid=os.getpid(), **{**me, "proc_start": me["proc_start"] + 1}
    )
    other_boot = _log(tmp_path / "c.jsonl", pid=os.getpid(), **{**me, "boot_id": "another-boot"})
    assert data.campaign_status(same) == "running"
    assert data.campaign_status(other) == "incomplete"
    assert data.campaign_status(other_boot) == "incomplete"


def test_log_without_stamp_still_reads_by_pid(tmp_path: Path) -> None:
    assert data.campaign_status(_log(tmp_path / "e.jsonl", pid=os.getpid())) == "running"


def test_campaign_start_carries_the_stamp(tmp_path: Path) -> None:
    cfg = RootConfig()
    cfg.models.backend = "mock"
    man = run_campaign(cfg, ["prompt"], Store(tmp_path / "m.db"), smoke=True, events_dir=tmp_path)
    first = events.read_events(tmp_path / man.campaign_id / "events.jsonl")[0][0]
    assert first["boot_id"] and isinstance(first["proc_start"], int)


def test_stream_ends_with_an_end_event(client, src, cid) -> None:
    with client.stream("GET", f"/api/campaigns/{cid}/events/stream?source={src}") as r:
        text = "".join(r.iter_text())
    assert text.rstrip().endswith('event: end\ndata: {"status": "ok"}')


def test_stream_end_event_on_dead_pid(client, src, cid, cut_log) -> None:
    with client.stream("GET", f"/api/campaigns/{cid}/events/stream?source={src}") as r:
        text = "".join(r.iter_text())
    assert text.rstrip().endswith('event: end\ndata: {"status": "incomplete"}')


class _Proc:
    pid = 77

    def __init__(self) -> None:
        self.timeouts: list[float | None] = []

    def poll(self) -> int | None:
        return None if not self.timeouts else 0

    def wait(self, timeout: float | None = None) -> int:
        self.timeouts.append(timeout)
        return 0


@pytest.mark.parametrize("name,grace", [("run", "RUN_STOP_GRACE_S"), ("init", "STOP_GRACE_S")])
def test_run_gets_the_longer_stop_grace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, grace: str
) -> None:
    proc = _Proc()
    monkeypatch.setattr(os, "killpg", lambda pid, sig: None)
    runner = ActionRunner(lambda argv, log: proc, tmp_path)
    runner.start(name, ["x"])
    runner.stop()
    assert proc.timeouts == [getattr(actions, grace)]
    assert actions.RUN_STOP_GRACE_S > actions.STOP_GRACE_S


@pytest.mark.parametrize("tail", ["", "/events", "/events/stream"])
def test_bad_campaign_id_is_422(client, src, tail) -> None:
    for bad in ("%2E%2E", "ui-actions", "A" * 32):
        r = client.get(f"/api/campaigns/{bad}{tail}?source={src}")
        assert r.status_code == 422, (bad, tail)


def test_negative_offset_is_422(client, src, cid) -> None:
    assert client.get(f"/api/campaigns/{cid}/events?source={src}&offset=-5").status_code == 422
    url = f"/api/campaigns/{cid}/events/stream?source={src}&offset=-5"
    assert client.get(url).status_code == 422
