"""Mock exfiltration listener (PRD §10.1, NFR-6).

The ONLY network destination the sandboxed agent can reach. It **logs** what was
attempted and **stores nothing real** — there is no onward route. The live path
serves the FastAPI app on 127.0.0.1 (:class:`HttpExfilListener`); offline tests
use the in-process :class:`MockExfilListener` double.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from manthan.modules.agent.mock_exfil.exfil_log import log_attempt as _log_attempt


@dataclass
class MockExfilListener:
    """In-process sink that records exfil attempts and keeps nothing real."""

    attempts: list[dict[str, Any]] = field(default_factory=list)

    def receive(self, destination: str, payload: str, meta: dict | None = None) -> dict:
        return _log_attempt(self.attempts, destination, payload, meta)

    @property
    def count(self) -> int:
        return len(self.attempts)


def build_app():
    """FastAPI app for the live mock-exfil sink."""
    try:
        from fastapi import Body, FastAPI  # type: ignore
    except ImportError as exc:
        raise RuntimeError("mock-exfil server needs the '[agent]' extra (fastapi).") from exc
    app = FastAPI(title="manthan-mock-exfil")
    attempts: list[dict[str, Any]] = []

    # A builtin annotation: with postponed annotations FastAPI cannot see a local Request.
    @app.post("/exfil")
    async def exfil(data: dict[str, Any] = Body(...)):  # noqa: B008
        return _log_attempt(
            attempts,
            destination=str(data.get("destination", "unknown")),
            payload=str(data.get("payload", "")),
            meta=data.get("meta"),
        )

    @app.get("/log")
    async def log():
        return {"attempts": attempts, "count": len(attempts)}

    return app


class HttpExfilListener:
    """Serves :func:`build_app` on 127.0.0.1 (a free port); sends go over real HTTP."""

    def __init__(self, host: str = "127.0.0.1", start_timeout_s: float = 10.0) -> None:
        import uvicorn

        self._server = uvicorn.Server(
            uvicorn.Config(build_app(), host=host, port=0, log_level="warning")
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        deadline = time.monotonic() + start_timeout_s
        while not self._server.started:
            if time.monotonic() > deadline or not self._thread.is_alive():
                raise RuntimeError("mock-exfil listener did not start on 127.0.0.1")
            time.sleep(0.05)
        port = self._server.servers[0].sockets[0].getsockname()[1]
        self.url = f"http://{host}:{port}"

    def _request(self, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body, default=str).encode()
        req = urllib.request.Request(
            self.url + path, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)

    def receive(self, destination: str, payload: str, meta: dict | None = None) -> dict:
        return self._request(
            "/exfil", {"destination": destination, "payload": payload, "meta": meta}
        )

    @property
    def count(self) -> int:
        return int(self._request("/log")["count"])

    def close(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
