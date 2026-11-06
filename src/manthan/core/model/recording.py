"""Backend wrapper that writes every model call to the event log (plan Task 2).

Everything else is forwarded to the inner backend, so the budget guard, the
scheduler and the RAG pipeline see the same ``name``, ``tokens_used`` and ``base_url``.
"""

from __future__ import annotations

import time
from typing import Any

from manthan.core import events
from manthan.core.model.base import ChatMessage, KeepAlive, ModelBackend


def _role(kw: dict[str, Any]) -> str:
    r = kw.get("role", "")
    return str(getattr(r, "value", r))


class RecordingBackend(ModelBackend):
    def __init__(self, inner: ModelBackend) -> None:
        self._inner = inner

    # ModelBackend declares these as class attributes, so __getattr__ never sees them.
    @property
    def name(self) -> str:  # type: ignore[override]
        return self._inner.name

    @property
    def tokens_used(self) -> int:  # type: ignore[override]
        return self._inner.tokens_used

    @tokens_used.setter
    def tokens_used(self, value: int) -> None:
        self._inner.tokens_used = value

    @property
    def is_local(self) -> bool:  # type: ignore[override]
        return self._inner.is_local

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._inner, attr)

    def _call(self, fn: Any, model: str, req: dict[str, Any], *args: Any, **kw: Any) -> Any:
        role = _role(kw)
        events.emit("model.request", role=role, model=model, **req)
        t0 = time.monotonic()
        try:
            reply = fn(model, *args, **kw)
        except Exception as exc:
            events.emit("model.error", role=role, model=model, error=str(exc))
            raise
        events.emit(
            "model.reply",
            role=role,
            model=model,
            reply=reply,
            latency_s=round(time.monotonic() - t0, 3),
        )
        return reply

    def chat(self, model: str, messages: list[ChatMessage], **kw: Any) -> str:
        req = {"messages": [{"role": m.role, "content": m.content} for m in messages]}
        return str(self._call(self._inner.chat, model, req, messages, **kw))

    def chat_tools(self, model: str, messages: list[dict], tools: list[dict], **kw: Any) -> dict:
        # Only OllamaBackend has chat_tools; AttributeError here matches the unwrapped backend.
        fn = self._inner.chat_tools  # type: ignore[attr-defined]
        names = [t.get("function", {}).get("name", t.get("name")) for t in tools]
        req = {"messages": messages, "tools": names}
        return self._call(fn, model, req, messages, tools, **kw)  # type: ignore[no-any-return]

    def embed(self, model: str, text: str) -> list[float]:
        return self._inner.embed(model, text)  # one event per vector would flood the log

    def load(self, model: str, keep_alive: KeepAlive = "5m") -> None:
        self._inner.load(model, keep_alive)
        events.emit("model.load", model=model)

    def unload(self, model: str) -> None:
        self._inner.unload(model)
        events.emit("model.unload", model=model)

    def model_digests(self) -> dict[str, str]:
        return self._inner.model_digests()
