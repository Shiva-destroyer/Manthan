"""Model layer: roles, the backend ABC, backends, and the slot scheduler."""

from manthan.core.model.base import (
    ChatMessage,
    KeepAlive,
    ModelBackend,
    Transcript,
    prompt_hash,
)
from manthan.core.model.mock_backend import MockBackend
from manthan.core.model.roles import ModelRole
from manthan.core.model.scheduler import (
    ModelSlotScheduler,
    ResidencyMode,
    SchedulerError,
    available_ram_gb,
)

__all__ = [
    "ChatMessage",
    "Transcript",
    "ModelBackend",
    "ModelRole",
    "MockBackend",
    "ModelSlotScheduler",
    "ResidencyMode",
    "SchedulerError",
    "available_ram_gb",
    "prompt_hash",
    "KeepAlive",
]


def make_backend(kind: str = "mock", **kwargs):
    """Factory: 'mock' (default/CI) or 'ollama' (local). Lazy on ollama."""
    kind = (kind or "mock").lower()
    if kind == "mock":
        return MockBackend(**kwargs)
    if kind == "ollama":
        from manthan.core.model.ollama_backend import OllamaBackend

        return OllamaBackend(**kwargs)
    raise ValueError(f"unknown backend kind: {kind!r} (expected 'mock' or 'ollama')")
