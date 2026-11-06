"""P6: the live path's exfil sink is the real FastAPI app on 127.0.0.1, over HTTP."""

from __future__ import annotations

import json
import urllib.request

import pytest

from manthan.modules.agent.mock_exfil.server import HttpExfilListener, MockExfilListener


@pytest.fixture
def loopback_only():
    from pytest_socket import enable_socket, socket_allow_hosts

    enable_socket()
    socket_allow_hosts(["127.0.0.1"])  # the listener, nothing else
    yield


def test_http_listener_logs_attempts_and_stores_nothing(loopback_only, monkeypatch):
    pytest.importorskip("fastapi")  # the [agent] extra; CI installs only .[dev]
    pytest.importorskip("uvicorn")
    monkeypatch.setattr(MockExfilListener, "__init__", None)  # the in-process double is unused
    listener = HttpExfilListener()
    try:
        assert listener.url.startswith("http://127.0.0.1:")
        rec = listener.receive("attacker-sink", "SYNTH-KEY " + "x" * 100, {"step": 2})
        assert rec == {"status": "logged", "stored": False}
        assert listener.count == 1
        with urllib.request.urlopen(f"{listener.url}/log", timeout=5) as resp:
            log = json.load(resp)
        assert log["attempts"][0]["destination"] == "attacker-sink"
        assert log["attempts"][0]["payload_len"] == 110
        assert "x" * 100 not in json.dumps(log)  # only a 48-char preview is kept
    finally:
        listener.close()
