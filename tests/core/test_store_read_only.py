"""Store.read_only: past databases open without a write or a side file (plan Task 6)."""

from __future__ import annotations

import hashlib
import sqlite3

import pytest

from manthan.core.store import Store


def test_read_only_queries_work_and_writes_fail(tmp_path):
    src = tmp_path / "m.db"
    with Store(src) as s:
        cid = s.add_campaign("prompt", "h", 1)
    ro = Store.read_only(src)
    assert ro.get_campaign(cid)["id"] == cid
    with pytest.raises(sqlite3.OperationalError):
        ro.add_campaign("prompt", "h", 1)
    ro.close()


def test_read_only_leaves_no_side_files(tmp_path):
    src = tmp_path / "m.db"
    with Store(src) as s:
        s.add_campaign("prompt", "h", 1)
    for side in ("m.db-wal", "m.db-shm"):
        (tmp_path / side).unlink(missing_ok=True)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    ro = Store.read_only(src)
    ro.campaigns()
    ro.close()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["m.db"]
    assert hashlib.sha256(src.read_bytes()).hexdigest() == digest


def test_read_only_reads_rows_still_in_wal(tmp_path):
    src = tmp_path / "m.db"
    s = Store(src)
    s.add_campaign("prompt", "h", 1)  # left open: the row sits in the WAL
    assert (tmp_path / "m.db-wal").stat().st_size > 0
    ro = Store.read_only(src)
    assert len(ro.campaigns()) == 1
    ro.close()
    s.close()


def test_read_only_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Store.read_only(tmp_path / "nope.db")
    assert not (tmp_path / "nope.db").exists()
