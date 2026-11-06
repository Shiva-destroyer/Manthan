"""Milestone 4 to 7 API: per-campaign device settings (plan Task 1)."""

from __future__ import annotations

from pathlib import Path

import yaml

from manthan.core.config import load_config

CONFIGS = Path(__file__).resolve().parents[2] / "configs"
# Keys a Virtual Lab preset may change (plan Task 9). The UI never edits files.
PRESET_KEYS = {"prompt.use_defended_target"}


def _url(src: str, cid: str) -> str:
    return f"/api/campaigns/{cid}/settings?source={src}"


def _stored_seed(client, src, cid) -> int:
    return int(client.get(f"/api/campaigns/{cid}?source={src}").json()["campaign"]["seed"])


def test_settings_match_config_file(client, src, cid):
    r = client.get(_url(src, cid))
    assert r.status_code == 200
    body = r.json()
    assert body["config"] == "manthan.yaml" and body["backend"] == "mock"
    assert body["seed"] == _stored_seed(client, src, cid)
    assert body["roles"]["judge"]["temperature"] == 0.0
    assert body["roles"]["target"]["temperature"] is None
    assert body["roles"]["target"]["num_predict"] == 256
    assert body["roles"]["attacker"]["num_predict"] == 160


def test_settings_no_match_gives_nulls(client, src, cid, tmp_path):
    cfg = tmp_path / "configs" / "manthan.yaml"
    cfg.write_text(cfg.read_text() + "budget:\n  max_wall_clock_min: 99\n")
    body = client.get(_url(src, cid)).json()
    assert body["config"] is None and body["backend"] is None and body["guard"] is None
    assert body["roles"]["target"]["model"] is None
    assert body["seed"] == _stored_seed(client, src, cid)


def test_settings_skips_bad_yaml(client, src, cid, tmp_path):
    (tmp_path / "configs" / "broken.yaml").write_text("not: [valid")
    r = client.get(_url(src, cid))
    assert r.status_code == 200 and r.json()["config"] == "manthan.yaml"


def test_settings_404_and_422(client, src):
    assert client.get(_url(src, "0" * 32)).status_code == 404
    assert client.get(_url(src, "not-hex")).status_code == 422


def _flat(d: dict, prefix: str = "") -> dict:
    out: dict = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        out.update(_flat(v, key + ".") if isinstance(v, dict) else {key: v})
    return out


def test_presets_differ_only_in_allowed_keys():
    base = _flat(yaml.safe_load((CONFIGS / "manthan.yaml").read_text()))
    for f in CONFIGS.glob("manthan-*.yaml"):
        other = _flat(yaml.safe_load(f.read_text()))
        diff = {k for k in base.keys() | other.keys() if base.get(k) != other.get(k)}
        assert diff <= PRESET_KEYS, (f.name, diff - PRESET_KEYS)


def test_preset_keys_are_read_by_runtime():
    runner = (CONFIGS.parent / "src/manthan/modules/prompt/runner.py").read_text()
    for key in PRESET_KEYS:
        assert key.split(".")[-1] in runner


def test_guard_off_preset_loads():
    cfg = load_config(CONFIGS / "manthan-guard-off.yaml", apply_env=False)
    assert cfg.prompt.use_defended_target is False


def _app_client(tmp_path, backend: str):
    from fastapi.testclient import TestClient

    from manthan.ui.app import create_app

    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    db = tmp_path / "x" / "manthan.db"
    db.parent.mkdir()
    (cfg_dir / "manthan.yaml").write_text(
        f"results_db: {db}\nmodels:\n  backend: {backend}\n", encoding="utf-8"
    )
    (cfg_dir / "budget.yaml").write_text("not_a_key: 1\n", encoding="utf-8")
    return TestClient(
        create_app(cfg_dir / "manthan.yaml", [], 8765), base_url="http://127.0.0.1:8765"
    )


def _ram_check(c) -> dict:
    return next(x for x in c.get("/api/preflight").json()["checks"] if x["name"] == "ram")


def test_preflight_ram_fails_when_the_scheduler_would_abort(tmp_path, monkeypatch):
    monkeypatch.delenv("MANTHAN_BACKEND", raising=False)
    c = _app_client(tmp_path, "ollama")
    monkeypatch.setattr("manthan.ui.app.available_ram_gb", lambda: 15.4)
    assert (
        _ram_check(c)["ok"] is False
    )  # a real run aborted here: estimated peak 11.8 GB vs 10.4 GB budget
    monkeypatch.setattr("manthan.ui.app.available_ram_gb", lambda: 24.0)
    assert _ram_check(c)["ok"] is True


def test_preflight_ram_passes_for_the_mock_backend(tmp_path, monkeypatch):
    monkeypatch.setattr("manthan.ui.app.available_ram_gb", lambda: 2.0)
    assert _ram_check(_app_client(tmp_path, "mock"))["ok"] is True


def test_system_marks_configs_a_run_can_use(tmp_path):
    configs = {
        x["name"]: x for x in _app_client(tmp_path, "mock").get("/api/system").json()["configs"]
    }
    assert (
        configs["manthan.yaml"]["runnable"] is True and configs["budget.yaml"]["runnable"] is False
    )


def test_system_data_check_hides_the_home_folder(tmp_path, monkeypatch):
    # Screenshots of the System page must not show the user's name.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    checks = {
        x["name"]: x for x in _app_client(tmp_path, "mock").get("/api/system").json()["checks"]
    }
    assert checks["data"]["detail"] == "~/x"
