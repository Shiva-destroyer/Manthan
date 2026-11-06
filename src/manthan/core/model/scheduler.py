"""Model-Slot Scheduler — the RAM problem, solved once (PRD §7).

CPU inference is memory-bandwidth-bound, so only a bounded set of models may be
resident at a time. The scheduler owns *which roles are co-resident per phase*,
issues explicit ``load``/``unload`` + ``keep_alive`` directives to the backend,
runs a pre-flight RAM check that **aborts rather than swaps** (NFR-1), and
records aggregate peak RSS so the budget is verifiable.

Two modes (``configs/models.yaml → residency``):

* ``sequential`` (default) — generation holds ≤2 LLMs; judging swaps the
  attacker out before loading the judge. Safe with a browser open.
* ``concurrent-fast`` (opt-in) — holds attacker+target+judge; refused if
  measured free RAM < ``min_free_gb_for_fast`` (default 11 GB).

Under the mock backend nothing is actually resident, so the sequential budget
gate is a no-op; the concurrent-fast free-RAM gate is always enforced because
it is a pure function of the RAM reading (AT-CORE7).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum

from manthan.core import events
from manthan.core.model.base import ModelBackend
from manthan.core.model.roles import ModelRole

log = logging.getLogger(__name__)


def available_ram_gb() -> float:
    """Measured available system RAM in GiB (monkeypatchable in tests)."""
    try:
        import psutil

        return float(psutil.virtual_memory().available) / (1024**3)
    except Exception:  # pragma: no cover - psutil always present via core deps
        return 0.0


def _process_tree_rss_mb() -> float:
    """Resident set size of this process + children, in MB (best effort)."""
    try:
        import psutil

        proc = psutil.Process()
        total = proc.memory_info().rss
        for child in proc.children(recursive=True):
            try:
                total += child.memory_info().rss
            except Exception:
                pass
        return total / (1024**2)
    except Exception:  # pragma: no cover
        return 0.0


def _system_memory_mb() -> tuple[float, float, int]:
    """(RSS of every ``ollama`` process, swap used, AccessDenied count), in MB.

    Ollama runs as its own service user, so the weights live outside this
    process tree. Each loaded model is a child runner (``llama-server`` in
    Ollama 0.40), so count every ``ollama`` process plus its children.
    """
    import psutil

    ollama, denied = 0, 0
    for proc in psutil.process_iter(["name"]):
        if proc.info.get("name") != "ollama":
            continue
        try:
            for p in [proc, *proc.children(recursive=True)]:
                ollama += p.memory_info().rss
        except psutil.AccessDenied:
            denied += 1
        except psutil.NoSuchProcess:  # a runner exited mid-scan (model unloaded)
            pass
    return ollama / (1024**2), psutil.swap_memory().used / (1024**2), denied


class ResidencyMode(str, Enum):
    SEQUENTIAL = "sequential"
    CONCURRENT_FAST = "concurrent-fast"


# Roles that are resident during each residency phase (§7.4). embed/guard are
# "persistent-tiny": loaded if configured, never force-unloaded between phases.
PHASE_ROLES: dict[str, set[ModelRole]] = {
    "generation": {ModelRole.ATTACKER, ModelRole.TARGET},
    "judging": {ModelRole.JUDGE},
    "rag": {ModelRole.TARGET},
    "agent": {ModelRole.TARGET},
}
PERSISTENT_ROLES: set[ModelRole] = {ModelRole.EMBED, ModelRole.GUARD}

# Honest per-model resident-weight estimates (GB) for the sequential budget
# gate under a *local* backend (§7.4). Conservative; includes KV + runtime.
DEFAULT_WEIGHT_GB: dict[str, float] = {
    "qwen2.5:7b": 6.5,
    "llama3.2:3b": 3.0,
    "phi4-mini": 2.8,
    "llama3.1:8b": 7.0,
    "nomic-embed-text": 0.3,
}
GUARD_RESIDENT_GB = 2.0  # DeBERTa incl. torch/transformers (§7.4)
BASE_OVERHEAD_GB = 6.0  # OS + desktop + python/orchestrator + sqlite (§7.4)
SAFETY_HEADROOM_GB = 5.0  # target headroom (NFR-1)


@dataclass
class SchedulerTelemetry:
    peak_rss_mb: float = 0.0  # peak of (all ollama processes + this process tree)
    peak_proc_rss_mb: float = 0.0  # this process tree only (the pre-session-4 figure)
    peak_ollama_rss_mb: float = 0.0
    peak_system_used_mb: float = 0.0  # psutil virtual_memory().used
    swap_start_mb: float = -1.0  # -1 = not sampled yet
    swap_peak_mb: float = 0.0
    access_denied: int = 0  # ollama processes whose RSS could not be read
    phases: list[str] = field(default_factory=list)
    preflight_available_gb: float = 0.0
    mode: str = "sequential"
    loads: int = 0
    unloads: int = 0

    @property
    def swap_delta_mb(self) -> float:
        return max(0.0, self.swap_peak_mb - self.swap_start_mb) if self.swap_start_mb >= 0 else 0.0


class SchedulerError(RuntimeError):
    """Raised when a residency mode would exceed the RAM budget (abort, no swap)."""


class ModelSlotScheduler:
    """Owns residency and RAM safety for a campaign."""

    def __init__(
        self,
        backend: ModelBackend,
        roles: dict[ModelRole, str],
        mode: ResidencyMode | str = ResidencyMode.SEQUENTIAL,
        min_free_gb_for_fast: float = 11.0,
        keep_alive: str | int = "5m",
        weight_gb: dict[str, float] | None = None,
        ram_reader: Callable[[], float] | None = None,
    ) -> None:
        self.backend = backend
        self.roles = dict(roles)
        self.mode = ResidencyMode(mode) if not isinstance(mode, ResidencyMode) else mode
        self.min_free_gb_for_fast = float(min_free_gb_for_fast)
        self.keep_alive = keep_alive
        self.weight_gb = dict(DEFAULT_WEIGHT_GB)
        if weight_gb:
            self.weight_gb.update(weight_gb)
        # Resolve the module global at call time so monkeypatching works, while
        # still allowing an explicit custom reader to be injected.
        self._ram_reader: Callable[[], float] = ram_reader or (lambda: available_ram_gb())
        self.telemetry = SchedulerTelemetry(mode=self.mode.value)
        self._resident: set[str] = set()
        self._sampler: threading.Thread | None = None
        self._stop = threading.Event()

    # --- RAM accounting ---------------------------------------------------
    def _model_for(self, role: ModelRole) -> str | None:
        return self.roles.get(role)

    def estimated_peak_gb(self, phase: str) -> float:
        """Estimated resident footprint for ``phase`` under a local backend."""
        roles = PHASE_ROLES.get(phase, set()) | PERSISTENT_ROLES
        total = BASE_OVERHEAD_GB
        for role in roles:
            model = self._model_for(role)
            if role == ModelRole.GUARD:
                total += GUARD_RESIDENT_GB
            elif model:
                total += self.weight_gb.get(model, 4.0)
        if self.mode == ResidencyMode.CONCURRENT_FAST:
            # fast mode additionally holds the judge during generation
            jm = self._model_for(ModelRole.JUDGE)
            if jm and phase == "generation":
                total += self.weight_gb.get(jm, 3.0)
        return total

    def worst_peak_gb(self) -> float:
        """Largest phase footprint, without the OS share that measured free RAM already excludes."""
        peaks = (self.estimated_peak_gb(p) for p in ("generation", "rag", "agent"))
        return max(peaks, default=0.0) - BASE_OVERHEAD_GB

    def preflight(self) -> float:
        """Verify RAM before a campaign. Raises SchedulerError rather than swap.

        Returns the measured available RAM (GiB). The concurrent-fast free-RAM
        gate is always enforced; the sequential budget gate is enforced only
        under a real local backend (the mock holds no weights).
        """
        available = float(self._ram_reader())
        self.telemetry.preflight_available_gb = available

        if self.mode == ResidencyMode.CONCURRENT_FAST and available < self.min_free_gb_for_fast:
            raise SchedulerError(
                f"concurrent-fast requires >= {self.min_free_gb_for_fast:.0f} GB free; "
                f"measured {available:.1f} GB. Close other apps or use "
                f"residency mode 'sequential'."
            )

        backend_is_mock = getattr(self.backend, "name", "") == "mock"
        if not backend_is_mock:
            # Measured "available" RAM already excludes the OS/desktop, so drop
            # BASE_OVERHEAD_GB here rather than count it twice.
            worst = self.worst_peak_gb()
            if worst > available - SAFETY_HEADROOM_GB:
                raise SchedulerError(
                    f"estimated model peak {worst:.1f} GB exceeds safe budget "
                    f"(available {available:.1f} GB minus {SAFETY_HEADROOM_GB:.0f} GB "
                    f"headroom). Aborting rather than swapping (NFR-1)."
                )
        return available

    # --- phase management -------------------------------------------------
    def _desired_models(self, phase: str) -> set[str]:
        roles = PHASE_ROLES.get(phase, set()) | PERSISTENT_ROLES
        if self.mode == ResidencyMode.CONCURRENT_FAST and phase == "generation":
            roles = roles | {ModelRole.JUDGE}
        out: set[str] = set()
        for role in roles:
            m = self._model_for(role)
            if m:
                out.add(m)
        return out

    def _persistent_models(self) -> set[str]:
        out: set[str] = set()
        for role in PERSISTENT_ROLES:
            m = self._model_for(role)
            if m:
                out.add(m)
        return out

    def _load(self, model: str) -> None:
        self.backend.load(model, keep_alive=self.keep_alive)
        self._resident.add(model)
        self.telemetry.loads += 1

    def _unload(self, model: str) -> None:
        self.backend.unload(model)
        self._resident.discard(model)
        self.telemetry.unloads += 1

    def sample_rss(self) -> float:
        rss = _process_tree_rss_mb()
        t = self.telemetry
        t.peak_proc_rss_mb = max(t.peak_proc_rss_mb, rss)
        t.peak_rss_mb = max(t.peak_rss_mb, rss)
        return rss

    def sample_memory(self) -> None:
        """One system-wide sample: Ollama RSS, system used, swap, process tree (NFR-1)."""
        import psutil

        proc = self.sample_rss()
        ollama, swap, denied = _system_memory_mb()
        t = self.telemetry
        t.access_denied = max(t.access_denied, denied)
        t.peak_ollama_rss_mb = max(t.peak_ollama_rss_mb, ollama)
        t.peak_rss_mb = max(t.peak_rss_mb, ollama + proc)
        t.peak_system_used_mb = max(t.peak_system_used_mb, psutil.virtual_memory().used / (1024**2))
        if t.swap_start_mb < 0:
            t.swap_start_mb = swap
        t.swap_peak_mb = max(t.swap_peak_mb, swap)

    def start_sampler(self, interval_s: float = 1.0) -> None:
        """Sample memory every ``interval_s`` on a daemon thread until stop_sampler()."""
        self._stop.clear()
        self.sample_memory()

        def loop() -> None:
            while not self._stop.wait(interval_s):
                self.sample_memory()

        self._sampler = threading.Thread(target=loop, name="manthan-mem", daemon=True)
        self._sampler.start()

    def stop_sampler(self) -> None:
        if self._sampler is None:
            return
        self._stop.set()
        self._sampler.join(timeout=5)
        self.sample_memory()

    @contextmanager
    def phase(self, name: str) -> Iterator[ModelSlotScheduler]:
        """Enter a residency phase: load desired models, unload the rest.

        On exit in ``sequential`` mode the phase's non-persistent models are
        unloaded so the next phase has headroom; in ``concurrent-fast`` they
        stay resident.
        """
        desired = self._desired_models(name)
        persistent = self._persistent_models()
        # Evict anything resident that this phase does not want (keep persistent).
        for model in sorted(self._resident - desired - persistent):
            self._unload(model)
        # Load desired models not yet resident.
        for model in sorted(desired - self._resident):
            self._load(model)
        self.telemetry.phases.append(name)
        log.info("phase %s resident=%s", name, sorted(self._resident))
        events.emit("phase.start", phase=name, resident=sorted(self._resident))
        self.sample_rss()
        try:
            yield self
        finally:
            events.emit("phase.end", phase=name, resident=sorted(self._resident))
            self.sample_rss()
            if self.mode == ResidencyMode.SEQUENTIAL:
                # Only what is still resident: an unload of an absent model makes Ollama load it.
                for model in sorted((desired - persistent) & self._resident):
                    self._unload(model)

    @property
    def resident(self) -> set[str]:
        return set(self._resident)
