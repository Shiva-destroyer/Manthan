"""Static (mcp-scan) and runtime detection for the agent lab."""

from manthan.modules.agent.detect.mcp_scan_runner import (
    MCPScanRunner,
    ScanFinding,
    catch_rate,
    detect_rug_pull,
    detect_shadowing,
    scan_descriptions,
)
from manthan.modules.agent.detect.runtime_monitor import MonitorResult, RuntimeMonitor

__all__ = [
    "MCPScanRunner",
    "ScanFinding",
    "scan_descriptions",
    "detect_rug_pull",
    "detect_shadowing",
    "catch_rate",
    "RuntimeMonitor",
    "MonitorResult",
]
