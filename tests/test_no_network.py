"""AT-CORE6 — the suite runs with zero network and no paid key.

The autouse socket-blocking fixture (conftest) disables sockets for every
non-local_only test; this test proves it by asserting a socket open fails, and
asserts no paid-API key is required in the environment.
"""

from __future__ import annotations

import os
import socket

import pytest


@pytest.mark.unit
def test_sockets_are_blocked():
    with pytest.raises(Exception):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


@pytest.mark.unit
def test_backend_defaults_to_mock_in_ci():
    assert os.environ.get("MANTHAN_BACKEND") == "mock"


@pytest.mark.unit
def test_no_paid_api_key_required():
    # Manthan must run with NO paid key present. We prove the mock path builds a
    # backend and passes the backend guard without reading any hosted-API key.
    from manthan.core.config import RootConfig
    from manthan.core.model import make_backend

    cfg = RootConfig()
    cfg.models.backend = "mock"
    cfg.assert_backend_allowed()  # no opt-in, no key, no raise
    assert make_backend("mock").name == "mock"
