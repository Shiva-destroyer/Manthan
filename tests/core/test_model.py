"""Model layer tests — MockBackend determinism, fixtures, factory."""

from __future__ import annotations

import pytest

from manthan.core.model import MockBackend, make_backend, prompt_hash
from manthan.core.model.base import ChatMessage


@pytest.mark.unit
def test_mock_chat_deterministic_and_seeded():
    a = MockBackend(seed=7)
    b = MockBackend(seed=7)
    msgs = [ChatMessage("user", "hello world this is a test")]
    assert a.chat("m", msgs) == b.chat("m", msgs)  # same seed -> same output


@pytest.mark.unit
def test_mock_responder_and_script():
    mb = MockBackend()
    mb.register("m", lambda msgs: "fixed")
    assert mb.chat("m", [ChatMessage("user", "x")]) == "fixed"
    mb.set_script("s", ["a", "b"])
    assert [mb.chat("s", []) for _ in range(3)] == ["a", "b", "a"]  # cycles


@pytest.mark.unit
def test_mock_fixture_replay(fixtures_dir):
    mb = MockBackend()
    n = mb.load_fixtures(fixtures_dir / "recordings")
    assert n >= 1
    msgs = [ChatMessage("user", "hello fixture")]
    assert mb.chat("qwen2.5:7b", msgs) == "recorded: hi there"


@pytest.mark.unit
def test_mock_embed_unit_norm_and_stable():
    mb = MockBackend()
    v1 = mb.embed("e", "abc")
    v2 = mb.embed("e", "abc")
    assert v1 == v2
    assert abs(sum(x * x for x in v1) ** 0.5 - 1.0) < 1e-9


@pytest.mark.unit
def test_mock_load_unload_bookkeeping():
    mb = MockBackend()
    mb.load("m1", keep_alive="5m")
    assert "m1" in mb.resident
    mb.unload("m1")
    assert "m1" not in mb.resident


@pytest.mark.unit
def test_make_backend_factory_and_prompt_hash():
    assert make_backend("mock").name == "mock"
    with pytest.raises(ValueError):
        make_backend("weird")
    assert prompt_hash("x") == prompt_hash("x")


@pytest.mark.unit
def test_ollama_backend_requires_client_when_absent():
    # The ollama client is not installed in CI; constructing the backend raises
    # a clear, offline-safe error rather than making a network call.
    import importlib.util

    if importlib.util.find_spec("ollama") is None:
        from manthan.core.model.ollama_backend import OllamaBackend

        with pytest.raises(RuntimeError):
            OllamaBackend()


@pytest.mark.unit
def test_ollama_load_unload_embedding_model_falls_back_to_embed():
    # Embedding-only models (nomic-embed-text) reject /api/chat with a 400; the
    # scheduler loads the persistent embed role, so load/unload must not crash.
    ollama = pytest.importorskip("ollama")
    from manthan.core.model.ollama_backend import OllamaBackend

    class FakeClient:
        def __init__(self) -> None:
            self.embed_calls: list[tuple[str, object]] = []

        def chat(self, model, messages, keep_alive):
            raise ollama.ResponseError(f'"{model}" does not support chat', 400)

        def embed(self, model, input, keep_alive):
            self.embed_calls.append((model, keep_alive))

    backend = OllamaBackend.__new__(OllamaBackend)
    backend._client = FakeClient()
    backend.load("nomic-embed-text", keep_alive="5m")
    backend.unload("nomic-embed-text")
    assert backend._client.embed_calls == [("nomic-embed-text", "5m"), ("nomic-embed-text", 0)]


@pytest.mark.unit
def test_ollama_backend_uses_configured_host_and_timeout(monkeypatch):
    # models.yaml base_url and the timeout must reach the client, not be ignored.
    ollama = pytest.importorskip("ollama")
    from manthan.core.model.ollama_backend import OllamaBackend

    made: dict = {}
    monkeypatch.setattr(ollama, "Client", lambda **kw: made.update(kw) or object())
    OllamaBackend(base_url="http://127.0.0.1:9", timeout=7.0)
    assert made == {"host": "http://127.0.0.1:9", "timeout": 7.0}


@pytest.mark.unit
def test_transcript_round_trip_and_accessors():
    from manthan.core.model.base import Transcript

    tr = Transcript("obj", "tgt", strategy="crescendo", seed=1)
    tr.add("user", "u1")
    tr.add("assistant", "a1")
    assert tr.last_assistant == "a1"
    assert tr.final_response == "a1"
    assert "[user] u1" in tr.transcript_text()
    d = tr.to_dict()
    tr2 = Transcript.from_dict(d)
    assert tr2.objective_id == "obj" and len(tr2.messages) == 2
