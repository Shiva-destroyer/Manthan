"""Event log: ordered JSONL, bind scopes, partial-line safety (plan Task 1)."""

from __future__ import annotations

import threading
from pathlib import Path

from manthan.core import events


def test_emit_writes_seq_ts_and_kind(tmp_path: Path) -> None:
    p = tmp_path / "c" / "events.jsonl"
    events.start(p)
    events.emit("campaign.start", campaign_id="abc")
    events.emit("domain.start", domain="prompt")
    events.stop()
    evs, _ = events.read_events(p)
    assert [e["seq"] for e in evs] == [1, 2]
    assert evs[0]["kind"] == "campaign.start" and evs[0]["campaign_id"] == "abc"
    assert evs[0]["ts"].endswith("+00:00") and evs[1]["t"] >= evs[0]["t"] >= 0.0


def test_emit_without_active_log_is_noop(tmp_path: Path) -> None:
    events.stop()
    events.emit("x")  # no error, no file
    assert list(tmp_path.iterdir()) == []


def test_bind_merges_and_restores(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    events.start(p)
    with events.bind(run_id="r1", stage="attack"):
        with events.bind(stage="judging"):
            events.emit("a")
        events.emit("b")
    events.emit("c")
    events.stop()
    a, b, c = events.read_events(p)[0]
    assert (a["run_id"], a["stage"]) == ("r1", "judging")
    assert (b["run_id"], b["stage"]) == ("r1", "attack")
    assert "run_id" not in c


def test_read_skips_partial_last_line(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    p.write_text('{"seq": 1, "kind": "a"}\n{"seq": 2, "ki', encoding="utf-8")
    evs, off = events.read_events(p)
    assert [e["seq"] for e in evs] == [1]
    assert off == len(b'{"seq": 1, "kind": "a"}\n')


def test_read_from_offset_returns_only_new_events(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    events.start(p)
    events.emit("a")
    _, off = events.read_events(p)
    events.emit("b")
    events.stop()
    evs, _ = events.read_events(p, off)
    assert [e["kind"] for e in evs] == ["b"]


def test_threads_never_interleave_lines(tmp_path: Path) -> None:
    p = tmp_path / "e.jsonl"
    events.start(p)

    def work() -> None:
        for i in range(200):
            events.emit("x", n=i)

    ts = [threading.Thread(target=work) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    events.stop()
    evs, _ = events.read_events(p)
    assert len(evs) == 400 and sorted(e["seq"] for e in evs) == list(range(1, 401))
