"""JSONL export of full transcripts (PRD §8.5).

``export_jsonl(store, run_id)`` writes one JSONL line per turn (plus its
verdicts) to ``data/results/<run>/transcript.jsonl`` for archival and
downstream analysis.
"""

from __future__ import annotations

import json
from pathlib import Path

from manthan.core.store.db import Store


def export_jsonl(
    store: Store,
    run_id: str,
    out_root: str | Path = "data/results",
) -> Path:
    """Write a run's turns + verdicts to ``<out_root>/<run>/transcript.jsonl``."""
    out_dir = Path(out_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "transcript.jsonl"

    verdicts_by_turn: dict[str, list[dict]] = {}
    for v in store.verdicts_for_run(run_id):
        verdicts_by_turn.setdefault(v["turn_id"], []).append(
            {
                "judge_name": v["judge_name"],
                "label": v["label"],
                "score": v["score"],
                "confidence": v["confidence"],
            }
        )

    lines: list[str] = []
    for turn in store.turns_for_run(run_id):
        row = {
            "run_id": run_id,
            "idx": turn["idx"],
            "role": turn["role"],
            "content": turn["content"],
            "latency_s": turn["latency_s"],
            "verdicts": verdicts_by_turn.get(turn["id"], []),
        }
        lines.append(json.dumps(row, ensure_ascii=False))

    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out_path
