"""P3: every domain stores turn-level evidence, with a measured latency."""

from __future__ import annotations

from manthan.core.cli.orchestrator import run_campaign
from manthan.core.config import RootConfig
from manthan.core.store import Store


def _turns(store: Store, domain: str):
    return store.conn.execute(
        "SELECT run.objective_id, run.target_label, turn.role, turn.latency_s FROM turn"
        " JOIN run ON run.id = turn.run_id WHERE run.domain = ?",
        (domain,),
    ).fetchall()


def test_evidence_rows_and_latency():
    cfg = RootConfig()
    cfg.models.backend = "mock"
    store = Store.in_memory()
    run_campaign(cfg, ["prompt", "agent", "rag"], store, smoke=True)

    prompt = _turns(store, "prompt")
    assert any(r[2] == "assistant" for r in prompt)
    assert all(r[3] > 0 for r in prompt if r[2] == "assistant"), "prompt latency_s is 0"

    agent = _turns(store, "agent")
    assert any(r[2] == "tool" for r in agent), "agent trajectory missing"

    rag = _turns(store, "rag")
    assert {"user", "assistant"} <= {r[2] for r in rag}, "RAG Q&A missing"
    assert all(r[3] > 0 for r in rag if r[2] == "assistant"), "RAG latency_s is 0"
