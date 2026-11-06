"""The one exfil-logging rule, stdlib only (it also runs in the no-network lab container)."""

from __future__ import annotations

from datetime import UTC, datetime


def log_attempt(attempts: list[dict], destination: str, payload: str, meta: dict | None) -> dict:
    attempts.append(
        {
            "at": datetime.now(UTC).isoformat(),
            "destination": destination,
            "payload_len": len(payload or ""),
            "payload_preview": (payload or "")[:48],
            "meta": meta or {},
        }
    )
    # Store nothing real: we deliberately discard the payload body.
    return {"status": "logged", "stored": False}
