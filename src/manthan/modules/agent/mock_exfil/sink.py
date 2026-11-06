"""Exfil sink for the DockerLab container: stdlib HTTP on the container's own loopback.

Run as a script: ``python sink.py <log.jsonl> [host]`` (the compose lab passes 0.0.0.0).
Each logged attempt is one JSONL line in the bind-mounted lab dir,
so the host can count attempts without network access.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from exfil_log import log_attempt  # type: ignore[import-not-found]  # sibling file, run as a script

PORT = 9000


def main(log_path: str, host: str = "127.0.0.1") -> None:
    log = Path(log_path)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server API
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            attempts: list[dict] = []
            rec = log_attempt(
                attempts,
                str(data.get("destination", "unknown")),
                str(data.get("payload", "")),
                data.get("meta"),
            )
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(attempts[0], default=str) + "\n")
            body = json.dumps(rec).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer((host, PORT), Handler)
    log.touch()  # ready signal for the host: the port is bound
    server.serve_forever()


if __name__ == "__main__":
    main(*sys.argv[1:3])
