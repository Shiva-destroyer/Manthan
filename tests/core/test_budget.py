"""P4: the budget guard stops between trials and records why (never silently)."""

from __future__ import annotations

import pytest

from manthan.core.cli.orchestrator import run_campaign
from manthan.core.config import RootConfig
from manthan.core.metrics.telemetry import BudgetExhausted, BudgetGuard
from manthan.core.model.base import ChatMessage
from manthan.core.model.ollama_backend import OllamaBackend
from manthan.core.store import Store


def test_zero_minute_budget_stops_and_records_reason():
    cfg = RootConfig()
    cfg.models.backend = "mock"
    cfg.budget.max_wall_clock_min = 0
    store = Store.in_memory()
    manifest = run_campaign(cfg, ["prompt", "rag"], store, smoke=True)
    assert "max_wall_clock_min" in manifest.budget_exhausted
    assert manifest.domains_run == []
    assert {s["domain"] for s in manifest.domains_skipped} == {"prompt", "rag"}
    names = [m["name"] for m in store.metrics_for_campaign(manifest.campaign_id)]
    assert "budget_exhausted" in names


def test_token_budget_uses_counted_tokens():
    class _Client:
        def chat(self, **kw):
            return {"message": {"content": "hi"}, "prompt_eval_count": 7, "eval_count": 5}

    backend = OllamaBackend.__new__(OllamaBackend)
    backend._client = _Client()
    backend.chat("m", [ChatMessage("user", "x")])
    assert backend.tokens_used == 12
    BudgetGuard(max_wall_clock_min=1, max_tokens=12, backend=backend).check()
    with pytest.raises(BudgetExhausted, match="max_tokens"):
        BudgetGuard(max_wall_clock_min=1, max_tokens=11, backend=backend).check()
