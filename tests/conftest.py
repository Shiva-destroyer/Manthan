"""Test harness config (PRD §15.1).

- Forces ``MANTHAN_BACKEND=mock`` so every test is offline and $0.
- Registers the unit / integration / local_only markers.
- Skips ``local_only`` tests unless ``MANTHAN_BACKEND=ollama`` (live models on the laptop).
- Installs an autouse **socket-blocking** fixture (pytest-socket) for every
  non-``local_only`` test, so a stray network call becomes a test failure rather
  than a silent paid/online dependency. "Zero network" is enforced and
  self-testing (AT-CORE6).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("MANTHAN_BACKEND", "mock")

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: pure-logic, cloud-runnable, no network")
    config.addinivalue_line("markers", "integration: MockBackend multi-component, no network")
    config.addinivalue_line(
        "markers", "local_only: needs live Ollama/HF on the laptop; skipped in CI"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("MANTHAN_BACKEND") == "ollama":  # live-test opt-in (docs/running-locally.md)
        return
    skip_local = pytest.mark.skip(
        reason="local_only: needs live Ollama/HF model (see docs/running-locally.md)"
    )
    for item in items:
        if "local_only" in item.keywords:
            item.add_marker(skip_local)


@pytest.fixture(autouse=True)
def _enforce_no_network(request: pytest.FixtureRequest):
    """Block all sockets for non-local_only tests (pytest-socket)."""
    if "local_only" in request.keywords:
        yield
        return
    from pytest_socket import disable_socket, enable_socket

    disable_socket(allow_unix_socket=True)  # asyncio event loops need an AF_UNIX pair; no network
    try:
        yield
    finally:
        enable_socket()


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(autouse=True)
def _reset_event_log():
    """A failed test must not leak an active event log into the next one."""
    yield
    from manthan.core import events

    events.stop()
