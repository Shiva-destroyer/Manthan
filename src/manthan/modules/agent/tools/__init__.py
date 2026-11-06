"""Sandboxed agent tools (PRD §10.2).

read_inbox · send_message · read_file · run_cmd(guarded). Every tool is
allowlisted and confined to a sandbox directory; ``run_cmd`` only executes
commands on an explicit allowlist. These run only inside the lab container in a
live run; in CI they are exercised as pure logic (no real shell, no real egress).
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path

# Commands the sandboxed run_cmd tool is permitted to execute.
RUN_CMD_ALLOWLIST = {"ls", "cat", "echo", "whoami", "pwd", "head", "wc"}


class ToolError(RuntimeError):
    pass


@dataclass
class ToolContext:
    """Sandbox + policy the tools operate under."""

    sandbox_dir: Path
    egress_allowlist: list[str] = field(default_factory=list)
    inbox: list[str] = field(default_factory=list)
    sent: list[dict] = field(default_factory=list)


def read_inbox(ctx: ToolContext) -> list[str]:
    """Return inbox messages (untrusted content — may carry injection)."""
    return list(ctx.inbox)


def read_file(ctx: ToolContext, path: str) -> str:
    """Read a file, confined to the sandbox directory (no traversal)."""
    target = (ctx.sandbox_dir / path).resolve()
    if ctx.sandbox_dir.resolve() not in target.parents and target != ctx.sandbox_dir.resolve():
        raise ToolError(f"path escapes sandbox: {path!r}")
    if not target.exists():
        raise ToolError(f"no such file: {path!r}")
    return target.read_text(encoding="utf-8")


def send_message(ctx: ToolContext, destination: str, body: str) -> dict:
    """Record a message send; the lab network only reaches the mock listener."""
    record = {"destination": destination, "body": body}
    ctx.sent.append(record)
    return record


def run_cmd(ctx: ToolContext, command: str) -> str:
    """Guarded shell: only allowlisted commands, inside the sandbox dir."""
    parts = shlex.split(command)
    if not parts or parts[0] not in RUN_CMD_ALLOWLIST:
        raise ToolError(f"command not on allowlist: {command!r}")
    # In CI we do not actually spawn a process; return a sanitized echo.
    return f"[sandboxed run_cmd ok] {command}"


TOOLS = {
    "read_inbox": read_inbox,
    "read_file": read_file,
    "send_message": send_message,
    "run_cmd": run_cmd,
}

__all__ = [
    "ToolContext",
    "ToolError",
    "read_inbox",
    "read_file",
    "send_message",
    "run_cmd",
    "TOOLS",
    "RUN_CMD_ALLOWLIST",
]
