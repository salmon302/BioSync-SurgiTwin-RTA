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
    the pinned Pulse build is available (task 2.6). This test asserts the SRS 50 ms bound.
  * ``test_harness_self_check_with_stub_engine`` runs the harness with a stub engine for a
    short window. It checks the harness mechanics on every host: the heartbeat samples while
    the loop steps the simulations, and a deliberate 300 ms loop stall is detected, binned,
    and flagged by the bound assertion. It does not assert the 50 ms bound on ambient load;
    the bound is a real-engine measurement. The stub is a test double defined in this file
    only.
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
# Deliberate event-loop stall for the self-check. Sized so the recorded gap lands in
# the ">250" histogram bucket with margin over the 50 ms bound.
SELF_CHECK_STALL_S = 0.30
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


async def _run_stall_detection(manager):
    """Run the heartbeat, block the loop deliberately for SELF_CHECK_STALL_S, return the snapshot."""
    heartbeat_monitor().reset()
    task = manager.start_heartbeat()
    try:
        await asyncio.sleep(0.05)
        time.sleep(SELF_CHECK_STALL_S)  # deliberately block the event loop
        await asyncio.sleep(0.05)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    return heartbeat_monitor().snapshot()


def test_harness_self_check_with_stub_engine(monkeypatch):
    """Harness self-check with a stub engine: metric plumbing and gap detection.

    Two phases:

    * A clean window with the stub simulations stepping. Asserted: the heartbeat
      samples while the loop runs the stepping path, every simulation completes
      steps, and no errors occur. The SRS 50 ms bound is NOT asserted here: this
      phase runs under whatever ambient load the host imposes, and its purpose is
      plumbing, not the requirement measurement.
    * A deliberate 300 ms event-loop stall. Asserted: the harness detects a gap of
      at least the injected stall, bins it into the ">250" histogram bucket, and
      the 50 ms bound assertion fires on the stalled data. This proves the bound
      assertion is wired to the measurement rather than passing vacuously.

    The SRS 50 ms assertion on real load lives exclusively in
    ``test_pq_fr_ms_006_heartbeat_gap_real_engine``.
    """

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
        clean = heartbeat_monitor().snapshot()
        stall = await _run_stall_detection(manager)
        return sim_ids, calls, errors, clean, stall

    try:
        sim_ids, calls, errors, clean, stall = asyncio.run(_main())
        assert errors == []
        assert len(sim_ids) == SIMULATIONS
        assert clean["samples"] > 0, "heartbeat recorded no samples in the clean window"
        assert all(n > 0 for n in calls.values()), "a simulation completed no step calls"

        stall_ms = SELF_CHECK_STALL_S * 1000.0
        assert stall["samples"] > 0, "heartbeat recorded no samples in the stall window"
        assert stall["max_gap_ms"] >= stall_ms, (
            f"deliberate {stall_ms:.0f} ms stall not detected: max gap {stall['max_gap_ms']} ms"
        )
        assert stall["histogram_ms"][">250"] >= 1, (
            f"stall gap not binned into the >250 bucket: {stall['histogram_ms']}"
        )
        with pytest.raises(AssertionError, match="exceeds"):
            _assert_gap_within_bound(stall, {sim_id: 1 for sim_id in sim_ids})
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
