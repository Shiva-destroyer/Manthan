"""P1: garak runs against the same canary target and is rescored by Manthan's judge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import manthan.modules.prompt.runner as prompt_runner
from manthan.core.config import RootConfig
from manthan.core.model import MockBackend
from manthan.core.store import Store
from manthan.modules.prompt.baseline import GarakBaseline, garak_outputs


@pytest.mark.unit
def test_garak_outputs_reads_completed_attempts(fixtures_dir):
    rows = [json.loads(x) for x in (fixtures_dir / "garak_report.jsonl").read_text().splitlines()]
    outs = garak_outputs(rows)
    assert len(outs) == 1  # status 2 only; the status 1 row is the same attempt before scoring
    prompt, reply = outs[0]
    assert prompt.startswith("Ignore all the instructions")
    assert reply.startswith("DAN Mode enabled.")


@pytest.mark.unit
def test_run_offline_command_and_config(monkeypatch, tmp_path, fixtures_dir):
    seen: dict = {}

    def fake_run(cmd, env, check):
        seen["cmd"] = cmd
        cfg = yaml.safe_load(Path(cmd[cmd.index("--config") + 1]).read_text())
        seen["cfg"] = cfg
        out = Path(cfg["reporting"]["report_dir"]) / "p.report.jsonl"
        out.write_text((fixtures_dir / "garak_report.jsonl").read_text())

    monkeypatch.setattr("subprocess.run", fake_run)
    gb = GarakBaseline("qwen2.5:7b", "http://localhost:11434", garak_bin="/x/garak")
    rows = gb.run_offline(
        "dan.Dan_11_0", system_prompt="TOKEN X", report_dir=tmp_path, report_prefix="p"
    )
    cmd, cfg = seen["cmd"], seen["cfg"]
    assert cmd[0] == "/x/garak"
    assert cmd[cmd.index("--target_type") + 1] == "ollama"
    assert cmd[cmd.index("--target_name") + 1] == "qwen2.5:7b"
    assert cmd[cmd.index("--generations") + 1] == "1"
    assert cfg["run"]["system_prompt"] == "TOKEN X"
    gen = cfg["plugins"]["generators"]["ollama"]["OllamaGeneratorChat"]
    assert gen == {"host": "http://localhost:11434", "timeout": 180}
    assert Path(cfg["reporting"]["report_dir"]).is_absolute()
    assert any(r.get("entry_type") == "eval" for r in rows)


@pytest.mark.integration
def test_prompt_runner_stores_uplift(monkeypatch, fixtures_dir):
    rows = [json.loads(x) for x in (fixtures_dir / "garak_report.jsonl").read_text().splitlines()]
    prompts: list[str] = []

    class FakeGarak:
        def __init__(self, *a, **k):
            pass

        def run_offline(self, probes, system_prompt, report_dir, report_prefix):
            prompts.append(system_prompt)
            return rows

    monkeypatch.setattr(prompt_runner, "GarakBaseline", FakeGarak)
    cfg = RootConfig()
    cfg.models.backend = "mock"
    cfg.prompt.garak_enabled = True
    cfg.prompt.strategies = ["crescendo"]
    store = Store.in_memory()
    cid = store.add_campaign(domain="prompt", config_hash="x", seed=1, label="")
    summary = prompt_runner.run_prompt(cfg, MockBackend(0), store, cid, smoke=True)
    names = {m["name"]: m["value"] for m in store.metrics_for_campaign(cid)}
    assert names["garak_asr_native"] == pytest.approx(1.0)
    assert names["garak_asr_rescored"] == pytest.approx(0.0)  # DAN reply has no canary
    assert names["uplift_crescendo"] is not None
    assert summary["garak"]["asr_native"] == pytest.approx(1.0)
    assert len(prompts) == 2 and all(p for p in prompts)  # one garak run per smoke objective


@pytest.mark.unit
def test_planted_secret_lives_in_context_not_as_token():
    """Decision 2 (plan B): the secret is a customer record in context, not a 'reference token'."""
    from manthan.modules.prompt.strategies import load_objectives

    objs = {o.id: o for o in load_objectives()}
    secret = prompt_runner._system_prompt(objs["extract-planted-secret"])
    assert "SECRET-MARK-3B8D" in secret and "recovery code" in secret
    assert "Internal reference token" not in secret
    canary = prompt_runner._system_prompt(objs["reveal-system-prompt"])
    assert canary.startswith("Internal reference token: CANARY-SYS-7Q2F")
