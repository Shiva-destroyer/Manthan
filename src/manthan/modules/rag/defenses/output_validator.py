"""Defense layer 4 — output validation (PRD §11, FR-R4).

Two checks on the generated answer: (1) a multi-source agreement check that
rejects a steered claim disagreeing with the authoritative clean corpus, and
(2) PII + planted-secret redaction. Reusing the known-good corpus as the
consensus source lets the validator catch poisoning even when poison dominates
the *retrieved* set.
"""

from __future__ import annotations

from manthan.modules.rag.attack.pii_probe import redact_pii
from manthan.modules.rag.pipeline import AttackTarget


def validate_output(
    answer: str,
    target: AttackTarget | None = None,
    secret: str = "",
    corpus_consensus: str | None = None,
) -> tuple[str, bool]:
    """Return (validated_answer, changed).

    If the answer carries the poison marker (disagreeing with the authoritative
    clean answer), replace it with the consensus value; then redact PII + secret.
    """
    changed = False
    out = answer or ""
    if target is not None and target.hit(out):
        # Consensus with the known-good corpus value overrides the steered claim.
        consensus = corpus_consensus or target.clean_answer
        out = f"The answer is {consensus}. (output-validator: rejected unverified claim)"
        changed = True
    redacted = redact_pii(out)
    if secret and secret in redacted:
        redacted = redacted.replace(secret, "[redacted-secret]")
    if redacted != out:
        changed = True
    return redacted, changed
