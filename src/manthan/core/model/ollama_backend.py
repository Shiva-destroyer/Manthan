"""OllamaBackend — the default, fully-local backend (PRD §8.1, §7).

Talks to a local Ollama daemon at ``http://localhost:11434`` via the ``ollama``
Python client. It is **lazy**: importing this module costs nothing and pulls in
no heavy dependency, so CI can import the package freely. The ``ollama`` client
is only required when the backend is actually constructed — which never happens
on the mock/CI path.

Zero paid API, zero network beyond localhost: this is a $0, offline backend
after the operator's one-time ``ollama pull`` (NFR-2/NFR-3).
"""

from __future__ import annotations

from typing import Any

from manthan.core.model.base import ChatMessage, KeepAlive, ModelBackend
from manthan.core.model.roles import ModelRole

# Output caps per role: qwen2.5:7b runs ~6.4 tok/s on CPU, so 256 tokens ≈ 40 s.
# The judge stays uncapped so its final VERDICT line is never cut off.
_NUM_PREDICT = {ModelRole.TARGET: 256, ModelRole.ATTACKER: 160}


class OllamaBackend(ModelBackend):
    """Local Ollama backend. Requires the optional ``ollama`` extra."""

    name = "ollama"
    is_local = True

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: float = 600.0,
        num_parallel: int = 1,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.num_parallel = num_parallel
        self._client = self._make_client()

    def _make_client(self) -> Any:
        try:
            import ollama  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised only locally
            raise RuntimeError(
                "OllamaBackend requires the 'ollama' client. Install the local "
                "extras:  pip install -e '.[ollama]'  and run a local Ollama "
                "daemon. For CI/offline use MANTHAN_BACKEND=mock instead."
            ) from exc
        return ollama.Client(host=self.base_url, timeout=self.timeout)

    # --- ModelBackend contract -------------------------------------------
    def chat(self, model: str, messages: list[ChatMessage], **kw: Any) -> str:  # pragma: no cover
        options: dict[str, Any] = {}
        if "temperature" in kw:
            options["temperature"] = kw["temperature"]
        if "seed" in kw and kw["seed"] is not None:
            options["seed"] = int(kw["seed"])
        if kw.get("role") in _NUM_PREDICT:
            options["num_predict"] = _NUM_PREDICT[kw["role"]]
        keep_alive = kw.get("keep_alive", "5m")
        resp = self._client.chat(
            model=model,
            messages=[m.to_dict() for m in messages],
            options=options or None,
            keep_alive=keep_alive,
        )
        self._count(resp)
        # ollama returns a dict-like with message.content
        try:
            return str(resp["message"]["content"])
        except (KeyError, TypeError):
            return str(getattr(resp, "message", resp))

    def chat_tools(
        self, model: str, messages: list[dict], tools: list[dict], **kw: Any
    ) -> dict:  # pragma: no cover
        """One tool-calling turn; returns the assistant message (content + tool_calls)."""
        options: dict[str, Any] = {"num_predict": _NUM_PREDICT[ModelRole.TARGET]}
        if kw.get("seed") is not None:
            options["seed"] = int(kw["seed"])
        resp = self._client.chat(model=model, messages=messages, tools=tools, options=options)
        self._count(resp)
        msg = resp["message"]
        return msg.model_dump(exclude_none=True) if hasattr(msg, "model_dump") else dict(msg)

    def _count(self, resp: Any) -> None:
        self.tokens_used += (resp.get("prompt_eval_count") or 0) + (resp.get("eval_count") or 0)

    def embed(self, model: str, text: str) -> list[float]:  # pragma: no cover
        resp = self._client.embeddings(model=model, prompt=text)
        emb = resp["embedding"] if isinstance(resp, dict) else resp.embedding
        return [float(x) for x in emb]

    def model_digests(self) -> dict[str, str]:  # pragma: no cover - local-only
        """Read digests from the local daemon's GET /api/tags (stdlib, no extra client API)."""
        import json
        import urllib.request

        with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=10) as resp:
            tags = json.load(resp)
        return {m["name"]: m["digest"] for m in tags.get("models", [])}

    def load(self, model: str, keep_alive: KeepAlive = "5m") -> None:
        # An empty chat with a keep_alive hint warms/pins the model.
        self._set_keep_alive(model, keep_alive)

    def unload(self, model: str) -> None:
        # keep_alive=0 tells Ollama to evict the model immediately.
        self._set_keep_alive(model, 0)

    def _set_keep_alive(self, model: str, keep_alive: KeepAlive) -> None:
        from ollama import ResponseError

        try:
            self._client.chat(model=model, messages=[], keep_alive=keep_alive)
        except ResponseError:
            # Embedding-only models (nomic-embed-text) reject /api/chat; an
            # empty /api/embed request loads or evicts them the same way.
            self._client.embed(model=model, input=[], keep_alive=keep_alive)
