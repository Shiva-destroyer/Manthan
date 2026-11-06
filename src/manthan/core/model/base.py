"""Backend ABC and the shared conversational datatypes (PRD §8.1).

``ModelBackend`` is the pluggable contract over which ``OllamaBackend``
(default, local) and ``MockBackend`` (CI, deterministic) are implemented.
``ChatMessage`` / ``Transcript`` are the conversational currency the whole
harness speaks; ``Transcript`` lives here so the judge can forward-reference it
without importing the judge package.
"""

from __future__ import annotations

import abc
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

# ``keep_alive`` accepts Ollama's duration strings ("5m") or an int number of
# seconds; 0 means "unload immediately after the call".
KeepAlive = str | int


@dataclass
class ChatMessage:
    """One turn in a conversation."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ChatMessage:
        return cls(role=str(d["role"]), content=str(d.get("content", "")))


@dataclass
class Transcript:
    """A scored-or-scoreable unit of work: the full exchange for one attempt.

    A ``Transcript`` is produced by a module's attack generator (a prompt
    strategy, an agent trajectory, a RAG query) and consumed by the judge
    ensemble. It carries just enough provenance to tag and store a finding.
    """

    objective_id: str
    target_label: str
    messages: list[ChatMessage] = field(default_factory=list)
    strategy: str = ""
    seed: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- convenience accessors -------------------------------------------
    def add(self, role: str, content: str, latency_s: float | None = None) -> ChatMessage:
        msg = ChatMessage(role=role, content=content)
        self.messages.append(msg)
        if latency_s is not None:
            self.metadata.setdefault("latencies", {})[str(len(self.messages) - 1)] = latency_s
        return msg

    @property
    def last_assistant(self) -> str:
        """The target's most recent reply, or '' if none yet."""
        for m in reversed(self.messages):
            if m.role == "assistant":
                return m.content
        return ""

    @property
    def final_response(self) -> str:
        """Alias used by judges and scorers."""
        return self.last_assistant

    def transcript_text(self) -> str:
        """A flat, judge-friendly rendering of the whole exchange."""
        return "\n".join(f"[{m.role}] {m.content}" for m in self.messages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "target_label": self.target_label,
            "strategy": self.strategy,
            "seed": self.seed,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Transcript:
        return cls(
            objective_id=str(d.get("objective_id", "")),
            target_label=str(d.get("target_label", "")),
            strategy=str(d.get("strategy", "")),
            seed=d.get("seed"),
            messages=[ChatMessage.from_dict(m) for m in d.get("messages", [])],
            metadata=dict(d.get("metadata", {})),
        )


def prompt_hash(messages: list[ChatMessage] | str) -> str:
    """Stable key for fixture lookups: sha1 over the normalized message list.

    Used by ``MockBackend`` to key recorded responses by (role, prompt-hash)
    exactly as the PRD specifies.
    """
    if isinstance(messages, str):
        payload = messages
    else:
        payload = json.dumps([m.to_dict() for m in messages], sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class ModelBackend(abc.ABC):
    """Pluggable model access contract (PRD §8.1).

    Concrete backends MUST honor these signatures. ``load``/``unload`` are the
    hooks the Model-Slot Scheduler uses to respect the RAM budget; backends
    that have nothing to load (the mock) may treat them as no-ops.
    """

    name: str = "base"
    tokens_used: int = 0  # real prompt+reply tokens, for the budget guard

    @abc.abstractmethod
    def chat(self, model: str, messages: list[ChatMessage], **kw: Any) -> str:
        """Return the assistant's reply to ``messages`` from ``model``."""
        raise NotImplementedError

    @abc.abstractmethod
    def embed(self, model: str, text: str) -> list[float]:
        """Return an embedding vector for ``text`` from ``model``."""
        raise NotImplementedError

    def load(self, model: str, keep_alive: KeepAlive = "5m") -> None:
        """Pre-load ``model`` into memory with a residency hint. Default no-op."""
        return None

    def unload(self, model: str) -> None:
        """Evict ``model`` from memory (``keep_alive=0``). Default no-op."""
        return None

    def model_digests(self) -> dict[str, str]:
        """Model name -> content digest, for provenance (NFR-5). Default: none known."""
        return {}

    # Backends may advertise locality so the budget guard (NFR-2) can refuse a
    # non-local backend unless the operator explicitly opted in.
    is_local: bool = True
