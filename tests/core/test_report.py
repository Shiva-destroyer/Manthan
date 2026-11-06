"""Reporter tests — AT-CORE4 (HTML+MD render; heatmap cells match tags)."""

from __future__ import annotations

import pytest

from manthan.core.judge.base import Verdict
from manthan.core.model.base import Transcript
from manthan.core.report import Reporter, render_heatmap
from manthan.core.store import Finding, Store


def _campaign(store: Store) -> str:
    cid = store.add_campaign("all", "cfg-hash", 1337, label="demo")
    rid = store.add_run(cid, "obj-prompt", "qwen2.5:7b", domain="prompt")
    tr = Transcript("obj-prompt", "qwen2.5:7b", strategy="crescendo")
    tr.add("user", "p")
    tr.add("assistant", "leaked CANARY")
    tids = store.add_transcript(rid, tr)
    store.add_verdicts(tids[-1], [Verdict("rubric", "success", 1.0, 0.9)])
    store.add_finding(
        Finding(rid, True, "crescendo", "obj-prompt", owasp=["LLM07"], atlas=["AML.T0054"])
    )
    store.add_metric(rid, "asr_crescendo", 0.6, 0.3, 0.8, method="wilson", seed=1337)
    rid2 = store.add_run(cid, "obj-rag", "qwen2.5:7b", domain="rag")
    store.add_finding(
        Finding(rid2, False, "poisoned_rag", "obj-rag", owasp=["LLM04"], atlas=["AML.T0070"])
    )
    return cid


@pytest.mark.integration
def test_at_core4_report_renders_html_md_with_heatmap(tmp_path):
    s = Store.in_memory()
    cid = _campaign(s)
    paths = Reporter(s).render(cid, out_dir=tmp_path)
    assert paths.html.exists() and paths.markdown.exists()
    html = paths.html.read_text()
    assert "<svg" in html  # heatmap embedded
    assert "₹0 / $0" in html  # $0 headline
    assert "AML.T0070" in html or "LLM04" in html  # RAG tag present
    md = paths.markdown.read_text()
    assert "Runtime cost: ₹0 / $0" in md


@pytest.mark.unit
def test_heatmap_cells_match_tags():
    s = Store.in_memory()
    cid = _campaign(s)
    counts = s.heatmap_counts(cid)
    svg = render_heatmap(counts)
    assert "<svg" in svg
    # both domains' tags are present in the aggregated counts
    assert ("LLM07", "AML.T0054") in counts
    assert ("LLM04", "AML.T0070") in counts


@pytest.mark.unit
def test_heatmap_empty_placeholder():
    svg = render_heatmap({})
    assert "<svg" in svg


@pytest.mark.integration
def test_report_with_calibration_block(tmp_path):
    from manthan.core.judge import JudgeEnsemble, RefusalJudge, RubricJudge
    from manthan.core.model.mock_backend import MockBackend

    s = Store.in_memory()
    cid = _campaign(s)
    ens = JudgeEnsemble([RefusalJudge(), RubricJudge(MockBackend(0))])
    cal = ens.calibrate()
    paths = Reporter(s).render(cid, out_dir=tmp_path, judge_calibration=cal)
    assert "calibration" in paths.html.read_text().lower()


# --- P5 (session 4): per-module panels + Markdown trajectory export ----------
def _step(i, tool, source="agent", malicious=False, flagged=False):
    import json

    return json.dumps(
        {"step": i, "tool": tool, "args": {}, "destination": None, "carries_secret": malicious,
         "off_task": False, "source": source, "malicious": malicious, "note": "",
         "flagged": flagged}  # fmt: skip
    )


def _panel_campaign(store: Store) -> str:
    cid = _campaign(store)
    pm = store.add_run(cid, "_metric_tap", "qwen2.5:7b", domain="prompt")
    store.add_metric(pm, "asr_tap", 0.2, 0.05, 0.5, method="wilson")
    store.add_metric(pm, "inline_vs_authoritative_kappa", 0.42, method="cohen")
    rr = store.add_run(cid, "rag-benchmark", "qwen2.5:3b", domain="rag")
    for n, v in ((1, 0.3), (2, 0.6), (3, 0.9)):
        store.add_metric(rr, f"asr_n{n}", v, v - 0.2, v + 0.1, method="wilson")
    store.add_metric(rr, "dASR_output_validator", 0.9, method="delta")
    store.add_metric(rr, "dASR_prompt_guard", 0.1, method="delta")
    store.add_metric(rr, "benign_acc:output_validator", 1.0, method="4 benign questions")
    ar = store.add_run(cid, "agent-benchmark", "qwen2.5:7b", domain="agent")
    store.add_metric(ar, "asr_indirect_injection", 0.33, 0.06, 0.79, method="wilson")
    store.add_metric(ar, "monitor_precision", 0.75, method="rate")
    store.add_metric(ar, "monitor_recall", 1.0, method="rate")
    tr_run = store.add_run(cid, "agent-indirect_injection", "qwen2.5:7b", domain="agent")
    tr = Transcript("agent-indirect_injection", "qwen2.5:7b")
    tr.add("tool", _step(0, "read_inbox"))
    tr.add("tool", _step(1, "read_inbox", source="injected-content"))
    tr.add("tool", _step(2, "send_message", malicious=True, flagged=True))
    store.add_transcript(tr_run, tr)
    store.add_metric(tr_run, "pwned", 1.0, method="exfil reached the listener")
    return cid


@pytest.mark.integration
def test_report_panels_render_with_svg_and_trajectory_export(tmp_path):
    s = Store.in_memory()
    cid = _panel_campaign(s)
    paths = Reporter(s).render(cid, out_dir=tmp_path)
    html = paths.html.read_text()
    for heading in ("Prompt ASR by strategy", "RAG ASR vs poisoned documents",
                    "Agent trajectories"):  # fmt: skip
        assert heading in html, heading
        assert "<svg" in html.split(heading, 1)[1].split("<h2", 1)[0], heading
    assert "0.420" in html  # inline-vs-authoritative kappa
    assert "oracle" in html  # output_validator is labelled an oracle defense
    md = paths.markdown.read_text()
    assert "## Agent trajectories" in md
    assert "agent-indirect_injection (pwned, injection at step 1, detected)" in md
    assert "| 2 | send_message | agent | yes | yes |" in md


@pytest.mark.integration
def test_report_reads_frozen_calibration_json(tmp_path, monkeypatch):
    import json

    from manthan.core.judge.ensemble import compute_calibration
    from manthan.core.report import report as report_mod

    rep = compute_calibration({"refusal": ["refusal", "success"], "rubric": ["success"] * 2},
                              ["refusal", "success"])  # fmt: skip
    frozen = tmp_path / "judge_calibration_real.json"
    frozen.write_text(json.dumps({**rep.as_dict(), "source": "real set, test split"}))
    monkeypatch.setattr(report_mod, "FROZEN_CALIBRATION", frozen)
    s = Store.in_memory()
    paths = Reporter(s).render(_campaign(s), out_dir=tmp_path)
    assert "real set, test split" in paths.html.read_text()
    assert "| rubric | 1.000 | 1.000 |" in paths.markdown.read_text()


@pytest.mark.integration
def test_runners_store_panel_series_kappa_flagged_pwned():
    import json

    from manthan.core.cli.orchestrator import run_campaign
    from manthan.core.config import RootConfig

    cfg = RootConfig()
    cfg.models.backend = "mock"
    s = Store.in_memory()
    man = run_campaign(cfg, ["prompt", "agent"], s, smoke=True)
    names = {m["name"] for m in s.metrics_for_campaign(man.campaign_id)}
    assert "inline_vs_authoritative_kappa" in names
    traj = [r for r in s.runs_for(man.campaign_id) if r["objective_id"].startswith("agent-")
            and r["objective_id"] != "agent-benchmark"]  # fmt: skip
    assert traj
    for r in traj:
        steps = [json.loads(t["content"]) for t in s.turns_for_run(r["id"])]
        assert all("flagged" in st for st in steps)
    pwned = [m for m in s.metrics_for_campaign(man.campaign_id) if m["name"] == "pwned"]
    assert len(pwned) == len(traj)
