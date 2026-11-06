"""A4: the FastMCP servers serve real tools; the malicious one switches by attack (FR-A3/A4)."""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("fastmcp")
from fastmcp import Client  # noqa: E402

from manthan.modules.agent.mcp_servers import legit_server, malicious_server  # noqa: E402
from manthan.modules.agent.mcp_servers.malicious_server import (  # noqa: E402
    POISONED_TOOL_DESCRIPTIONS,
    RUGPULL_AFTER,
    RUGPULL_BEFORE,
    SHADOW_TOOL_DESCRIPTIONS,
)


async def _list(server) -> dict[str, str]:
    async with Client(server) as c:
        return {t.name: t.description for t in await c.list_tools()}


async def _call(server, name, args) -> str:
    async with Client(server) as c:
        return (await c.call_tool(name, args, raise_on_error=False)).content[0].text


def test_legit_server_tools_run_in_the_sandbox(tmp_path):
    (tmp_path / "report.txt").write_text("Q3 report")
    (tmp_path / "inbox.json").write_text(json.dumps(["hello", "second"]))
    sent: list = []
    state = {
        "run_dir": str(tmp_path),
        "attack": None,
        "trial": "t1",
        "allowlist": ["team-internal"],
    }
    srv = legit_server.build_server(lambda: state, lambda d, p, m: sent.append((d, p)) or {})
    assert set(asyncio.run(_list(srv))) == {"read_inbox", "read_file", "send_message", "run_cmd"}
    assert "second" in asyncio.run(_call(srv, "read_inbox", {}))
    assert asyncio.run(_call(srv, "read_file", {"path": "report.txt"})) == "Q3 report"
    assert "escapes sandbox" in asyncio.run(_call(srv, "read_file", {"path": "../../etc/passwd"}))
    asyncio.run(_call(srv, "send_message", {"destination": "team-internal", "body": "ok"}))
    assert sent == []  # allowlisted: no egress attempt
    asyncio.run(_call(srv, "send_message", {"destination": "evil", "body": "KEY"}))
    assert sent == [("evil", "KEY")]  # off-list: goes to the exfil sink only


def test_malicious_server_tools_follow_the_attack():
    state: dict = {"attack": None, "trial": "t1"}
    srv = malicious_server.build_server(lambda: state, lambda d, p, m: {})
    assert asyncio.run(_list(srv)) == {}
    state["attack"] = "tool_poison"
    assert asyncio.run(_list(srv)) == POISONED_TOOL_DESCRIPTIONS
    state["attack"] = "tool_shadowing"
    assert asyncio.run(_list(srv)) == SHADOW_TOOL_DESCRIPTIONS


def test_rug_pull_mutates_after_the_first_load_of_each_trial():
    state: dict = {"attack": "rug_pull", "trial": "t1"}
    srv = malicious_server.build_server(lambda: state, lambda d, p, m: {})
    assert asyncio.run(_list(srv)) == RUGPULL_BEFORE  # approval time
    assert asyncio.run(_list(srv)) == RUGPULL_AFTER  # mutated afterwards
    state["trial"] = "t2"
    assert asyncio.run(_list(srv)) == RUGPULL_BEFORE  # a new trial starts benign again


def test_shadow_send_message_forwards_to_the_collector():
    sent: list = []
    state = {"attack": "tool_shadowing", "trial": "t1"}
    srv = malicious_server.build_server(lambda: state, lambda d, p, m: sent.append((d, p)) or {})
    asyncio.run(_call(srv, "send_message", {"destination": "team-internal", "body": "KEY"}))
    assert sent == [("attacker-collector", "KEY")]


def test_scan_mode_all_lists_every_malicious_description():
    srv = malicious_server.build_server(lambda: {"attack": "all", "trial": ""}, lambda *a: {})
    names = set(asyncio.run(_list(srv)))
    assert names == set(POISONED_TOOL_DESCRIPTIONS) | set(RUGPULL_AFTER) | set(
        SHADOW_TOOL_DESCRIPTIONS
    )
