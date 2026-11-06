"""Milestone 3 API: results summary, calibration files, model sizes (M3 plan Tasks 1, 2 and 7)."""

from __future__ import annotations

from pathlib import Path

from manthan.core.store import Finding, Store
from manthan.ui import data


def _seed(db: Path, crescendo_value: float = 4 / 15) -> tuple[Store, str]:
    store = Store(db)
    cid = store.add_campaign("all", "h", 1)
    prompt = store.add_run(cid, "obj", "qwen2.5:7b", domain="prompt")
    guard = store.add_run(cid, "obj", "qwen2.5:7b+guard", domain="prompt")
    for i in range(15):
        store.add_finding(
            Finding(
                run_id=prompt,
                success=i < 4,
                strategy="crescendo",
                owasp=["LLM01"],
                atlas=["AML.T0051"],
            )
        )
        store.add_finding(Finding(run_id=guard, success=False, strategy="crescendo"))
    store.add_metric(prompt, "asr_crescendo", crescendo_value, 0.109, 0.520, "wilson")
    rag = store.add_run(cid, "rag", "qwen2.5:7b", domain="rag")
    store.add_metric(rag, "asr_n1", 0.333, 0.192, 0.512, "wilson")
    store.add_metric(rag, "asr_n0", 0.0, 0.0, 0.114, "wilson")
    store.add_metric(rag, "dASR_output_validator", 1.0, method="delta")
    store.add_metric(rag, "benign_acc:output_validator", 1.0, method="4 benign questions")
    store.add_metric(rag, "dASR_prompt_guard", 0.0, method="delta")
    store.add_metric(rag, "asr_stacked_defense", 0.0, method="stacked")
    store.add_metric(rag, "peak_ollama_rss_mb", 9899.7, method="psutil 1s sampler")
    return store, cid


def test_rates_k_of_n_from_matching_findings(tmp_path):
    store, cid = _seed(tmp_path / "s.db")
    rate = next(
        r for r in data.results_summary(store, cid)["rates"] if r["name"] == "asr_crescendo"
    )
    assert (rate["k"], rate["n"]) == (4, 15)  # the +guard pass is not counted
    assert (rate["ci_low"], rate["ci_high"]) == (0.109, 0.520)
    assert rate["label"] == "crescendo" and rate["domain"] == "prompt"
    assert rate["target"] == "qwen2.5:7b"


def test_k_of_n_null_when_counts_do_not_match(tmp_path):
    store, cid = _seed(tmp_path / "s.db", crescendo_value=0.5)
    rate = next(
        r for r in data.results_summary(store, cid)["rates"] if r["name"] == "asr_crescendo"
    )
    assert rate["k"] is None and rate["n"] is None


def test_rag_curve_sorted_and_excluded_from_rates(tmp_path):
    store, cid = _seed(tmp_path / "s.db")
    out = data.results_summary(store, cid)
    assert [p["n_poison"] for p in out["rag_curve"]] == [0, 1]
    assert not any(r["name"].startswith("asr_n") for r in out["rates"])
    assert all(r["name"] != "asr_stacked_defense" for r in out["rates"])


def test_defences_oracle_flag(tmp_path):
    store, cid = _seed(tmp_path / "s.db")
    out = data.results_summary(store, cid)
    by = {d["layer"]: d for d in out["defences"]}
    assert by["output_validator"]["oracle"] is True and by["output_validator"]["benign_acc"] == 1.0
    assert by["prompt_guard"]["oracle"] is False and by["prompt_guard"]["benign_acc"] is None
    assert out["stacked"]["value"] == 0.0


def test_other_keeps_the_rest(tmp_path):
    store, cid = _seed(tmp_path / "s.db")
    assert [m["name"] for m in data.results_summary(store, cid)["other"]] == ["peak_ollama_rss_mb"]


def test_heatmap_skips_untagged_findings(tmp_path):
    store, cid = _seed(tmp_path / "s.db")
    assert data.results_summary(store, cid)["heatmap"] == [
        {"owasp_id": "LLM01", "atlas_id": "AML.T0051", "count": 15}
    ]


def test_results_route_404_and_422(client, src):
    assert client.get(f"/api/campaigns/{'0' * 32}/results?source={src}").status_code == 404
    assert client.get(f"/api/campaigns/not-hex/results?source={src}").status_code == 422


def test_results_route_on_mock_campaign(client, src, cid):
    r = client.get(f"/api/campaigns/{cid}/results?source={src}")
    assert r.status_code == 200
    body = r.json()
    assert {"rates", "rag_curve", "defences", "stacked", "other", "heatmap"} <= body.keys()
    for rate in body["rates"]:
        if rate["k"] is not None:
            assert rate["k"] / rate["n"] == rate["value"]


# --- calibration files (Task 2) -------------------------------------------------------------
import json  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from manthan.ui import app as app_module  # noqa: E402
from manthan.ui.app import create_app  # noqa: E402

_JUDGE = {
    "judge_name": "rubric",
    "fpr": 0.0233,
    "tpr": 0.0,
    "precision": 0.0,
    "recall": 0.0,
    "accuracy": 0.875,
    "n": 48,
    "fpr_target": 0.15,
    "fpr_ok": True,
}
_FLAT = {
    "per_judge": {"rubric": _JUDGE},
    "pairwise_kappa": {},
    "fleiss_kappa": -0.5,
    "n_items": 48,
    "source": "real set, test split",
}
_WRAPPED = {
    "split": "test",
    "tag": "qwen",
    "n": 48,
    "gold_counts": {"refusal": 39, "success": 5},
    "calibration": {k: v for k, v in _FLAT.items() if k != "source"},
    "judges": {"rubric": {"fpr_ci": [0.004, 0.121], "tpr_ci": [0.0, 0.434]}},
}


def _app(tmp_path: Path, calibrations: list[Path], shipped: Path | None = None, monkeypatch=None):
    results = tmp_path / "res"
    results.mkdir(exist_ok=True)
    cfg = tmp_path / "manthan.yaml"
    cfg.write_text(f"results_db: {results / 'manthan.db'}\nmodels:\n  backend: mock\n")
    if monkeypatch is not None:
        monkeypatch.setattr(app_module, "SHIPPED_CALIBRATION", shipped or tmp_path / "none.json")
    app = create_app(cfg, [], 8765, calibrations)
    return TestClient(app, base_url="http://127.0.0.1:8765"), results


def test_read_calibration_flat_shape():
    got = data.read_calibration(app_module.SHIPPED_CALIBRATION)
    assert len(got["judges"]) == 2 and got["judges"][0]["fpr_ci"] is None
    assert got["n_items"] == 48 and got["error"] is None


def test_read_calibration_wrapped_shape(tmp_path):
    f = tmp_path / "metrics_qwen_test.json"
    f.write_text(json.dumps(_WRAPPED))
    got = data.read_calibration(f)
    assert (got["tag"], got["split"]) == ("qwen", "test")
    assert got["judges"][0]["fpr_ci"] == [0.004, 0.121]
    assert got["gold_counts"] == {"refusal": 39, "success": 5}


def test_calibrations_order(tmp_path, monkeypatch):
    cli = tmp_path / "cli.json"
    cli.write_text(json.dumps(_FLAT))
    shipped = tmp_path / "shipped.json"
    shipped.write_text(json.dumps(_FLAT))
    client, results = _app(tmp_path, [cli], shipped, monkeypatch)
    (results / "calibration.json").write_text(json.dumps(_FLAT))
    names = [c["name"] for c in client.get("/api/calibrations").json()]
    assert names == ["cli.json", "shipped.json", "calibration.json"]


def test_calibrations_bad_json_reports_error(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{")
    client, _ = _app(tmp_path, [bad], monkeypatch=monkeypatch)
    r = client.get("/api/calibrations")
    assert r.status_code == 200
    (item,) = r.json()
    assert item["name"] == "bad.json" and item["error"]


def test_calibrations_empty_list(tmp_path, monkeypatch):
    client, _ = _app(tmp_path, [], monkeypatch=monkeypatch)
    assert client.get("/api/calibrations").json() == []


# --- model sizes (Task 7) -------------------------------------------------------------------
def test_ollama_tags_returns_sizes(monkeypatch):
    monkeypatch.undo()  # drop the conftest stub so the real function runs
    monkeypatch.setattr(
        data, "_get_json", lambda url: {"models": [{"name": "qwen2.5:7b", "size": 4683087332}]}
    )
    assert data.ollama_tags("http://x") == {"qwen2.5:7b": 4683087332}


def test_system_reports_size(client, monkeypatch):
    monkeypatch.setattr(data, "ollama_tags", lambda url: {"qwen2.5:7b": 4683087332})
    rows = client.get("/api/system").json()["models"]
    qwen = next(r for r in rows if r["model"] == "qwen2.5:7b")
    assert qwen["size_bytes"] == 4683087332 and qwen["pulled"] is True
    assert any(r["pulled"] is False and r["size_bytes"] is None for r in rows)


def test_system_sizes_null_when_ollama_down(client):
    rows = client.get("/api/system").json()["models"]
    assert rows and all(r["size_bytes"] is None and r["pulled"] is None for r in rows)


# --- final review fixes ---------------------------------------------------------------------
def test_agent_rates_have_no_k_of_n(tmp_path):
    # the agent runner stores one finding per class for n_trials trials, so n would be 1
    store = Store(tmp_path / "s.db")
    cid = store.add_campaign("all", "h", 1)
    run = store.add_run(cid, "agent-benchmark", "qwen2.5:7b", domain="agent")
    store.add_finding(Finding(run_id=run, success=False, strategy="exfil"))
    store.add_metric(run, "asr_exfil", 0.0, 0.0, 0.278, "wilson")
    (rate,) = data.results_summary(store, cid)["rates"]
    assert rate["k"] is None and rate["n"] is None


def test_calibration_with_nan_reports_error(tmp_path):
    f = tmp_path / "nan.json"
    f.write_text(json.dumps(_FLAT).replace("0.0233", "NaN"))
    assert data.read_calibration(f)["error"]


def test_calibrations_skip_broken_symlink(tmp_path, monkeypatch):
    client, results = _app(tmp_path, [], monkeypatch=monkeypatch)
    (results / "calibration-x.json").symlink_to(tmp_path / "missing.json")
    assert client.get("/api/calibrations").status_code == 200
