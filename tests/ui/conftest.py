"""UI fixtures: a mock campaign with an event log, one without, and an empty database."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from manthan.core.cli.orchestrator import run_campaign  # noqa: E402
from manthan.core.config import RootConfig  # noqa: E402
from manthan.core.store import Store  # noqa: E402
from manthan.ui import data  # noqa: E402
from manthan.ui.app import create_app  # noqa: E402

BASE_URL = "http://127.0.0.1:8765"


def _dead_pid() -> int:
    pid = 4_000_000
    while Path(f"/proc/{pid}").exists():
        pid += 1
    return pid


def _mock_campaign(db: Path, events_dir: Path | None) -> str:
    cfg = RootConfig()
    cfg.models.backend = "mock"
    cfg.results_db = str(db)
    with Store(db) as store:
        return run_campaign(
            cfg, ["prompt", "rag"], store, smoke=True, events_dir=events_dir
        ).campaign_id


def _config_file(root: Path, db: Path) -> Path:
    cfg_dir = root / "configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    path = cfg_dir / "manthan.yaml"
    path.write_text(f"results_db: {db}\nmodels:\n  backend: mock\n", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _offline_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never reach a real Ollama or Docker from a test."""
    monkeypatch.setattr(data, "ollama_ps", lambda url: None)
    monkeypatch.setattr(data, "ollama_tags", lambda url: None)
    monkeypatch.setattr(data, "docker_image_present", lambda name: False)


@pytest.fixture
def live_db(tmp_path: Path) -> Path:
    db = tmp_path / "live" / "manthan.db"
    db.parent.mkdir()
    _mock_campaign(db, events_dir=db.parent)
    return db


@pytest.fixture
def tables_db(tmp_path: Path) -> Path:
    db = tmp_path / "tables" / "manthan.db"
    db.parent.mkdir()
    _mock_campaign(db, events_dir=None)
    return db


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    db = tmp_path / "empty" / "manthan.db"
    db.parent.mkdir()
    Store(db).close()
    return db


@pytest.fixture
def client(tmp_path: Path, live_db: Path, tables_db: Path, empty_db: Path) -> TestClient:
    app = create_app(_config_file(tmp_path, live_db), [tables_db, empty_db], 8765)
    return TestClient(app, base_url=BASE_URL)


@pytest.fixture
def empty_client(tmp_path: Path, empty_db: Path) -> TestClient:
    return TestClient(create_app(_config_file(tmp_path, empty_db), [], 8765), base_url=BASE_URL)


def _source_id(client: TestClient, path: Path) -> str:
    return next(s["id"] for s in client.get("/api/sources").json() if s["path"] == str(path))


@pytest.fixture
def src(client: TestClient, live_db: Path) -> str:
    return _source_id(client, live_db.resolve())


@pytest.fixture
def tables_src(client: TestClient, tables_db: Path) -> str:
    return _source_id(client, tables_db.resolve())


@pytest.fixture
def empty_src(empty_client: TestClient, empty_db: Path) -> str:
    return _source_id(empty_client, empty_db.resolve())


@pytest.fixture
def cid(client: TestClient, src: str) -> str:
    return client.get(f"/api/campaigns?source={src}").json()[0]["id"]


def _cut_log(live_db: Path, pid: int) -> None:
    """Drop the campaign.end line and point campaign.start at ``pid``."""
    (log,) = live_db.parent.glob("*/events.jsonl")
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    kept = [e for e in lines if e["kind"] != "campaign.end"]
    kept[0]["pid"] = pid
    log.write_text("".join(json.dumps(e) + "\n" for e in kept), encoding="utf-8")


@pytest.fixture
def cut_log(live_db: Path) -> None:
    _cut_log(live_db, _dead_pid())


@pytest.fixture
def live_pid_log(live_db: Path) -> None:
    _cut_log(live_db, os.getpid())
