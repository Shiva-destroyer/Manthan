"""Model roles — the single source of truth (PRD §8.1, fix-pass 1).

Every other module imports ``ModelRole`` from here so the enum is defined
exactly once.
"""

from __future__ import annotations

from enum import Enum


class ModelRole(str, Enum):
    """The five roles a backend model can play in a campaign."""

    TARGET = "target"
    ATTACKER = "attacker"
    JUDGE = "judge"
    EMBED = "embed"
    GUARD = "guard"

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value
