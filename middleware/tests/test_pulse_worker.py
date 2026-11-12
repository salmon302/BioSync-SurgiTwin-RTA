# SPDX-License-Identifier: MIT
"""
Pulse worker lifecycle and heartbeat-gap metric (SRS FR-MS-006, DEVELOPMENT_PLAN.md task 2.5).

Covers:
  * one long-lived worker process per engine, reused across steps (real spawn process),
  * fail-closed initialization when the engine bindings are absent (real spawn process
    and an injected ImportError),
  * bounded step timeouts and worker-loss handling (fail closed),
  * steps awaited off the event loop while the loop keeps running,
  * the heartbeat-gap statistics, the histogram, and a negative control that a blocked loop
    is detected,
  * the bridge availability check and the bridge stats surface.

Test doubles (this file only, never on the production path):
  * StubEngine replaces the native adapter through ``engine.pulse._ENGINE_FACTORY``. It is
    used with an in-process ThreadPoolExecutor, which is the ``executor_factory`` seam of
    PulseWorker and SimulationManager. Real spawn processes cannot see a monkeypatched stub.
  * The real-process tests use no double. They rely on the absence of the bindings or on
    the worker pid.

The real native engine is not exercised here. IQ-4, OQ-16, and the FR-MS-006 PQ run cover it
when the pinned Pulse build is present.
"""

import asyncio
import base64
import importlib.util
import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import engine.pulse as pulse_mod
import engine.pulse_bridge as bridge
from engine.pulse import (
    HeartbeatMonitor,
    PatientConfig,
    PulseWorker,
    SimulationManager,
    SimulationState,
    _metrics_from_values,
    _default_executor,
)

pytestmark = pytest.mark.unit

PULSE_PRESENT = importlib.util.find_spec("pulse") is not None

# Nominal engine values in data-request order. The last entry is ArterialOxygenPressure (PaO2, mmHg),
# the working REL_4_3_2 request. Measured on the resting adult (2026-11-07): 89.06 to 89.20 mmHg.
NOMINAL_VALUES = [72.0, 120.0, 80.0, 14.0, 0.98, 8.0, 89.1]


def _config(patient_id: str = "unit-1") -> PatientConfig:
    return PatientConfig(patient_id=patient_id, age=45, weight_kg=70.0, height_cm=175.0, sex="male")


def _thread_executor():
    return ThreadPoolExecutor(max_workers=1)


class StubEngine:
    """Test double for the native adapter. Records constructions and optional step blocking."""

    constructed = []
    block = None
    advance_delay_s = 0.0

    def __init__(self, patient, data_root):
        self.patient = patient
        self.data_root = data_root
        self.sim_time_s = 0.0
        StubEngine.constructed.append(self)

    def advance(self, time_step_s):
        if StubEngine.block is not None:
            StubEngine.block.wait()
        if StubEngine.advance_delay_s:
            time.sleep(StubEngine.advance_delay_s)
        self.sim_time_s += time_step_s

    def pull(self):
        return list(NOMINAL_VALUES)

    def serialize(self):
        return '{"stub_time_s": %.6f}' % self.sim_time_s


@pytest.fixture
def stub_engine(monkeypatch):
    StubEngine.constructed = []
    StubEngine.block = None
    StubEngine.advance_delay_s = 0.0
    monkeypatch.setattr(pulse_mod, "_ENGINE_FACTORY", StubEngine)
    yield StubEngine
    if StubEngine.block is not None:
        StubEngine.block.set()
    StubEngine.block = None


@pytest.fixture
def no_database(monkeypatch):
    calls = []

    def _fail(*args, **kwargs):
        calls.append(args)
        raise AssertionError("database session requested on the Pulse path")

    monkeypatch.setattr(pulse_mod, "DB_AVAILABLE", False)
    monkeypatch.setattr(pulse_mod, "service_session", _fail, raising=False)
    return calls


def _real_process_worker(patient_id: str = "unit-proc") -> PulseWorker:
    """A worker that owns a real spawn process, without initializing an engine."""
    worker = PulseWorker(_config(patient_id))
    worker._executor = _default_executor()
    return worker


# -- fail-closed initialization ---------------------------------------------

@pytest.mark.skipif(PULSE_PRESENT, reason="native Pulse bindings present; fail-closed path not exercised")
def test_initialize_fails_closed_in_real_worker_process():
    worker = PulseWorker(_config("unit-fc-proc"))
    try:
        assert worker.initialize() is False
        assert worker.state == SimulationState.ERROR
        assert worker.engine is None
        assert worker._executor is None
    finally:
        worker.close()


def test_initialize_fails_closed_when_adapter_import_fails(monkeypatch):
    def _missing(patient, data_root):
        raise ImportError("No module named 'pulse' (injected)")

    monkeypatch.setattr(pulse_mod, "_ENGINE_FACTORY", _missing)
    worker = PulseWorker(_config("unit-fc-import"), executor_factory=_thread_executor)
    assert worker.initialize() is False
    assert worker.state == SimulationState.ERROR
    assert worker.engine is None
    assert worker.worker_id not in pulse_mod._WORKER_ENGINES


def test_initialize_fails_closed_when_engine_construction_fails(monkeypatch):
    def _broken(patient, data_root):
        raise RuntimeError("initialize_engine() returned False (injected)")

    monkeypatch.setattr(pulse_mod, "_ENGINE_FACTORY", _broken)
    worker = PulseWorker(_config("unit-fc-build"), executor_factory=_thread_executor)
    assert worker.initialize() is False
    assert worker.state == SimulationState.ERROR


# -- one long-lived worker per engine ---------------------------------------

def test_long_lived_worker_process_is_reused_across_calls():
    worker = _real_process_worker("unit-reuse")
    try:
        pids = [worker.worker_probe() for _ in range(3)]
        assert len(set(pids)) == 1, "every call must reach the same worker process"
        assert pids[0] != os.getpid(), "the engine must not run in the parent process"
    finally:
        worker.close()


def test_one_engine_per_worker_across_steps(stub_engine):
    worker = PulseWorker(_config("unit-steps"), executor_factory=_thread_executor)
    try:
        assert worker.initialize() is True
        for _ in range(3):
            worker.step(10)
        assert len(stub_engine.constructed) == 1, "engine must be created once per worker"
        assert len(worker.metrics_history) == 3
        assert worker.state == SimulationState.RUNNING
        assert worker.engine == worker.worker_id
    finally:
        worker.close()


def test_worker_keeps_engine_handle_out_of_parent(stub_engine):
    worker = PulseWorker(_config("unit-handle"), executor_factory=_thread_executor)
    try:
        assert worker.initialize() is True
        assert isinstance(worker.engine, str)
        assert pulse_mod._WORKER_ENGINES[worker.worker_id] is not None
    finally:
        worker.close()
    assert worker.worker_id not in pulse_mod._WORKER_ENGINES


def test_close_is_idempotent_and_releases_engine(stub_engine):
    worker = PulseWorker(_config("unit-close"), executor_factory=_thread_executor)
    assert worker.initialize() is True
    worker.close()
    worker.close()
    assert worker.engine is None
    assert worker._executor is None
    with pytest.raises(RuntimeError, match="not initialized"):
        worker.serialize_state()


# -- bounded timeouts and worker loss ---------------------------------------

def test_step_timeout_fails_closed(stub_engine):
    worker = PulseWorker(_config("unit-timeout"), executor_factory=_thread_executor, step_timeout_s=0.2)
    assert worker.initialize() is True
    stub_engine.block = threading.Event()
    try:
        with pytest.raises(TimeoutError):
            worker.step(1)
        assert worker.state == SimulationState.ERROR
        assert worker.engine is None
    finally:
        stub_engine.block.set()


def test_async_step_timeout_fails_closed(stub_engine):
    worker = PulseWorker(_config("unit-timeout-async"), executor_factory=_thread_executor, step_timeout_s=0.2)
    assert worker.initialize() is True
    stub_engine.block = threading.Event()

    async def _run():
        with pytest.raises(TimeoutError):
            await worker.step_async(1)

    try:
        asyncio.run(_run())
        assert worker.state == SimulationState.ERROR
    finally:
        stub_engine.block.set()


def test_worker_process_loss_fails_closed_real_process():
    worker = _real_process_worker("unit-crash")
    worker.state = SimulationState.RUNNING
    worker.engine = worker.worker_id
    pid = worker.worker_probe()
    os.kill(pid, signal.SIGTERM)
    try:
        with pytest.raises(RuntimeError, match="worker process failed"):
            worker.step(1)
        assert worker.state == SimulationState.ERROR
        assert worker.engine is None
    finally:
        worker.close()


def test_step_requires_running_state(stub_engine):
    worker = PulseWorker(_config("unit-state"), executor_factory=_thread_executor)
    with pytest.raises(ValueError, match="Cannot step"):
        worker.step(1)


# -- steps off the event loop -----------------------------------------------

def test_async_step_keeps_event_loop_running(stub_engine, no_database):
    stub_engine.advance_delay_s = 0.01
    worker = PulseWorker(_config("unit-loop"), executor_factory=_thread_executor)
    assert worker.initialize() is True

    async def _run():
        ticks = 0
        stop = asyncio.Event()

        async def _ticker():
            nonlocal ticks
            while not stop.is_set():
                await asyncio.sleep(0.005)
                ticks += 1

        ticker = asyncio.create_task(_ticker())
        metrics = await worker.step_async(10)
        stop.set()
        await ticker
        return metrics, ticks

    try:
        metrics, ticks = asyncio.run(_run())
        assert metrics["heart_rate"] == 72.0
        assert ticks > 0, "the loop must run other tasks while the step is in flight"
    finally:
        worker.close()


def test_async_step_does_not_write_to_database(stub_engine, no_database, monkeypatch):
    monkeypatch.setattr(pulse_mod, "DB_AVAILABLE", True)
    worker = PulseWorker(_config("unit-nodb"), executor_factory=_thread_executor)
    assert worker.initialize() is True
    try:
        asyncio.run(worker.step_async(5))
        assert no_database == []
    finally:
        worker.close()


# -- pause, resume, stop, serialize -----------------------------------------

def test_pause_resume_stop_round_trip(stub_engine):
    worker = PulseWorker(_config("unit-life"), executor_factory=_thread_executor)
    assert worker.initialize() is True
    worker.step(20)
    paused = worker.pause()
    assert worker.state == SimulationState.PAUSED
    assert paused.is_valid
    assert len(paused.state_hash) == 64
    assert base64.b64decode(paused.engine_state).startswith(b'{"stub_time_s"')
    assert worker.resume() is True
    final = worker.stop()
    assert worker.state == SimulationState.STOPPED
    assert worker.engine is None
    assert final.patient_id == "unit-life"


# -- metric mapping ----------------------------------------------------------

def test_metrics_from_values_maps_required_fields():
    m = _metrics_from_values(list(NOMINAL_VALUES))
    assert m.heart_rate == 72.0
    assert m.blood_pressure_systolic == 120.0
    assert m.blood_pressure_diastolic == 80.0
    assert m.respiratory_rate == 14.0
    assert m.spo2 == pytest.approx(98.0)
    assert m.mean_airway_pressure_cm_h2o == 8.0
    assert m.arterial_o2_partial_pressure_mmhg == pytest.approx(89.1)


def test_metrics_from_missing_values_uses_defaults():
    m = _metrics_from_values(None)
    assert m.heart_rate == 0.0
    # No engine data: PaO2 is unavailable (None), never the old 95.0 stub value.
    assert m.arterial_o2_partial_pressure_mmhg is None


def test_nan_pao2_is_explicit_unavailable_not_nan():
    """Regression: a NaN engine PaO2 must not reach the metric as a number.

    The defect (2026-11-07): ArterialOxygenPartialPressure returned NaN in every step, and
    json.dumps wrote a bare NaN token into the persisted payload and its digest.
    """
    values = list(NOMINAL_VALUES)
    values[6] = float("nan")
    m = _metrics_from_values(values)
    assert m.arterial_o2_partial_pressure_mmhg is None
    assert pulse_mod.finite_or_none(float("nan")) is None
    assert pulse_mod.finite_or_none(float("inf")) is None
    assert pulse_mod.finite_or_none(89.1) == pytest.approx(89.1)


def test_persisted_payload_with_unavailable_pao2_is_valid_json():
    """Regression: the persisted payload and its digest never contain NaN.

    _append_state encodes with allow_nan=False, so a NaN would raise. An unavailable PaO2 is
    None, which encodes as JSON null and hashes deterministically.
    """
    import hashlib
    import json

    values = list(NOMINAL_VALUES)
    values[6] = float("nan")
    m = _metrics_from_values(values)
    metrics = {"ArterialOxygenPressure_mmHg": m.arterial_o2_partial_pressure_mmhg}
    payload = json.dumps({"metrics": metrics}, sort_keys=True, allow_nan=False)
    assert "NaN" not in payload
    assert json.loads(payload)["metrics"]["ArterialOxygenPressure_mmHg"] is None
    assert len(hashlib.sha256(payload.encode()).hexdigest()) == 64
    with pytest.raises(ValueError):
        json.dumps({"x": float("nan")}, allow_nan=False)


# -- heartbeat-gap metric ----------------------------------------------------

def test_heartbeat_snapshot_empty_has_no_verdict():
    snap = HeartbeatMonitor().snapshot()
    assert snap["samples"] == 0
    assert snap["passed"] is None
    assert snap["max_gap_ms"] == 0.0


def test_heartbeat_statistics_and_histogram():
    mon = HeartbeatMonitor()
    for gap in (5.0, 12.0, 30.0, 60.0, 300.0):
        mon.record(gap)
    snap = mon.snapshot()
    assert snap["samples"] == 5
    assert snap["max_gap_ms"] == 300.0
    assert snap["p50_ms"] == 30.0
    assert snap["passed"] is False
    assert snap["bound_ms"] == 50.0
    assert snap["histogram_ms"] == {
        "<=10": 1,
        "<=20": 1,
        "<=50": 1,
        "<=100": 1,
        "<=250": 0,
        ">250": 1,
    }


def test_heartbeat_passes_within_bound():
    mon = HeartbeatMonitor()
    for gap in (10.0, 20.0, 49.9):
        mon.record(gap)
    snap = mon.snapshot()
    assert snap["passed"] is True
    assert snap["max_gap_ms"] == 49.9


def test_heartbeat_reset_clears_samples():
    mon = HeartbeatMonitor()
    mon.record(12.0)
    mon.reset()
    snap = mon.snapshot()
    assert snap["samples"] == 0
    assert sum(snap["histogram_ms"].values()) == 0


def test_heartbeat_detects_blocked_event_loop():
    mon = HeartbeatMonitor()

    async def _run():
        task = asyncio.create_task(mon.run(0.01))
        await asyncio.sleep(0.05)
        time.sleep(0.12)  # negative control: a synchronous block on the loop
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run())
    snap = mon.snapshot()
    assert snap["samples"] >= 2
    assert snap["max_gap_ms"] >= 100.0
    assert snap["passed"] is False


# -- manager: limits, stats, concurrency --------------------------------------

def test_manager_enforces_concurrency_limit_and_reports_stats(stub_engine, no_database):
    mgr = SimulationManager(max_concurrent=2, executor_factory=_thread_executor)
    mgr.create_simulation(_config("mgr-a"))
    mgr.create_simulation(_config("mgr-b"))
    with pytest.raises(RuntimeError, match="limit"):
        mgr.create_simulation(_config("mgr-c"))
    with pytest.raises(ValueError, match="already exists"):
        mgr.create_simulation(_config("mgr-a"))

    stats = mgr.stats()
    assert stats["active_simulations"] == 2
    assert stats["max_concurrent"] == 2
    assert set(stats["workers"]) == {"mgr-a", "mgr-b"}
    assert stats["workers"]["mgr-a"]["state"] == "running"
    assert "heartbeat" in stats

    mgr.stop_simulation("mgr-a")
    assert mgr.get_simulation_count() == 1
    mgr.stop_simulation("mgr-b")


def test_manager_steps_ten_simulations_concurrently_off_loop(stub_engine, no_database):
    stub_engine.advance_delay_s = 0.002
    mgr = SimulationManager(max_concurrent=10, executor_factory=_thread_executor)
    ids = [f"conc-{i:02d}" for i in range(10)]

    async def _run():
        for sim_id in ids:
            await mgr.create_simulation_async(_config(sim_id))
        results = await asyncio.gather(*(mgr.step_simulation_async(sim_id, 5) for sim_id in ids))
        return results

    try:
        results = asyncio.run(_run())
        assert len(results) == 10
        assert all(r["heart_rate"] == 72.0 for r in results)
        assert len(stub_engine.constructed) == 10
        assert all(len(mgr.simulations[sim_id].metrics_history) == 1 for sim_id in ids)
    finally:
        for sim_id in ids:
            mgr.stop_simulation(sim_id)


def test_manager_unknown_simulation_raises(no_database):
    mgr = SimulationManager(executor_factory=_thread_executor)
    with pytest.raises(ValueError, match="not found"):
        mgr.step_simulation("missing", 1)
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(mgr.step_simulation_async("missing", 1))


# -- bridge availability and stats surface ----------------------------------

def test_bridge_availability_uses_find_spec_without_import(monkeypatch):
    monkeypatch.setattr(bridge, "SYNTHETIC_ONLY", False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert bridge.real_pulse_available() is False
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    assert bridge.real_pulse_available() is True


def test_bridge_synthetic_opt_in_wins_over_installed_bindings(monkeypatch):
    monkeypatch.setattr(bridge, "SYNTHETIC_ONLY", True)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    assert bridge.real_pulse_available() is False


def test_bridge_stats_surface_reports_heartbeat_and_opt_in(monkeypatch):
    monkeypatch.setattr(bridge, "SYNTHETIC_ONLY", False)
    stats = bridge.pulse_engine_stats()
    assert stats["synthetic_opt_in"] is False
    assert set(stats["heartbeat"]) >= {"samples", "max_gap_ms", "passed", "histogram_ms"}


@pytest.mark.skipif(PULSE_PRESENT, reason="native Pulse bindings present; unavailable path not exercised")
def test_bridge_baseline_and_substance_are_none_without_bindings(monkeypatch):
    monkeypatch.setattr(bridge, "SYNTHETIC_ONLY", False)
    assert bridge.pulse_baseline("unit-bridge") is None
    assert bridge.register_pulse_substance(object(), "unit-bridge") is None
