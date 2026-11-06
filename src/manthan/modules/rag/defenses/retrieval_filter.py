"""Defense layer 1 — retrieval filtering (PRD §11, FR-R4).

Outlier / duplicate / source-allowlist filtering of retrieved chunks. Needs no
model internals, so it is the always-available shipped core layer. A perplexity
filter is OPTIONAL and contingent on token-logprob availability; since Ollama
does not cleanly expose per-token logprobs, perplexity defaults OFF and this
outlier/dup/allowlist trio is the core layer (§11, fix-pass 5).
"""

from __future__ import annotations

from manthan.modules.rag.pipeline import Retrieved

DEFAULT_ALLOWLIST = ["corpus", "handbook", "wiki-internal", "pii-fixture"]


def retrieval_filter(
    retrieved: list[Retrieved],
    allowlist: list[str] | None = None,
    dedup: bool = True,
    perplexity_filter: bool = False,
) -> list[Retrieved]:
    """Drop chunks from non-allowlisted sources and near-duplicates."""
    allow = set(allowlist or DEFAULT_ALLOWLIST)
    seen: set[str] = set()
    out: list[Retrieved] = []
    for r in retrieved:
        if allow and r.document.source not in allow:
            continue  # outlier / untrusted source removed
        key = r.document.text[:80].strip().lower()
        if dedup and key in seen:
            continue
        seen.add(key)
        out.append(r)
    # perplexity_filter intentionally a no-op here: Ollama lacks clean logprobs.
    return out
