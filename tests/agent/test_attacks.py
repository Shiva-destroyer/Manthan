"""Agent attack tests — AT-A1 (tool_poison -> exfil attempt -> success)."""

from __future__ import annotations

import pytest

from manthan.modules.agent.lab import SimulatedLab, load_synthetic_secrets
from manthan.modules.agent.mock_exfil import MockExfilListener
from manthan.modules.agent.tools import ToolContext, ToolError, run_cmd

ALL_OFF = {
    "indirect_injection": False,
    "tool_poison": False,
    "rug_pull": False,
    "tool_shadowing": False,
    "excessive_agency": False,
}


@pytest.mark.integration
def test_at_a1_tool_poison_attempts_exfil_to_mock_listener():
    """AT-A1: with tool_poison ON, the agent attempts send to mock-exfil; success."""
    listener = MockExfilListener()
    lab = SimulatedLab(listener=listener)
    result = lab.run("probe", {**ALL_OFF, "tool_poison": True})
    assert result.success is True
    assert len(result.exfil_attempts) == 1
    assert listener.count == 1
    # the listener logged the attempt but stored nothing real
    assert listener.attempts[0]["destination"] == "attacker-exfil"
    assert listener.attempts[0].get("stored") is False or "stored" not in listener.attempts[0]
    # injection entered context at step 0 (US-A3 trajectory provenance)
    assert result.trajectory.injection_step == 0


@pytest.mark.integration
def test_benign_run_has_no_exfil():
    lab = SimulatedLab()
    result = lab.run("process-inbox", ALL_OFF)
    assert result.success is False
    assert len(result.exfil_attempts) == 0


@pytest.mark.integration
def test_all_attack_classes_attempt_exfil():
    lab = SimulatedLab()
    for cls in (
        "indirect_injection",
        "tool_poison",
        "rug_pull",
        "tool_shadowing",
        "excessive_agency",
    ):
        result = lab.run(f"{cls}-obj", {**ALL_OFF, cls: True})
        assert result.success, f"{cls} should attempt exfil"


@pytest.mark.unit
def test_synthetic_secrets_are_fake():
    secrets = load_synthetic_secrets()
    assert "SYNTHETIC-FAKE-KEY" in secrets["ssh_key"]
    assert secrets["pii"]["email"].endswith("example.invalid")
    assert secrets["pii"]["ssn"] == "000-00-0000"  # all-zero placeholder


@pytest.mark.unit
def test_run_cmd_guard_rejects_non_allowlisted(tmp_path):
    ctx = ToolContext(sandbox_dir=tmp_path)
    assert "ok" in run_cmd(ctx, "ls -la")
    with pytest.raises(ToolError):
        run_cmd(ctx, "rm -rf /")  # not on allowlist
