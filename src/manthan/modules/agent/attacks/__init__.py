"""Agent attack payloads (synthetic only)."""

from manthan.modules.agent.attacks.indirect_injection import (
    INJECTED_INBOX_MESSAGE,
    STRONG_INBOX_MESSAGE,
    injected_inbox_message,
)

ATTACK_CLASSES = [
    "indirect_injection",
    "tool_poison",
    "rug_pull",
    "tool_shadowing",
    "excessive_agency",
]

__all__ = [
    "INJECTED_INBOX_MESSAGE",
    "STRONG_INBOX_MESSAGE",
    "injected_inbox_message",
    "ATTACK_CLASSES",
]
