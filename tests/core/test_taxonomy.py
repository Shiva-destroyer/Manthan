"""Taxonomy registry tests — AT-CORE2 (verify-taxonomy gate)."""

from __future__ import annotations

import pytest

from manthan.core.taxonomy import TaxonomyError, TaxonomyRegistry, get_registry


@pytest.mark.unit
def test_registry_loads_shipped_ids():
    reg = get_registry()
    # Primary ids from §13.4 are present.
    for oid in ("LLM01", "LLM02", "LLM04", "LLM06", "LLM07", "LLM08", "ASI01", "ASI02", "ASI06"):
        assert reg.has_owasp(oid)
    for aid in (
        "AML.T0051",
        "AML.T0051.000",
        "AML.T0051.001",
        "AML.T0054",
        "AML.T0057",
        "AML.T0065",
        "AML.T0066",
        "AML.T0068",
        "AML.T0070",
        "AML.T0053",
        "AML.T0086",
        "AML.T0110",
    ):
        assert reg.has_atlas(aid)
    assert "verified 2026-10-22" in reg.atlas_version


@pytest.mark.unit
def test_at_core2_unknown_id_rejected_known_accepted():
    """AT-CORE2: validator fails on an unknown id, passes on the shipped set."""
    reg = get_registry()
    reg.validate_tags("LLM07", ["AML.T0051.000", "AML.T0054"])  # ok
    with pytest.raises(TaxonomyError):
        reg.validate_atlas("AML.T9999")  # unknown
    with pytest.raises(TaxonomyError):
        reg.validate_owasp("LLM99")  # unknown
    with pytest.raises(TaxonomyError):
        reg.validate_atlas("NOTATECH")  # malformed


@pytest.mark.unit
def test_validate_tags_requires_both():
    reg = get_registry()
    with pytest.raises(TaxonomyError):
        reg.validate_tags("LLM01", [])  # no atlas
    with pytest.raises(TaxonomyError):
        reg.validate_tags([], ["AML.T0054"])  # no owasp


@pytest.mark.unit
def test_validate_findings_reports_index():
    reg = get_registry()
    findings = [
        {"id": "ok", "owasp": "LLM01", "atlas": ["AML.T0054"]},
        {"id": "bad", "owasp": "LLM01", "atlas": ["AML.T0000"]},
    ]
    with pytest.raises(TaxonomyError) as exc:
        reg.validate_findings(findings)
    assert "bad" in str(exc.value)


@pytest.mark.unit
def test_registry_load_from_custom_dir(tmp_path):
    # Re-load from the shipped data dir path via the classmethod.
    reg = TaxonomyRegistry.load()
    assert reg.known("LLM01") and reg.known("AML.T0110")
    assert not reg.known("NOPE")
