"""`/` serves the built page when it exists, else a short JSON note (plan Task 10)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from manthan.ui import app as app_module


def test_root_note_without_a_built_page(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "STATIC_INDEX", Path("/nonexistent/index.html"))
    r = client.get("/")
    assert r.status_code == 200 and "note" in r.json()


def test_root_serves_the_built_page(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    page = tmp_path / "index.html"
    page.write_text("<h1>Manthan</h1>", encoding="utf-8")
    monkeypatch.setattr(app_module, "STATIC_INDEX", page)
    r = client.get("/")
    assert r.status_code == 200 and "<h1>Manthan</h1>" in r.text


# --- /assets mount (M3 plan Task 3) ------------------------------------------------------------
from manthan.ui.app import create_app  # noqa: E402


def _app_with_static(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_assets: bool
) -> TestClient:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>Manthan</h1>", encoding="utf-8")
    if with_assets:
        (static / "assets").mkdir()
        (static / "assets" / "a.js").write_text("1", encoding="utf-8")
    monkeypatch.setattr(app_module, "STATIC_INDEX", static / "index.html")
    cfg = tmp_path / "manthan.yaml"
    cfg.write_text(f"results_db: {tmp_path / 'm.db'}\nmodels:\n  backend: mock\n", encoding="utf-8")
    return TestClient(create_app(cfg, [], 8765), base_url="http://127.0.0.1:8765")


def test_assets_served_when_built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _app_with_static(tmp_path, monkeypatch, True).get("/assets/a.js").status_code == 200


def test_assets_missing_dir_is_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _app_with_static(tmp_path, monkeypatch, False).get("/assets/a.js").status_code == 404


def test_assets_bad_host_is_403(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app_with_static(tmp_path, monkeypatch, True)
    assert client.get("/assets/a.js", headers={"Host": "evil.test"}).status_code == 403
