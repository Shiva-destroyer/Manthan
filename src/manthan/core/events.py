"""Per-campaign event log: one JSON object per line, written as the run goes.

The web UI replays and live-follows this file. ``emit`` is a no-op while no log is
active, so library code and tests pay nothing unless a campaign opts in.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any


class EventLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._fh: IO[str] = path.open("a", encoding="utf-8")
        self._lock = threading.Lock()
        self._seq = 0
        self._t0 = time.monotonic()

    def emit(self, kind: str, **fields: Any) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            ev: dict[str, Any] = {
                "seq": self._seq,
                "ts": datetime.now(UTC).isoformat(),
                "t": round(time.monotonic() - self._t0, 3),
                "kind": kind,
                **_bound,
                **fields,
            }
            self._fh.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
            self._fh.flush()
        return ev

    def close(self) -> None:
        with self._lock:
            self._fh.close()


_active: EventLog | None = None
# shortcut: bound fields are process-wide, not per thread; fine while one campaign runs
# per process, upgrade to contextvars if runs go concurrent.
_bound: dict[str, Any] = {}


def start(path: Path) -> EventLog:
    global _active
    stop()
    _active = EventLog(path)
    return _active


def stop() -> None:
    global _active
    if _active is not None:
        _active.close()
    _active = None
    _bound.clear()


def active() -> EventLog | None:
    return _active


def emit(kind: str, **fields: Any) -> None:
    if _active is not None:
        _active.emit(kind, **fields)


@contextmanager
def bind(**fields: Any) -> Iterator[None]:
    saved = dict(_bound)
    _bound.update(fields)
    try:
        yield
    finally:
        _bound.clear()
        _bound.update(saved)


def proc_stamp(pid: int) -> dict[str, Any] | None:
    """Boot id and start tick of a live, non-zombie process; tells it from a reused pid."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
        boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except (OSError, IndexError):
        return None
    if fields[0] == "Z":
        return None
    return {"boot_id": boot, "proc_start": int(fields[19])}  # field 22 of proc(5), after the ")"


def read_events(path: Path, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    """Complete events after ``offset`` and the new byte offset; a half-written last line waits."""
    with path.open("rb") as fh:
        fh.seek(offset)
        data = fh.read()
    end = data.rfind(b"\n") + 1
    out = [json.loads(line) for line in data[:end].decode("utf-8").splitlines() if line.strip()]
    return out, offset + end
