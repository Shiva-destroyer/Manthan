"""RecordingBackend: pass-through wrapper that logs model traffic (plan Task 2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from manthan.core import events
from manthan.core.model import ChatMessage, MockBackend, ModelRole
from manthan.core.model.recording import RecordingBackend


def test_name_and_tokens_read_through() -> None:
    inner = MockBackend(seed=1)
    rb = RecordingBackend(inner)
    assert rb.name == "mock"  # build_guard checks == "mock"
    inner.tokens_used = 42
    assert rb.tokens_used == 42  # BudgetGuard reads this (telemetry.py:105)


def test_unknown_attributes_forward() -> None:
    inner = MockBackend(seed=1)
    inner.base_url = "http://127.0.0.1:11434"  # type: ignore[attr-defined]
    assert RecordingBackend(inner).base_url == "http://127.0.0.1:11434"  # type: ignore[attr-defined]


def test_chat_emits_request_and_reply_with_role(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    events.start(p)
    rb = RecordingBackend(MockBackend(seed=1))
    reply = rb.chat("qwen2.5:7b", [ChatMessage("user", "hi")], role=ModelRole.TARGET, seed=1)
    events.stop()
    req, rep = events.read_events(p)[0]
    assert (req["kind"], req["role"], req["model"]) == ("model.request", "target", "qwen2.5:7b")
    assert req["messages"] == [{"role": "user", "content": "hi"}]
    assert rep["kind"] == "model.reply" and rep["reply"] == reply and rep["latency_s"] >= 0


def test_chat_error_emits_and_reraises(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    events.start(p)

    class Boom(MockBackend):
        def chat(self, *a: Any, **k: Any) -> str:
            raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        RecordingBackend(Boom(seed=1)).chat("m", [], role=ModelRole.JUDGE)
    events.stop()
    assert events.read_events(p)[0][-1]["kind"] == "model.error"
