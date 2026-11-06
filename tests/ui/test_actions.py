"""Fixed action list and the one-run lock (plan Task 9). No test starts a real run."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from manthan.ui import actions, data
from manthan.ui.actions import ActionRunner

ORIGIN = {"origin": "http://127.0.0.1:8765"}


class FakeProc:
    """Stands in for Popen: alive until ``code`` is set."""

    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self.code: int | None = None

    def poll(self) -> int | None:
        return self.code

    def wait(self, timeout: float | None = None) -> int:
        if self.code is None:
            raise subprocess.TimeoutExpired("fake", timeout or 0)
        return self.code


@pytest.fixture
def spawned() -> list[list[str]]:
    return []


@pytest.fixture
def proc() -> FakeProc:
    return FakeProc()


@pytest.fixture
def ui(client: TestClient, tmp_path: Path, spawned: list[list[str]], proc: FakeProc) -> TestClient:
    def fake_spawn(argv: list[str], log: Path) -> FakeProc:
        spawned.append(argv)
        log.write_text("hello from the run\n", encoding="utf-8")
        return proc

    client.app.state.runner = ActionRunner(fake_spawn, tmp_path / "logs")  # type: ignore[attr-defined]
    return client


@pytest.fixture
def cfg_dir(tmp_path: Path) -> Path:
    return tmp_path / "configs"


def post(c: TestClient, name: str, body: dict[str, Any] | None = None) -> Any:
    return c.post(f"/api/actions/{name}", json=body or {}, headers=ORIGIN)


def test_run_argv_is_exact(ui: TestClient, spawned: list[list[str]], cfg_dir: Path) -> None:
    body = {"target": "prompt", "smoke": True, "seed": 7, "skip": [], "config": "manthan.yaml"}
    r = post(ui, "run", body)
    assert r.status_code == 200
    assert spawned[-1][3:] == ["run", "prompt", "--smoke", "--seed", "7", "--config",
                               str(cfg_dir / "manthan.yaml")]  # fmt: skip
    assert spawned[-1][:3] == [actions.sys.executable, "-m", "manthan.core.cli.main"]


def test_run_skip_and_verbose(ui: TestClient, spawned: list[list[str]]) -> None:
    post(ui, "run", {"target": "all", "skip": ["agent", "rag"], "verbose": True})
    argv = spawned[-1][3:]
    assert argv[:2] == ["run", "all"] and argv.count("--skip") == 2 and "--verbose" in argv


def test_server_config_is_the_default(
    ui: TestClient, spawned: list[list[str]], cfg_dir: Path
) -> None:
    for name, body in [("run", {"target": "prompt"}), ("report", {"campaign_id": "a" * 32})]:
        post(ui, name, body)
        assert spawned[-1][-2:] == ["--config", str(cfg_dir / "manthan.yaml")]
        ui.app.state.runner._proc.code = 0  # type: ignore[attr-defined]


def test_extra_field_rejected(ui: TestClient, spawned: list[list[str]]) -> None:
    r = post(ui, "run", {"target": "prompt", "cmd": "rm -rf /"})
    assert r.status_code == 422 and not spawned


@pytest.mark.parametrize(
    "bad", ["../pyproject.toml", "/etc/passwd", "configs/../x.yaml", "missing.yaml"]
)
def test_config_path_traversal_rejected(ui: TestClient, spawned: list[list[str]], bad: str) -> None:
    assert post(ui, "run", {"target": "prompt", "config": bad}).status_code == 422
    assert not spawned


def test_bad_values_rejected(ui: TestClient) -> None:
    assert post(ui, "run", {"target": "shell"}).status_code == 422
    assert post(ui, "run", {"target": "prompt", "seed": -1}).status_code == 422
    assert post(ui, "run", {"target": "prompt", "skip": ["x"]}).status_code == 422
    assert post(ui, "report", {"campaign_id": "../x"}).status_code == 422
    assert post(ui, "judge", {"run_id": "A" * 32}).status_code == 422


def test_report_and_judge_argv(ui: TestClient, spawned: list[list[str]]) -> None:
    post(ui, "report", {"campaign_id": "a" * 32})
    assert spawned[-1][3:5] == ["report", "--campaign"] and spawned[-1][5] == "a" * 32
    ui.app.state.runner._proc.code = 0  # type: ignore[attr-defined]
    post(ui, "judge", {"run_id": "b" * 32})
    assert spawned[-1][3:6] == ["judge", "--run", "b" * 32]


def test_calibrate_adds_out_and_checks_labeled(
    ui: TestClient, spawned: list[list[str]], live_db: Path
) -> None:
    assert post(ui, "calibrate", {"labeled": "../../x.jsonl"}).status_code == 422
    assert post(ui, "calibrate", {"labeled": "nope.jsonl"}).status_code == 422
    assert not spawned
    r = post(ui, "calibrate", {"labeled": "labeled_set.jsonl", "split": "dev"})
    assert r.status_code == 200
    argv = spawned[-1]
    assert argv[3] == "calibrate" and argv[argv.index("--split") + 1] == "dev"
    assert argv[argv.index("--labeled") + 1] == str(actions.CALIBRATION_DIR / "labeled_set.jsonl")
    out = Path(argv[argv.index("--out") + 1])
    assert out.parent == live_db.parent and out.name.startswith("calibration-")


def test_init_and_models_pull_argv(ui: TestClient, spawned: list[list[str]]) -> None:
    post(ui, "init")
    assert spawned[-1][3:] == ["init"]
    ui.app.state.runner._proc.code = 0  # type: ignore[attr-defined]
    post(ui, "models_pull")
    assert spawned[-1][3:] == ["models", "pull"]


def test_unknown_action_404(ui: TestClient) -> None:
    assert post(ui, "shell").status_code == 404


def test_second_start_refused(ui: TestClient) -> None:
    assert post(ui, "init").status_code == 200
    r = post(ui, "init")
    assert r.status_code == 409 and "already" in r.json()["error"]


def test_finished_action_frees_the_lock(ui: TestClient, proc: FakeProc) -> None:
    post(ui, "init")
    proc.code = 0
    assert post(ui, "init").status_code == 200


def test_start_refused_while_terminal_run_active(
    ui: TestClient, live_pid_log: None, live_db: Path, spawned: list[list[str]]
) -> None:
    (log,) = live_db.parent.glob("*/events.jsonl")
    old = time.time() - 3600
    os.utime(log, (old, old))  # a quiet log is still a live run: the pid decides, not the age
    r = post(ui, "report", {"campaign_id": "a" * 32})
    assert r.status_code == 409 and "already" in r.json()["error"] and not spawned


def test_run_refused_when_preflight_fails(
    ui: TestClient, monkeypatch: pytest.MonkeyPatch, spawned: list[list[str]]
) -> None:
    monkeypatch.setattr(data, "ollama_ps", lambda url: [{"name": "qwen2.5:7b"}])
    r = post(ui, "run", {"target": "prompt"})
    assert r.status_code == 412 and r.json()["checks"] and not spawned
    assert post(ui, "report", {"campaign_id": "a" * 32}).status_code == 200  # only run is gated


def test_stop_signals_the_process_group(
    ui: TestClient, proc: FakeProc, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[int, int]] = []

    def killpg(pid: int, sig: int) -> None:
        sent.append((pid, sig))
        proc.code = -sig

    monkeypatch.setattr(os, "killpg", killpg)
    post(ui, "init")
    r = post(ui, "stop")
    assert r.status_code == 200 and r.json() == {"stopped": True, "signal": "SIGTERM"}
    assert sent == [(proc.pid, signal.SIGTERM)]


def test_stop_escalates_to_sigkill(
    ui: TestClient, proc: FakeProc, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[int] = []

    def killpg(pid: int, sig: int) -> None:
        sent.append(sig)
        if sig == signal.SIGKILL:
            proc.code = -9

    monkeypatch.setattr(os, "killpg", killpg)
    monkeypatch.setattr(actions, "STOP_GRACE_S", 0.01)
    post(ui, "init")
    assert post(ui, "stop").json()["signal"] == "SIGKILL"
    assert sent == [signal.SIGTERM, signal.SIGKILL]


def test_stop_with_nothing_running(ui: TestClient) -> None:
    assert post(ui, "stop").json() == {"stopped": False, "signal": None}


def test_current_and_preflight_shapes(ui: TestClient, proc: FakeProc) -> None:
    assert ui.get("/api/actions/current").json() is None
    post(ui, "init")
    cur = ui.get("/api/actions/current").json()
    assert cur["name"] == "init" and cur["pid"] == proc.pid and cur["exit_code"] is None
    assert cur["argv"][3:] == ["init"] and "hello from the run" in cur["log_tail"]
    proc.code = 3
    assert ui.get("/api/actions/current").json()["exit_code"] == 3
    pre = ui.get("/api/preflight").json()
    assert {"ok", "checks"} <= pre.keys() and pre["ok"] is True
    assert {c["name"] for c in pre["checks"]} == {"models_unloaded", "ram", "no_other_run"}


def test_preflight_sees_a_running_action(ui: TestClient) -> None:
    post(ui, "init")
    pre = ui.get("/api/preflight").json()
    assert pre["ok"] is False
    assert next(c for c in pre["checks"] if c["name"] == "no_other_run")["ok"] is False


def test_spawn_never_uses_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_popen(argv: list[str], **kw: Any) -> FakeProc:
        seen.update(kw, argv=argv)
        return FakeProc()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    actions.default_spawn(["x", "y"], tmp_path / "a.log")
    assert seen["shell"] is False and seen["start_new_session"] is True
    assert seen["argv"] == ["x", "y"]
