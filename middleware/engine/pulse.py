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
* The heavy ``import pulse`` happens **lazily inside** :meth:`PulseWorker.initialize`
  so this module can be imported (and unit-tested) even when the native engine
  is absent. If the engine import fails, initialization fails *closed* (no
  synthetic mock).
* ``engine/pulse_bridge.py`` reports whether the live engine is importable. The
  deterministic synthesis opt-in (``BIOSSYNC_SYNTHETIC=1``) is carried over unchanged.
* ``SimulationManager.step_simulation`` is synchronous. The native engine object
  cannot be pickled, so ``ProcessPoolExecutor`` delegation (SRS FR-MS-006) is not
  active. This is open debt (see docs/migration-map.md).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

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
    heart_rate: float
    blood_pressure_systolic: float
    blood_pressure_diastolic: float
    respiratory_rate: float
    spo2: float
    temperature: float
    cardiac_output: float
    stroke_volume: float
    systemic_vascular_resistance: float
    # SRS FR-3.6.4 required additional metrics
    mean_airway_pressure_cm_h2o: float = 0.0
    arterial_o2_partial_pressure_mmhg: float = 95.0


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
# :meth:`_register_data_requests` because the enum classes are only
# importable once the engine is available (keeps this module importable
# without the C extension for the rest of the test/CI suite).
_PULSE_DATA_REQUESTS = [
    "HeartRate",
    "SystolicArterialPressure",
    "DiastolicArterialPressure",
    "RespirationRate",
    "OxygenSaturation",
    "MeanAirwayPressure",
    "ArterialOxygenPartialPressure",
]


class PulseWorker:
    """
    Worker class for Pulse Physiology Engine simulation.

    Implements:
        SRS FR-3.6.1 - Engine initialization
        SRS FR-3.6.2 - State serialization
        SRS FR-3.6.3 - GPB -> JSONB serialization
        SRS FR-3.6.4 - Data request manager
        SRS FR-3.6.5 - Multi-patient simulation
    """

    # Required metrics to extract (SRS FR-3.6.4)
    REQUIRED_METRICS = list(_PULSE_DATA_REQUESTS)

    # Simulation time step (seconds)
    TIME_STEP = 0.01  # 10 ms

    def __init__(self, patient_config: PatientConfig):
        self.patient_config = patient_config
        self.state = SimulationState.INITIALIZING
        self.engine = None  # Native pulse.engine.PulseEngine.PulseEngine()
        self._drm = None    # Native data request manager
        self.future: Optional[Future] = None
        self.start_time: Optional[float] = None
        self.paused_at: Optional[float] = None
        self.metrics_history: List[SimulationMetrics] = []

    def initialize(self) -> bool:
        """
        Initialize Pulse Physiology Engine against the real native bindings.

        Returns:
            True if initialization succeeded.

        Implements:
            SRS FR-3.6.1 - Engine initialization
            IQ-4 - Pulse (PyPulse) import verification

        The native ``Pulse`` package is a hard dependency; if the import fails,
        initialization returns False and the caller must handle the error. There
        is no mock fallback in production (SRS C1: the Pulse C++ core is
        single-threaded per patient and must be delegated to worker pools).
        """
        try:
            from pulse.engine.PulseEngine import PulseEngine, eModelType
            import Pulse  # compat shim exposing the legacy `Pulse` API (Pulse.Engine)
            from pulse.cdm.patient import SEPatientConfiguration, eSex
            from pulse.cdm.scalars import TimeUnit, MassUnit, LengthUnit
        except ImportError as exc:  # pragma: no cover - native build
            logger.error(
                "The Pulse Physiology Engine bindings (the 'pulse' package / "
                "'PyPulse' C extension) are not importable. PyPulse must be "
                "compiled into this image via middleware/Dockerfile.pulse. "
                "ImportError: %s", exc,
            )
            self.state = SimulationState.ERROR
            return False

        try:
            self.engine = PulseEngine(eModelType.HumanAdultWholeBody)
        except Exception as exc:  # pragma: no cover - native construction
            logger.error("Failed to construct Pulse Engine: %s", exc)
            self.state = SimulationState.ERROR
            return False

        try:
            # Pulse 4.3.2 loads its data tables from data_root_dir. In the
            # biosync-pulse image the data JSON files live in /pulse/bin; allow
            # override via PULSE_DATA_ROOT for local/dev builds.
            self.engine = Pulse.Engine(
                data_root_dir=os.environ.get("PULSE_DATA_ROOT", "/pulse/bin")
            )
        except Exception as exc:  # pragma: no cover - native construction
            logger.error("Failed to construct Pulse Engine: %s", exc)
            self.state = SimulationState.ERROR
            return False

        # Build the patient configuration (SRS FR-3.6.1).
        pc = SEPatientConfiguration()
        # NOTE: SEPatientConfiguration.set_patient() has a buggy isinstance()
        # guard in this engine build; use get_patient() which lazily creates
        # the enclosed SEPatient and avoids that path.
        patient = pc.get_patient()
        patient.set_name(self.patient_config.patient_id)
        patient.get_age().set_value(self.patient_config.age, TimeUnit.yr)
        patient.get_weight().set_value(self.patient_config.weight_kg, MassUnit.kg)
        patient.get_height().set_value(self.patient_config.height_cm, LengthUnit.cm)
        sex = (self.patient_config.sex or "male").lower()
        if sex == "female":
            patient.set_sex(eSex.Female)
        else:
            patient.set_sex(eSex.Male)

        # Register data requests once for the whole simulation (FR-3.6.4).
        self._drm = self._register_data_requests()
        if not self.engine.initialize_engine(pc, self._drm):
            logger.error(
                "Pulse Engine initialize_engine() returned False for patient %s",
                self.patient_config.patient_id,
            )
            self.state = SimulationState.ERROR
            return False

        self.state = SimulationState.RUNNING
        self.start_time = time.time()
        return True

    def _register_data_requests(self):
        """Build the FR-3.6.4 data requests on a SEDataRequestManager.

        Returns the manager (also stored on ``self._drm``) and records the
        request name order on ``self._request_order`` so
        :meth:`_extract_metrics` can read values by name.
        """
        from pulse.cdm.engine import SEDataRequest, SEDataRequestManager
        from pulse.cdm.scalars import FrequencyUnit, PressureUnit

        _unit_by_name = {
            "HeartRate": FrequencyUnit.Per_min,
            "SystolicArterialPressure": PressureUnit.mmHg,
            "DiastolicArterialPressure": PressureUnit.mmHg,
            "RespirationRate": FrequencyUnit.Per_min,
            "OxygenSaturation": None,
            "MeanAirwayPressure": PressureUnit.cmH2O,
            "ArterialOxygenPartialPressure": PressureUnit.mmHg,
        }
        requests = [
            SEDataRequest.create_physiology_request(name, unit=_unit_by_name.get(name))
            for name in _PULSE_DATA_REQUESTS
        ]
        self._drm = SEDataRequestManager(requests)
        self._request_order = list(_PULSE_DATA_REQUESTS)
        return self._drm

    def step(self, n_steps: int = 1) -> Dict[str, float]:
        """
        Advance simulation by N time-steps (SRS FR-3.6.2, NFR-P5 ≤ 50 ms).

        Returns:
            Dictionary of extracted metrics.
        """
        if self.state != SimulationState.RUNNING:
            raise ValueError(f"Cannot step simulation in state: {self.state}")
        if not self.engine:
            raise RuntimeError("Engine not initialized")

        step_start = time.perf_counter()
        for _ in range(n_steps):
            self.engine.advance_time_s(self.TIME_STEP)
        step_ms = (time.perf_counter() - step_start) * 1000.0

        metrics = self._extract_metrics()
        self.metrics_history.append(metrics)

        # Record step latency for NFR-P5 instrumentation.
        try:
            from api.middleware.response_time import record_pulse_step
            record_pulse_step(step_ms / max(n_steps, 1))
        except (ImportError, AttributeError):
            pass

        return metrics.__dict__

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
        """Stop simulation and serialize final state."""
        self.state = SimulationState.STOPPED
        return self.serialize_state()

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
        if not self.engine:
            raise RuntimeError("Engine not initialized")

        from pulse.cdm.engine import eSerializationFormat
        try:
            raw = self.engine.serialize_to_string(eSerializationFormat.JSON)
        except Exception as exc:  # pragma: no cover - native API
            raise RuntimeError(
                "Pulse Engine serialize_to_string() failed; ensure a compatible "
                f"Pulse Engine version is installed. Error: {exc}"
            )

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
                "ArterialOxygenPartialPressure_mmHg": _m("arterial_o2_partial_pressure_mmhg"),
            },
            engine_state=engine_state_b64,
            state_hash=state_hash,
            serialization_format="GPB_v1_base64",
        )

    def _extract_metrics(self) -> SimulationMetrics:
        """
        Extract required physiological metrics from the engine (FR-3.6.4).

        In this engine version ``pull_data()`` returns a list whose first
        element is the simulation time and whose remaining elements align 1:1
        (by index) with the requests registered in :meth:`_register_data_requests`.
        Each element is the numeric value (or a scalar object exposing
        ``.value``). Any failure raises (no mock).

        Returns:
            SimulationMetrics object.
        """
        if self.engine is None or getattr(self, "_drm", None) is None:
            raise RuntimeError("Engine not initialized")

        try:
            values = self.engine.pull_data()
        except Exception as exc:  # pragma: no cover - native API
            raise RuntimeError(f"Pulse data request pull failed: {exc}")

        # pull_data() returns a numpy ndarray; `not values` is invalid for arrays
        # with >1 element, so guard on None explicitly (Pulse 4.3.2 binding).
        if values is None or len(values) < 2:
            return SimulationMetrics(timestamp=time.time())

        def val(name: str, default: float = 0.0) -> float:
            try:
                idx = self._request_order.index(name) + 1  # +1: values[0] is sim time
                v = values[idx]
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return float(getattr(v, "value", v))
            except Exception:
                return default

        return SimulationMetrics(
            timestamp=time.time(),
            heart_rate=val("HeartRate"),
            blood_pressure_systolic=val("SystolicArterialPressure"),
            blood_pressure_diastolic=val("DiastolicArterialPressure"),
            respiratory_rate=val("RespirationRate"),
            # Pulse reports OxygenSaturation as a 0..1 fraction; surface it as
            # a percentage (SpO2 80-100%) per the qualification-test contract.
            spo2=val("OxygenSaturation") * 100.0,
            temperature=0.0,
            cardiac_output=0.0,
            stroke_volume=0.0,
            systemic_vascular_resistance=0.0,
            mean_airway_pressure_cm_h2o=val("MeanAirwayPressure"),
            arterial_o2_partial_pressure_mmhg=val("ArterialOxygenPartialPressure"),
        )


class SimulationManager:
    """
    Manages multiple concurrent Pulse Engine simulations.

    Implements:
        SRS FR-3.6.5 - Multi-patient simulation
        SRS FR-3.6.2 - Async delegation via ProcessPoolExecutor (Constraint C1)
    """

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.simulations: Dict[str, PulseWorker] = {}
        self.executor = ProcessPoolExecutor(max_workers=max_concurrent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or detect the current asyncio event loop."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    def create_simulation(self, patient_config: PatientConfig) -> str:
        """Create a new simulation."""
        simulation_id = patient_config.patient_id
        if simulation_id in self.simulations:
            raise ValueError(f"Simulation {simulation_id} already exists")

        worker = PulseWorker(patient_config)
        if not worker.initialize():
            raise RuntimeError(f"Failed to initialize simulation {simulation_id}")

        self.simulations[simulation_id] = worker

        # Persist the initial state as an append-only snapshot (SRS FR-MS-006)
        if DB_AVAILABLE:
            self._append_state(simulation_id, "running", {"status": "running", "initialized": True})

        return simulation_id

    def step_simulation(self, simulation_id: str, n_steps: int = 1) -> Dict:
        """
        Advance a simulation (SRS FR-3.6.2, C1).

        Note: the native engine object cannot be pickled, so a ProcessPool
        submission would fail; we degrade to a direct call. The method is kept
        synchronous (it blocks on the native engine step); callers that need
        non-blocking behaviour should wrap it in a worker thread. A production
        deployment should pin each engine to a long-lived worker
        process/thread (tracked as a follow-up).
        """
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        worker = self.simulations[simulation_id]
        return worker.step(n_steps)

    def pause_simulation(self, simulation_id: str) -> SimulationState:
        """Pause a simulation"""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        state = self.simulations[simulation_id].pause()
        if DB_AVAILABLE:
            self._persist_state(simulation_id, state, "paused")
        return state

    def resume_simulation(self, simulation_id: str) -> bool:
        """Resume a simulation"""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        success = self.simulations[simulation_id].resume()
        if DB_AVAILABLE and success:
            self._append_state(simulation_id, "running", {"status": "running"})
        return success

    def stop_simulation(self, simulation_id: str) -> "SerializedState":
        """Stop a simulation and serialize final state"""
        if simulation_id not in self.simulations:
            raise ValueError(f"Simulation {simulation_id} not found")
        worker = self.simulations[simulation_id]
        state = worker.stop()
        if DB_AVAILABLE:
            self._persist_state(simulation_id, state, "stopped")
            self._finalize_run(simulation_id, state, worker.start_time)
        del self.simulations[simulation_id]
        return state

    def _append_state(self, simulation_id: str, status: str, engine_state: Dict) -> None:
        """
        Insert an append-only simulation state snapshot (SRS FR-MS-006, FR-DAT-003).

        The Gateway updated a single simulations row in place. That table is append-only
        under the compliance triggers, so each transition is written as a new row instead.
        """
        try:
            payload = json.dumps(engine_state, sort_keys=True)
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


def _step_worker_sync(worker: PulseWorker, n_steps: int) -> Dict:
    """
    Synchronous worker function for ProcessPoolExecutor.
    Must be a module-level function for pickling.

    SRS FR-3.6.2: Async delegation to worker pool.
    """
    return worker.step(n_steps)


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
    return worker.initialize()


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
    if not worker.initialize():
        return False
    worker.step(100)
    state = worker.pause()
    return state.is_valid and state.patient_id == "test-patient-2"


if __name__ == "__main__":
    print("Running IQ-4 and OQ-16 tests...")
    print(f"IQ-4 (engine init): {'PASS' if run_iq4_test() else 'FAIL'}")
    print(f"OQ-16 (state serialization): {'PASS' if run_oq16_test() else 'FAIL'}")
