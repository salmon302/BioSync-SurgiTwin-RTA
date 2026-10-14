# SPDX-License-Identifier: MIT
"""
PQ: FR-MS-006 event-loop heartbeat gap under concurrent Pulse simulations (VAL-007, gate G2.5, task 2.5)

Acceptance (VTM row FR-MS-006, proposed): the maximum event-loop heartbeat gap is at most 50 ms
during a 10-minute run with 10 concurrent physiological simulations. The measurement definition
is in ``engine/pulse.py`` (``HeartbeatMonitor``): the raw wall time between consecutive wakeups
of a 10 ms heartbeat coroutine on the event loop that runs the simulations.

Run settings (environment variables, read at import):
  BIOSYNC_PQ_MS006_DURATION_S  window length in seconds. Default 60 (smoke run). The VTM run uses 600.
  BIOSYNC_PQ_MS006_RUN_ID     label in the capture file name. Default "smoke".

Captures: when the real-engine test runs, the result is written to
``SNDEV/logs/pq-<UTC date>-fr-ms-006-<run id>.json`` (the logs directory is gitignored).

Skips and verification scope:
  * ``test_pq_fr_ms_006_heartbeat_gap_real_engine`` requires the native Pulse bindings. It is
    skipped on hosts without the ``pulse`` package, and that skip is the recorded status until
    the pinned Pulse build is available (task 2.6).
  * ``test_harness_self_check_with_stub_engine`` runs the same harness with a stub engine for
    a short window. It checks the harness and the metric plumbing on every host. The stub is a
    test double defined in this file only.
"""

import asyncio
import datetime
import importlib.util
import json
import os
import pathlib
import platform
import sys
import time

import pytest

import engine.pulse as pulse_mod
from engine.pulse import (
    HEARTBEAT_BOUND_MS,
    PatientConfig,
    SimulationManager,
    heartbeat_monitor,
)
from concurrent.futures import ThreadPoolExecutor

pytestmark = pytest.mark.pq

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
LOGS_DIR = REPO_ROOT / "SNDEV" / "logs"

SIMULATIONS = 10
STEPS_PER_CALL = 10
DEFAULT_DURATION_S = 60.0
SELF_CHECK_DURATION_S = 3.0
PULSE_PRESENT = importlib.util.find_spec("pulse") is not None

DURATION_S = float(os.environ.get("BIOSYNC_PQ_MS006_DURATION_S", DEFAULT_DURATION_S))
RUN_ID = os.environ.get("BIOSYNC_PQ_MS006_RUN_ID", "smoke")


def _patient(index: int) -> PatientConfig:
    return PatientConfig(
        patient_id=f"ms006-{index:02d}",
        age=40 + index,
        weight_kg=65.0 + index,
        height_cm=165.0 + index,
        sex="female" if index % 2 else "male",
    )


async def _drive(manager, sim_ids, duration_s):
    """Step every simulation in a loop for duration_s while the heartbeat samples the loop."""
    errors = []
    calls = {sim_id: 0 for sim_id in sim_ids}
    end = time.perf_counter() + duration_s

    async def _one(sim_id):
        while time.perf_counter() < end:
            try:
                await manager.step_simulation_async(sim_id, STEPS_PER_CALL)
                calls[sim_id] += 1
            except Exception as exc:  # recorded and counted as a failure
                errors.append(f"{sim_id}: {type(exc).__name__}: {exc}")
                return

    await asyncio.gather(*(_one(sim_id) for sim_id in sim_ids))
    return calls, errors


async def _run_window(manager, configs, duration_s):
    sim_ids = []
    for cfg in configs:
        sim_ids.append(await manager.create_simulation_async(cfg))
    heartbeat_monitor().reset()
    task = manager.start_heartbeat()
    try:
        calls, errors = await _drive(manager, sim_ids, duration_s)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return sim_ids, calls, errors


def _disable_persistence(monkeypatch):
    # Persistence is off so the window isolates the stepping path. Database writes run off the
    # loop (asyncio.to_thread) and are not part of this measurement.
    monkeypatch.setattr(pulse_mod, "DB_AVAILABLE", False)


def _write_capture(record):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    path = LOGS_DIR / f"pq-{stamp}-fr-ms-006-{RUN_ID}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _assert_gap_within_bound(snapshot, calls):
    assert snapshot["samples"] > 0, "heartbeat recorded no samples"
    assert snapshot["max_gap_ms"] <= HEARTBEAT_BOUND_MS, (
        f"maximum heartbeat gap {snapshot['max_gap_ms']} ms exceeds {HEARTBEAT_BOUND_MS} ms"
    )
    assert all(n > 0 for n in calls.values()), "a simulation completed no step calls"


def test_harness_self_check_with_stub_engine(monkeypatch):
    """Harness and metric plumbing with a stub engine (test double, this file only)."""

    class _SelfCheckStub:
        def __init__(self, patient, data_root):
            pass

        def advance(self, time_step_s):
            time.sleep(0.0005)

        def pull(self):
            return [72.0, 120.0, 80.0, 14.0, 0.98, 8.0, 95.0]

        def serialize(self):
            return "{}"

    _disable_persistence(monkeypatch)
    monkeypatch.setattr(pulse_mod, "_ENGINE_FACTORY", _SelfCheckStub)
    manager = SimulationManager(
        max_concurrent=SIMULATIONS,
        executor_factory=lambda: ThreadPoolExecutor(max_workers=1),
    )
    configs = [_patient(i) for i in range(SIMULATIONS)]

    async def _main():
        sim_ids, calls, errors = await _run_window(manager, configs, SELF_CHECK_DURATION_S)
        return sim_ids, calls, errors

    try:
        sim_ids, calls, errors = asyncio.run(_main())
        assert errors == []
        _assert_gap_within_bound(heartbeat_monitor().snapshot(), calls)
        assert len(sim_ids) == SIMULATIONS
    finally:
        for sim_id in list(manager.simulations):
            manager.stop_simulation(sim_id)


@pytest.mark.skipif(
    not PULSE_PRESENT,
    reason=(
        "native Pulse bindings not importable on this host; the FR-MS-006 real-engine heartbeat "
        "run is pending the pinned Pulse build (DEVELOPMENT_PLAN.md task 2.6)"
    ),
)
def test_pq_fr_ms_006_heartbeat_gap_real_engine(monkeypatch):
    _disable_persistence(monkeypatch)
    manager = SimulationManager(max_concurrent=SIMULATIONS)
    configs = [_patient(i) for i in range(SIMULATIONS)]

    async def _main():
        return await _run_window(manager, configs, DURATION_S)

    started = time.time()
    try:
        sim_ids, calls, errors = asyncio.run(_main())
        snapshot = heartbeat_monitor().snapshot()
        record = {
            "requirement": "FR-MS-006",
            "run_id": RUN_ID,
            "started_utc": datetime.datetime.fromtimestamp(started, datetime.timezone.utc).isoformat(),
            "window_s": DURATION_S,
            "simulations": SIMULATIONS,
            "steps_per_call": STEPS_PER_CALL,
            "time_step_s": pulse_mod.PulseWorker.TIME_STEP,
            "step_calls_per_simulation": calls,
            "errors": errors,
            "heartbeat": snapshot,
            "bound_ms": HEARTBEAT_BOUND_MS,
            "host": {"platform": platform.platform(), "python": sys.version.split()[0]},
        }
        record["capture"] = str(_write_capture(record).relative_to(REPO_ROOT))
        assert errors == []
        _assert_gap_within_bound(snapshot, calls)
    finally:
        for sim_id in list(manager.simulations):
            manager.stop_simulation(sim_id)
