"""Garak static-scanner baseline + adaptive-uplift delta (PRD §9, FR-P6).

Garak is the *sole* static baseline (promptfoo is intentionally out of scope to
keep Manthan a single Python, fully-offline toolchain — §9.1 scope note). A live
Garak run is **local-only**: garak 0.17.1's ollama chat generator hits the same
local target with the same canary system prompt. Tests parse a real saved report.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class GarakResult:
    asr: float
    successes: int
    total: int
    by_probe: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "asr": self.asr,
            "successes": self.successes,
            "total": self.total,
            "by_probe": self.by_probe,
        }


def parse_garak_report(rows: list[dict[str, Any]]) -> GarakResult:
    """Garak's own static ASR from the ``eval`` rows of a garak 0.17.1 report.

    One eval row per (probe, detector): ``fails`` are attack successes. ``nones``
    (unscored outputs) are left out, as garak does.
    """
    total = 0
    successes = 0
    by_probe: dict[str, tuple[int, int]] = {}
    for r in rows:
        if r.get("entry_type") != "eval":
            continue
        s = int(r.get("fails", 0))
        t = s + int(r.get("passed", 0))
        total += t
        successes += s
        probe = str(r.get("probe", "unknown"))
        pt, ps = by_probe.get(probe, (0, 0))
        by_probe[probe] = (pt + t, ps + s)
    asr = successes / total if total else 0.0
    return GarakResult(
        asr=asr,
        successes=successes,
        total=total,
        by_probe={k: (sv / tv if tv else 0.0) for k, (tv, sv) in by_probe.items()},
    )


def garak_outputs(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(prompt, reply) for every scored attempt (status 2), for Manthan's judge."""
    pairs = []
    for r in rows:
        if r.get("entry_type") != "attempt" or r.get("status") != 2:
            continue
        prompt = r["prompt"]["turns"][-1]["content"]["text"]
        pairs += [(prompt, o["text"]) for o in r.get("outputs", []) if o and o.get("text")]
    return pairs


def load_recorded_report(path: str | Path) -> list[dict[str, Any]]:
    """Load a garak report (JSONL rows or a JSON list)."""
    p = Path(path)
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.lstrip().startswith("["):
        return list(json.loads(text))
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def adaptive_uplift(adaptive_asr: float, static_asr: float) -> float:
    """ASR delta in percentage points: adaptive − static (target > +20 pts)."""
    return (adaptive_asr - static_asr) * 100.0


class GarakBaseline:
    """Runs the garak CLI (its own venv) against the local Ollama target."""

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        garak_bin: str = "garak",
        timeout: int = 180,  # garak's default 30 s is too short for qwen on CPU
    ):
        self.model = model
        self.base_url = base_url
        self.garak_bin = garak_bin
        self.timeout = timeout

    def run_offline(
        self,
        probes: str,
        system_prompt: str,
        report_dir: str | Path,
        report_prefix: str = "garak_report",
    ) -> list[dict[str, Any]]:
        """Run the probes once (1 generation each) and return the report rows."""
        report_dir = Path(report_dir).resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        cfg = {
            "run": {"system_prompt": system_prompt},
            "reporting": {"report_dir": str(report_dir)},
            "plugins": {
                "generators": {
                    "ollama": {
                        "OllamaGeneratorChat": {"host": self.base_url, "timeout": self.timeout}
                    }
                }
            },
        }
        cfg_path = report_dir / f"{report_prefix}.config.yaml"
        cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        env = dict(os.environ)
        env["HF_HUB_OFFLINE"] = "1"
        cmd = [
            self.garak_bin,
            "--config",
            str(cfg_path),
            "--target_type",
            "ollama",
            "--target_name",
            self.model,
            "--probes",
            probes,
            "--generations",
            "1",
            "--report_prefix",
            report_prefix,
        ]
        subprocess.run(cmd, env=env, check=True)
        return load_recorded_report(report_dir / f"{report_prefix}.report.jsonl")
