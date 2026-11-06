"""Orchestrator tests — AT-CORE5 (run all spans 3 domains), AT-CORE8 (agent skip)."""

from __future__ import annotations

import pytest

from manthan.core.cli.orchestrator import run_campaign
from manthan.core.config import RootConfig
from manthan.core.store import Store


def _mock_cfg(**over) -> RootConfig:
    c = RootConfig()
    c.models.backend = "mock"
    for k, v in over.items():
        setattr(c, k, v)
    return c


@pytest.mark.integration
def test_at_core5_run_all_smoke_spans_three_domains():
    """AT-CORE5: run all --smoke (mock) -> one campaign spanning 3 domains."""
    cfg = _mock_cfg()
    store = Store.in_memory()
    manifest = run_campaign(cfg, ["prompt", "agent", "rag"], store, smoke=True, label="smoke")
    assert manifest.domains_run == ["prompt", "agent", "rag"]
    assert not manifest.domains_skipped
    assert set(manifest.summaries) == {"prompt", "agent", "rag"}
    # findings landed across domains
    findings = store.findings_for_campaign(manifest.campaign_id)
    run_domains = {r["domain"] for r in store.runs_for(manifest.campaign_id)}
    assert {"prompt", "agent", "rag"} <= run_domains
    assert len(findings) > 0
    assert manifest.peak_rss_mb >= 0.0


@pytest.mark.integration
def test_campaign_stores_system_memory_metrics():
    """P1: system-wide memory peaks land in the manifest and as campaign metrics."""
    cfg = _mock_cfg()
    store = Store.in_memory()
    manifest = run_campaign(cfg, ["rag"], store, smoke=True)
    d = manifest.as_dict()
    names = {m["name"] for m in store.metrics_for_campaign(manifest.campaign_id)}
    for key in ("peak_ollama_rss_mb", "peak_system_used_mb", "swap_delta_mb", "peak_proc_rss_mb"):
        assert key in d and key in names
    assert d["peak_system_used_mb"] > 0  # real psutil reading, not the old process tree
    assert "memory_access_denied" in d


@pytest.mark.integration
def test_at_core8_agent_skipped_when_docker_absent(monkeypatch):
    """AT-CORE8: live docker lab + Docker absent -> agent skipped, recorded in manifest."""
    import manthan.modules.agent.lab as lab_mod

    monkeypatch.setattr(lab_mod, "docker_available", lambda: False)
    cfg = _mock_cfg()
    cfg.agent.lab = "docker"  # force the live docker path
    store = Store.in_memory()
    manifest = run_campaign(cfg, ["prompt", "agent", "rag"], store, smoke=True)
    assert "agent" not in manifest.domains_run
    assert any(s["domain"] == "agent" for s in manifest.domains_skipped)
    assert manifest.warnings  # a warning, not an error
    # prompt + rag still succeeded
    assert "prompt" in manifest.domains_run and "rag" in manifest.domains_run


@pytest.mark.integration
def test_at_core8_mock_path_keeps_all_three(monkeypatch):
    """Mock-path run all --smoke keeps all three domains (SimulatedLab)."""
    import manthan.modules.agent.lab as lab_mod

    monkeypatch.setattr(lab_mod, "docker_available", lambda: False)
    cfg = _mock_cfg()  # agent.lab defaults to 'simulated'
    store = Store.in_memory()
    manifest = run_campaign(cfg, ["prompt", "agent", "rag"], store, smoke=True)
    assert manifest.domains_run == ["prompt", "agent", "rag"]
    assert not manifest.domains_skipped


@pytest.mark.integration
def test_non_local_backend_blocks_campaign():
    cfg = RootConfig()
    cfg.models.backend = "remote-paid"
    store = Store.in_memory()
    from manthan.core.config import BackendConfigError

    with pytest.raises(BackendConfigError):
        run_campaign(cfg, ["prompt"], store, smoke=True)
