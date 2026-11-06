"""The UI's FastAPI app: read-only routes over result databases, event logs and the system."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Collection, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NamedTuple

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from manthan.core import events
from manthan.core.cli.orchestrator import build_scheduler
from manthan.core.config.models import RootConfig, load_config
from manthan.core.model import make_backend
from manthan.core.model.scheduler import SAFETY_HEADROOM_GB, available_ram_gb
from manthan.core.store import Store
from manthan.ui import data
from manthan.ui.actions import ACTIONS, ActionRunner, Busy, build_argv, default_spawn
from manthan.ui.security import LocalOnly

LAB_IMAGE = "manthan-lab:local"
_POLL_S = 0.5
CID = PathParam(pattern=r"^[0-9a-f]{32}$")  # also keeps ".." out of the log path
STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"
SHIPPED_CALIBRATION = (
    Path(__file__).resolve().parents[1] / "core" / "calibration" / "judge_calibration_real.json"
)


class Source(NamedTuple):
    id: str
    path: Path
    label: str
    live: bool


def _norm(model: str, names: Collection[str]) -> bool:
    return model in names or f"{model}:latest" in names


def _size(model: str, tags: dict[str, int] | None) -> int | None:
    return None if tags is None else tags.get(model, tags.get(f"{model}:latest"))


def _loads(path: Path) -> bool:
    """True when the file is a full config a run can start from (models.yaml and budget.yaml are parts)."""
    try:
        load_config(path)
    except (ValidationError, ValueError, OSError):
        return False
    return True


def create_app(
    cfg_path: Path | None,
    extra_dbs: list[Path],
    port: int,
    calibrations: Sequence[Path] = (),
) -> FastAPI:
    """The source list is fixed here; a request names a source by id and never sends a path."""
    cfg: RootConfig = load_config(cfg_path)
    live = Path(cfg.results_db).resolve()
    sources: dict[str, Source] = {}
    for path, is_live in [(live, True), *[(Path(p).resolve(), False) for p in extra_dbs]]:
        sid = data.source_id(path)
        sources.setdefault(sid, Source(sid, path, data.source_label(path), is_live))
    config_dir = cfg_path.resolve().parent if cfg_path else Path("configs")

    app = FastAPI(title="Manthan", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(LocalOnly, port=port)
    app.state.port = port
    app.state.cfg = cfg
    app.state.sources = sources
    app.state.config_dir = config_dir
    app.state.calibrations = [Path(c).resolve() for c in calibrations]
    app.state.runner = ActionRunner(default_spawn, live.parent / "ui-actions")

    assets = STATIC_INDEX.parent / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def index() -> Any:
        if STATIC_INDEX.is_file():
            return FileResponse(STATIC_INDEX)
        return {"note": "The web page is not built yet. The API is under /api."}

    def source_of(sid: str) -> Source:
        if sid not in sources:
            raise HTTPException(404, "unknown source")
        return sources[sid]

    @contextmanager
    def opened(src: Source) -> Iterator[Store | None]:
        """A fresh read-only connection per request; None while the live database is not made yet."""
        if not src.path.is_file():
            if src.live:
                yield None
                return
            raise HTTPException(404, "database file is missing")
        store = Store.read_only(src.path, immutable=not src.live)
        try:
            yield store
        finally:
            store.close()

    @app.get("/api/sources")
    def list_sources() -> list[dict[str, Any]]:
        return [
            {"id": s.id, "path": str(s.path), "label": s.label, "live": s.live}
            for s in sources.values()
        ]

    @app.get("/api/campaigns")
    def list_campaigns(source: str) -> list[dict[str, Any]]:
        src = source_of(source)
        with opened(src) as store:
            if store is None:
                return []
            return [
                {**dict(r), "status": data.campaign_status(data.event_log_path(src.path, r["id"]))}
                for r in store.campaigns()
            ]

    @app.get("/api/campaigns/{cid}")
    def campaign_detail(source: str, cid: str = CID) -> dict[str, Any]:
        src = source_of(source)
        with opened(src) as store:
            row = store.get_campaign(cid) if store else None
            if store is None or row is None:
                raise HTTPException(404, "unknown campaign")
            tags: dict[str, list[dict[str, str]]] = {}
            for t in store.tags_for_campaign(cid):
                tags.setdefault(t["finding_id"], []).append(
                    {"owasp_id": t["owasp_id"], "atlas_id": t["atlas_id"]}
                )
            findings = [
                {
                    **dict(f),
                    "success": bool(f["success"]),
                    "evaded_defense": bool(f["evaded_defense"]),
                    "tags": tags.get(f["id"], []),
                }
                for f in store.findings_for_campaign(cid)
            ]
            runs = store.conn.execute(
                "SELECT * FROM run WHERE campaign_id=? ORDER BY rowid", (cid,)
            ).fetchall()
            return {
                "campaign": {
                    **dict(row),
                    "status": data.campaign_status(data.event_log_path(src.path, cid)),
                },
                "runs": [dict(r) for r in runs],
                "metrics": [dict(m) for m in store.metrics_for_campaign(cid)],
                "findings": findings,
                "heatmap": [
                    {"owasp_id": o, "atlas_id": a, "count": n}
                    for (o, a), n in store.heatmap_counts(cid).items()
                ],
                "manifest": data.read_manifest(src.path, cid),
            }

    @app.get("/api/campaigns/{cid}/settings")
    def campaign_settings(source: str, cid: str = CID) -> dict[str, Any]:
        with opened(source_of(source)) as store:
            if store is None or store.get_campaign(cid) is None:
                raise HTTPException(404, "unknown campaign")
            return data.campaign_settings(store, cid, config_dir)

    @app.get("/api/campaigns/{cid}/results")
    def campaign_results(source: str, cid: str = CID) -> dict[str, Any]:
        with opened(source_of(source)) as store:
            if store is None or store.get_campaign(cid) is None:
                raise HTTPException(404, "unknown campaign")
            return data.results_summary(store, cid)

    @app.get("/api/runs/{rid}")
    def run_detail(rid: str, source: str) -> dict[str, Any]:
        with opened(source_of(source)) as store:
            run = (
                store.conn.execute("SELECT * FROM run WHERE id=?", (rid,)).fetchone()
                if store
                else None
            )
            if store is None or run is None:
                raise HTTPException(404, "unknown run")
            return {
                "run": dict(run),
                "turns": [dict(t) for t in store.turns_for_run(rid)],
                "verdicts": [dict(v) for v in store.verdicts_for_run(rid)],
            }

    @app.get("/api/campaigns/{cid}/events")
    def campaign_events(
        source: str, cid: str = CID, offset: int = Query(0, ge=0)
    ) -> dict[str, Any]:
        src = source_of(source)
        log = data.event_log_path(src.path, cid)
        if log.exists():
            evs, new = events.read_events(log, offset)
            return {"events": evs, "offset": new, "from_log": True}
        with opened(src) as store:
            if store is None or store.get_campaign(cid) is None:
                raise HTTPException(404, "unknown campaign")
            return {"events": data.events_from_tables(store, cid), "offset": 0, "from_log": False}

    @app.get("/api/campaigns/{cid}/events/stream")
    def campaign_stream(
        source: str, cid: str = CID, offset: int = Query(0, ge=0)
    ) -> StreamingResponse:
        log = data.event_log_path(source_of(source).path, cid)
        if not log.exists():
            raise HTTPException(404, "this campaign has no event log")

        async def gen() -> AsyncIterator[str]:
            pos = offset
            while True:
                evs, pos = events.read_events(log, pos)
                for e in evs:
                    yield f"id: {e['seq']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
                status = data.campaign_status(log)
                if status != "running":
                    # The run may have written its last lines after the read above.
                    evs, pos = events.read_events(log, pos)
                    for e in evs:
                        yield f"id: {e['seq']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"
                    yield f"event: end\ndata: {json.dumps({'status': status})}\n\n"
                    return
                await asyncio.sleep(_POLL_S)

        return StreamingResponse(
            gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    @app.get("/api/calibrations")
    def list_calibrations() -> list[dict[str, Any]]:
        """Fixed list: --calibration files, the shipped real file, then calibration*.json files
        in the results folder (newest first). The results-folder files come last because
        ``calibrate`` there may have run on a mock backend."""
        paths: list[Path] = list(app.state.calibrations)
        if SHIPPED_CALIBRATION.is_file():
            paths.append(SHIPPED_CALIBRATION.resolve())
        found = sorted(
            (p for p in live.parent.glob("calibration*.json") if p.is_file()),
            key=lambda p: -p.stat().st_mtime,
        )
        paths += [p.resolve() for p in found]
        return [data.read_calibration(p) for p in dict.fromkeys(paths)]

    @app.get("/api/resources")
    def resources() -> dict[str, Any]:
        ps = data.ollama_ps(cfg.models.base_url)
        used: float | None = None
        with opened(sources[data.source_id(live)]) as store:
            for r in store.campaigns() if store else []:
                log = data.event_log_path(live, r["id"])
                if data.campaign_status(log) == "running":
                    used = data.elapsed_min(log)
                    break
        return {
            "free_ram_gb": available_ram_gb(),
            "ollama_ps": ps,
            "ollama_error": (
                None if ps is not None else f"Ollama not reachable at {cfg.models.base_url}"
            ),
            "budget_min": cfg.budget.max_wall_clock_min,
            "used_min": used,
        }

    @app.get("/api/system")
    def system() -> dict[str, Any]:
        from manthan.core.cli.main import taxonomy_check

        ps = data.ollama_ps(cfg.models.base_url)
        tags = data.ollama_tags(cfg.models.base_url)
        loaded = None if ps is None else {m.get("name", "") for m in ps}
        image = data.docker_image_present(LAB_IMAGE)
        tax_ok, tax_text = taxonomy_check()
        free, need = available_ram_gb(), cfg.models.residency.min_free_gb_for_fast
        checks = [
            {
                "name": "ollama",
                "ok": ps is not None,
                "detail": (
                    f"reachable, {len(ps)} model(s) loaded"
                    if ps is not None
                    else f"not reachable at {cfg.models.base_url}"
                ),
            },
            {
                "name": "lab_image",
                "ok": image,
                "detail": f"{LAB_IMAGE} present" if image else f"{LAB_IMAGE} not found",
            },
            {"name": "taxonomy", "ok": tax_ok, "detail": tax_text.splitlines()[0]},
            {
                "name": "ram",
                "ok": free >= need,
                "detail": f"{free:.1f} GiB free; fast mode needs {need:g}",
            },
            {
                "name": "data",
                "ok": live.parent.is_dir(),
                "detail": (  # "~/..." keeps the user name out of screenshots
                    f"~/{live.parent.relative_to(Path.home())}"
                    if live.parent.is_relative_to(Path.home())
                    else str(live.parent)
                ),
            },
        ]
        models = [
            {
                "role": role,
                "model": rm.model,
                "pulled": None if tags is None else _norm(rm.model, tags),
                "loaded": None if loaded is None else _norm(rm.model, loaded),
                "size_bytes": _size(rm.model, tags),
            }
            for role, rm in cfg.models.roles.items()
        ]
        configs = [
            {"name": f.name, "text": f.read_text(encoding="utf-8"), "runnable": _loads(f)}
            for f in sorted(config_dir.glob("*.yaml"))
        ]
        return {"checks": checks, "models": models, "configs": configs}

    def campaign_running() -> bool:
        with opened(sources[data.source_id(live)]) as store:
            return any(
                data.campaign_status(data.event_log_path(live, r["id"])) == "running"
                for r in (store.campaigns() if store else [])
            )

    def busy_reason() -> str | None:
        runner: ActionRunner = app.state.runner
        if runner.running():
            return f"{(runner.current() or {})['name']} is already running from this page"
        if campaign_running():
            return "A campaign is already running (started outside this page)"
        return None

    def preflight() -> dict[str, Any]:
        loaded = [m.get("name", "") for m in data.ollama_ps(cfg.models.base_url) or []]
        free, res = available_ram_gb(), cfg.models.residency
        # Same test as the run's own scheduler (mock holds no weights): fail here, not after a click.
        need = res.min_free_gb_for_fast
        if res.mode == "concurrent-fast":
            ram_ok = free >= need
        elif cfg.models.backend == "ollama":
            need = (
                build_scheduler(cfg, make_backend("mock", seed=cfg.seed)).worst_peak_gb()
                + SAFETY_HEADROOM_GB
            )
            ram_ok = free >= need
        else:
            ram_ok = True
        busy = busy_reason()
        checks = [
            {
                "name": "models_unloaded",
                "ok": not loaded,
                "detail": (
                    f"loaded in Ollama: {', '.join(loaded)}" if loaded else "no model is loaded"
                ),
            },
            {
                "name": "ram",
                "ok": ram_ok,
                "detail": f"{free:.1f} GiB free; {res.mode} mode"
                + (f" needs {need:.1f}" if cfg.models.backend == "ollama" else ""),
            },
            {
                "name": "no_other_run",
                "ok": busy is None,
                "detail": busy or "nothing else is running",
            },
        ]
        return {"ok": all(c["ok"] for c in checks), "checks": checks}

    @app.get("/api/preflight")
    def get_preflight() -> dict[str, Any]:
        return preflight()

    @app.get("/api/actions/current")
    def current_action() -> dict[str, Any] | None:
        return app.state.runner.current()  # type: ignore[no-any-return]

    @app.post("/api/actions/stop")  # before /{name}, or "stop" would be read as an action name
    def stop_action() -> dict[str, Any]:
        return app.state.runner.stop()  # type: ignore[no-any-return]

    @app.post("/api/actions/{name}")
    def start_action(name: str, payload: dict[str, Any] = Body(default_factory=dict)) -> Any:
        model = ACTIONS.get(name)
        if model is None:
            return JSONResponse({"error": f"unknown action: {name}"}, status_code=404)
        try:
            action = model.model_validate(payload)
            argv = build_argv(name, action, config_dir, live.parent, cfg_path)
        except ValidationError as exc:
            detail = exc.errors(include_url=False, include_context=False, include_input=False)
            return JSONResponse(
                {"error": "invalid request", "detail": jsonable_encoder(detail)}, status_code=422
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        if (busy := busy_reason()) is not None:
            return JSONResponse({"error": busy}, status_code=409)
        if name == "run" and not (pre := preflight())["ok"]:
            return JSONResponse(
                {"error": "Not ready to start a run.", "checks": pre["checks"]}, status_code=412
            )
        try:
            return app.state.runner.start(name, argv)
        except Busy as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)

    return app
