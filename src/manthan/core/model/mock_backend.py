"""MockBackend — deterministic, seedable, network-free (PRD §8.1, §15.2).

This is what makes the whole harness cloud-green at $0. It never touches the
network and never loads a model weight. It answers ``chat`` and ``embed``
three ways, in priority order:

1. **Programmed responders** — a callable registered for a model name or
   :class:`~manthan.core.model.roles.ModelRole`. Tests use this to script the
   precise target behaviour a strategy must react to (refuse-then-comply, etc.).
2. **Recorded fixtures** — JSONL rows ``{model, role, prompt_sha, response}``
   captured once on the laptop by ``scripts/record_fixtures.py`` and committed
   under ``tests/fixtures/recordings/``. Keyed by (model, prompt-hash).
3. **Deterministic fallback** — a stable pseudo-response derived from a seeded
   hash of the prompt, so a run with the same seed reproduces exactly (NFR-5).
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from manthan.core.model.base import ChatMessage, ModelBackend, prompt_hash
from manthan.core.model.roles import ModelRole

Responder = Callable[[list[ChatMessage]], str]

# A small, stable set of refusal phrases the deterministic fallback can emit so
# that the refusal/keyword scorer has something consistent to key on. Kept
# benign and generic on purpose (PRD §18 — no weaponized content).
_REFUSAL = "I'm sorry, but I can't help with that request."
_EMBED_DIM = 64


class MockBackend(ModelBackend):
    """Deterministic in-memory backend for CI and reproducible demos."""

    name = "mock"
    is_local = True

    def __init__(
        self,
        seed: int = 0,
        fixtures: str | Path | None = None,
        responders: dict[str, Responder] | None = None,
        embed_dim: int = _EMBED_DIM,
    ) -> None:
        self.seed = seed
        self.embed_dim = embed_dim
        self._rng = random.Random(seed)
        self._responders: dict[str, Responder] = dict(responders or {})
        self._fixtures: dict[tuple[str, str], str] = {}
        # Per-(model) call counters make round-robin scripts possible and give
        # the load/unload bookkeeping something to assert against in tests.
        self.load_calls: list[tuple[str, Any]] = []
        self.unload_calls: list[str] = []
        self.resident: set[str] = set()
        if fixtures is not None:
            self.load_fixtures(fixtures)

    # --- programming the mock --------------------------------------------
    def register(self, key: str | ModelRole, responder: Responder) -> None:
        """Register a responder for a model name or a role."""
        self._responders[str(key)] = responder

    def set_script(self, key: str | ModelRole, replies: list[str]) -> None:
        """Register a round-robin list of canned replies (cycles if exhausted)."""
        seq = list(replies)
        state = {"i": 0}

        def _responder(_messages: list[ChatMessage]) -> str:
            r = seq[state["i"] % len(seq)]
            state["i"] += 1
            return r

        self._responders[str(key)] = _responder

    def load_fixtures(self, path: str | Path) -> int:
        """Load recorded JSONL responses. Returns the count loaded."""
        p = Path(path)
        files = sorted(p.glob("*.jsonl")) if p.is_dir() else [p]
        n = 0
        for f in files:
            if not f.exists():
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                model = str(row.get("model", row.get("role", "")))
                sha = str(row.get("prompt_sha", ""))
                self._fixtures[(model, sha)] = str(row.get("response", ""))
                n += 1
        return n

    # --- the ModelBackend contract ---------------------------------------
    def chat(self, model: str, messages: list[ChatMessage], **kw: Any) -> str:
        role = kw.get("role")
        # 1) programmed responder by model, then by role
        for key in (model, str(role) if role is not None else None):
            if key is not None and key in self._responders:
                return self._responders[key](messages)
        # 2) recorded fixture by (model, prompt-hash), then (role, prompt-hash)
        sha = prompt_hash(messages)
        for key in (model, str(role) if role is not None else None):
            if key is not None and (key, sha) in self._fixtures:
                return self._fixtures[(key, sha)]
        # 3) deterministic fallback
        return self._fallback(model, messages, sha)

    def embed(self, model: str, text: str) -> list[float]:
        # Deterministic unit-ish vector seeded by text; good enough for cosine
        # similarity in mocked RAG tests, and identical across runs.
        rng = random.Random(f"{self.seed}:{model}:{text}")
        vec = [rng.uniform(-1.0, 1.0) for _ in range(self.embed_dim)]
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    def load(self, model: str, keep_alive: Any = "5m") -> None:
        self.load_calls.append((model, keep_alive))
        self.resident.add(model)

    def model_digests(self) -> dict[str, str]:
        return {"*": "mock-no-digest"}

    def unload(self, model: str) -> None:
        self.unload_calls.append(model)
        self.resident.discard(model)

    # --- internals --------------------------------------------------------
    def _fallback(self, model: str, messages: list[ChatMessage], sha: str) -> str:
        # Seeded, stable: same (seed, model, prompt) -> same reply.
        rng = random.Random(f"{self.seed}:{model}:{sha}")
        # ~30% of the time emit a refusal so refusal-scorer paths are exercised.
        if rng.random() < 0.30:
            return _REFUSAL
        last_user = ""
        for m in reversed(messages):
            if m.role in ("user", "system"):
                last_user = m.content
                break
        snippet = (last_user or "").strip().split("\n")[0][:80]
        return f"[mock:{model}] acknowledged. Context: {snippet}"
