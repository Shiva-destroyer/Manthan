"""Readers behind the UI API: event logs, run status, Ollama, Docker, and table replay."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from manthan.core import events
from manthan.core.config.models import RootConfig, load_config
from manthan.core.judge import RubricJudge
from manthan.core.model import ModelRole
from manthan.core.model.ollama_backend import _NUM_PREDICT
from manthan.core.report.panels import ORACLE_LAYERS
from manthan.core.store import Store

_TAIL_BYTES = 64 * 1024


def source_id(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[
        :12
    ]  # noqa: S324 - id only


def source_label(path: Path) -> str:
    """`c1a` for `c1a/data/results/manthan.db`, else the file name."""
    p = path.resolve()
    if p.parent.name == "results" and p.parent.parent.name == "data":
        return p.parent.parent.parent.name
    return p.stem


def event_log_path(db: Path, campaign_id: str) -> Path:
    return db.parent / campaign_id / "events.jsonl"


def manifest_path(db: Path, campaign_id: str) -> Path:
    return db.parent / campaign_id / "manifest.json"


def read_manifest(db: Path, campaign_id: str) -> dict[str, Any] | None:
    try:
        return json.loads(manifest_path(db, campaign_id).read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (OSError, ValueError):
        return None


def _first_event(log: Path) -> dict[str, Any] | None:
    try:
        with log.open("rb") as fh:
            return json.loads(fh.readline())  # type: ignore[no-any-return]
    except (OSError, ValueError):
        return None


def _last_event(log: Path) -> dict[str, Any] | None:
    """The last complete event, read from the file tail so a large log is not loaded."""
    try:
        size = log.stat().st_size
        with log.open("rb") as fh:
            fh.seek(max(0, size - _TAIL_BYTES))
            tail = fh.read()
    except OSError:
        return None
    lines = tail[: tail.rfind(b"\n") + 1].splitlines()
    try:
        return json.loads(lines[-1]) if lines else None  # type: ignore[no-any-return]
    except ValueError:
        return None  # last event longer than the tail window: not campaign.end


def campaign_status(log: Path) -> str | None:
    """`campaign.end` status, else `running` while the logged pid lives, else `incomplete`.

    None when there is no log. File age is never used: a slow CPU reply can leave it silent.
    """
    if not log.exists():
        return None
    last = _last_event(log)
    if last and last.get("kind") == "campaign.end":
        return str(last.get("status"))
    first = _first_event(log)
    start = first if first and first.get("kind") == "campaign.start" else {}
    return "running" if _alive(start) else "incomplete"


def _alive(start: dict[str, Any]) -> bool:
    """The logged process is still the same live run: not exited, not a zombie, not a reused pid."""
    pid = start.get("pid")
    stamp = events.proc_stamp(pid) if isinstance(pid, int) else None
    if stamp is None:
        return False
    if "proc_start" not in start:  # a log from before the stamp existed: the pid is all we have
        return True
    return stamp["proc_start"] == start["proc_start"] and stamp["boot_id"] == start.get("boot_id")


def elapsed_min(log: Path) -> float | None:
    """Minutes since `campaign.start`, from its own timestamp; None when the log has none."""
    first = _first_event(log)
    try:
        return (datetime.now(UTC) - datetime.fromisoformat(first["ts"])).total_seconds() / 60  # type: ignore[index]
    except (TypeError, KeyError, ValueError):
        return None


def _get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=2) as resp:  # noqa: S310 - fixed local URL
        return json.load(resp)


def ollama_ps(base_url: str) -> list[dict[str, Any]] | None:
    """Models Ollama holds in memory now; None when it cannot be reached."""
    try:
        return list(_get_json(f"{base_url}/api/ps").get("models", []))
    except Exception:  # unreachable, refused, bad JSON: all read as "Ollama is down"
        return None


def ollama_tags(base_url: str) -> dict[str, int] | None:
    """Pulled models as name -> size in bytes; None when Ollama cannot be reached."""
    try:
        return {
            m["name"]: m.get("size") for m in _get_json(f"{base_url}/api/tags").get("models", [])
        }
    except Exception:
        return None


def docker_image_present(name: str) -> bool:
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["docker", "image", "inspect", name], capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def events_from_tables(store: Store, campaign_id: str) -> list[dict[str, Any]]:
    """Replay a past campaign from its tables. No clock was stored, so `ts` and `t` stay null."""
    out: list[dict[str, Any]] = []

    def add(kind: str, **fields: Any) -> None:
        out.append(
            {"seq": len(out) + 1, "ts": None, "t": None, "source": "tables", "kind": kind, **fields}
        )

    q = store.conn.execute
    for run in q("SELECT * FROM run WHERE campaign_id=? ORDER BY rowid", (campaign_id,)).fetchall():
        rid = run["id"]
        add(
            "run.stored",
            run_id=rid,
            objective_id=run["objective_id"],
            target_label=run["target_label"],
            status=run["status"],
            domain=run["domain"],
        )
        for t in q("SELECT * FROM turn WHERE run_id=? ORDER BY idx", (rid,)).fetchall():
            add(
                "turn",
                run_id=rid,
                idx=t["idx"],
                role=t["role"],
                content=t["content"],
                latency_s=t["latency_s"],
            )
        rows = q(
            "SELECT v.*, t.idx AS turn_idx FROM verdict v JOIN turn t ON v.turn_id=t.id"
            " WHERE t.run_id=? ORDER BY t.idx, v.rowid",
            (rid,),
        ).fetchall()
        for v in rows:
            add(
                "verdict",
                run_id=rid,
                turn_idx=v["turn_idx"],
                judge_name=v["judge_name"],
                label=v["label"],
                score=v["score"],
                confidence=v["confidence"],
                started_at=None,
            )
        for f in q("SELECT * FROM finding WHERE run_id=? ORDER BY rowid", (rid,)).fetchall():
            add(
                "finding.stored",
                run_id=rid,
                success=bool(f["success"]),
                evaded_defense=bool(f["evaded_defense"]),
                strategy=f["strategy"],
                objective_id=f["objective_id"],
                score=f["score"],
            )
        for m in q("SELECT * FROM metric WHERE run_id=? ORDER BY rowid", (rid,)).fetchall():
            add(
                "metric.stored",
                run_id=rid,
                name=m["name"],
                value=m["value"],
                ci_low=m["ci_low"],
                ci_high=m["ci_high"],
                method=m["method"],
            )
    return out


_CI = ("ci_low", "ci_high")


def _count_findings(store: Store, cid: str, strategy: str, target: str) -> tuple[int, int]:
    row = store.conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(f.success), 0) FROM finding f JOIN run r ON f.run_id=r.id"
        " WHERE r.campaign_id=? AND f.strategy=? AND r.target_label=?",
        (cid, strategy, target),
    ).fetchone()
    return int(row[1]), int(row[0])


def results_summary(store: Store, cid: str) -> dict[str, Any]:
    """Stored metrics grouped for the Results page. Ranges are copied, never computed.

    The metric table has no trial count, so k and n come from counting findings, and are
    kept only when k / n reproduces the stored value.
    """
    targets = {
        r["id"]: r["target_label"]
        for r in store.conn.execute("SELECT id, target_label FROM run WHERE campaign_id=?", (cid,))
    }
    metrics = [dict(m) for m in store.metrics_for_campaign(cid)]
    by_name = {m["name"]: m for m in metrics}
    used: set[str] = set()
    out: dict[str, Any] = {"rates": [], "rag_curve": [], "defences": [], "stacked": None}

    for m in metrics:
        name = m["name"]
        if re.fullmatch(r"asr_n\d+", name):
            used.add(name)
            out["rag_curve"].append(
                {
                    "n_poison": int(name[5:]),
                    "value": m["value"],
                    "ci_low": m["ci_low"],
                    "ci_high": m["ci_high"],
                }
            )
        elif name == "asr_stacked_defense":
            used.add(name)
            out["stacked"] = {"value": m["value"], "method": m["method"]}
        elif name.startswith("asr_"):
            used.add(name)
            label = name[4:]
            k, n = _count_findings(store, cid, label, targets.get(m["run_id"], ""))
            # agent runs store one finding per class, not per trial, so their n would be 1
            ok = n > 0 and m["run_domain"] != "agent" and abs(k / n - m["value"]) < 1e-9
            out["rates"].append(
                {
                    "name": name,
                    "domain": m["run_domain"],
                    "label": label,
                    "target": targets.get(m["run_id"]),
                    "value": m["value"],
                    "ci_low": m["ci_low"],
                    "ci_high": m["ci_high"],
                    "method": m["method"],
                    "k": k if ok else None,
                    "n": n if ok else None,
                }
            )
    out["rag_curve"].sort(key=lambda p: p["n_poison"])

    for name in sorted(by_name):
        if name.startswith("dASR_"):
            layer = name[5:]
            used.add(name)
            benign = by_name.get(f"benign_acc:{layer}")
            if benign:
                used.add(benign["name"])
            out["defences"].append(
                {
                    "layer": layer,
                    "dasr": by_name[name]["value"],
                    "benign_acc": benign["value"] if benign else None,
                    "oracle": layer in ORACLE_LAYERS,
                }
            )
    out["other"] = [
        {k: m[k] for k in ("name", "value", "ci_low", "ci_high", "method")}
        | {"domain": m["run_domain"]}
        for m in metrics
        if m["name"] not in used
    ]
    # Findings with no OWASP or ATLAS id are stored with empty tags; they have no place on the map.
    out["heatmap"] = [
        {"owasp_id": o, "atlas_id": a, "count": n}
        for (o, a), n in store.heatmap_counts(cid).items()
        if o and a
    ]
    return out


def calibration_id(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:16]


def _bad_number(token: str) -> float:
    raise ValueError(f"{token} is not a valid number")


def read_calibration(path: Path) -> dict[str, Any]:
    """One calibration file in the shape the Judge page reads. Accepts the flat file that
    ``calibrate --out`` writes and the wrapped ``metrics_*.json`` files of sessions 4 and 5.
    Stored intervals are copied when present and never computed."""
    item: dict[str, Any] = {"id": calibration_id(path), "name": path.name, "error": None}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), parse_constant=_bad_number)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
        flat = raw["calibration"] if "calibration" in raw else raw
        ci = raw.get("judges", {}) if "calibration" in raw else {}
        judges = [
            {
                "name": name,
                "fpr": j["fpr"],
                "tpr": j["tpr"],
                "accuracy": j["accuracy"],
                "n": j["n"],
                "fpr_target": j["fpr_target"],
                "fpr_ok": j["fpr_ok"],
                "fpr_ci": ci.get(name, {}).get("fpr_ci"),
                "tpr_ci": ci.get(name, {}).get("tpr_ci"),
            }
            for name, j in flat["per_judge"].items()
        ]
        item |= {
            "mtime": mtime,
            "tag": raw.get("tag"),
            "split": raw.get("split"),
            "source": raw.get("source"),
            "n_items": flat.get("n_items"),
            "gold_counts": raw.get("gold_counts"),
            "fleiss_kappa": flat.get("fleiss_kappa"),
            "pairwise_kappa": flat.get("pairwise_kappa", {}),
            "judges": judges,
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        item["error"] = f"Could not read this file: {exc}"
    return item


_TEMP_WHY = "Manthan does not set it, so Ollama uses the model's default."
_SETTING_ROLES = ("target", "attacker", "judge", "embed")


def _matching_config(row: Any, config_dir: Path) -> tuple[str, RootConfig] | None:
    """The first config file whose hash equals the campaign's stored hash, with the stored seed."""
    for f in sorted(config_dir.glob("*.yaml")):
        try:
            cfg = load_config(f).model_copy(update={"seed": row["seed"]})
        except Exception:  # an unreadable or disallowed file is skipped, not an error
            continue
        if cfg.config_hash() == row["config_hash"]:
            return f.name, cfg
    return None


def campaign_settings(store: Store, cid: str, config_dir: Path) -> dict[str, Any]:
    """Device settings of one campaign. A config file is proof only when its hash matches."""
    row = store.get_campaign(cid)
    if row is None:
        raise KeyError(cid)
    found = _matching_config(row, config_dir)
    name, cfg = found if found else (None, None)
    judge_temp = inspect.signature(RubricJudge.__init__).parameters["temperature"].default
    roles: dict[str, Any] = {}
    for role in _SETTING_ROLES:
        rm = cfg.models.roles.get(role) if cfg else None
        roles[role] = {
            "model": rm.model if rm else None,
            "keep_alive": rm.keep_alive if rm else None,
            "temperature": judge_temp if role == "judge" else None,
            "temperature_why": None if role == "judge" else _TEMP_WHY,
            "num_predict": _NUM_PREDICT.get(ModelRole(role)),
        }
    return {
        "config": name,
        "backend": cfg.models.backend if cfg else None,
        "seed": row["seed"],
        "config_hash": row["config_hash"],
        "roles": roles,
        "guard": cfg.models.guard.model_dump() if cfg else None,
        "use_defended_target": cfg.prompt.use_defended_target if cfg else None,
        "agent_lab": cfg.agent.lab if cfg else None,
        "rag_k": cfg.rag.k if cfg else None,
    }
