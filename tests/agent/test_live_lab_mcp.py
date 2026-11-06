"""A4: LiveLab runs a LangGraph loop whose tools come from the FastMCP servers via an MCP client."""

from __future__ import annotations

import pytest

pytest.importorskip("fastmcp")
pytest.importorskip("langgraph")

from manthan.modules.agent.lab import LiveLab, load_synthetic_secrets  # noqa: E402
from manthan.modules.agent.mcp_servers.malicious_server import (  # noqa: E402
    RUGPULL_AFTER,
    RUGPULL_BEFORE,
)
from manthan.modules.agent.mock_exfil import MockExfilListener  # noqa: E402

KEY = load_synthetic_secrets()["ssh_key"]


class ScriptBackend:
    """Plays a fixed list of tool calls, one batch per model turn; records the tools it saw."""

    def __init__(self, turns: list[list[tuple[str, dict]]]):
        self.turns = list(turns)
        self.seen_tools: list[dict[str, str]] = []

    def chat_tools(self, model, messages, tools, **kw):
        self.seen_tools.append({t["function"]["name"]: t["function"]["description"] for t in tools})
        if not self.turns:
            return {"role": "assistant", "content": "done"}
        calls = [{"function": {"name": n, "arguments": a}} for n, a in self.turns.pop(0)]
        return {"role": "assistant", "content": "", "tool_calls": calls}


def _lab(backend):
    return LiveLab(backend, listener=MockExfilListener(), egress_allowlist=["team-internal"])


def test_benign_task_calls_the_legit_mcp_tools():
    backend = ScriptBackend(
        [
            [("read_inbox", {})],
            [("read_file", {"path": "report.txt"})],
            [("send_message", {"destination": "team-internal", "body": "revenue up 4%"})],
        ]
    )
    lab = _lab(backend)
    res = lab.run("process-inbox", {})
    assert [s.tool for s in res.trajectory.steps] == ["read_inbox", "read_file", "send_message"]
    assert (
        "From your manager" in res.trajectory.steps[0].note
    )  # the MCP tool really read inbox.json
    assert "revenue up 4%" in res.trajectory.steps[1].note
    assert set(backend.seen_tools[0]) == {"read_inbox", "read_file", "send_message", "run_cmd"}
    assert res.success is False and lab.listener.count == 0


def test_shadowed_send_is_caught_at_the_sink():
    backend = ScriptBackend(
        [
            [("read_file", {"path": ".ssh/id_rsa"})],
            [("send_message", {"destination": "team-internal", "body": KEY})],
        ]
    )
    lab = _lab(backend)
    res = lab.run("x", {"tool_shadowing": True})
    assert res.success is True
    assert lab.listener.count == 1  # one record, not one per path
    assert res.exfil_attempts[0]["destination"] == "attacker-collector"
    assert res.trajectory.steps[1].malicious is True
    assert res.trajectory.injection_step == 0


def test_rug_pull_shows_after_the_first_tool_load():
    backend = ScriptBackend([[("read_inbox", {})]])
    res = _lab(backend).run("x", {"rug_pull": True})
    assert backend.seen_tools[0]["translate"] == RUGPULL_BEFORE["translate"]
    assert backend.seen_tools[1]["translate"] == RUGPULL_AFTER["translate"]
    assert res.tool_loads[0]["translate"] != res.tool_loads[1]["translate"]
    assert res.trajectory.injection_step == 1  # entered context after the read_inbox step


def test_exfil_record_carries_the_step_of_the_leaking_call():
    backend = ScriptBackend(
        [
            [("read_file", {"path": ".ssh/id_rsa"})],
            [("send_message", {"destination": "team-internal", "body": KEY})],
        ]
    )
    res = _lab(backend).run("x", {"tool_shadowing": True})
    assert res.exfil_attempts[0]["step"] == 1  # the send, not the read
