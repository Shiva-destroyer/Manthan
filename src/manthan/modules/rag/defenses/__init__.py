"""The 4-layer RAG defense stack (PRD §11, FR-R4/R5).

Each layer is independently toggleable and stackable. The stack applies
retrieval filtering, injection screening, instruction/data separation (as
partial poison neutralization), and output validation + redaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from manthan.core.config.models import DefensesConfig
from manthan.core.judge.guard import Guard
from manthan.modules.rag.attack.pii_probe import redact_pii
from manthan.modules.rag.defenses.context_sep import (
    neutralize_poison,
    separated_system_prompt,
)
from manthan.modules.rag.defenses.output_validator import validate_output
from manthan.modules.rag.defenses.prompt_guard import query_blocked, screen_contexts
from manthan.modules.rag.defenses.retrieval_filter import retrieval_filter
from manthan.modules.rag.pipeline import AttackTarget, Retrieved

__all__ = [
    "DefenseStack",
    "retrieval_filter",
    "screen_contexts",
    "query_blocked",
    "neutralize_poison",
    "separated_system_prompt",
    "validate_output",
    "redact_pii",
]


@dataclass
class DefenseStack:
    """Composes the four layers per a :class:`DefensesConfig`."""

    config: DefensesConfig = field(default_factory=DefensesConfig)
    guard: Guard | None = None
    allowlist: list[str] | None = None
    secret: str = ""
    threshold: float = 0.5

    def __post_init__(self) -> None:
        if self.config.prompt_guard and self.guard is None:
            raise ValueError("prompt_guard layer needs a guard (no silent MockGuard)")

    @property
    def active_layers(self) -> list[str]:
        c = self.config
        names = []
        if c.retrieval_filter:
            names.append("retrieval_filter")
        if c.prompt_guard:
            names.append("prompt_guard")
        if c.context_sep:
            names.append("context_sep")
        if c.output_validator:
            names.append("output_validator")
        return names

    def apply_retrieval(self, retrieved: list[Retrieved]) -> list[Retrieved]:
        out = retrieved
        if self.config.retrieval_filter:
            out = retrieval_filter(
                out, self.allowlist, perplexity_filter=self.config.perplexity_filter
            )
        if self.config.prompt_guard:
            out = screen_contexts(out, self.guard, self.threshold)
        if self.config.context_sep:
            out = neutralize_poison(out)
        return out

    def block_query(self, query: str) -> bool:
        return bool(self.config.prompt_guard) and query_blocked(query, self.guard, self.threshold)

    def validate(self, answer: str, target: AttackTarget | None = None) -> str:
        if self.config.output_validator:
            answer, _ = validate_output(answer, target, secret=self.secret)
        return answer
