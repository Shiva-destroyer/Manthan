"""OWASP + ATLAS taxonomy registry and validator (PRD §8.4, FR-C7).

One version-stamped registry, loaded from ``data/owasp.yaml`` and
``data/atlas.yaml``. Every finding MUST carry one OWASP id and ≥1 ATLAS id;
``validate`` raises on any unknown or malformed id, and ``manthan
verify-taxonomy`` turns that into a CI gate. Matching is *by id against the
registry*, so an out-of-registry id fails rather than silently mis-tagging
(failure mode F11 — ATLAS renumbering).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DATA = Path(__file__).resolve().parent / "data"

# An ATLAS id looks like AML.T0051 or AML.T0051.001. OWASP like LLM01 / ASI06.
_ATLAS_RE = re.compile(r"^AML\.T\d{4}(?:\.\d{3})?$")
_OWASP_RE = re.compile(r"^(?:LLM|ASI)\d{2}$")


class TaxonomyError(ValueError):
    """Raised on an unknown or malformed taxonomy id."""


@dataclass
class Entry:
    id: str
    name: str
    url: str = ""
    notes: str = ""


@dataclass
class TaxonomyRegistry:
    owasp: dict[str, Entry] = field(default_factory=dict)
    atlas: dict[str, Entry] = field(default_factory=dict)
    owasp_version: str = ""
    atlas_version: str = ""

    # --- loading ----------------------------------------------------------
    @classmethod
    def load(cls, data_dir: str | Path | None = None) -> TaxonomyRegistry:
        base = Path(data_dir) if data_dir else _DATA
        owasp_doc = yaml.safe_load((base / "owasp.yaml").read_text(encoding="utf-8"))
        atlas_doc = yaml.safe_load((base / "atlas.yaml").read_text(encoding="utf-8"))
        reg = cls(
            owasp={k: Entry(id=k, **v) for k, v in owasp_doc["ids"].items()},
            atlas={k: Entry(id=k, **v) for k, v in atlas_doc["ids"].items()},
            owasp_version=str(owasp_doc.get("framework_version", "")),
            atlas_version=str(atlas_doc.get("framework_version", "")),
        )
        return reg

    # --- membership -------------------------------------------------------
    def has_owasp(self, oid: str) -> bool:
        return oid in self.owasp

    def has_atlas(self, aid: str) -> bool:
        return aid in self.atlas

    def known(self, any_id: str) -> bool:
        return any_id in self.owasp or any_id in self.atlas

    # --- validation -------------------------------------------------------
    def validate_owasp(self, oid: str) -> None:
        if not _OWASP_RE.match(oid):
            raise TaxonomyError(f"malformed OWASP id: {oid!r}")
        if oid not in self.owasp:
            raise TaxonomyError(f"unknown OWASP id (not in registry): {oid!r}")

    def validate_atlas(self, aid: str) -> None:
        if not _ATLAS_RE.match(aid):
            raise TaxonomyError(f"malformed ATLAS id: {aid!r}")
        if aid not in self.atlas:
            raise TaxonomyError(f"unknown ATLAS id (not in registry): {aid!r}")

    def validate_tags(self, owasp: str | Iterable[str], atlas: Iterable[str]) -> None:
        """Validate the tags for a single finding/objective."""
        owasp_ids = [owasp] if isinstance(owasp, str) else list(owasp)
        if not owasp_ids:
            raise TaxonomyError("every finding must carry at least one OWASP id")
        for oid in owasp_ids:
            self.validate_owasp(oid)
        atlas_ids = list(atlas)
        if not atlas_ids:
            raise TaxonomyError("every finding must carry at least one ATLAS id")
        for aid in atlas_ids:
            self.validate_atlas(aid)

    def validate_findings(self, findings: Iterable[dict[str, Any]]) -> None:
        """Validate an iterable of ``{owasp, atlas}`` tag dicts."""
        for i, f in enumerate(findings):
            try:
                self.validate_tags(f.get("owasp", []), f.get("atlas", []))
            except TaxonomyError as exc:
                raise TaxonomyError(f"finding #{i} ({f.get('id', '?')}): {exc}") from exc


# Module-level singleton for convenience.
_REGISTRY: TaxonomyRegistry | None = None


def get_registry() -> TaxonomyRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = TaxonomyRegistry.load()
    return _REGISTRY
