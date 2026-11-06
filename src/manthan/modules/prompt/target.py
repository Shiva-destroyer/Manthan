"""Target adapters: Target and DefendedTarget (PRD §9, FR-P3).

``Target`` wraps the model layer (local Ollama via the OpenAI-compatible
endpoint, or the mock backend). ``DefendedTarget`` wraps a target with the input
guard so *evasion* can be measured: if the guard flags the latest user input the
target returns a refusal (blocked); an attack that still succeeds has evaded the
defense.
"""

from __future__ import annotations

import time

from manthan.core import events
from manthan.core.judge.guard import Guard
from manthan.core.model.base import ChatMessage, ModelBackend
from manthan.core.model.roles import ModelRole

_GUARD_REFUSAL = "I can't help with that — this request looks like a prompt-injection attempt."


class Target:
    """A chat target backed by a model role."""

    def __init__(
        self,
        backend: ModelBackend,
        model: str = "qwen2.5:7b",
        label: str | None = None,
        system_prompt: str | None = None,
        seed: int | None = None,
    ) -> None:
        self.backend = backend
        self.model = model
        self.label = label or model
        self.system_prompt = system_prompt
        self.seed = seed
        self.last_blocked = False
        self.last_latency = 0.0

    def _messages(self, user_messages: list[ChatMessage]) -> list[ChatMessage]:
        msgs: list[ChatMessage] = []
        if self.system_prompt:
            msgs.append(ChatMessage("system", self.system_prompt))
        msgs.extend(user_messages)
        return msgs

    def respond(self, user_messages: list[ChatMessage]) -> str:
        self.last_blocked = False
        t0 = time.perf_counter()
        reply = self.backend.chat(
            self.model,
            self._messages(user_messages),
            role=ModelRole.TARGET,
            seed=self.seed,
        )
        self.last_latency = time.perf_counter() - t0
        return reply


class DefendedTarget(Target):
    """A Target wrapped with the input guard to enable evasion measurement."""

    def __init__(
        self,
        backend: ModelBackend,
        model: str = "qwen2.5:7b",
        guard: Guard | None = None,
        threshold: float = 0.5,
        **kw,
    ) -> None:
        super().__init__(backend, model, **kw)
        if guard is None:
            raise ValueError("DefendedTarget needs a guard (no silent MockGuard)")
        self.guard = guard
        self.threshold = threshold

    def respond(self, user_messages: list[ChatMessage]) -> str:
        latest = user_messages[-1].content if user_messages else ""
        t0 = time.perf_counter()
        prob = self.guard.classify(latest)
        events.emit(
            "guard.score", score=prob, threshold=self.threshold, blocked=prob >= self.threshold
        )
        if prob >= self.threshold:
            self.last_blocked = True
            self.last_latency = time.perf_counter() - t0  # guard time only, no model call
            return _GUARD_REFUSAL
        self.last_blocked = False
        return super().respond(user_messages)
