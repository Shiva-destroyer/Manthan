"""P2: the RAG benchmark can measure something (retrieval is selective, poison is plausible)."""

from __future__ import annotations

import pytest

from manthan.core.config import RootConfig
from manthan.modules.rag.attack import craft_poison
from manthan.modules.rag.pipeline import load_corpus
from manthan.modules.rag.runner import _load_targets


@pytest.mark.unit
def test_corpus_bigger_than_k():
    docs = load_corpus(include_pii=True)
    assert len(docs) >= 30
    assert RootConfig().rag.k in (3, 4)


@pytest.mark.unit
def test_first_target_is_an_answer_the_poison_can_change():
    t = _load_targets()[0]
    poison = craft_poison(t, 1)[0].text
    assert t.poisoned_answer in poison and t.clean_answer not in poison
    assert "ignore" not in poison.lower()  # a plausible update, not a blatant injection
    holders = [d.id for d in load_corpus() if t.clean_answer in d.text]
    assert len(holders) == 1  # one clean source states the true answer
