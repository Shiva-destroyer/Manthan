"""SQLite results store — one schema, all three domains (PRD §6.3, §8.5).

stdlib ``sqlite3``, WAL mode, one DB file. The store is the single home for
campaigns, runs, turns, verdicts, findings, tags and metrics, and the source of
truth the reporter reads. Ids are uuid4 unless supplied.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from manthan.core import events
from manthan.core.judge.base import Verdict
from manthan.core.model.base import Transcript

log = logging.getLogger(__name__)

_SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def _uid() -> str:
    return uuid.uuid4().hex


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Finding:
    """One scored attack attempt (PRD definition of a finding)."""

    run_id: str
    success: bool
    strategy: str = ""
    objective_id: str = ""
    score: float = 0.0
    evaded_defense: bool = False
    owasp: list[str] = field(default_factory=list)
    atlas: list[str] = field(default_factory=list)
    id: str = field(default_factory=_uid)


class Store:
    """Thin, typed wrapper over the SQLite results database."""

    def __init__(self, path: str | Path = "data/results/manthan.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    @classmethod
    def in_memory(cls) -> Store:
        obj = cls.__new__(cls)
        obj.path = Path(":memory:")
        obj.conn = sqlite3.connect(":memory:")
        obj.conn.row_factory = sqlite3.Row
        obj.conn.execute("PRAGMA foreign_keys = ON")
        obj._init_schema()
        return obj

    @classmethod
    def read_only(cls, path: str | Path, immutable: bool = True) -> Store:
        """Open an existing database for reading: no schema script, no mkdir, no side files.

        ``immutable`` skips the WAL and creates no ``-shm``; use ``immutable=False`` for a
        database a run may still write. A non-empty ``-wal`` forces that too, so no row is hidden.
        """
        p = Path(path).resolve()
        if not p.is_file():
            raise FileNotFoundError(p)
        wal = p.with_name(p.name + "-wal")
        immutable = immutable and not (wal.exists() and wal.stat().st_size > 0)
        obj = cls.__new__(cls)
        obj.path = p
        obj.conn = sqlite3.connect(
            f"{p.as_uri()}?mode=ro{'&immutable=1' if immutable else ''}", uri=True
        )
        obj.conn.row_factory = sqlite3.Row
        return obj

    def _init_schema(self) -> None:
        self.conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # --- inserts ----------------------------------------------------------
    def add_campaign(
        self,
        domain: str,
        config_hash: str,
        seed: int,
        label: str = "",
        campaign_id: str | None = None,
    ) -> str:
        cid = campaign_id or _uid()
        self.conn.execute(
            "INSERT INTO campaign(id, domain, config_hash, seed, created_at, label)"
            " VALUES (?,?,?,?,?,?)",
            (cid, domain, config_hash, seed, _now(), label),
        )
        self.conn.commit()
        return cid

    def add_run(
        self,
        campaign_id: str,
        objective_id: str,
        target_label: str,
        status: str = "completed",
        domain: str = "",
        run_id: str | None = None,
    ) -> str:
        rid = run_id or _uid()
        log.debug("run %s domain=%s target=%s", objective_id, domain, target_label)
        self.conn.execute(
            "INSERT INTO run(id, campaign_id, objective_id, target_label, status, domain)"
            " VALUES (?,?,?,?,?,?)",
            (rid, campaign_id, objective_id, target_label, status, domain),
        )
        self.conn.commit()
        events.emit(
            "run.stored",
            run_id=rid,
            objective_id=objective_id,
            target_label=target_label,
            status=status,
        )
        return rid

    def add_transcript(self, run_id: str, transcript: Transcript) -> list[str]:
        """Persist every turn of a transcript; returns the turn ids."""
        ids: list[str] = []
        cur = self.conn.cursor()
        for idx, msg in enumerate(transcript.messages):
            tid = _uid()
            latency = float(transcript.metadata.get("latencies", {}).get(str(idx), 0.0))
            cur.execute(
                "INSERT INTO turn(id, run_id, idx, role, content, latency_s) VALUES (?,?,?,?,?,?)",
                (tid, run_id, idx, msg.role, msg.content, latency),
            )
            ids.append(tid)
        self.conn.commit()
        return ids

    def add_verdicts(self, turn_id: str, verdicts: Iterable[Verdict]) -> None:
        cur = self.conn.cursor()
        for v in verdicts:
            cur.execute(
                "INSERT INTO verdict(id, turn_id, judge_name, label, score, confidence)"
                " VALUES (?,?,?,?,?,?)",
                (_uid(), turn_id, v.judge_name, v.label, v.score, v.confidence),
            )
        self.conn.commit()

    def add_finding(self, finding: Finding) -> str:
        self.conn.execute(
            "INSERT INTO finding(id, run_id, success, evaded_defense, strategy, objective_id, score)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                finding.id,
                finding.run_id,
                int(finding.success),
                int(finding.evaded_defense),
                finding.strategy,
                finding.objective_id,
                finding.score,
            ),
        )
        # Tags: cross-product of owasp x atlas (every finding ≥1 of each).
        cur = self.conn.cursor()
        for oid in finding.owasp or [""]:
            for aid in finding.atlas or [""]:
                cur.execute(
                    "INSERT INTO tag(id, finding_id, owasp_id, atlas_id) VALUES (?,?,?,?)",
                    (_uid(), finding.id, oid, aid),
                )
        self.conn.commit()
        events.emit(
            "finding.stored",
            finding_id=finding.id,
            run_id=finding.run_id,
            success=finding.success,
            evaded_defense=finding.evaded_defense,
            strategy=finding.strategy,
            score=finding.score,
        )
        return finding.id

    def add_metric(
        self,
        run_id: str,
        name: str,
        value: float,
        ci_low: float | None = None,
        ci_high: float | None = None,
        method: str = "",
        seed: int | None = None,
    ) -> str:
        mid = _uid()
        self.conn.execute(
            "INSERT INTO metric(id, run_id, name, value, ci_low, ci_high, method, seed)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (mid, run_id, name, value, ci_low, ci_high, method, seed),
        )
        self.conn.commit()
        events.emit(
            "metric.stored",
            run_id=run_id,
            name=name,
            value=value,
            ci_low=ci_low,
            ci_high=ci_high,
            method=method,
        )
        return mid

    # --- queries ----------------------------------------------------------
    def _rows(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, params).fetchall())

    def campaigns(self) -> list[sqlite3.Row]:
        return self._rows("SELECT * FROM campaign ORDER BY created_at DESC")

    def get_campaign(self, campaign_id: str) -> sqlite3.Row | None:
        rows = self._rows("SELECT * FROM campaign WHERE id=?", (campaign_id,))
        return rows[0] if rows else None

    def runs_for(self, campaign_id: str) -> list[sqlite3.Row]:
        return self._rows("SELECT * FROM run WHERE campaign_id=? ORDER BY id", (campaign_id,))

    def findings_for_campaign(self, campaign_id: str) -> list[sqlite3.Row]:
        return self._rows(
            "SELECT f.* FROM finding f JOIN run r ON f.run_id=r.id WHERE r.campaign_id=?",
            (campaign_id,),
        )

    def tags_for_campaign(self, campaign_id: str) -> list[sqlite3.Row]:
        return self._rows(
            "SELECT t.* FROM tag t JOIN finding f ON t.finding_id=f.id "
            "JOIN run r ON f.run_id=r.id WHERE r.campaign_id=?",
            (campaign_id,),
        )

    def metrics_for_campaign(self, campaign_id: str) -> list[sqlite3.Row]:
        return self._rows(
            "SELECT m.*, r.domain AS run_domain, r.objective_id AS objective_id "
            "FROM metric m JOIN run r ON m.run_id=r.id WHERE r.campaign_id=?",
            (campaign_id,),
        )

    def turns_for_run(self, run_id: str) -> list[sqlite3.Row]:
        return self._rows("SELECT * FROM turn WHERE run_id=? ORDER BY idx", (run_id,))

    def verdicts_for_run(self, run_id: str) -> list[sqlite3.Row]:
        return self._rows(
            "SELECT v.* FROM verdict v JOIN turn t ON v.turn_id=t.id WHERE t.run_id=?",
            (run_id,),
        )

    def heatmap_counts(self, campaign_id: str) -> dict[tuple[str, str], int]:
        """OWASP×ATLAS finding counts for the cross-domain heatmap (FR-C8)."""
        out: dict[tuple[str, str], int] = {}
        for row in self.tags_for_campaign(campaign_id):
            key = (row["owasp_id"], row["atlas_id"])
            out[key] = out.get(key, 0) + 1
        return out
