"""A5: LlamaIndexPipeline retrieves through VectorStoreIndex + a persisted Chroma store."""

from __future__ import annotations

import math
import random

import pytest

pytest.importorskip("chromadb")
pytest.importorskip("llama_index.vector_stores.chroma")

from llama_index.core.embeddings import BaseEmbedding  # noqa: E402

from manthan.core.model import MockBackend  # noqa: E402
from manthan.modules.rag.pipeline import Document, LlamaIndexPipeline  # noqa: E402

rng = random.Random(7)
TEXTS = [f"doc text {i}" for i in range(12)]
QUERY = "which doc?"
VECS = {t: [rng.uniform(-1, 1) for _ in range(8)] for t in [*TEXTS, QUERY]}


class FixedEmbedding(BaseEmbedding):
    """Looks each text up in VECS, so ranking is known in advance."""

    def _get_text_embedding(self, text: str) -> list[float]:
        return VECS[text]

    def _get_query_embedding(self, query: str) -> list[float]:
        return VECS[query]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return VECS[query]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def _pipeline(tmp_path, k=4):
    return LlamaIndexPipeline(
        MockBackend(0), k=k, embed_model=FixedEmbedding(), persist_dir=tmp_path / "chroma"
    )


def test_top_k_matches_brute_force_cosine(tmp_path):
    docs = [Document(id=f"d{i}", text=t) for i, t in enumerate(TEXTS)]
    expected = sorted(docs, key=lambda d: _cosine(VECS[QUERY], VECS[d.text]), reverse=True)[:4]
    p = _pipeline(tmp_path)
    p.index(docs)
    got = p.retrieve(QUERY)
    assert [r.document.id for r in got] == [d.id for d in expected]
    assert got[0].document is docs[int(expected[0].id[1:])]  # maps back to our Document
    assert (tmp_path / "chroma").is_dir()


def test_reindex_replaces_the_collection(tmp_path):
    p = _pipeline(tmp_path, k=12)
    p.index([Document(id=f"d{i}", text=t) for i, t in enumerate(TEXTS)])
    p.index([Document(id="only", text=TEXTS[0])])
    assert [r.document.id for r in p.retrieve(QUERY)] == ["only"]
