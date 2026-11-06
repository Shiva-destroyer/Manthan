"""Shared entry point for the lab MCP servers (stdio for the scanner, HTTP in compose)."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

State = Callable[[], dict[str, Any]]
Exfil = Callable[[str, str, dict], dict]


def http_exfil(url: str | None) -> Exfil:
    """POST off-allowlist sends to the mock-exfil sink; with no sink (scan mode) drop them."""

    def send(destination: str, payload: str, meta: dict) -> dict:
        if not url:
            return {}
        body = json.dumps({"destination": destination, "payload": payload, "meta": meta}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return dict(json.load(resp))

    return send


def serve(build: Callable[..., Any], argv: list[str] | None = None, **kw: Any) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", default=None, help="fixed attack view (stdio scan mode)")
    p.add_argument("--state", default=None, help="JSON file naming the current trial (compose)")
    p.add_argument("--http", default=None, metavar="HOST:PORT", help="serve HTTP, not stdio")
    args = p.parse_args(argv)
    if args.state:
        path = Path(args.state)

        def state() -> dict[str, Any]:  # re-read per request: the host writes it per trial
            return json.loads(path.read_text()) if path.exists() else {}

    else:

        def state() -> dict[str, Any]:
            return {"attack": args.mode, "trial": "", "run_dir": "."}

    server = build(state, http_exfil(os.environ.get("EXFIL_URL")), **kw)
    if args.http:
        host, port = args.http.rsplit(":", 1)
        server.run(transport="http", host=host, port=int(port), show_banner=False)
    else:
        server.run(show_banner=False)  # stdio: stdout carries JSON-RPC only
