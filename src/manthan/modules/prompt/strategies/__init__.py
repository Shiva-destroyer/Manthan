"""Adaptive prompt strategies: Crescendo and TAP (native implementations)."""

from manthan.modules.prompt.strategies.base import (
    Attacker,
    Objective,
    Strategy,
    StrategyResult,
    load_objectives,
)
from manthan.modules.prompt.strategies.crescendo import Crescendo
from manthan.modules.prompt.strategies.tap import TAP

STRATEGIES: dict[str, type[Strategy]] = {"crescendo": Crescendo, "tap": TAP}

__all__ = [
    "Strategy",
    "StrategyResult",
    "Objective",
    "Attacker",
    "load_objectives",
    "Crescendo",
    "TAP",
    "STRATEGIES",
]
