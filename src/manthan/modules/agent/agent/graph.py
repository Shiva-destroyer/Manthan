"""Agent trajectory model + LangGraph agent (PRD §10, FR-A2).

The tool-call / trajectory datatypes are the lingua franca of the agent module:
the SimulatedLab emits them deterministically for CI, the runtime monitor scores
them, and the report renders them step-by-step (showing where an injected
instruction entered context). The live labs run the LangGraph loop below, with
tools served by the FastMCP lab servers (lazy imports, local-only).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypedDict

# The small tool registry the agent is given (§10.2). Descriptions double as the
# "legit" MCP tool descriptions the static scanner diffs against.
LEGIT_TOOLS: dict[str, str] = {
    "read_inbox": "Read the user's inbox messages and return their text.",
    "send_message": "Send a short message to an internal destination on the allowlist.",
    "read_file": "Read a file from the agent's sandboxed working directory.",
    "run_cmd": "Run an allowlisted, sandboxed shell command and return its output.",
}


@dataclass
class ToolCall:
    """One step of an agent trajectory, with a ground-truth malicious label."""

    step: int
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    destination: str | None = None
    carries_secret: bool = False
    off_task: bool = False
    source: str = "agent"  # "agent" | "injected-content"
    malicious: bool = False  # ground truth, for monitor precision/recall
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "tool": self.tool,
            "args": self.args,
            "destination": self.destination,
            "carries_secret": self.carries_secret,
            "off_task": self.off_task,
            "source": self.source,
            "malicious": self.malicious,
            "note": self.note,
        }


@dataclass
class Trajectory:
    """An ordered agent run, with the step where injection entered context."""

    objective: str
    steps: list[ToolCall] = field(default_factory=list)
    injection_step: int | None = None  # where injected instruction entered (US-A3)

    def as_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "injection_step": self.injection_step,
            "steps": [s.as_dict() for s in self.steps],
        }

    @property
    def ground_truth(self) -> list[bool]:
        return [s.malicious for s in self.steps]


class McpToolbox:
    """Tools from MCP servers through open fastmcp ``Client`` sessions.

    Later clients win a name clash (that is how a shadowing server takes over a
    legit tool). Every ``list_tools`` is kept in ``loads`` so a rug pull shows.
    """

    def __init__(self, clients: list[Any]) -> None:
        self.clients = clients
        self.owner: dict[str, Any] = {}
        self.loads: list[dict[str, str]] = []

    async def list_tools(self) -> list[dict]:
        merged: dict[str, tuple[Any, Any]] = {}
        for client in self.clients:
            for tool in await client.list_tools():
                merged[tool.name] = (client, tool)
        self.owner = {name: client for name, (client, _) in merged.items()}
        self.loads.append({name: tool.description or "" for name, (_, tool) in merged.items()})
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for name, (_, tool) in merged.items()
        ]

    async def call(self, name: str, args: dict) -> str:
        client = self.owner.get(name)
        if client is None:
            return f"error: unknown tool {name!r}"
        res = await client.call_tool(name, args, raise_on_error=False)
        return "\n".join(getattr(block, "text", "") for block in res.content)


class AgentState(TypedDict):
    messages: list[dict]
    steps: int


def build_langgraph_agent(
    backend: Any,
    model: str,
    toolbox: McpToolbox,
    call_tool: Callable[[str, dict], Awaitable[str]] | None = None,
    on_tool: Callable[[str, dict, str], None] | None = None,
    max_steps: int = 6,
    seed: int | None = None,
):
    """Plan, call tools, observe; stop on a final answer or after ``max_steps`` model turns.

    Invoke with ``ainvoke(state, {"recursion_limit": 2 * max_steps + 2})``.
    """
    try:
        from langgraph.graph import END, StateGraph  # type: ignore
    except ImportError as exc:
        raise RuntimeError("the live agent needs the '[agent]' extra (langgraph).") from exc
    run_tool = call_tool or toolbox.call

    async def agent(state: AgentState) -> dict:
        tools = await toolbox.list_tools()  # re-list every turn, so a rug pull reaches the model
        msg = backend.chat_tools(model, state["messages"], tools, seed=seed)
        return {"messages": [*state["messages"], msg], "steps": state["steps"] + 1}

    async def act(state: AgentState) -> dict:
        messages = list(state["messages"])
        for call in messages[-1].get("tool_calls") or []:
            name = call["function"]["name"]
            args = dict(call["function"].get("arguments") or {})
            result = await run_tool(name, args)
            if on_tool:
                on_tool(name, args, result)
            messages.append({"role": "tool", "content": result, "tool_name": name})
        return {"messages": messages}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent)
    graph.add_node("tools", act)
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent", lambda s: "tools" if s["messages"][-1].get("tool_calls") else END
    )
    graph.add_conditional_edges("tools", lambda s: "agent" if s["steps"] < max_steps else END)
    return graph.compile()
