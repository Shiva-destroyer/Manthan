"""Scheduler tests — AT-CORE7 (RAM gate + peak RSS) and phase residency."""

from __future__ import annotations

import pytest

from manthan.core.model import MockBackend, ModelRole
from manthan.core.model.scheduler import (
    ModelSlotScheduler,
    ResidencyMode,
    SchedulerError,
)

ROLES = {
    ModelRole.TARGET: "qwen2.5:7b",
    ModelRole.ATTACKER: "llama3.2:3b",
    ModelRole.JUDGE: "phi4-mini",
    ModelRole.EMBED: "nomic-embed-text",
}


@pytest.mark.unit
def test_at_core7_fast_mode_ram_gate(monkeypatch):
    """AT-CORE7: monkeypatched RAM < 11 GB -> concurrent-fast refused; >= 11 proceeds."""
    import manthan.core.model.scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "available_ram_gb", lambda: 5.0)
    s = ModelSlotScheduler(MockBackend(), ROLES, mode=ResidencyMode.CONCURRENT_FAST)
    with pytest.raises(SchedulerError):
        s.preflight()

    monkeypatch.setattr(sched_mod, "available_ram_gb", lambda: 12.0)
    s2 = ModelSlotScheduler(MockBackend(), ROLES, mode=ResidencyMode.CONCURRENT_FAST)
    assert s2.preflight() == pytest.approx(12.0)


@pytest.mark.unit
def test_sequential_mock_preflight_passes_low_ram(monkeypatch):
    # Under the mock backend the sequential budget gate is a no-op (no weights).
    import manthan.core.model.scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "available_ram_gb", lambda: 4.0)
    s = ModelSlotScheduler(MockBackend(), ROLES, mode="sequential")
    assert s.preflight() == pytest.approx(4.0)


@pytest.mark.unit
def test_phases_load_unload_and_peak_rss():
    backend = MockBackend()
    s = ModelSlotScheduler(backend, ROLES, mode="sequential", ram_reader=lambda: 20.0)
    s.preflight()
    with s.phase("generation") as sc:
        # attacker + target + persistent embed resident during generation
        assert "qwen2.5:7b" in sc.resident and "llama3.2:3b" in sc.resident
        assert "nomic-embed-text" in sc.resident
    with s.phase("judging") as sc:
        # judge resident; attacker/target swapped out (sequential)
        assert "phi4-mini" in sc.resident
        assert "llama3.2:3b" not in sc.resident
    assert s.telemetry.peak_rss_mb >= 0.0
    assert s.telemetry.loads > 0 and s.telemetry.unloads > 0
    # backend recorded the load/unload directives
    assert backend.load_calls and backend.unload_calls


@pytest.mark.unit
def test_concurrent_fast_keeps_models_resident():
    backend = MockBackend()
    s = ModelSlotScheduler(backend, ROLES, mode="concurrent-fast", ram_reader=lambda: 20.0)
    s.preflight()
    with s.phase("generation") as sc:
        # fast mode also holds the judge during generation
        assert "phi4-mini" in sc.resident
    # not unloaded on exit in fast mode
    assert "qwen2.5:7b" in s.resident


@pytest.mark.unit
def test_ollama_backend_budget_gate_enforced(monkeypatch):
    # A non-mock backend name triggers the sequential budget gate.
    class FakeLocal(MockBackend):
        name = "ollama"

    import manthan.core.model.scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "available_ram_gb", lambda: 8.0)
    s = ModelSlotScheduler(FakeLocal(), ROLES, mode="sequential")
    with pytest.raises(SchedulerError):
        s.preflight()  # estimated peak > 8 - 5 headroom


@pytest.mark.unit
def test_ollama_budget_gate_does_not_double_count_os_overhead(monkeypatch):
    # "available" RAM already excludes the OS/desktop, so a 24 GB laptop with
    # 18 GB free fits qwen+llama+embed+guard (~11.8 GB) plus 5 GB headroom.
    class FakeLocal(MockBackend):
        name = "ollama"

    import manthan.core.model.scheduler as sched_mod

    monkeypatch.setattr(sched_mod, "available_ram_gb", lambda: 18.0)
    s = ModelSlotScheduler(FakeLocal(), ROLES, mode="sequential")
    assert s.preflight() == pytest.approx(18.0)


@pytest.mark.unit
def test_memory_sampler_records_ollama_and_system_not_just_process_tree(monkeypatch):
    """P1 (NFR-1): the peak covers Ollama (server + runner) and the system, not only this process."""
    from types import SimpleNamespace

    import psutil

    import manthan.core.model.scheduler as sched_mod

    mib = 1024**2

    class Proc:
        def __init__(self, name, rss, denied=False, children=()):
            self.info = {"name": name}
            self._rss, self._denied, self._children = rss, denied, list(children)

        def memory_info(self):
            if self._denied:
                raise psutil.AccessDenied(pid=1)
            return SimpleNamespace(rss=self._rss)

        def children(self, recursive=False):
            return self._children

    # Ollama 0.40: `ollama serve` holds no weights; each model is a llama-server child.
    procs = [
        Proc("ollama", 40 * mib, children=[Proc("llama-server", 6000 * mib)]),
        Proc("ollama", 0, denied=True),
        Proc("firefox", 9000 * mib),  # not counted
    ]
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter(procs))
    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(used=15000 * mib))
    swap = iter([1300, 1500, 1400])
    monkeypatch.setattr(psutil, "swap_memory", lambda: SimpleNamespace(used=next(swap, 1400) * mib))
    monkeypatch.setattr(sched_mod, "_process_tree_rss_mb", lambda: 700.0)

    s = ModelSlotScheduler(MockBackend(), ROLES, ram_reader=lambda: 20.0)
    s.start_sampler(interval_s=0.01)
    assert s._sampler is not None and s._sampler.is_alive()
    s.sample_memory()
    s.stop_sampler()
    t = s.telemetry
    assert s._sampler is None or not s._sampler.is_alive()
    assert t.peak_ollama_rss_mb == pytest.approx(6040.0)
    assert t.peak_system_used_mb == pytest.approx(15000.0)
    assert t.peak_proc_rss_mb == pytest.approx(700.0)
    assert t.swap_delta_mb == pytest.approx(200.0)  # 1500 peak - 1300 at start
    assert t.access_denied >= 1
    # manifest peak_rss_mb = Ollama + process tree, not the process tree alone
    assert t.peak_rss_mb == pytest.approx(6740.0)


@pytest.mark.unit
def test_nested_phases_never_unload_an_absent_model():
    """An unload of a model that is not resident makes Ollama load it first (A2)."""
    s = ModelSlotScheduler(MockBackend(), ROLES, mode="sequential", ram_reader=lambda: 20.0)
    unloaded: list[str] = []
    orig = s._unload
    s._unload = lambda m: (unloaded.append(m), orig(m))  # type: ignore[method-assign]
    with s.phase("generation"):
        with s.phase("generation"):
            pass
        with s.phase("judging"):
            pass
    assert sorted(unloaded) == ["llama3.2:3b", "phi4-mini", "qwen2.5:7b"]
