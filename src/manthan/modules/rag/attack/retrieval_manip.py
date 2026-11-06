"""Retrieval manipulation — keyword-stuffed decoys (PRD §11, FR-R3, AML.T0066).

Craft documents whose only purpose is to rank highly for a target query and
crowd out legitimate context, degrading retrieval precision even without
flipping the final answer.
"""

from __future__ import annotations

from manthan.modules.rag.pipeline import AttackTarget, Document


def craft_retrieval_manip(target: AttackTarget, n: int = 2) -> list[Document]:
    """Return ``n`` keyword-stuffed decoy documents (is_poison=True)."""
    stuffed = " ".join([target.query] * 6)
    return [
        Document(
            id=f"manip-{i}",
            text=f"{stuffed} {target.query} relevant relevant relevant.",
            source="web-untrusted",
            is_poison=True,
            metadata={"kind": "retrieval_manip"},
        )
        for i in range(n)
    ]
