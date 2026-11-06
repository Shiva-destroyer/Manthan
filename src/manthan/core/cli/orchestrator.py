"""Campaign orchestrator — builds the shared context and runs the domains.

Ties the shared core to the three module runners. Honors the agent auto-skip
rule (FR-C1a): a *live* agent run (lab=docker) with Docker unavailable is skipped
with a warning (not an error) and recorded in the manifest, while under the mock
backend the agent uses SimulatedLab and is never skipped — so ``run all --smoke``
always spans all three domains (AT-CORE5/AT-CORE8).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from manthan.core import events
from manthan.core.config.models import RootConfig
from manthan.core.judge.ensemble import JudgeEnsemble
from manthan.core.judge.guard import Guard, MockGuard, make_guard
from manthan.core.judge.refusal import RefusalJudge
from manthan.core.judge.rubric import RubricJudge
from manthan.core.metrics.telemetry import BudgetExhausted, BudgetGuard
from manthan.core.model import ModelBackend, ModelRole, make_backend
from manthan.core.model.recording import RecordingBackend
from manthan.core.model.scheduler import ModelSlotScheduler
from manthan.core.store.db import Store
from manthan.modules.agent import lab as agent_lab
from manthan.modules.agent.runner import run_agent
from manthan.modules.prompt.runner import run_prompt
from manthan.modules.rag.runner import run_rag

_PHASE = {"prompt": "generation", "rag": "rag", "agent": "agent"}
log = logging.getLogger(__name__)


@dataclass
class CampaignManifest:
    campaign_id: str
    domains_requested: list[str]
    domains_run: list[str] = field(default_factory=list)
    domains_skipped: list[dict[str, str]] = field(default_factory=list)
    summaries: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    peak_rss_mb: float = 0.0  # all ollama processes + this process tree (NFR-1)
    memory: dict[str, float] = field(default_factory=dict)  # system-wide peaks (P1)
    budget_exhausted: str = ""  # why the budget guard stopped the campaign
    model_digests: dict[str, str] = field(default_factory=dict)  # NFR-5 provenance
    agent_lab: dict[str, str] = field(default_factory=dict)  # lab kind + image (P4d)

    def as_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "domains_requested": self.domains_requested,
            "domains_run": self.domains_run,
            "domains_skipped": self.domains_skipped,
            "warnings": self.warnings,
            "peak_rss_mb": self.peak_rss_mb,
            **self.memory,
            "budget_exhausted": self.budget_exhausted,
            "model_digests": self.model_digests,
            "agent_lab": self.agent_lab,
            "summaries": self.summaries,
        }


def build_backend(cfg: RootConfig) -> ModelBackend:
    kind = cfg.models.backend
    if kind == "ollama":
        return make_backend("ollama", base_url=cfg.models.base_url)
    return make_backend("mock", seed=cfg.seed)


def build_guard(cfg: RootConfig, backend: ModelBackend) -> Guard:
    # Offline-test rule (§8.2): the real HF guard loads only under a local
    # (ollama) backend; under mock the guard is always a MockGuard.
    if backend.name == "mock":
        return MockGuard()
    return make_guard(
        cfg.models.guard.kind, model=cfg.models.guard.model, use_onnx=cfg.models.guard.use_onnx
    )


def build_scheduler(cfg: RootConfig, backend: ModelBackend) -> ModelSlotScheduler:
    roles = {ModelRole(r): rm.model for r, rm in cfg.models.roles.items()}
    return ModelSlotScheduler(
        backend,
        roles,
        mode=cfg.models.residency.mode,
        min_free_gb_for_fast=cfg.models.residency.min_free_gb_for_fast,
    )


def build_ensemble(cfg: RootConfig, backend: ModelBackend) -> JudgeEnsemble:
    judge_role = cfg.models.roles.get("judge")
    judge_model = judge_role.model if judge_role is not None else "phi4-mini"
    return JudgeEnsemble([RefusalJudge(), RubricJudge(backend, model=judge_model)])


def _agent_should_skip(cfg: RootConfig) -> bool:
    """Live docker lab requested but Docker unavailable → skip (FR-C1a)."""
    if cfg.agent.lab != "docker":
        return False
    return not agent_lab.docker_available()


def run_campaign(
    cfg: RootConfig,
    domains: list[str],
    store: Store,
    smoke: bool = False,
    label: str = "",
    scheduler: ModelSlotScheduler | None = None,
    skip: list[str] | None = None,
    events_dir: Path | None = None,
) -> CampaignManifest:
    cfg.assert_backend_allowed()
    backend = RecordingBackend(build_backend(cfg))
    guard = build_guard(cfg, backend)
    ensemble = build_ensemble(cfg, backend)
    scheduler = scheduler or build_scheduler(cfg, backend)
    scheduler.preflight()  # aborts rather than swaps (NFR-1)

    campaign_id = store.add_campaign(
        domain=",".join(domains) if len(domains) > 1 else (domains[0] if domains else "all"),
        config_hash=cfg.config_hash(),
        seed=cfg.seed,
        label=label,
    )
    if events_dir is not None:
        events.start(events_dir / campaign_id / "events.jsonl")
    events.emit(
        "campaign.start",
        campaign_id=campaign_id,
        pid=os.getpid(),
        **(events.proc_stamp(os.getpid()) or {}),
        domains=list(domains),
        seed=cfg.seed,
        config_hash=cfg.config_hash(),
        smoke=smoke,
        budget_min=cfg.budget.max_wall_clock_min,
    )
    manifest = CampaignManifest(campaign_id=campaign_id, domains_requested=list(domains))
    status, error = "ok", None
    try:
        log.info("campaign start %s domains=%s skip=%s", campaign_id, domains, skip or [])
        try:
            manifest.model_digests = _used_digests(cfg, backend.model_digests())
        except Exception as exc:  # provenance must not stop a run (daemon down, socket blocked)
            manifest.warnings.append(f"model digests unavailable: {exc}")
        for d in skip or []:
            manifest.domains_skipped.append({"domain": d, "reason": "skipped by --skip"})
        domains = [d for d in domains if d not in (skip or [])]
        budget = BudgetGuard(cfg.budget.max_wall_clock_min, cfg.budget.max_tokens, backend)
        scheduler.start_sampler()
        try:
            _run_domains(
                cfg, domains, store, backend, ensemble, guard, scheduler, smoke, budget, manifest
            )
        finally:
            scheduler.stop_sampler()
        _store_memory(store, campaign_id, backend.name, scheduler, manifest)
        log.info("campaign done %s run=%s skipped=%s", campaign_id, manifest.domains_run,
                 [s["domain"] for s in manifest.domains_skipped])  # fmt: skip
    except (SystemExit, KeyboardInterrupt):
        status = "stopped"
        raise
    except Exception as exc:
        status, error = "error", str(exc)
        raise
    finally:
        events.emit(
            "campaign.end",
            campaign_id=campaign_id,
            status=status,
            error=error,
            domains_run=manifest.domains_run,
            domains_skipped=[s["domain"] for s in manifest.domains_skipped],
        )
        events.stop()
    return manifest


def _used_digests(cfg: RootConfig, digests: dict[str, str]) -> dict[str, str]:
    used = {rm.model for rm in cfg.models.roles.values()}
    used |= {cfg.rag.embedder, cfg.rag.generator, cfg.agent.model, "*"}
    return {n: d for n, d in digests.items() if n in used or n.removesuffix(":latest") in used}


def _store_memory(
    store: Store,
    campaign_id: str,
    backend_name: str,
    scheduler: ModelSlotScheduler,
    manifest: CampaignManifest,
) -> None:
    t = scheduler.telemetry
    manifest.peak_rss_mb = t.peak_rss_mb
    manifest.memory = {
        "peak_ollama_rss_mb": round(t.peak_ollama_rss_mb, 1),
        "peak_system_used_mb": round(t.peak_system_used_mb, 1),
        "swap_delta_mb": round(t.swap_delta_mb, 1),
        "swap_start_mb": round(max(t.swap_start_mb, 0.0), 1),
        "peak_proc_rss_mb": round(t.peak_proc_rss_mb, 1),
        "memory_access_denied": t.access_denied,
    }
    rid = store.add_run(campaign_id, "_telemetry", backend_name, domain="core")
    for name in ("peak_ollama_rss_mb", "peak_system_used_mb", "swap_delta_mb", "peak_proc_rss_mb"):
        store.add_metric(rid, name, manifest.memory[name], method="psutil 1s sampler")


def _run_domains(
    cfg: RootConfig,
    domains: list[str],
    store: Store,
    backend: ModelBackend,
    ensemble: JudgeEnsemble,
    guard: Guard,
    scheduler: ModelSlotScheduler,
    smoke: bool,
    budget: BudgetGuard,
    manifest: CampaignManifest,
) -> None:
    campaign_id = manifest.campaign_id
    for domain in domains:
        if manifest.budget_exhausted:
            manifest.domains_skipped.append({"domain": domain, "reason": manifest.budget_exhausted})
            continue
        if domain == "agent" and _agent_should_skip(cfg):
            msg = (
                "agent domain skipped: lab=docker but Docker is unavailable. "
                "run all still succeeds (prompt+RAG). See docs/running-locally.md for AT-A4."
            )
            manifest.domains_skipped.append({"domain": "agent", "reason": msg})
            manifest.warnings.append(msg)
            continue

        log.info("domain %s start", domain)
        events.emit("domain.start", domain=domain)
        try:
            summary = _run_domain(
                cfg, domain, backend, store, campaign_id, ensemble, guard, scheduler, smoke, budget
            )
        except BudgetExhausted as exc:
            manifest.budget_exhausted = str(exc)
            manifest.warnings.append(f"budget exhausted during {domain}: {exc}")
            manifest.domains_skipped.append({"domain": domain, "reason": str(exc)})
            rid = store.add_run(campaign_id, "_budget", backend.name, domain=domain)
            store.add_metric(rid, "budget_exhausted", 1.0, method=str(exc))
            continue
        events.emit("domain.end", domain=domain)
        manifest.domains_run.append(domain)
        manifest.summaries[domain] = summary
        if domain == "agent":
            manifest.agent_lab = summary.get("lab", {})
        log.info("domain %s done", domain)


def _run_domain(
    cfg: RootConfig,
    domain: str,
    backend: ModelBackend,
    store: Store,
    campaign_id: str,
    ensemble: JudgeEnsemble,
    guard: Guard,
    scheduler: ModelSlotScheduler,
    smoke: bool,
    budget: BudgetGuard,
) -> dict[str, Any]:
    with scheduler.phase(_PHASE.get(domain, "generation")):
        if domain == "prompt":
            return run_prompt(
                cfg,
                backend,
                store,
                campaign_id,
                ensemble=ensemble,
                guard=guard,
                scheduler=scheduler,
                smoke=smoke,
                budget=budget,
            )
        kw: dict[str, Any] = {
            "guard": guard,
            "scheduler": scheduler,
            "smoke": smoke,
            "budget": budget,
        }
        if domain == "rag":
            return run_rag(cfg, backend, store, campaign_id, ensemble=ensemble, **kw)
        if domain == "agent":
            return run_agent(cfg, backend, store, campaign_id, **kw)
    raise ValueError(f"unknown domain: {domain!r}")


def expand_domains(target: str, cfg: RootConfig) -> list[str]:
    if target == "all":
        return list(cfg.domains)
    return [target]
