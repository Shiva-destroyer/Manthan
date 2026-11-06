"""Static detection: snyk-agent-scan inspect + in-repo heuristic (PRD §10, FR-A5).

Live mode runs ``snyk-agent-scan inspect`` (local, offline) on a config that
lists only the lab's own two MCP servers and feeds the descriptions it prints to
the in-repo heuristic; the hosted ``scan`` command is never called. A missing or
failing binary degrades to the heuristic over the shipped descriptions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Signatures of a poisoned / hidden-instruction tool description.
_SIGNATURES = [
    r"ignore (?:all |the |your )?(?:previous|prior|above)",
    r"disregard (?:prior|previous|safety)",
    r"exfiltrat",
    r"\.ssh/id_rsa",
    r"\bcredential",
    r"\bapi[_ ]?token",
    r"send .{0,40}(?:external|collector|attacker)",
    r"</?(?:important|system|secret|instructions?)>",
    r"do not (?:mention|tell) (?:the )?user",
    r"override (?:the )?(?:trusted|safety)",
]
_SIG_RE = re.compile("|".join(_SIGNATURES), re.IGNORECASE)
log = logging.getLogger(__name__)


@dataclass
class ScanFinding:
    tool: str
    flagged: bool
    reasons: list[str] = field(default_factory=list)


def _hash(desc: str) -> str:
    return hashlib.sha256(desc.encode("utf-8")).hexdigest()[:16]


def scan_descriptions(descriptions: dict[str, str]) -> dict[str, ScanFinding]:
    """Heuristically flag poisoned tool descriptions."""
    out: dict[str, ScanFinding] = {}
    for tool, desc in descriptions.items():
        reasons = [m.group(0) for m in _SIG_RE.finditer(desc or "")]
        out[tool] = ScanFinding(tool=tool, flagged=bool(reasons), reasons=reasons)
    return out


def detect_rug_pull(before: dict[str, str], after: dict[str, str]) -> dict[str, bool]:
    """Flag tools whose description hash changed after approval (rug-pull)."""
    changed: dict[str, bool] = {}
    for tool, desc in after.items():
        if tool in before:
            changed[tool] = _hash(before[tool]) != _hash(desc)
    return changed


def detect_shadowing(legit: dict[str, str], candidate: dict[str, str]) -> dict[str, bool]:
    """Flag candidate tools that shadow a legit tool name with a poisoned desc."""
    out: dict[str, bool] = {}
    for tool, desc in candidate.items():
        if tool in legit:
            out[tool] = scan_descriptions({tool: desc})[tool].flagged
    return out


def catch_rate(descriptions: dict[str, str], poison_names: set[str]) -> float:
    """Fraction of truly-poisoned tools the heuristic flags (target > 0.90)."""
    if not poison_names:
        return 1.0
    findings = scan_descriptions(descriptions)
    caught = sum(1 for n in poison_names if findings.get(n) and findings[n].flagged)
    return caught / len(poison_names)


class MCPScanRunner:
    """Live ``snyk-agent-scan inspect`` on the lab's own servers, heuristic fallback.

    ``inspect`` only lists each server's tool descriptions (it flags nothing and
    never calls the hosted ``scan`` service), so the in-repo heuristic still makes
    the call; ``scanner`` records where the descriptions came from.
    """

    def __init__(self, use_live: bool = False, venv: str | Path | None = None):
        self.use_live = use_live
        self.venv = Path(venv) if venv else Path.home() / ".venvs" / "mcp-scan"
        self.scanner = "heuristic"

    def run(self, descriptions: dict[str, str]) -> dict[str, ScanFinding]:
        return scan_descriptions(descriptions)

    def scan_lab(self) -> tuple[dict[str, ScanFinding], dict[str, ScanFinding]]:
        """Findings for the legit and the malicious lab server (every malicious view)."""
        self.scanner = "heuristic"
        if self.use_live:
            try:
                legit, malicious = self._inspect_lab()
                self.scanner = "snyk-inspect"
                return scan_descriptions(legit), scan_descriptions(malicious)
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
                log.warning("snyk-agent-scan inspect failed (%s); using the heuristic", exc)
        from manthan.modules.agent.agent.graph import LEGIT_TOOLS
        from manthan.modules.agent.mcp_servers.malicious_server import _VIEWS

        return scan_descriptions(dict(LEGIT_TOOLS)), scan_descriptions(_VIEWS["all"])

    def _inspect_lab(self) -> tuple[dict[str, str], dict[str, str]]:
        pkg = "manthan.modules.agent.mcp_servers."
        servers = {
            "manthan-legit": {"command": sys.executable, "args": ["-m", pkg + "legit_server"]},
            "manthan-malicious": {
                "command": sys.executable,
                "args": ["-m", pkg + "malicious_server", "--mode", "all"],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "lab-mcp.json"
            cfg.write_text(json.dumps({"mcpServers": servers}))
            proc = subprocess.run(
                [
                    str(self.venv / "bin" / "snyk-agent-scan"),
                    "inspect",
                    "--json",
                    "--no-skills",
                    "--storage-file",
                    str(Path(tmp) / "scan-state.json"),
                    "--dangerously-run-mcp-servers",  # only our own two lab modules
                    "--suppress-mcpserver-io",
                    "true",
                    str(cfg),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
        found: dict[str, dict[str, str]] = {}
        for entry in json.loads(proc.stdout).values():
            for srv in entry.get("servers") or []:
                tools = (srv.get("signature") or {}).get("tools") or []
                found[srv["name"]] = {t["name"]: t.get("description") or "" for t in tools}
        return found["manthan-legit"], found["manthan-malicious"]

    @staticmethod
    def parse_recorded_scan(path: str | Path) -> dict[str, ScanFinding]:
        """Parse a recorded mcp-scan output fixture (JSON) into findings."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return MCPScanRunner._from_rows(data)

    @staticmethod
    def _from_rows(data: Any) -> dict[str, ScanFinding]:
        out: dict[str, ScanFinding] = {}
        rows = data.get("tools", data) if isinstance(data, dict) else data
        for row in rows:
            tool = str(row.get("tool", row.get("name", "unknown")))
            flagged = bool(row.get("flagged", row.get("risk", "").lower() in {"high", "critical"}))
            out[tool] = ScanFinding(tool=tool, flagged=flagged, reasons=row.get("reasons", []))
        return out
