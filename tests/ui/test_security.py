"""D4 middleware: Host and Origin checks, no CORS (plan Task 8)."""

from __future__ import annotations

LOCAL = {"origin": "http://127.0.0.1:8765"}


def test_bad_host_rejected(client):
    assert client.get("/api/sources", headers={"host": "evil.example:8765"}).status_code == 403


def test_wrong_port_host_rejected(client):
    assert client.get("/api/sources", headers={"host": "127.0.0.1:9999"}).status_code == 403


def test_localhost_name_allowed(client):
    assert client.get("/api/sources", headers={"host": "localhost:8765"}).status_code == 200


def test_foreign_origin_rejected_on_get(client):
    assert client.get("/api/sources", headers={"origin": "http://evil.example"}).status_code == 403


def test_null_origin_rejected(client):
    assert client.get("/api/sources", headers={"origin": "null"}).status_code == 403


def test_post_needs_local_origin(client):
    assert client.post("/api/actions/init", json={}).status_code == 403
    bad = client.post("/api/actions/init", json={}, headers={"origin": "http://evil.example"})
    assert bad.status_code == 403
    assert client.post("/api/actions/init", json={}, headers=LOCAL).status_code != 403


def test_same_host_get_without_origin_ok(client):
    assert client.get("/api/sources").status_code == 200


def test_no_cors_headers(client):
    r = client.get("/api/sources", headers=LOCAL)
    assert r.status_code == 200 and "access-control-allow-origin" not in r.headers
    pre = client.options("/api/sources", headers={"origin": "http://evil.example"})
    assert pre.status_code == 403 and "access-control-allow-origin" not in pre.headers
