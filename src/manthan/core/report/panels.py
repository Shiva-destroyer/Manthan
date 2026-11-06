"""Per-module report panels (PRD FR-C8, FR-A7): series read from the store, inline SVG.

Prompt ASR by strategy, the RAG ASR-vs-N curve with the dASR table, and the agent
trajectories with detection P/R. Same head-less matplotlib pattern as ``heatmap.py``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from manthan.core.report.heatmap import _svg_body
from manthan.core.store.db import Store

# These two defenses know the attack target or the poison, so their dASR is an upper bound.
ORACLE_LAYERS = ("output_validator", "retrieval_filter")


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _err(rows: list[dict[str, Any]]) -> list[list[float]]:
    lo = [r["value"] - r["ci_low"] if r["ci_low"] is not None else 0.0 for r in rows]
    hi = [r["ci_high"] - r["value"] if r["ci_high"] is not None else 0.0 for r in rows]
    return [lo, hi]


def bar_svg(rows: list[dict[str, Any]], labels: list[str], title: str) -> str:
    """Bars of metric values with Wilson CI whiskers where the metric has a CI."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(max(4, 1.2 * len(rows) + 2), 3))
    ax.bar(labels, [r["value"] for r in rows], yerr=_err(rows), capsize=4, color="#36b3c2")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("ASR")
    ax.set_title(title, fontsize=10)
    ax.tick_params(axis="x", labelsize=8)
    out = _svg_body(fig)
    plt.close(fig)
    return out


def line_svg(xs: list[int], rows: list[dict[str, Any]], title: str) -> str:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(5, 3))
    ys = [r["value"] for r in rows]
    ax.errorbar(xs, ys, yerr=_err(rows), marker="o", capsize=4, color="#e3a84a")
    ax.set_xticks(xs)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("poisoned documents in the corpus (N)")
    ax.set_ylabel("ASR")
    ax.set_title(title, fontsize=10)
    out = _svg_body(fig)
    plt.close(fig)
    return out


def _trajectories(store: Store, campaign_id: str, pwned: dict[str, float]) -> list[dict[str, Any]]:
    out = []
    for r in store.runs_for(campaign_id):
        if r["domain"] != "agent" or r["objective_id"] == "agent-benchmark":
            continue
        steps = [json.loads(t["content"]) for t in store.turns_for_run(r["id"])]
        inj = next((s["step"] for s in steps if s.get("source") == "injected-content"), None)
        out.append(
            {
                "label": r["objective_id"],
                "steps": steps,
                "injection_step": inj,
                "pwned": bool(pwned.get(r["id"])),
                "detected": any(s.get("flagged") for s in steps),
            }
        )
    return out


def collect_panels(store: Store, campaign_id: str) -> dict[str, Any]:
    """Return the prompt / rag / agent panels that have data (absent keys = no panel)."""
    by: dict[str, dict[str, dict[str, Any]]] = {}
    pwned: dict[str, float] = {}
    for m in store.metrics_for_campaign(campaign_id):
        by.setdefault(m["run_domain"], {})[m["name"]] = dict(m)
        if m["name"] == "pwned":
            pwned[m["run_id"]] = m["value"]
    panels: dict[str, Any] = {}

    pm = by.get("prompt", {})
    strat = sorted(n for n in pm if n.startswith("asr_"))
    if strat:
        rows = [pm[n] for n in strat]
        kappa = pm.get("inline_vs_authoritative_kappa")
        panels["prompt"] = {
            "svg": bar_svg(rows, [n[4:] for n in strat], "Prompt ASR by strategy (95% CI)"),
            "kappa": kappa["value"] if kappa else None,
        }

    rm = by.get("rag", {})
    ns = sorted(int(n[5:]) for n in rm if re.fullmatch(r"asr_n\d+", n))
    if ns:
        layers = sorted(n[5:] for n in rm if n.startswith("dASR_"))
        agree = rm.get("rag_judge_agreement")
        panels["rag"] = {
            "svg": line_svg(ns, [rm[f"asr_n{n}"] for n in ns], "RAG ASR vs N (95% CI)"),
            "dasr": [
                {
                    "layer": layer,
                    "dasr": rm[f"dASR_{layer}"]["value"],
                    "benign_acc": rm.get(f"benign_acc:{layer}", {}).get("value"),
                    "oracle": layer in ORACLE_LAYERS,
                }
                for layer in layers
            ],
            "judge_agreement": agree["value"] if agree else None,
        }

    am = by.get("agent", {})
    classes = sorted(n for n in am if n.startswith("asr_"))
    traj = _trajectories(store, campaign_id, pwned)
    if classes or traj:
        panels["agent"] = {
            "svg": (
                bar_svg([am[n] for n in classes], [n[4:] for n in classes], "Agent ASR by class")
                if classes
                else ""
            ),
            "precision": am.get("monitor_precision", {}).get("value"),
            "recall": am.get("monitor_recall", {}).get("value"),
            "static": am.get("static_detection_rate", {}).get("value"),
            "utility": {n[8:]: am[n]["value"] for n in sorted(am) if n.startswith("utility_")},
            "steps_to_exfil": am.get("steps_to_exfil", {}).get("value"),
            "trajectories": traj,
        }
    return panels


def trajectory_markdown(agent: dict[str, Any]) -> list[str]:
    """FR-A7 Markdown export: one table per stored trajectory."""
    lines = ["", "## Agent trajectories", ""]
    if agent.get("precision") is not None:
        lines.append(f"Monitor precision {agent['precision']:.3f} · recall {agent['recall']:.3f}")
    if agent.get("utility"):
        util = ", ".join(f"{c} {u:.2f}" for c, u in agent["utility"].items())
        lines.append(f"Utility under attack: {util}")
    if agent.get("steps_to_exfil") is not None:
        lines.append(f"Median steps to exfil: {agent['steps_to_exfil']}")
    for t in agent["trajectories"]:
        inj = (
            f"injection at step {t['injection_step']}"
            if t["injection_step"] is not None
            else ("no injection")
        )
        lines += [
            "",
            f"### {t['label']} ({'pwned' if t['pwned'] else 'not pwned'}, {inj}, "
            f"{'detected' if t['detected'] else 'not detected'})",
            "",
            "| Step | Tool | Source | Malicious | Flagged |",
            "|---:|---|---|---|---|",
        ]
        for s in t["steps"]:
            yn = {True: "yes", False: "no"}
            lines.append(
                f"| {s['step']} | {s['tool']} | {s.get('source', '')} | "
                f"{yn[bool(s.get('malicious'))]} | {yn[bool(s.get('flagged'))]} |"
            )
    return lines
