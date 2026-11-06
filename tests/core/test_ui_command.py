"""`manthan ui` serves on loopback only (plan Task 10)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("uvicorn")
pytest.importorskip("fastapi")

from typer.testing import CliRunner  # noqa: E402

from manthan.core.cli import main  # noqa: E402
from manthan.core.store import Store  # noqa: E402


def test_ui_binds_loopback_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: seen.update(kw))
    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(main.app, ["ui", "--port", "8799"])
    assert res.exit_code == 0 and seen == {"host": "127.0.0.1", "port": 8799}
    assert "http://127.0.0.1:8799" in res.output


def test_ui_has_no_host_option() -> None:
    res = CliRunner().invoke(main.app, ["ui", "--host", "0.0.0.0"])
    assert res.exit_code != 0


def test_ui_passes_port_and_databases_to_the_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: seen.update(app=app))
    monkeypatch.chdir(tmp_path)
    past = tmp_path / "past" / "manthan.db"
    Store(past).close()
    res = CliRunner().invoke(main.app, ["ui", "--port", "8801", "--db", str(past)])
    assert res.exit_code == 0
    app = seen["app"]
    assert app.state.port == 8801
    assert [s.path for s in app.state.sources.values() if not s.live] == [past.resolve()]


def test_ui_passes_calibration_files_to_the_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: seen.update(app=app))
    monkeypatch.chdir(tmp_path)
    cal = tmp_path / "cal.json"
    cal.write_text("{}", encoding="utf-8")
    res = CliRunner().invoke(main.app, ["ui", "--calibration", str(cal)])
    assert res.exit_code == 0
    assert seen["app"].state.calibrations == [cal.resolve()]
