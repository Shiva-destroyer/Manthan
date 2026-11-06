"""D4: the UI answers only to this machine's own pages (DNS rebinding and cross-site writes)."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def allowed_hosts(port: int) -> set[str]:
    return {f"127.0.0.1:{port}", f"localhost:{port}"}


def allowed_origins(port: int) -> set[str]:
    return {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}


class LocalOnly:
    """Pure ASGI middleware. Sends no CORS headers, so a browser never lets another site read us."""

    def __init__(self, app: ASGIApp, port: int) -> None:
        self.app = app
        self.hosts = allowed_hosts(port)
        self.origins = allowed_origins(port)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        origin = headers.get("origin")
        reason = None
        if headers.get("host") not in self.hosts:
            reason = "host not allowed"
        elif origin is not None and origin not in self.origins:
            reason = "origin not allowed"
        elif origin is None and scope.get("method") not in ("GET", "HEAD"):
            reason = "origin required"
        if reason is None:
            await self.app(scope, receive, send)
        elif scope["type"] == "http":
            await JSONResponse({"error": reason}, status_code=403)(scope, receive, send)
        else:
            await send({"type": "websocket.close", "code": 1008})
