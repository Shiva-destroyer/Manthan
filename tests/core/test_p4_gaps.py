"""P4 (session 4): benign QA, model digests, --skip, lab provenance, phase logging."""

from __future__ import annotations

import json
import logging

import pytest
from typer.testing import CliRunner

from manthan.core.cli.main import app
from manthan.core.cli.orchestrator import run_campaign
from manthan.core.config import RootConfig
from manthan.core.config.models import BudgetConfig
from manthan.core.judge import MockGuard
from manthan.core.model import MockBackend
from manthan.core.store import Store
from manthan.modules.rag.runner import run_rag

LAYERS = ("retrieval_filter", "prompt_guard", "context_sep", "output_validator", "stacked")


def _mock_cfg() -> RootConfig:
    c = RootConfig()
    c.models.backend = "mock"
    return c


@pytest.mark.integration
def test_rag_stores_benign_accuracy_per_defense():
    cfg = _mock_cfg()
    store = Store.in_memory()
    cid = store.add_campaign("rag", cfg.config_hash(), cfg.seed)
    run_rag(cfg, MockBackend(0), store, cid, guard=MockGuard(), smoke=True)
    m = {x["name"]: x["value"] for x in store.metrics_for_campaign(cid)}
    names = {"benign_acc"} | {f"benign_acc:{d}" for d in LAYERS}
    assert names <= set(m)
    assert all(0.0 <= m[n] <= 1.0 for n in names)
    assert m["benign_acc"] > 0  # the mock echoes retrieved context, so clean answers appear


def test_mock_backend_gives_stub_digests_and_manifest_keeps_them():
    assert MockBackend(0).model_digests() == {"*": "mock-no-digest"}
    manifest = run_campaign(_mock_cfg(), ["rag"], Store.in_memory(), smoke=True)
    assert manifest.as_dict()["model_digests"] == {"*": "mock-no-digest"}


def test_run_all_skip_agent_skips_only_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("MANTHAN_BACKEND", "mock")
    monkeypatch.setenv("MANTHAN_RESULTS_DB", str(tmp_path / "m.db"))
    res = CliRunner().invoke(app, ["run", "all", "--smoke", "--skip", "agent"])
    assert res.exit_code == 0, res.output
    (man,) = tmp_path.glob("*/manifest.json")
    d = json.loads(man.read_text())
    assert d["domains_run"] == ["prompt", "rag"]
    assert d["domains_skipped"] == [{"domain": "agent", "reason": "skipped by --skip"}]
    (md,) = tmp_path.glob("report-*.md")
    assert "mock-no-digest" in md.read_text()  # digests reach the report provenance


@pytest.mark.integration
def test_agent_lab_is_recorded_in_manifest_and_metric():
    manifest = run_campaign(_mock_cfg(), ["agent"], Store.in_memory(), smoke=True)
    assert manifest.as_dict()["agent_lab"] == {"kind": "SimulatedLab", "image": ""}
    assert BudgetConfig().max_wall_clock_min == 180


def test_verbose_logs_campaign_domain_and_phase_lines(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("MANTHAN_BACKEND", "mock")
    monkeypatch.setenv("MANTHAN_RESULTS_DB", str(tmp_path / "m.db"))
    with caplog.at_level(logging.DEBUG, logger="manthan"):
        res = CliRunner().invoke(app, ["run", "rag", "--smoke", "--verbose"])
    assert res.exit_code == 0, res.output
    text = caplog.text
    for line in (
        "campaign start",
        "domain rag start",
        "phase rag",
        "domain rag done",
        "campaign done",
    ):
        assert line in text, line
    assert "run rag-benchmark" in text  # DEBUG: one line per stored run


def test_log_json_writes_one_json_object_per_line(tmp_path):
    """NFR-8: every stderr line of a mock run parses as one JSON log record."""
    import os
    import subprocess
    import sys

    env = {**os.environ, "MANTHAN_BACKEND": "mock", "MANTHAN_RESULTS_DB": str(tmp_path / "m.db")}
    code = "from manthan.core.cli.main import app; app()"
    out = subprocess.run(
        [sys.executable, "-c", code, "run", "rag", "--smoke", "--log-json"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr
    lines = [ln for ln in out.stderr.splitlines() if ln.strip()]
    records = [json.loads(ln) for ln in lines]
    assert records and all({"ts", "level", "logger", "msg"} <= set(r) for r in records)
    assert any(r["msg"] == "campaign start" or "campaign start" in r["msg"] for r in records)
