"""taxonomy_check() is the plain function behind `manthan verify-taxonomy` (plan Task 7)."""

from __future__ import annotations

from typer.testing import CliRunner

from manthan.core.cli.main import app, taxonomy_check


def test_taxonomy_check_returns_ok_and_detail() -> None:
    ok, detail = taxonomy_check()
    assert ok is True and detail.startswith("OK") and "OWASP:" in detail


def test_verify_taxonomy_command_prints_the_same_detail() -> None:
    res = CliRunner().invoke(app, ["verify-taxonomy"])
    assert res.exit_code == 0
    assert res.output.strip() == taxonomy_check()[1].strip()
