"""Shared reporter — one HTML + Markdown report with the coverage heatmap.

Reads the SQLite store for a campaign and renders a self-contained HTML report
(inline CSS + inline SVG heatmap) and a Markdown summary (PRD §8.6, FR-C8). The
report leads with the defensive-scope banner and the "Runtime cost ₹0/$0"
headline, aggregates findings into the cross-domain OWASP×ATLAS heatmap, and
records full provenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from manthan.core.judge.ensemble import REAL_LABELED_SET, CalibrationReport, JudgeCalibration
from manthan.core.metrics.asr import asr
from manthan.core.report.heatmap import render_heatmap
from manthan.core.report.panels import collect_panels, trajectory_markdown
from manthan.core.store.db import Store
from manthan.core.taxonomy.registry import get_registry

_TEMPLATES = Path(__file__).resolve().parent / "templates"
_ASSETS = Path(__file__).resolve().parents[4] / "assets"  # repo-root assets/
# Written once from the frozen test-split scoring (session 4, P2); read when present.
FROZEN_CALIBRATION = REAL_LABELED_SET.with_name("judge_calibration_real.json")
_LOGO_FALLBACK = (
    '<svg viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="48" cy="48" r="30" fill="none" stroke="currentColor" stroke-width="4"/>'
    '<circle cx="48" cy="48" r="4" fill="#e3a84a"/></svg>'
)


@dataclass
class ReportPaths:
    html: Path
    markdown: Path


def _load_frozen_calibration() -> tuple[CalibrationReport | None, str]:
    if not FROZEN_CALIBRATION.exists():
        return None, ""
    d = json.loads(FROZEN_CALIBRATION.read_text(encoding="utf-8"))
    per = {k: JudgeCalibration(**v) for k, v in d["per_judge"].items()}
    rep = CalibrationReport(per, d["pairwise_kappa"], d["fleiss_kappa"], d["n_items"])
    return rep, str(d.get("source", FROZEN_CALIBRATION.name))


def _load_logo() -> str:
    p = _ASSETS / "logo.svg"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return _LOGO_FALLBACK


class Reporter:
    """Renders the unified report for a campaign from the store."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self.env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES)),
            autoescape=select_autoescape(["html"]),
        )
        self.registry = get_registry()

    # --- context assembly -------------------------------------------------
    def _context(
        self,
        campaign_id: str,
        judge_calibration: Any | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        manifest = manifest or {}
        calibration_source = ""
        if judge_calibration is None:
            judge_calibration, calibration_source = _load_frozen_calibration()
        camp = self.store.get_campaign(campaign_id)
        if camp is None:
            raise ValueError(f"no campaign {campaign_id!r} in store")
        runs = self.store.runs_for(campaign_id)
        findings_rows = self.store.findings_for_campaign(campaign_id)

        # Attach tags to each finding.
        tags_by_finding: dict[str, dict[str, list[str]]] = {}
        for t in self.store.tags_for_campaign(campaign_id):
            d = tags_by_finding.setdefault(t["finding_id"], {"owasp": [], "atlas": []})
            if t["owasp_id"] and t["owasp_id"] not in d["owasp"]:
                d["owasp"].append(t["owasp_id"])
            if t["atlas_id"] and t["atlas_id"] not in d["atlas"]:
                d["atlas"].append(t["atlas_id"])

        findings = []
        n_success = 0
        for f in findings_rows:
            tg = tags_by_finding.get(f["id"], {"owasp": [], "atlas": []})
            if f["success"]:
                n_success += 1
            findings.append(
                {
                    "objective_id": f["objective_id"],
                    "strategy": f["strategy"],
                    "success": bool(f["success"]),
                    "evaded_defense": bool(f["evaded_defense"]),
                    "owasp": tg["owasp"],
                    "atlas": tg["atlas"],
                }
            )

        n_findings = len(findings)
        overall = asr(n_success, n_findings) if n_findings else None

        metrics = []
        for m in self.store.metrics_for_campaign(campaign_id):
            metrics.append(
                {
                    "domain": m["run_domain"] or camp["domain"],
                    "name": m["name"],
                    "value": m["value"],
                    "ci_low": m["ci_low"],
                    "ci_high": m["ci_high"],
                    "method": m["method"],
                }
            )

        heatmap_svg = render_heatmap(self.store.heatmap_counts(campaign_id))

        provenance = {
            "config_hash": camp["config_hash"],
            "seed": camp["seed"],
            "backend": "mock / ollama (local)",
            "models": "target=qwen2.5:7b · attacker=llama3.2:3b · judge=phi4-mini",
            "owasp_version": self.registry.owasp_version,
            "atlas_version": self.registry.atlas_version,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "model_digests": manifest.get("model_digests", {}),
            "agent_lab": manifest.get("agent_lab", {}),
        }

        return {
            "campaign": dict(camp),
            "n_runs": len(runs),
            "n_findings": n_findings,
            "overall_asr": overall.point if overall else 0.0,
            "metrics": metrics,
            "findings": findings,
            "heatmap_svg": heatmap_svg,
            "logo_svg": _load_logo(),
            "provenance": provenance,
            "judge_calibration": judge_calibration,
            "calibration_source": calibration_source,
            "panels": collect_panels(self.store, campaign_id),
        }

    # --- rendering --------------------------------------------------------
    def render(
        self,
        campaign_id: str,
        out_dir: str | Path = "data/results",
        judge_calibration: Any | None = None,
    ) -> ReportPaths:
        out = Path(out_dir)
        man_path = out / campaign_id / "manifest.json"
        manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
        ctx = self._context(campaign_id, judge_calibration=judge_calibration, manifest=manifest)
        out.mkdir(parents=True, exist_ok=True)
        html_path = out / f"report-{campaign_id}.html"
        md_path = out / f"report-{campaign_id}.md"
        html_path.write_text(
            self.env.get_template("report.html.j2").render(**ctx), encoding="utf-8"
        )
        md_path.write_text(self._markdown(ctx), encoding="utf-8")
        return ReportPaths(html=html_path, markdown=md_path)

    def _markdown(self, ctx: dict[str, Any]) -> str:
        lines = [
            "# Manthan report",
            "",
            "**Runtime cost: ₹0 / $0 — fully local, offline, CPU-only.**",
            "",
            "> Defensive scope: attacks ran only against locally-hosted open-weight "
            "models and self-owned, in-repo vulnerable apps. All secrets are synthetic.",
            "",
            f"- Campaign: `{ctx['campaign']['id']}` (domain: {ctx['campaign']['domain']})",
            f"- Runs: {ctx['n_runs']} · Findings: {ctx['n_findings']} · "
            f"Overall ASR: {ctx['overall_asr'] * 100:.0f}%",
            f"- Config hash: `{ctx['provenance']['config_hash']}` · seed: {ctx['provenance']['seed']}",
            "",
            "## Metrics by domain",
            "",
            "| Domain | Metric | Value | 95% CI | Method |",
            "|---|---|---:|---|---|",
        ]
        for m in ctx["metrics"]:
            ci = f"[{m['ci_low']:.3f}, {m['ci_high']:.3f}]" if m["ci_low"] is not None else "—"
            lines.append(
                f"| {m['domain']} | {m['name']} | {m['value']:.3f} | {ci} | {m['method'] or '—'} |"
            )
        if ctx.get("judge_calibration"):
            jc = ctx["judge_calibration"]
            lines += [
                "",
                "## Judge calibration",
                "",
                "| Judge | FPR | TPR | Accuracy |",
                "|---|---:|---:|---:|",
            ]
            for name, cal in jc.per_judge.items():
                lines.append(f"| {name} | {cal.fpr:.3f} | {cal.tpr:.3f} | {cal.accuracy:.3f} |")
            lines.append(f"\nFleiss κ: {jc.fleiss_kappa:.3f} (n={jc.n_items})")
            if ctx.get("calibration_source"):
                lines.append(f"\nSource: {ctx['calibration_source']}")
        if "agent" in ctx["panels"]:
            lines += trajectory_markdown(ctx["panels"]["agent"])
        prov = ctx["provenance"]
        if prov["model_digests"] or prov["agent_lab"]:
            lines += ["", "## Provenance", ""]
            lines += [f"- `{n}`: `{d}`" for n, d in sorted(prov["model_digests"].items())]
            if prov["agent_lab"]:
                lab = prov["agent_lab"]
                lines.append(f"- agent lab: {lab.get('kind')} {lab.get('image') or ''}".rstrip())
        lines += [
            "",
            "## Framework coverage",
            f"- OWASP: {ctx['provenance']['owasp_version']}",
            f"- ATLAS: {ctx['provenance']['atlas_version']}",
            "",
            f"_Generated {ctx['provenance']['generated_at']}._",
            "",
        ]
        return "\n".join(lines)
