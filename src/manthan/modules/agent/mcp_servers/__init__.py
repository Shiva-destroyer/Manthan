"""Legit and malicious MCP servers (FastMCP; descriptions exposed as data)."""

from manthan.modules.agent.mcp_servers.legit_server import LEGIT_TOOL_DESCRIPTIONS
from manthan.modules.agent.mcp_servers.malicious_server import (
    POISONED_TOOL_DESCRIPTIONS,
    RUGPULL_AFTER,
    RUGPULL_BEFORE,
    SHADOW_TOOL_DESCRIPTIONS,
)

__all__ = [
    "LEGIT_TOOL_DESCRIPTIONS",
    "POISONED_TOOL_DESCRIPTIONS",
    "RUGPULL_BEFORE",
    "RUGPULL_AFTER",
    "SHADOW_TOOL_DESCRIPTIONS",
]
