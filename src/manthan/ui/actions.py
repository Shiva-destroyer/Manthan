"""D4: the only things the page can start. A fixed list, typed bodies, no shell, one at a time."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

STOP_GRACE_S = 10.0
RUN_STOP_GRACE_S = 120.0  # a run closes its lab (compose down) before it writes campaign.end
LOG_TAIL_BYTES = 4096
CALIBRATION_DIR = Path(__file__).resolve().parents[1] / "core" / "calibration"
_ID = r"^[0-9a-f]{32}$"

Domain = Literal["prompt", "agent", "rag"]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunAction(_Body):
    target: Literal["prompt", "agent", "rag", "all"]
    smoke: bool = False
    seed: int | None = Field(None, ge=0, le=2**31 - 1)
    skip: list[Domain] = []
    config: str | None = None
    verbose: bool = False


class ReportAction(_Body):
    campaign_id: str = Field(pattern=_ID)


class JudgeAction(_Body):
    run_id: str = Field(pattern=_ID)


class CalibrateAction(_Body):
    labeled: str | None = None
    split: Literal["dev", "test"] | None = None


class InitAction(_Body):
    pass


class ModelsPullAction(_Body):
    pass


ACTIONS: dict[str, type[_Body]] = {
    "run": RunAction,
    "report": ReportAction,
    "judge": JudgeAction,
    "calibrate": CalibrateAction,
    "init": InitAction,
    "models_pull": ModelsPullAction,
}


def _named_file(name: str, folder: Path, suffix: str) -> Path:
    """A plain file name that sits directly in ``folder``; anything else is a ValueError."""
    path = folder / name
    ok = Path(name).name == name and name.endswith(suffix) and path.is_file()
    if not ok or path.resolve().parent != folder.resolve():
        raise ValueError(f"{name!r} is not a {suffix} file in {folder.name}/")
    return path


def build_argv(
    name: str,
    action: BaseModel,
    cfg_dir: Path,
    results_dir: Path | None = None,
    base_config: Path | None = None,
) -> list[str]:
    """The exact command for one action. ``base_config`` is the config this server was started with."""
    argv = [sys.executable, "-m", "manthan.core.cli.main"]
    cfg = base_config
    if isinstance(action, RunAction):
        if action.config:
            cfg = _named_file(action.config, cfg_dir, ".yaml")
        argv += ["run", action.target]
        if action.smoke:
            argv.append("--smoke")
        if action.seed is not None:
            argv += ["--seed", str(action.seed)]
        for domain in action.skip:
            argv += ["--skip", domain]
        if action.verbose:
            argv.append("--verbose")
    elif isinstance(action, ReportAction):
        argv += ["report", "--campaign", action.campaign_id]
    elif isinstance(action, JudgeAction):
        argv += ["judge", "--run", action.run_id]
    elif isinstance(action, CalibrateAction):
        argv.append("calibrate")
        if action.labeled:
            argv += ["--labeled", str(_named_file(action.labeled, CALIBRATION_DIR, ".jsonl"))]
        if action.split:
            argv += ["--split", action.split]
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out = (results_dir or Path("data/results")) / f"calibration-{stamp}.json"
        argv += ["--out", str(out)]
    elif name == "init":
        argv.append("init")
    elif name == "models_pull":
        argv += ["models", "pull"]
    else:
        raise ValueError(f"unknown action: {name!r}")
    if cfg is not None and name != "init" and name != "models_pull":
        argv += ["--config", str(cfg)]
    return argv


class Busy(Exception):
    """An action from this server is still running."""


Spawn = Callable[[list[str], Path], Any]


def default_spawn(argv: list[str], log_path: Path) -> subprocess.Popen[bytes]:
    """Own process group, so Stop also reaches children such as garak or compose."""
    with log_path.open("wb") as log:
        return subprocess.Popen(  # noqa: S603 - argv built from the fixed list above
            argv,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            shell=False,
            start_new_session=True,
        )


def _tail(path: Path) -> str:
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - LOG_TAIL_BYTES))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


class ActionRunner:
    def __init__(self, spawn: Spawn, log_dir: Path) -> None:
        self._spawn = spawn
        self._log_dir = log_dir
        self._lock = threading.Lock()
        self._proc: Any = None
        self._info: dict[str, Any] = {}

    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self, name: str, argv: list[str]) -> dict[str, Any]:
        with self._lock:
            if self.running():
                raise Busy(f"{self._info['name']} is already running")
            self._log_dir.mkdir(parents=True, exist_ok=True)
            started = datetime.now(UTC)
            log = self._log_dir / f"{name}-{started:%Y%m%dT%H%M%S}.log"
            self._proc = self._spawn(argv, log)
            self._info = {
                "name": name,
                "argv": argv,
                "pid": self._proc.pid,
                "started_at": started.isoformat(),
                "log": log,
            }
        return self.current() or {}

    def current(self) -> dict[str, Any] | None:
        if self._proc is None:
            return None
        keys = ("name", "argv", "pid", "started_at")
        return {
            **{k: self._info[k] for k in keys},
            "exit_code": self._proc.poll(),
            "log_tail": _tail(self._info["log"]),
        }

    def stop(self) -> dict[str, Any]:
        """SIGTERM to the whole group; SIGKILL if it is still there after the grace time."""
        if not self.running():
            return {"stopped": False, "signal": None}
        pid = self._proc.pid
        grace = RUN_STOP_GRACE_S if self._info["name"] == "run" else STOP_GRACE_S
        sent = "SIGTERM"
        try:
            os.killpg(pid, signal.SIGTERM)
            try:
                self._proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                sent = "SIGKILL"
                os.killpg(pid, signal.SIGKILL)
                self._proc.wait(timeout=grace)
        except ProcessLookupError:  # it exited between our check and the signal
            pass
        return {"stopped": True, "signal": sent}
