"""Read-only API: sources, campaigns, runs, events, resources, system (plan Task 7)."""

from __future__ import annotations

import hashlib


def test_metrics_carry_stored_ci(client, src, cid):
    m = client.get(f"/api/campaigns/{cid}?source={src}").json()["metrics"]
    asr = [x for x in m if x["name"].startswith("asr_")]
    assert asr and all({"ci_low", "ci_high", "method"} <= x.keys() for x in asr)


def test_campaign_status_ok_with_end_event(client, src):
    assert client.get(f"/api/campaigns?source={src}").json()[0]["status"] == "ok"


def test_campaign_status_null_without_log(client, tables_src):
    assert client.get(f"/api/campaigns?source={tables_src}").json()[0]["status"] is None


def test_campaign_status_incomplete_without_end_event(client, src, cut_log):
    assert client.get(f"/api/campaigns?source={src}").json()[0]["status"] == "incomplete"


def test_campaign_status_running_when_pid_alive(client, src, live_pid_log):
    assert client.get(f"/api/campaigns?source={src}").json()[0]["status"] == "running"


def test_events_from_tables_have_null_times(client, tables_src):
    cid = client.get(f"/api/campaigns?source={tables_src}").json()[0]["id"]
    body = client.get(f"/api/campaigns/{cid}/events?source={tables_src}").json()
    assert body["from_log"] is False and body["events"]
    assert all(
        e["ts"] is None and e["t"] is None and e["source"] == "tables" for e in body["events"]
    )
    assert {"run.stored", "turn", "verdict", "finding.stored", "metric.stored"} <= {
        e["kind"] for e in body["events"]
    }


def test_log_events_read_from_offset(client, src, cid):
    first = client.get(f"/api/campaigns/{cid}/events?source={src}").json()
    assert first["from_log"] is True and first["events"][0]["kind"] == "campaign.start"
    again = client.get(f"/api/campaigns/{cid}/events?source={src}&offset={first['offset']}").json()
    assert again["events"] == [] and again["offset"] == first["offset"]


def test_stream_sends_ids_and_closes_at_end(client, src, cid):
    with client.stream("GET", f"/api/campaigns/{cid}/events/stream?source={src}") as r:
        text = "".join(r.iter_text())
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "id: 1\n" in text and '"kind": "campaign.end"' in text


def test_stream_closes_on_dead_pid(client, src, cid, cut_log):
    with client.stream("GET", f"/api/campaigns/{cid}/events/stream?source={src}") as r:
        text = "".join(r.iter_text())  # returns, does not hang
    assert "campaign.start" in text and "campaign.end" not in text


def test_sources_never_expose_unlisted_paths(client, tables_db):
    sources = client.get("/api/sources").json()
    assert str(tables_db.resolve()) in {s["path"] for s in sources} and len(sources) == 3
    assert [s["live"] for s in sources] == [True, False, False]


def test_unknown_source_is_404(client):
    assert client.get("/api/campaigns?source=deadbeef0000").status_code == 404


def test_run_detail_has_turns_and_verdicts(client, src, cid):
    runs = client.get(f"/api/campaigns/{cid}?source={src}").json()["runs"]
    rid = next(r["id"] for r in runs if r["domain"] == "prompt")
    body = client.get(f"/api/runs/{rid}?source={src}").json()
    assert body["run"]["id"] == rid and body["turns"] and body["verdicts"]


def test_empty_db_gives_empty_lists_not_samples(empty_client, empty_src):
    assert empty_client.get(f"/api/campaigns?source={empty_src}").json() == []


def test_resources_null_when_ollama_down(client):
    body = client.get("/api/resources").json()
    assert body["ollama_ps"] is None and body["ollama_error"] and body["free_ram_gb"] > 0
    assert body["used_min"] is None and body["budget_min"] > 0


def test_system_reports_failed_checks(client):
    body = client.get("/api/system").json()
    checks = {c["name"]: c["ok"] for c in body["checks"]}
    assert checks["ollama"] is False and checks["lab_image"] is False
    assert set(checks) == {"ollama", "lab_image", "taxonomy", "ram", "data"}
    assert all(m["pulled"] is None and m["loaded"] is None for m in body["models"])
    assert [c["name"] for c in body["configs"]] == ["manthan.yaml"]


def test_reading_never_changes_past_db(client, tables_src, tables_db):
    digest = hashlib.sha256(tables_db.read_bytes()).hexdigest()
    before = sorted(p.name for p in tables_db.parent.iterdir())
    for path in ("/api/campaigns", "/api/sources"):
        client.get(f"{path}?source={tables_src}")
    cid = client.get(f"/api/campaigns?source={tables_src}").json()[0]["id"]
    client.get(f"/api/campaigns/{cid}?source={tables_src}")
    client.get(f"/api/campaigns/{cid}/events?source={tables_src}")
    assert hashlib.sha256(tables_db.read_bytes()).hexdigest() == digest
    assert sorted(p.name for p in tables_db.parent.iterdir()) == before


def test_resources_used_min_while_a_run_is_live(client, live_pid_log):
    used = client.get("/api/resources").json()["used_min"]
    assert used is not None and used >= 0
