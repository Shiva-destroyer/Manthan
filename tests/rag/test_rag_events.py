"""RAG runner event log: retrieved docs point at stored answers (plan Task 5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from manthan.core import events
from manthan.core.config import RootConfig
from manthan.core.judge.guard import MockGuard
from manthan.core.model import MockBackend
from manthan.core.model.recording import RecordingBackend
from manthan.core.store import Store
from manthan.modules.rag.runner import run_rag


@pytest.fixture
def rag_run(tmp_path: Path) -> tuple[Store, list[dict[str, Any]]]:
    cfg = RootConfig()
    cfg.models.backend = "mock"
    store = Store(tmp_path / "m.db")
    cid = store.add_campaign("rag", cfg.config_hash(), cfg.seed)
    log = tmp_path / "e.jsonl"
    events.start(log)
    run_rag(cfg, RecordingBackend(MockBackend(0)), store, cid, guard=MockGuard(), smoke=True)
    events.stop()
    return store, events.read_events(log)[0]


def test_retrieved_docs_point_at_stored_answers(rag_run) -> None:
    store, evs = rag_run
    pointed = [e for e in evs if e["kind"] == "rag.retrieved" and e["qa_idx"] is not None]
    assert pointed
    for e in pointed:
        turns = store.turns_for_run(e["run_id"])
        assert turns[2 * e["qa_idx"]]["content"] == e["query"]
        assert turns[2 * e["qa_idx"] + 1]["role"] == "assistant"


def test_poison_visible_when_n_at_least_one(rag_run) -> None:
    _, evs = rag_run
    poisoned = [e for e in evs if e["kind"] == "rag.retrieved" and e.get("n_poison", 0) >= 1]
    assert poisoned
    assert any(d["is_poison"] for e in poisoned for d in e["docs"])
