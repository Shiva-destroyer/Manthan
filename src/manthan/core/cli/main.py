"""The single ``manthan`` CLI / orchestrator (PRD §8.8).

Subcommands: run · judge · calibrate · report · dashboard · verify-taxonomy ·
models (pull/status) · init. One Typer app; the console_scripts entry is
``manthan = "manthan.core.cli.main:app"``.
"""

from __future__ import annotations

import json
import logging
import signal
import sys
from pathlib import Path
from typing import Any

import typer
import yaml

from manthan.core.cli.orchestrator import (
    build_backend,
    build_ensemble,
    expand_domains,
    run_campaign,
)
from manthan.core.config.models import load_config
from manthan.core.model import Transcript
from manthan.core.report.report import Reporter
from manthan.core.store.db import Store
from manthan.core.taxonomy.registry import TaxonomyError, get_registry

app = typer.Typer(
    name="manthan",
    help="Manthan — unified local-first AI red-teaming & defense harness. Churn the model; separate the poison from the nectar.",
    no_args_is_help=True,
    add_completion=False,
)
models_app = typer.Typer(help="Manage local Ollama models (pull/status).")
app.add_typer(models_app, name="models")

_PULL_LIST = [
    "qwen2.5:7b",
    "llama3.2:3b",
    "phi4-mini",
    "nomic-embed-text",
]
_OPTIONAL_PULL = ["llama3.1:8b"]


def _echo(msg: str) -> None:
    typer.echo(msg)


# --- init -----------------------------------------------------------------
@app.command()
def init(
    root: Path = typer.Option(Path("."), help="Project root to scaffold data dirs under."),
) -> None:
    """Scaffold data dirs, print the model pull-list and residency plan."""
    (root / "data" / "results").mkdir(parents=True, exist_ok=True)
    _echo("Created data/results/")
    _echo("\nModels to pull (operator runs these once; Manthan does not):")
    _echo(f"  ollama pull {' '.join(_PULL_LIST)}")
    _echo(f"  (optional RAG generator)  ollama pull {' '.join(_OPTIONAL_PULL)}")
    _echo("  HF guard (non-gated, auto-downloads on first use):")
    _echo("    protectai/deberta-v3-base-prompt-injection-v2")
    _echo("\nCI / offline default:  MANTHAN_BACKEND=mock   (zero network, $0)")
    _echo("See docs/running-locally.md for the full laptop runbook.")


# --- models ---------------------------------------------------------------
@models_app.command("status")
def models_status(config: Path | None = typer.Option(None, "--config")) -> None:
    """Print the residency plan and a RAM pre-flight check."""
    cfg = load_config(config)
    _echo(f"Backend: {cfg.models.backend}  |  residency mode: {cfg.models.residency.mode}")
    _echo("Roles:")
    for role, rm in cfg.models.roles.items():
        _echo(f"  {role:9s} -> {rm.model}  (keep_alive={rm.keep_alive})")
    try:
        from manthan.core.model.scheduler import available_ram_gb

        avail = available_ram_gb()
        _echo(f"\nMeasured available RAM: {avail:.1f} GiB")
        _echo("Peak-RAM budget per phase (generation): ~17-18 GB; target headroom >= 5 GB (NFR-1).")
    except Exception as exc:  # pragma: no cover
        _echo(f"(RAM check unavailable: {exc})")


@models_app.command("pull")
def models_pull() -> None:
    """Print the exact `ollama pull` commands (does not download anything)."""
    _echo(f"ollama pull {' '.join(_PULL_LIST)}")
    _echo(f"ollama pull {' '.join(_OPTIONAL_PULL)}   # optional RAG generator")
    _echo("\nManthan never downloads models for you — run these on your laptop.")


class _JsonFormatter(logging.Formatter):
    """NFR-8: one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        rec = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            rec["exc"] = self.formatException(record.exc_info)
        return json.dumps(rec)


# --- run ------------------------------------------------------------------
@app.command()
def run(
    target: str = typer.Argument(..., help="prompt | agent | rag | all"),
    smoke: bool = typer.Option(False, "--smoke", help="Reduced objective set for fast end-to-end."),
    seed: int | None = typer.Option(None, "--seed"),
    config: Path | None = typer.Option(None, "--config"),
    skip: list[str] = typer.Option(
        [], "--skip", help="Domain to leave out (repeatable); recorded in the manifest."
    ),
    verbose: bool = typer.Option(False, "--verbose", help="DEBUG logging (one line per run)."),
    log_json: bool = typer.Option(False, "--log-json", help="One JSON object per log line."),
) -> None:
    """Run a campaign in one or all domains and render the unified report."""
    if target not in ("prompt", "agent", "rag", "all"):
        raise typer.BadParameter("target must be one of: prompt, agent, rag, all")
    if bad := set(skip) - {"prompt", "agent", "rag"}:
        raise typer.BadParameter(f"--skip takes prompt, agent or rag, not {sorted(bad)}")
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(
        _JsonFormatter()
        if log_json
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.basicConfig(level=level, handlers=[handler])
    logging.getLogger("manthan").setLevel(level)
    cfg = load_config(config)
    if seed is not None:
        cfg.seed = seed
    domains = expand_domains(target, cfg)
    store = Store(cfg.results_db)
    label = f"{target}{' smoke' if smoke else ''}"
    # The UI's Stop sends SIGTERM; exiting through SystemExit lets run_campaign close its log.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    manifest = run_campaign(
        cfg,
        domains,
        store,
        smoke=smoke,
        label=label,
        skip=skip,
        events_dir=Path(cfg.results_db).parent,
    )

    _echo(f"Campaign {manifest.campaign_id} — domains run: {manifest.domains_run}")
    for sk in manifest.domains_skipped:
        _echo(f"  [skipped] {sk['domain']}: {sk['reason']}")
    # Persist the run manifest first (skipped domains, digests); the report reads it.
    man_dir = Path(cfg.results_db).parent / manifest.campaign_id
    man_dir.mkdir(parents=True, exist_ok=True)
    (man_dir / "manifest.json").write_text(
        json.dumps(manifest.as_dict(), indent=2), encoding="utf-8"
    )
    reporter = Reporter(store)
    paths = reporter.render(manifest.campaign_id, out_dir=Path(cfg.results_db).parent)

    _echo(f"Report: {paths.html}")
    _echo(f"Manifest: {man_dir / 'manifest.json'}")
    _echo("Runtime cost: ₹0 / $0 — fully local, offline, CPU-only.")
    store.close()


# --- judge ----------------------------------------------------------------
@app.command()
def judge(
    run_id: str = typer.Option(..., "--run", help="Run id to (re)score with the ensemble."),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """(Re)score a run's transcripts with the judge ensemble (batched)."""
    cfg = load_config(config)
    store = Store(cfg.results_db)
    backend = build_backend(cfg)
    ensemble = build_ensemble(cfg, backend)
    turns = store.turns_for_run(run_id)
    if not turns:
        _echo(f"No turns found for run {run_id!r}.")
        raise typer.Exit(code=1)
    tr = Transcript(objective_id="rescore", target_label="rescore")
    for t in turns:
        tr.add(t["role"], t["content"])
    ev = ensemble.score(tr)
    _echo(f"Ensemble verdict: {ev.label} (score={ev.score:.2f}, conf={ev.confidence:.2f})")
    for v in ev.member_verdicts:
        _echo(f"  {v.judge_name}: {v.label} ({v.score:.2f})")
    store.close()


# --- calibrate ------------------------------------------------------------
@app.command()
def calibrate(
    config: Path | None = typer.Option(None, "--config"),
    out: Path | None = typer.Option(None, "--out", help="Write calibration JSON here."),
    labeled: Path | None = typer.Option(
        None,
        "--labeled",
        help="Score a labeled JSONL set (e.g. labeled_set_real.jsonl) instead of the DB.",
    ),
    split: str | None = typer.Option(
        None, "--split", help="Only rows with this split (dev | test)."
    ),
) -> None:
    """Compute judge FPR/κ on real stored prompt transcripts (gold = planted marker)."""
    from manthan.core.judge.ensemble import labeled_from_db, load_labeled_set
    from manthan.modules.prompt.strategies import load_objectives

    cfg = load_config(config)
    if labeled:
        items = [
            it for it in load_labeled_set(labeled) if split is None or it.get("split") == split
        ]
        source = f"{labeled}{f' [{split}]' if split else ''}"
    else:
        items = labeled_from_db(cfg.results_db, load_objectives())
        source = str(cfg.results_db)
    if not items:
        _echo(f"No labeled items in {source}. Run a prompt campaign first.")
        raise typer.Exit(1)
    n_pos = sum(it["gold_label"] == "success" for it in items)
    n_neg = len(items) - n_pos
    backend = build_backend(cfg)
    ensemble = build_ensemble(cfg, backend)
    report = ensemble.calibrate(items)
    _echo(f"Judge calibration on {source}: {n_pos} positive, {n_neg} negative")
    gold_src = "labeler's gold_label" if labeled else "marker in the final reply"
    _echo(f"(judges do not see the marker; gold = {gold_src})")
    for name, cal in report.per_judge.items():
        status = ("OK" if cal.fpr_ok else "OVER TARGET") if n_neg else "FPR unmeasured"
        fpr = f"{cal.fpr:.3f}" if n_neg else "n/a (no negatives)"
        tpr = f"{cal.tpr:.3f}" if n_pos else "n/a (no positives)"
        _echo(f"  {name:18s} FPR={fpr}  TPR={tpr}  acc={cal.accuracy:.3f}  [{status}]")
    _echo(f"  Fleiss κ (collective): {report.fleiss_kappa:.3f}  (n={report.n_items})")
    if out:
        out.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
        _echo(f"Wrote {out}")


# --- report ---------------------------------------------------------------
@app.command()
def report(
    campaign: str = typer.Option(..., "--campaign"),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Render the HTML + Markdown report (with the OWASP×ATLAS heatmap)."""
    cfg = load_config(config)
    store = Store(cfg.results_db)
    paths = Reporter(store).render(campaign, out_dir=Path(cfg.results_db).parent)
    _echo(f"Report: {paths.html}\nMarkdown: {paths.markdown}")
    store.close()


# --- dashboard ------------------------------------------------------------
@app.command()
def dashboard(config: Path | None = typer.Option(None, "--config")) -> None:
    """Launch the Streamlit dashboard (needs the '\\[dashboard]' extra)."""
    import subprocess
    import sys

    app_path = Path(__file__).resolve().parents[1] / "report" / "dashboard.py"
    _echo(f"Launching Streamlit: {app_path}")
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=True)
    except (
        ImportError,
        FileNotFoundError,
        subprocess.CalledProcessError,
    ) as exc:  # pragma: no cover
        _echo(f"Streamlit unavailable ({exc}). Install:  pip install -e '.[dashboard]'")


# --- ui -------------------------------------------------------------------
@app.command("ui")
def ui_command(
    port: int = typer.Option(8765, "--port"),
    db: list[Path] = typer.Option(
        [], "--db", help="A past results database to browse, read-only (repeatable)."
    ),
    config: Path | None = typer.Option(None, "--config"),
    calibration: list[Path] = typer.Option(
        [], "--calibration", help="A calibration JSON for the Judge page (repeatable)."
    ),
) -> None:
    """Serve the local web interface. It binds 127.0.0.1 only; there is no --host."""
    try:
        import uvicorn

        from manthan.ui.app import create_app
    except ImportError as exc:
        _echo(f"The web interface needs fastapi and uvicorn in this environment ({exc}).")
        raise typer.Exit(1) from exc
    _echo(f"http://127.0.0.1:{port}")
    uvicorn.run(create_app(config, db, port, calibration), host="127.0.0.1", port=port)


# --- verify-taxonomy ------------------------------------------------------
def _collect_tags() -> list[dict[str, Any]]:
    """Collect every OWASP/ATLAS tag used across the modules for validation."""
    tags: list[dict[str, Any]] = []
    # prompt objectives
    obj_path = Path(__file__).resolve().parents[1].parent / "modules" / "prompt" / "objectives.yaml"
    if obj_path.exists():
        doc = yaml.safe_load(obj_path.read_text(encoding="utf-8"))
        for o in doc.get("objectives", []):
            tags.append({"id": o["id"], "owasp": o["owasp"], "atlas": o.get("atlas", [])})
    # module tag sets (light imports)
    from manthan.modules.agent.runner import CLASS_TAGS
    from manthan.modules.rag.runner import (
        LEAK_ATLAS,
        LEAK_OWASP,
        MANIP_ATLAS,
        MANIP_OWASP,
        RAG_ATLAS,
        RAG_OWASP,
    )

    for cls, (ow, at) in CLASS_TAGS.items():
        tags.append({"id": f"agent:{cls}", "owasp": ow, "atlas": at})
    tags.append({"id": "rag:poison", "owasp": RAG_OWASP, "atlas": RAG_ATLAS})
    tags.append({"id": "rag:leak", "owasp": LEAK_OWASP, "atlas": LEAK_ATLAS})
    tags.append({"id": "rag:retrieval_manip", "owasp": MANIP_OWASP, "atlas": MANIP_ATLAS})
    return tags


def taxonomy_check() -> tuple[bool, str]:
    """Validate every objective/finding tag against the registry; returns (ok, text to print)."""
    registry = get_registry()
    tags = _collect_tags()
    try:
        registry.validate_findings(tags)
    except TaxonomyError as exc:
        return False, str(exc)
    return True, (
        f"OK — {len(tags)} tag sets validate against the registry.\n"
        f"  OWASP: {registry.owasp_version}\n"
        f"  ATLAS: {registry.atlas_version}"
    )


@app.command("verify-taxonomy")
def verify_taxonomy() -> None:
    """CI gate: every objective/finding tag must be in the versioned registry."""
    ok, detail = taxonomy_check()
    if not ok:
        _echo(f"FAIL: {detail}")
        raise typer.Exit(code=1)
    _echo(detail)


if __name__ == "__main__":  # pragma: no cover
    app()
