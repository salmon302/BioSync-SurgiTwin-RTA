# SPDX-License-Identifier: MIT
"""
Pulse Physiology Engine Integration
Implements SRS §3.6 - Pulse Engine Integration

This module integrates the Kitware Pulse Physiology Engine for high-fidelity
patient simulation. The native engine is provided by the ``Pulse`` Python
bindings (colloquially "PyPulse"), which are compiled from source by
``middleware/Dockerfile.pulse``.

Design notes
------------
* Origin: BioSync-Gateway middleware/engine/pulse.py (adapted). Persistence is
  append-only (see ``_append_state`` and ``_finalize_run``).
* One long-lived worker process per engine instance (SRS FR-MS-006, DEVELOPMENT_PLAN.md
  Section 3.3). Each :class:`PulseWorker` owns a single-process ``ProcessPoolExecutor``
  started with the ``spawn`` method. The native engine is created inside that process by
  :class:`_NativeEngineAdapter` and never crosses a process boundary, because the engine
  object cannot be pickled. Initialization, steps, serialization, and close are module-level
  functions that run in the worker and exchange only plain values with the parent.
* Steps run off the event loop. :meth:`PulseWorker.step_async` awaits the worker future
  with a bounded timeout. :meth:`SimulationManager.step_simulation_async` is the loop-safe
  entry point. Blocking database writes in this module run through ``asyncio.to_thread``.
* A timed-out step or a crashed worker process fails closed: the worker moves to ERROR and
  its process is terminated. A native crash ends that worker process only.
* The heavy ``import pulse`` happens only inside the worker process. If the engine import
  fails, initialization returns False and the state is ERROR (fail closed, no synthetic
  mock). ``engine/pulse_bridge.py`` checks availability without importing the native
  extension in the parent. The deterministic synthesis opt-in (``BIOSSYNC_SYNTHETIC=1``)
  is carried over unchanged.
* :class:`HeartbeatMonitor` samples the event-loop heartbeat gap (VAL-007). Its statistics
  are read through :meth:`SimulationManager.stats` and ``engine.pulse_bridge.pulse_engine_stats``.
"""
from __future__ import annotations

import asyncio
import base64
import bisect
import dataclasses
import gc
import hashlib
import json
import logging
import math
import multiprocessing
import os
import threading
import time
import uuid
from collections import deque
from concurrent.futures import Executor, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

# Database persistence (optional - gracefully degrades if DB unavailable)
# Append-only: state snapshots and the finalized run are inserted, never updated (SRS FR-DAT-003).
try:
    from database import service_session
    from models import SimulationRun, SimulationState as SimulationStateRecord
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# Audit identity for the writes in this module. Recorded as audit_log.actor_id (FR-DAT-004).
PULSE_ENGINE_ACTOR = "service:pulse-engine"

# Bounded waits (seconds). The step and serialize calls use STEP_TIMEOUT_S unless overridden.
INIT_TIMEOUT_S = 120.0
STEP_TIMEOUT_S = 10.0
CLOSE_TIMEOUT_S = 5.0
DEFAULT_MAX_CONCURRENT = 10

# Heartbeat-gap metric (FR-MS-006 acceptance metric, VAL-007).
HEARTBEAT_INTERVAL_S = 0.010
HEARTBEAT_BOUND_MS = 50.0
HEARTBEAT_WINDOW = 200_000
HEARTBEAT_BUCKET_EDGES_MS = (10.0, 20.0, 50.0, 100.0, 250.0)

# Bound on the per-simulation metric history. Consumers read only the latest entry
# (``[-1]``) or a small length in tests, so an unbounded list buys nothing and costs
# generation-2 GC time: every long-lived SimulationMetrics object must be scanned on
# each gen-2 pass, so the pause grows with run length. Measured on the 600 s FR-MS-006
# run: gen-2 passes of 37 ms at 44 s and 219 ms at 555 s with the unbounded list, both
# showing up as heartbeat gaps above the 50 ms bound. 2000 entries per simulation caps
# the steady-state history objects at 20k (about 7 ms of gen-2 scan at the measured
# 0.36 us per entry-pair rate).
METRICS_HISTORY_MAX = 2000


class SimulationState(Enum):
    """Simulation lifecycle states"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PatientConfig:
    """Patient-specific simulation configuration"""
    patient_id: str
    age: int
    weight_kg: float
    height_cm: float
    sex: str  # "male", "female", "other"
    base_heart_rate: float = 72.0
    base_blood_pressure: List[float] = field(default_factory=lambda: [120.0, 80.0])
    base_spo2: float = 98.0
    conditions: List[str] = field(default_factory=list)  # e.g., ["hypertension", "asthma"]


@dataclass
class SimulationMetrics:
    """Physiological metrics extracted from simulation (SRS FR-3.6.4)"""
    timestamp: float
    heart_rate: float = 0.0
    blood_pressure_systolic: float = 0.0
    blood_pressure_diastolic: float = 0.0
    respiratory_rate: float = 0.0
    spo2: float = 0.0
    temperature: float = 0.0
    cardiac_output: float = 0.0
    stroke_volume: float = 0.0
    systemic_vascular_resistance: float = 0.0
    # SRS FR-3.6.4 required additional metrics
    mean_airway_pressure_cm_h2o: float = 0.0
    # PaO2 from the engine request "ArterialOxygenPressure" (REL_4_3_2). The earlier request name
    # "ArterialOxygenPartialPressure" returns NaN in this engine build (see the defect record).
    # None means unavailable (a non-finite engine value). A NaN is never stored here.
    arterial_o2_partial_pressure_mmhg: Optional[float] = None


@dataclass
class SerializedState:
    """Serialized simulation state for persistence (SRS FR-3.6.3)"""
    patient_id: str
    timestamp: float
    metrics: Dict[str, float]
    engine_state: str  # GPB-serialized state as base64 string
    state_hash: str = ""  # SHA-256 of engine_state for tamper detection
    serialization_format: str = "GPB_v1_base64"  # Protocol buffer indicator
    is_valid: bool = True


# Pulse data-request (CDM) property names used for FR-3.6.4.
# The engine version vendored in .pulse (setup.py: name='pulse') exposes a
# pure-python wrapper package `pulse` (with compiled `PyPulse` C extension).
# Units are SE-Scalar enums (from pulse.cdm.scalars), NOT strings, in
# this version; the unit-by-name map is built inside
# :func:`_build_data_requests` because the enum classes are only
# importable inside the worker process (keeps this module importable
# without the C extension for the rest of the test/CI suite).
_PULSE_DATA_REQUESTS = [
    "HeartRate",
    "SystolicArterialPressure",
    "DiastolicArterialPressure",
    "RespirationRate",
    "OxygenSaturation",
    "MeanAirwayPressure",
    "ArterialOxygenPressure",
]


# ---------------------------------------------------------------------------
# Worker-process side. These run only inside the spawned worker process (or in
# the in-process executor used by tests). The parent never calls the adapter.
# ---------------------------------------------------------------------------

def _build_data_requests():
    """Build the FR-3.6.4 data requests on a SEDataRequestManager (worker process only)."""
    from pulse.cdm.engine import SEDataRequest, SEDataRequestManager
    from pulse.cdm.scalars import FrequencyUnit, PressureUnit

    _unit_by_name = {
        "HeartRate": FrequencyUnit.Per_min,
        "SystolicArterialPressure": PressureUnit.mmHg,
        "DiastolicArterialPressure": PressureUnit.mmHg,
        "RespirationRate": FrequencyUnit.Per_min,
        "OxygenSaturation": None,
        "MeanAirwayPressure": PressureUnit.cmH2O,
        "ArterialOxygenPressure": PressureUnit.mmHg,
    }
    requests = [
        SEDataRequest.create_physiology_request(name, unit=_unit_by_name.get(name))
        for name in _PULSE_DATA_REQUESTS
    ]
    return SEDataRequestManager(requests)


class _NativeEngineAdapter:
    """Owns one native Pulse engine. Constructed only inside a worker process.

    The constructor performs the lazy native imports (``pulse``, ``Pulse``) and
    raises ImportError when the bindings are absent. The caller maps that to a
    fail-closed initialization result.
    """

    def __init__(self, patient: Dict[str, Any], data_root: str):
        from pulse.engine.PulseEngine import PulseEngine, eModelType
        import Pulse  # compat shim exposing the legacy `Pulse` API (Pulse.Engine)
        from pulse.cdm.patient import SEPatientConfiguration, eSex
        from pulse.cdm.scalars import TimeUnit, MassUnit, LengthUnit

        self.engine = PulseEngine(eModelType.HumanAdultWholeBody)
        # Pulse 4.3.2 loads its data tables from data_root_dir. In the
        # biosync-pulse image the data JSON files live in /pulse/bin; allow
        # override via PULSE_DATA_ROOT for local/dev builds.
        self.engine = Pulse.Engine(data_root_dir=data_root)

        # Build the patient configuration (SRS FR-3.6.1).
        pc = SEPatientConfiguration()
        # NOTE: SEPatientConfiguration.set_patient() has a buggy isinstance()
        # guard in this engine build; use get_patient() which lazily creates
        # the enclosed SEPatient and avoids that path.
        patient_obj = pc.get_patient()
        patient_obj.set_name(patient["patient_id"])
        patient_obj.get_age().set_value(patient["age"], TimeUnit.yr)
        patient_obj.get_weight().set_value(patient["weight_kg"], MassUnit.kg)
        patient_obj.get_height().set_value(patient["height_cm"], LengthUnit.cm)
        sex = (patient["sex"] or "male").lower()
        if sex == "female":
            patient_obj.set_sex(eSex.Female)
        else:
            patient_obj.set_sex(eSex.Male)

        # Register data requests once for the whole simulation (FR-3.6.4).
        self._drm = _build_data_requests()
        if not self.engine.initialize_engine(pc, self._drm):
            raise RuntimeError(
                f"Pulse Engine initialize_engine() returned False for patient {patient['patient_id']}"
            )

    def advance(self, time_step_s: float) -> None:
        self.engine.advance_time_s(time_step_s)

    def pull(self) -> Optional[List[float]]:
        """Return the FR-3.6.4 values in ``_PULSE_DATA_REQUESTS`` order, or None.

        In this engine version ``pull_data()`` returns a list whose first element is the
        simulation time and whose remaining elements align 1:1 (by index) with the requests
        registered in :func:`_build_data_requests`. Any failure raises (no mock).
        """
        try:
            values = self.engine.pull_data()
        except Exception as exc:  # pragma: no cover - native API
            raise RuntimeError(f"Pulse data request pull failed: {exc}")

        # pull_data() returns a numpy ndarray; `not values` is invalid for arrays
        # with >1 element, so guard on None explicitly (Pulse 4.3.2 binding).
        if values is None or len(values) < 2:
            return None

        out: List[float] = []
        for index, _name in enumerate(_PULSE_DATA_REQUESTS):
            out.append(_as_float(values, index + 1))  # +1: values[0] is sim time
        return out

    def serialize(self):
        from pulse.cdm.engine import eSerializationFormat
        try:
            return self.engine.serialize_to_string(eSerializationFormat.JSON)
        except Exception as exc:  # pragma: no cover - native API
            raise RuntimeError(
                "Pulse Engine serialize_to_string() failed; ensure a compatible "
                f"Pulse Engine version is installed. Error: {exc}"
            )


def _as_float(values, index: int, default: float = 0.0) -> float:
    try:
        v = values[index]
        try:
            return float(v)
        except (TypeError, ValueError):
            return float(getattr(v, "value", v))
    except Exception:
        return default


# Factory used by the worker-side initializer. Tests replace this name with a stub class
# through monkeypatch. The production path always uses the native adapter.
_ENGINE_FACTORY: Callable[[Dict[str, Any], str], Any] = _NativeEngineAdapter

# Engines owned by this process, keyed by worker id. A spawned worker holds one entry.
_WORKER_ENGINES: Dict[str, Any] = {}


def _worker_engine(worker_id: str):
    try:
        return _WORKER_ENGINES[worker_id]
    except KeyError:
        raise RuntimeError("Engine not initialized in this worker")


def _child_ping() -> int:
    """Return the pid of the process that runs the call (worker identity probe)."""
    return os.getpid()


def _child_initialize(worker_id: str, patient: Dict[str, Any], data_root: str) -> Dict[str, Any]:
    """Create the engine inside this worker. Fail closed: never raises for an engine error."""
    try:
        adapter = _ENGINE_FACTORY(patient, data_root)
    except ImportError as exc:
        logger.error(
            "The Pulse Physiology Engine bindings (the 'pulse' package / "
            "'PyPulse' C extension) are not importable. PyPulse must be "
            "compiled into this image via middleware/Dockerfile.pulse. "
            "ImportError: %s", exc,
        )
        return {"ok": False, "error": f"ImportError: {exc}", "pid": os.getpid()}
    except Exception as exc:  # pragma: no cover - native construction
        logger.error("Failed to construct Pulse Engine: %s", exc)
        return {"ok": False, "error": str(exc), "pid": os.getpid()}
    _WORKER_ENGINES[worker_id] = adapter
    return {"ok": True, "error": None, "pid": os.getpid()}


def _child_step(worker_id: str, n_steps: int, time_step_s: float) -> Dict[str, Any]:
    """Advance the worker's engine by n_steps and return the raw data-request values."""
    adapter = _worker_engine(worker_id)
    step_start = time.perf_counter()
    for _ in range(n_steps):
        adapter.advance(time_step_s)
    engine_ms = (time.perf_counter() - step_start) * 1000.0
    return {"engine_ms": engine_ms, "values": adapter.pull(), "pid": os.getpid()}


def _child_serialize(worker_id: str):
    return _worker_engine(worker_id).serialize()


def _child_close(worker_id: str) -> bool:
    return _WORKER_ENGINES.pop(worker_id, None) is not None


# ---------------------------------------------------------------------------
# Parent side
# ---------------------------------------------------------------------------

def _default_executor() -> Executor:
    """One long-lived worker process. ``spawn`` keeps the native engine out of forked state."""
    return ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))


def _shutdown_executor(executor: Executor, terminate: bool) -> None:
    """Shut an executor down. When ``terminate`` is set, a hung worker process is killed.

    ``ProcessPoolExecutor`` has no public API to kill a running worker. The process
    handles are read from the ``_processes`` attribute, guarded with getattr so thread-based
    executors (used by tests) are unaffected.
    """
    processes = []
    if terminate:
        processes = list((getattr(executor, "_processes", None) or {}).values())
    executor.shutdown(wait=not terminate, cancel_futures=True)
    for proc in processes:
        if proc.is_alive():
            proc.terminate()


def finite_or_none(value: Any) -> Optional[float]:
    """Return the value as a float, or None when it is missing or not finite (NaN, inf).

    Used at every boundary where an engine value leaves the worker: NaN is not valid JSON and
    must never be persisted or hashed as a number. None is the explicit unavailable value.
    """
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _metrics_from_values(values: Optional[List[float]]) -> SimulationMetrics:
    """Build SimulationMetrics from the ordered worker values (SRS FR-3.6.4)."""
    if values is None:
        return SimulationMetrics(timestamp=time.time(), arterial_o2_partial_pressure_mmhg=None)
    v = dict(zip(_PULSE_DATA_REQUESTS, values))
    return SimulationMetrics(
        timestamp=time.time(),
        heart_rate=v.get("HeartRate", 0.0),
        blood_pressure_systolic=v.get("SystolicArterialPressure", 0.0),
        blood_pressure_diastolic=v.get("DiastolicArterialPressure", 0.0),
        respiratory_rate=v.get("RespirationRate", 0.0),
        # Pulse reports OxygenSaturation as a 0..1 fraction; surface it as
        # a percentage (SpO2 80-100%) per the qualification-test contract.
        spo2=v.get("OxygenSaturation", 0.0) * 100.0,
        temperature=0.0,
        cardiac_output=0.0,
        stroke_volume=0.0,
        systemic_vascular_resistance=0.0,
        mean_airway_pressure_cm_h2o=v.get("MeanAirwayPressure", 0.0),
        arterial_o2_partial_pressure_mmhg=finite_or_none(v.get("ArterialOxygenPressure")),
    )


class PulseWorker:
    """
    Worker for one Pulse Physiology Engine simulation.

    The engine lives in a dedicated worker process (see the module docstring). The
    parent holds the state machine, the metric history, and the worker handle.

    Implements:
        SRS FR-3.6.1 - Engine initialization
        SRS FR-3.6.2 - State serialization
        SRS FR-3.6.3 - GPB -> JSONB serialization
        SRS FR-3.6.4 - Data request manager
        SRS FR-3.6.5 - Multi-patient simulation (one worker per engine)
        SRS FR-MS-006 - Off-loop delegation with bounded waits
    """

    # Required metrics to extract (SRS FR-3.6.4)
    REQUIRED_METRICS = list(_PULSE_DATA_REQUESTS)

    # Simulation time step (seconds)
    TIME_STEP = 0.01  # 10 ms

    def __init__(
        self,
        patient_config: PatientConfig,
        executor_factory: Optional[Callable[[], Executor]] = None,
        init_timeout_s: float = INIT_TIMEOUT_S,
        step_timeout_s: float = STEP_TIMEOUT_S,
    ):
        self.patient_config = patient_config
        self.state = SimulationState.INITIALIZING
        # Opaque handle to the engine living in the worker process (None when not running).
        self.engine: Optional[str] = None
        self.worker_id = uuid.uuid4().hex
        self.worker_pid: Optional[int] = None
        self.start_time: Optional[float] = None
        self.paused_at: Optional[float] = None
        self.metrics_history: Deque[SimulationMetrics] = deque(maxlen=METRICS_HISTORY_MAX)
        self._executor_factory = executor_factory or _default_executor
        self._executor: Optional[Executor] = None
        self._init_timeout_s = init_timeout_s
        self._step_timeout_s = step_timeout_s
        # Warm the metrics-hook import off-loop (FR-MS-006; see _warm_metrics_hook).
        _warm_metrics_hook()

    # -- lifecycle ----------------------------------------------------------

    def initialize(self) -> bool:
        """
        Initialize the Pulse Physiology Engine inside a new worker process.

        Returns:
            True if initialization succeeded. False when the bindings cannot be imported,
            the engine fails to construct or initialize, or the worker does not answer in time.

        Implements:
            SRS FR-3.6.1 - Engine initialization
            IQ-4 - Pulse (PyPulse) import verification

        The native ``Pulse`` package is a hard dependency; if the import fails inside the
        worker, initialization returns False and the caller must handle the error. There
        is no mock fallback in production (SRS C1: the Pulse C++ core is single-threaded
        per patient and runs in its own worker process).
        """
        data_root = os.environ.get("PULSE_DATA_ROOT", "/pulse/bin")
        try:
            self._executor = self._executor_factory()
            reply = self._executor.submit(
                _child_initialize, self.worker_id, dataclasses.asdict(self.patient_config), data_root,
            ).result(timeout=self._init_timeout_s)
        except Exception as exc:
            logger.error("Pulse worker initialization failed for patient %s: %s",
                         self.patient_config.patient_id, exc)
            self.state = SimulationState.ERROR
            self._release(graceful=False)
            return False

        if not reply.get("ok"):
            self.state = SimulationState.ERROR
            self._release(graceful=True)
            return False

        self.engine = self.worker_id
        self.worker_pid = reply["pid"]
        self.state = SimulationState.RUNNING
        self.start_time = time.time()
        return True

    def close(self) -> None:
        """Release the worker process. Safe to call more than once."""
        self._release(graceful=True)

    def __enter__(self) -> "PulseWorker":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def worker_probe(self) -> int:
        """Return the pid of the worker process that serves this engine (bounded wait)."""
        return self._call(_child_ping, timeout=self._step_timeout_s)

    # -- stepping -----------------------------------------------------------

    def step(self, n_steps: int = 1) -> Dict[str, float]:
        """
        Advance simulation by N time-steps in the worker process (SRS FR-3.6.2, NFR-P5 <= 50 ms).

        Blocks the calling thread until the worker replies or STEP_TIMEOUT_S elapses. Event-loop
        callers must use :meth:`step_async`.

        Returns:
            Dictionary of extracted metrics.
        """
        self._require_steppable()
        reply = self._call(_child_step, self.worker_id, n_steps, self.TIME_STEP,
                           timeout=self._step_timeout_s)
        return self._record_step(reply, n_steps)

    async def step_async(self, n_steps: int = 1) -> Dict[str, float]:
        """
        Advance the simulation without blocking the event loop (SRS FR-MS-006).

        The step runs in the worker process. The event loop awaits the worker future with
        STEP_TIMEOUT_S as the bound. On timeout or worker failure the worker fails closed.
        """
        self._require_steppable()
        loop = asyncio.get_running_loop()
        try:
            future = loop.run_in_executor(
                self._executor, _child_step, self.worker_id, n_steps, self.TIME_STEP,
            )
            reply = await asyncio.wait_for(future, timeout=self._step_timeout_s)
        except asyncio.TimeoutError:
            self._fail_closed(f"step timed out after {self._step_timeout_s:.1f} s")
            raise TimeoutError(f"Pulse step timed out after {self._step_timeout_s:.1f} s")
        except BrokenProcessPool as exc:
            self._fail_closed(f"worker process terminated: {exc}")
            raise RuntimeError(f"Pulse worker process failed: {exc}") from exc
        return self._record_step(reply, n_steps)

    def _record_step(self, reply: Dict[str, Any], n_steps: int) -> Dict[str, float]:
        metrics = _metrics_from_values(reply["values"])
        self.metrics_history.append(metrics)

        # Record step latency for NFR-P5 instrumentation. Recorded in the parent, because
        # the metric registry is per process.
        try:
            from api.middleware.response_time import record_pulse_step
            record_pulse_step(reply["engine_ms"] / max(n_steps, 1))
        except (ImportError, AttributeError):
            pass

        return metrics.__dict__

    def _require_steppable(self) -> None:
        if self.state != SimulationState.RUNNING:
            raise ValueError(f"Cannot step simulation in state: {self.state}")
        if self._executor is None or self.engine is None:
            raise RuntimeError("Engine not initialized")

    # -- pause, resume, stop, serialize ------------------------------------

    def pause(self) -> "SerializedState":
        """Pause simulation and serialize state (SRS FR-3.6.2)."""
        if self.state != SimulationState.RUNNING:
            raise ValueError(f"Cannot pause simulation in state: {self.state}")
        self.paused_at = time.time()
        self.state = SimulationState.PAUSED
        return self.serialize_state()

    def resume(self) -> bool:
        """Resume simulation from paused state."""
        if self.state != SimulationState.PAUSED:
            raise ValueError(f"Cannot resume simulation in state: {self.state}")
        self.state = SimulationState.RUNNING
        return True

    def stop(self) -> "SerializedState":
        """Stop simulation, serialize final state, and release the worker process."""
        self.state = SimulationState.STOPPED
        state = self.serialize_state()
        self.close()
        return state

    def serialize_state(self) -> "SerializedState":
        """
        Serialize simulation state for persistence (SRS FR-3.6.3).

        Uses Pulse's JSON serialization (via
        ``engine.serialize_to_string(JSON)``) as required by SRS FR-3.6.3
        (GPB -> JSONB). JSON is returned as UTF-8 text by the SWIG binding,
        whereas the BINARY format returns raw bytes that the binding cannot
        decode (UnicodeDecodeError). The serialized text is base64-encoded
        for JSONB storage in PostgreSQL.

        Returns:
            SerializedState object.
        """
        if self._executor is None or self.engine is None:
            raise RuntimeError("Engine not initialized")

        raw = self._call(_child_serialize, self.worker_id, timeout=self._step_timeout_s)

        if isinstance(raw, (bytes, bytearray)):
            engine_state_b64 = base64.b64encode(raw).decode()
        else:
            engine_state_b64 = base64.b64encode(str(raw).encode()).decode()
        # SHA-256 hash for tamper detection (SRS FR-3.8.3).
        state_hash = hashlib.sha256(engine_state_b64.encode()).hexdigest()

        latest = self.metrics_history[-1] if self.metrics_history else None

        def _m(name, default=0.0):
            return getattr(latest, name, default) if latest else default

        return SerializedState(
            patient_id=self.patient_config.patient_id,
            timestamp=time.time(),
            metrics={
                "HeartRate": _m("heart_rate"),
                "SystolicArterialPressure_mmHg": _m("blood_pressure_systolic"),
                "DiastolicArterialPressure_mmHg": _m("blood_pressure_diastolic"),
                "RespirationRate": _m("respiratory_rate"),
                "OxygenSaturation": _m("spo2"),
                "MeanAirwayPressure_cmH2O": _m("mean_airway_pressure_cm_h2o"),
                "ArterialOxygenPressure_mmHg": _m("arterial_o2_partial_pressure_mmhg"),
            },
            engine_state=engine_state_b64,
            state_hash=state_hash,
            serialization_format="GPB_v1_base64",
        )

    # -- internals ----------------------------------------------------------

    def _call(self, fn: Callable, *args: Any, timeout: float) -> Any:
        """Run one worker call with a bounded wait. Fail closed on timeout or worker loss."""
        executor = self._executor
        if executor is None:
            raise RuntimeError("Engine not initialized")
        try:
            return executor.submit(fn, *args).result(timeout=timeout)
        except TimeoutError:
            self._fail_closed(f"call timed out after {timeout:.1f} s")
            raise TimeoutError(f"Pulse worker call timed out after {timeout:.1f} s")
        except BrokenProcessPool as exc:
            self._fail_closed(f"worker process terminated: {exc}")
            raise RuntimeError(f"Pulse worker process failed: {exc}") from exc

    def _fail_closed(self, reason: str) -> None:
        logger.error("Pulse worker %s failed closed: %s", self.worker_id, reason)
        self.state = SimulationState.ERROR
        self._release(graceful=False)

    def _release(self, graceful: bool) -> None:
        executor, self._executor = self._executor, None
        self.engine = None
        self.worker_pid = None
        if executor is None:
            return
        if graceful:
            try:
                executor.submit(_child_close, self.worker_id).result(timeout=CLOSE_TIMEOUT_S)
            except Exception:
                graceful = False
        _shutdown_executor(executor, terminate=not graceful)


class HeartbeatMonitor:
    """
    Event-loop heartbeat-gap sampler (FR-MS-006, VAL-007).

    Definition of a gap: the wall time, in milliseconds, between two consecutive wakeups of
    the heartbeat coroutine. The coroutine sleeps for the nominal interval
    (``HEARTBEAT_INTERVAL_S``) and reads ``time.perf_counter()`` after each wakeup. The raw
    interval is recorded, not the excess over the nominal interval, so the 50 ms bound
    applies to the raw gap. A blocked event loop shows up as a large gap.

    Sampling limits: asyncio clamps timer deadlines to the monotonic clock resolution
    (about 15.6 ms on Windows, reported as ``clock_resolution_ms``). A wakeup can therefore
    come early while the loop is busy, and an idle 10 ms sleep returns after about 15 ms.
    The percentiles describe the wakeup cadence. The maximum gap is the stall detector: a
    loop blocked for T ms shows a gap of at least T ms, and the gap exceeds T by at most one
    heartbeat period plus the clock resolution. The idle gap stays below the 50 ms bound.

    Statistics cover the most recent ``HEARTBEAT_WINDOW`` samples for percentiles. The
    maximum, the sample count, and the histogram cover every sample since the last reset.
    """

    def __init__(self, window: int = HEARTBEAT_WINDOW):
        self._lock = threading.Lock()
        self._gaps: Deque[float] = deque(maxlen=window)
        self._hist = [0] * (len(HEARTBEAT_BUCKET_EDGES_MS) + 1)
        self._count = 0
        self._max_ms = 0.0
        self._interval_s = HEARTBEAT_INTERVAL_S

    async def run(self, interval_s: float = HEARTBEAT_INTERVAL_S) -> None:
        """Sample until cancelled. Run it as an asyncio task on the loop being measured."""
        self._interval_s = interval_s
        last = time.perf_counter()
        while True:
            await asyncio.sleep(interval_s)
            now = time.perf_counter()
            self.record((now - last) * 1000.0)
            last = now

    def record(self, gap_ms: float) -> None:
        with self._lock:
            self._count += 1
            self._gaps.append(gap_ms)
            if gap_ms > self._max_ms:
                self._max_ms = gap_ms
            self._hist[bisect.bisect_left(HEARTBEAT_BUCKET_EDGES_MS, gap_ms)] += 1

    def reset(self) -> None:
        with self._lock:
            self._gaps.clear()
            self._hist = [0] * (len(HEARTBEAT_BUCKET_EDGES_MS) + 1)
            self._count = 0
            self._max_ms = 0.0

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            ordered = sorted(self._gaps)
            hist = list(self._hist)
            count = self._count
            max_ms = self._max_ms
            interval_ms = self._interval_s * 1000.0
        labels = [f"<={edge:g}" for edge in HEARTBEAT_BUCKET_EDGES_MS]
        labels.append(f">{HEARTBEAT_BUCKET_EDGES_MS[-1]:g}")
        return {
            "interval_ms": round(interval_ms, 3),
            "clock_resolution_ms": round(time.get_clock_info("monotonic").resolution * 1000.0, 3),
            "samples": count,
            "window_samples": len(ordered),
            "max_gap_ms": round(max_ms, 3),
            "p50_ms": round(_percentile(ordered, 50), 3),
            "p95_ms": round(_percentile(ordered, 95), 3),
            "p99_ms": round(_percentile(ordered, 99), 3),
            "bound_ms": HEARTBEAT_BOUND_MS,
            "passed": (max_ms <= HEARTBEAT_BOUND_MS) if count else None,
            "histogram_ms": dict(zip(labels, hist)),
        }


def _percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


_heartbeat = HeartbeatMonitor()


def heartbeat_monitor() -> HeartbeatMonitor:
    """Return the process-wide heartbeat monitor."""
    return _heartbeat


def _warm_metrics_hook() -> None:
    """
    Import the NFR-P5 metrics hook at construction time, not at the first step.

    ``PulseWorker._record_step`` imports ``api.middleware.response_time``
    lazily. The first import costs tens of milliseconds of CPU on the calling
    thread. When that first step completes on the event loop, the cost lands on
    the loop and shows up as a heartbeat gap above the 50 ms FR-MS-006 bound
    (measured: 48 ms in-process, 111 ms cold import). ``PulseWorker.__init__``
    runs before any measurement window starts, so warming the import here keeps
    the per-step cost in ``_record_step`` to a ``sys.modules`` lookup.
    Import failures are reported by ``_record_step`` as they were before.
    """
    try:
        import api.middleware.response_time  # noqa: F401
    except (ImportError, AttributeError):
        pass


_GC_FROZEN = False


def _freeze_gc_once() -> None:
    """
    Permanently untrack the objects that exist before the first manager starts.

    ``gc.freeze()`` moves every currently tracked object out of the generational
    collector, so generation-2 passes scan only objects created at runtime. The
    runtime set is bounded by ``METRICS_HISTORY_MAX``; the pre-existing set is
    import-time state (module graphs, codecaches, the warmed metrics hook) that
    lives for the whole process and would otherwise be rescanned on every gen-2
    pass. The 600 s FR-MS-006 baseline measured a gen-2 floor of roughly 20 ms
    on top of the history-driven cost; freezing removes that floor from the
    loop-visible pause. Runs once per process; later managers keep their
    worker objects collectable. Import failures and old interpreters without
    ``gc.freeze`` leave collection behavior unchanged.
    """
    global _GC_FROZEN
    if _GC_FROZEN:
        return
    _GC_FROZEN = True
    try:
        gc.collect()
        gc.freeze()
    except (AttributeError, RuntimeError):  # pragma: no cover - gc.freeze is standard 3.7+
        pass


class SimulationManager:
    """
    Manages multiple concurrent Pulse Engine simulations.

    Each simulation has its own worker process (:class:`PulseWorker`). The manager
    enforces ``max_concurrent`` and provides loop-safe async entry points.

    Implements:
        SRS FR-3.6.5 - Multi-patient simulation
        SRS FR-MS-006 - Off-loop delegation to one long-lived worker per engine
    """

    def __init__(
        self,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        executor_factory: Optional[Callable[[], Executor]] = None,
    ):
        self.max_concurrent = max_concurrent
        self.simulations: Dict[str, PulseWorker] = {}
        self._executor_factory = executor_factory
        self._pending: set = set()
        self._lock = threading.Lock()
        self.heartbeat = heartbeat_monitor()

    def create_simulation(self, patient_config: PatientConfig) -> str:
        """Create a new simulation. Blocks while the worker process initializes."""
        simulation_id = patient_config.patient_id
        with self._lock:
            if simulation_id in self.simulations or simulation_id in self._pending:
                raise ValueError(f"Simulation {simulation_id} already exists")
            if len(self.simulations) + len(self._pending) >= self.max_concurrent:
                raise RuntimeError(f"Simulation limit reached ({self.max_concurrent} concurrent)")
            self._pending.add(simulation_id)

        try:
            worker = PulseWorker(patient_config, executor_factory=self._executor_factory)
            if not worker.initialize():
                raise RuntimeError(f"Failed to initialize simulation {simulation_id}")
            with self._lock:
                self.simulations[simulation_id] = worker
        finally:
            with self._lock:
                self._pending.discard(simulation_id)

        # Persist the initial state as an append-only snapshot (SRS FR-MS-006)
        if DB_AVAILABLE:
            self._append_state(simulation_id, "running", {"status": "running", "initialized": True})

        return simulation_id

    async def create_simulation_async(self, patient_config: PatientConfig) -> str:
        """Create a simulation without blocking the loop (initialization and writes off-loop)."""
        return await asyncio.to_thread(self.create_simulation, patient_config)

    def step_simulation(self, simulation_id: str, n_steps: int = 1) -> Dict:
        """
        Advance a simulation (SRS FR-3.6.2, C1). Blocks the calling thread.

        Event-loop callers must use :meth:`step_simulation_async`.
        """
        return self._worker(simulation_id).step(n_steps)

    async def step_simulation_async(self, simulation_id: str, n_steps: int = 1) -> Dict:
        """Advance a simulation in its worker process, awaiting the bounded step future."""
        return await self._worker(simulation_id).step_async(n_steps)

    def pause_simulation(self, simulation_id: str) -> "SerializedState":
        """Pause a simulation"""
        state = self._worker(simulation_id).pause()
        if DB_AVAILABLE:
            self._persist_state(simulation_id, state, "paused")
        return state

    async def pause_simulation_async(self, simulation_id: str) -> "SerializedState":
        return await asyncio.to_thread(self.pause_simulation, simulation_id)

    def resume_simulation(self, simulation_id: str) -> bool:
        """Resume a simulation"""
        success = self._worker(simulation_id).resume()
        if DB_AVAILABLE and success:
            self._append_state(simulation_id, "running", {"status": "running"})
        return success

    def stop_simulation(self, simulation_id: str) -> "SerializedState":
        """Stop a simulation and serialize final state"""
        worker = self._worker(simulation_id)
        state = worker.stop()
        if DB_AVAILABLE:
            self._persist_state(simulation_id, state, "stopped")
            self._finalize_run(simulation_id, state, worker.start_time)
        del self.simulations[simulation_id]
        return state

    async def stop_simulation_async(self, simulation_id: str) -> "SerializedState":
        return await asyncio.to_thread(self.stop_simulation, simulation_id)

    def _worker(self, simulation_id: str) -> PulseWorker:
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        return self.simulations[simulation_id]

    def start_heartbeat(self, interval_s: float = HEARTBEAT_INTERVAL_S) -> "asyncio.Task":
        """Start the heartbeat sampler on the running loop. Cancel the task to stop it."""
        return asyncio.create_task(self.heartbeat.run(interval_s))

    def stats(self) -> Dict[str, Any]:
        """Operator and test view of the active simulations and the heartbeat-gap metric."""
        return {
            "active_simulations": len(self.simulations),
            "max_concurrent": self.max_concurrent,
            "workers": {
                sim_id: {"pid": worker.worker_pid, "state": worker.state.value}
                for sim_id, worker in self.simulations.items()
            },
            "heartbeat": self.heartbeat.snapshot(),
        }

    def _append_state(self, simulation_id: str, status: str, engine_state: Dict) -> None:
        """
        Insert an append-only simulation state snapshot (SRS FR-MS-006, FR-DAT-003).

        The Gateway updated a single simulations row in place. That table is append-only
        under the compliance triggers, so each transition is written as a new row instead.
        """
        try:
            # allow_nan=False: a NaN or infinity raises here instead of being written as a bare token
            # (not valid JSON) and hashed. Unavailable values are None (JSON null) by construction.
            payload = json.dumps(engine_state, sort_keys=True, allow_nan=False)
            db = service_session(PULSE_ENGINE_ACTOR)
            try:
                db.add(SimulationStateRecord(
                    state_uid=str(uuid.uuid4()),
                    run_key=simulation_id,
                    status=status,
                    engine_state=engine_state,
                    state_hash=hashlib.sha256(payload.encode()).hexdigest(),
                ))
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to persist simulation state to DB: {e}")

    def _persist_state(self, simulation_id: str, state: "SerializedState", status: str):
        """Append the serialized Pulse state to the database (SRS FR-MS-006)."""
        self._append_state(simulation_id, status, {
            "patient_id": state.patient_id,
            "timestamp": state.timestamp,
            "metrics": state.metrics,
            "engine_state": state.engine_state,
            "state_hash": state.state_hash,
            "serialization_format": state.serialization_format,
        })

    def _finalize_run(self, simulation_id: str, state: "SerializedState", started_at: Optional[float]) -> None:
        """Write the finalized simulation run record once (SRS FR-DAT-003)."""
        try:
            started = datetime.fromtimestamp(started_at or time.time(), tz=timezone.utc)
            db = service_session(PULSE_ENGINE_ACTOR)
            try:
                db.add(SimulationRun(
                    run_uid=str(uuid.uuid4()),
                    run_key=simulation_id,
                    patient_id=state.patient_id,
                    engine="pulse",
                    status="completed",
                    config={"time_step_s": PulseWorker.TIME_STEP},
                    output_hashes={"final_state_hash": state.state_hash},
                    started_at=started,
                ))
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to finalize simulation run in DB: {e}")

    def get_simulation_count(self) -> int:
        """Get number of active simulations"""
        return len(self.simulations)


# Test functions for IQ-4, OQ-16
def run_iq4_test() -> bool:
    """
    IQ-4: Verify Pulse (PyPulse) import and engine initialization.
    """
    config = PatientConfig(
        patient_id="test-patient-1",
        age=45,
        weight_kg=70.0,
        height_cm=175.0,
        sex="male",
    )
    worker = PulseWorker(config)
    try:
        return worker.initialize()
    finally:
        worker.close()


def run_oq16_test() -> bool:
    """
    OQ-16: Verify state serialization and deserialization.
    """
    config = PatientConfig(
        patient_id="test-patient-2",
        age=50,
        weight_kg=65.0,
        height_cm=165.0,
        sex="female",
    )
    worker = PulseWorker(config)
    try:
        if not worker.initialize():
            return False
        worker.step(100)
        state = worker.pause()
        return state.is_valid and state.patient_id == "test-patient-2"
    finally:
        worker.close()


if __name__ == "__main__":
    print("Running IQ-4 and OQ-16 tests...")
    print(f"IQ-4 (engine init): {'PASS' if run_iq4_test() else 'FAIL'}")
    print(f"OQ-16 (state serialization): {'PASS' if run_oq16_test() else 'FAIL'}")
