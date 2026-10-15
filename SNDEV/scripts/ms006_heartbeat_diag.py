# SPDX-License-Identifier: MIT
# Title: FR-MS-006 heartbeat-gap diagnostic harness
# Date: 2026-10-14T00:00:00Z
# Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
# Contribution Type: Implementation
# Ticket/Context: ad-hoc (FR-MS-006 heartbeat gap failure, run vtm-600s)
# Summary: Runs the FR-MS-006 window with GC, parent step-processing, and cgroup instrumentation to attribute heartbeat gaps.
"""
Diagnostic run for the FR-MS-006 heartbeat-gap measurement. Not a qualification test.

Usage (inside the test image, repo mounted at /repo):
  python SNDEV/scripts/ms006_heartbeat_diag.py --engine stub --duration 3 --run-id stub-3s
  python SNDEV/scripts/ms006_heartbeat_diag.py --engine real --duration 600 --run-id heartbeat-diag-1

Mitigation switches (test-side measurement only, recorded in the output):
  --freeze      gc.collect() then gc.freeze() after the simulations are initialized
  --gc-off      gc.disable() for the measured window (attribution experiment, not a fix)

Attribution switches:
  --warm-import pre-imports api.middleware.response_time (the lazy import inside
                PulseWorker._record_step) before the window and times it. With this flag the
                per-call phases (metrics parse, metrics hook, residual) are timed separately.

The heartbeat uses the same definition as engine.pulse.HeartbeatMonitor (raw wall time between
wakeups of a 10 ms sleep). Gaps above GAP_LOG_MS are logged with the GC passes and parent step
completions that fall inside them.
"""
import argparse
import asyncio
import datetime
import gc
import json
import os
import pathlib
import platform
import resource
import sys
import time
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://localhost:5432/surgitwin_test")
os.environ.setdefault("DB_SSLMODE", "prefer")

import engine.pulse as pulse_mod  # noqa: E402
from engine.pulse import HEARTBEAT_BOUND_MS, PatientConfig, SimulationManager, heartbeat_monitor  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LOGS_DIR = REPO_ROOT / "SNDEV" / "logs"
SIMULATIONS = 10
STEPS_PER_CALL = 10
INTERVAL_S = 0.010
GAP_LOG_MS = 20.0
STEP_LOG_MS = 2.0


def _patient(index):
    return PatientConfig(
        patient_id=f"ms006-{index:02d}", age=40 + index, weight_kg=65.0 + index,
        height_cm=165.0 + index, sex="female" if index % 2 else "male",
    )


def _cgroup_cpu():
    try:
        out = {}
        with open("/sys/fs/cgroup/cpu.stat", encoding="utf-8") as fh:
            for line in fh:
                key, value = line.split()
                out[key] = int(value)
        return out
    except OSError:
        return None


def _rusage():
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return {"nivcsw": ru.ru_nivcsw, "nvcsw": ru.ru_nvcsw, "utime_s": ru.ru_utime, "stime_s": ru.ru_stime}


def _psi():
    """CPU/memory/io pressure-stall averages inside the container (context for outliers)."""
    out = {}
    for name in ("cpu", "memory", "io"):
        try:
            with open(f"/proc/pressure/{name}", encoding="utf-8") as fh:
                out[name] = fh.read().strip()
        except OSError:
            out[name] = None
    return out


class Probe:
    def __init__(self):
        self.active = False
        self.gc_events = []
        self.gc_starts = []
        self._gc_t0 = 0.0
        self.step_intervals = []
        self.step_total = 0
        self.step_proc_total_ms = 0.0
        self.gaps = []
        self.parent_step_max_ms = 0.0
        # Phase timing for _record_step (metrics parse / metrics hook / residual).
        self.metrics_total_ms = 0.0
        self.metrics_max_ms = 0.0
        self.hook_total_ms = 0.0
        self.hook_max_ms = 0.0
        self.slow_calls = []  # (t0, total_ms, metrics_ms, hook_ms) for the slowest calls
        self._cur_metrics_ms = 0.0
        self._cur_hook_ms = 0.0

    def gc_callback(self, phase, info):
        if not self.active:
            return
        if phase == "start":
            self._gc_t0 = time.perf_counter()
        else:
            t1 = time.perf_counter()
            self.gc_events.append((self._gc_t0, t1, info["generation"], info["collected"]))

    def reset(self):
        self.gc_events.clear()
        self.step_intervals.clear()
        self.gaps.clear()
        self.step_total = 0
        self.step_proc_total_ms = 0.0
        self.parent_step_max_ms = 0.0
        self.metrics_total_ms = 0.0
        self.metrics_max_ms = 0.0
        self.hook_total_ms = 0.0
        self.hook_max_ms = 0.0
        self.slow_calls.clear()
        self._cur_metrics_ms = 0.0
        self._cur_hook_ms = 0.0


PROBE = Probe()

# Window start (perf_counter) so gap start_s can be converted to an offset.
WINDOW_START = {"t": 0.0}
# Original (unpatched) api.middleware.response_time.record_pulse_step, bound when --warm-import.
HOOK_ORIGINAL = [None]
SLOW_CALL_MIN_MS = 1.0
SLOW_CALL_KEEP = 40


def _install_step_probe(warm_hook: bool):
    original_record = pulse_mod.PulseWorker._record_step
    original_metrics = pulse_mod._metrics_from_values
    window_start = WINDOW_START["t"]

    def timed_metrics(values):
        t0 = time.perf_counter()
        out = original_metrics(values)
        if PROBE.active:
            PROBE._cur_metrics_ms += (time.perf_counter() - t0) * 1000.0
        return out

    def timed_hook(latency_ms):
        t0 = time.perf_counter()
        HOOK_ORIGINAL[0](latency_ms)
        if PROBE.active:
            PROBE._cur_hook_ms += (time.perf_counter() - t0) * 1000.0

    def timed(self, reply, n_steps):
        PROBE._cur_metrics_ms = 0.0
        PROBE._cur_hook_ms = 0.0
        t0 = time.perf_counter()
        out = original_record(self, reply, n_steps)
        t1 = time.perf_counter()
        if PROBE.active:
            proc_ms = (t1 - t0) * 1000.0
            PROBE.step_total += 1
            PROBE.step_proc_total_ms += proc_ms
            if proc_ms > PROBE.parent_step_max_ms:
                PROBE.parent_step_max_ms = proc_ms
            if proc_ms >= STEP_LOG_MS:
                PROBE.step_intervals.append((t0, t1))
            PROBE.metrics_total_ms += PROBE._cur_metrics_ms
            PROBE.metrics_max_ms = max(PROBE.metrics_max_ms, PROBE._cur_metrics_ms)
            PROBE.hook_total_ms += PROBE._cur_hook_ms
            PROBE.hook_max_ms = max(PROBE.hook_max_ms, PROBE._cur_hook_ms)
            if proc_ms >= SLOW_CALL_MIN_MS:
                PROBE.slow_calls.append(
                    (round((t0 - window_start) * 1000.0, 3), round(proc_ms, 3),
                     round(PROBE._cur_metrics_ms, 3), round(PROBE._cur_hook_ms, 3))
                )
                if len(PROBE.slow_calls) > SLOW_CALL_KEEP:
                    PROBE.slow_calls.sort(key=lambda c: -c[1])
                    del PROBE.slow_calls[SLOW_CALL_KEEP:]
        return out

    pulse_mod._metrics_from_values = timed_metrics
    pulse_mod.PulseWorker._record_step = timed
    if warm_hook:
        import api.middleware.response_time as response_time_mod

        HOOK_ORIGINAL[0] = response_time_mod.record_pulse_step
        response_time_mod.record_pulse_step = timed_hook


async def _heartbeat(end_time):
    monitor = heartbeat_monitor()
    last = time.perf_counter()
    while time.perf_counter() < end_time:
        await asyncio.sleep(INTERVAL_S)
        now = time.perf_counter()
        gap_ms = (now - last) * 1000.0
        monitor.record(gap_ms)
        if gap_ms > GAP_LOG_MS:
            PROBE.gaps.append((last, now, gap_ms))
        last = now


async def _drive(manager, sim_ids, end):
    errors = []
    calls = {sim_id: 0 for sim_id in sim_ids}

    async def _one(sim_id):
        while time.perf_counter() < end:
            try:
                await manager.step_simulation_async(sim_id, STEPS_PER_CALL)
                calls[sim_id] += 1
            except Exception as exc:
                errors.append(f"{sim_id}: {type(exc).__name__}: {exc}")
                return

    await asyncio.gather(*(_one(s) for s in sim_ids))
    return calls, errors


def _attribute(gap_start, gap_end):
    """Return GC passes and parent step completions that overlap one gap."""
    gcs = [
        {"gen": g, "ms": round((t1 - t0) * 1000.0, 3), "collected": c,
         "at_ms": round((t0 - gap_start) * 1000.0, 3)}
        for (t0, t1, g, c) in PROBE.gc_events
        if t1 >= gap_start and t0 <= gap_end
    ]
    steps = [
        {"proc_ms": round((t1 - t0) * 1000.0, 3), "at_ms": round((t0 - gap_start) * 1000.0, 3)}
        for (t0, t1) in PROBE.step_intervals
        if t1 >= gap_start and t0 <= gap_end
    ]
    return gcs, steps


def _gap_records():
    records = []
    for gap_start, gap_end, gap_ms in PROBE.gaps:
        gcs, steps = _attribute(gap_start, gap_end)
        records.append({
            "gap_ms": round(gap_ms, 3),
            "start_s": round(gap_start, 6),
            "offset_ms": round((gap_start - WINDOW_START["t"]) * 1000.0, 3) if WINDOW_START["t"] else None,
            "gc_in_gap": gcs,
            "parent_steps_over_threshold_in_gap": steps,
        })
    records.sort(key=lambda r: r["gap_ms"], reverse=True)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["stub", "real"], required=True)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--gc-off", action="store_true")
    parser.add_argument("--warm-import", action="store_true",
                        help="pre-import api.middleware.response_time off-loop and time it")
    args = parser.parse_args()

    warm_import_ms = None
    if args.warm_import:
        t0 = time.perf_counter()
        import api.middleware.response_time  # noqa: F401
        warm_import_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    if args.engine == "stub":
        class _SelfCheckStub:
            def __init__(self, patient, data_root):
                pass

            def advance(self, time_step_s):
                time.sleep(0.0005)

            def pull(self):
                return [72.0, 120.0, 80.0, 14.0, 0.98, 8.0, 95.0]

            def serialize(self):
                return "{}"

        pulse_mod._ENGINE_FACTORY = _SelfCheckStub
        pulse_mod.DB_AVAILABLE = False
        manager = SimulationManager(
            max_concurrent=SIMULATIONS, executor_factory=lambda: ThreadPoolExecutor(max_workers=1),
        )
    else:
        pulse_mod.DB_AVAILABLE = False
        manager = SimulationManager(max_concurrent=SIMULATIONS)

    _install_step_probe(args.warm_import)
    gc.callbacks.append(PROBE.gc_callback)
    cpu_before_all = _cgroup_cpu()
    ru_before_all = _rusage()

    async def _main():
        sim_ids = []
        for i in range(SIMULATIONS):
            sim_ids.append(await manager.create_simulation_async(_patient(i)))
        if args.freeze:
            gc.collect()
            gc.freeze()
        if args.gc_off:
            gc.disable()
        heartbeat_monitor().reset()
        PROBE.reset()
        PROBE.active = True
        cpu_before = _cgroup_cpu()
        ru_before = _rusage()
        gc_counts_before = gc.get_count()
        gc_threshold = gc.get_threshold()
        psi_before = _psi()
        wall_start = time.perf_counter()
        WINDOW_START["t"] = wall_start
        end = wall_start + args.duration
        hb_task = asyncio.ensure_future(_heartbeat(end))
        calls, errors = await _drive(manager, sim_ids, end)
        await hb_task
        wall_s = time.perf_counter() - wall_start
        PROBE.active = False
        cpu_after = _cgroup_cpu()
        ru_after = _rusage()
        gc_counts_after = gc.get_count()
        psi_after = _psi()
        if args.gc_off:
            gc.enable()
        return (sim_ids, calls, errors, wall_s, cpu_before, cpu_after, ru_before, ru_after,
                gc_counts_before, gc_counts_after, gc_threshold, psi_before, psi_after)

    started = time.time()
    try:
        (sim_ids, calls, errors, wall_s, cpu_before, cpu_after,
         ru_before, ru_after, gc_counts_before, gc_counts_after,
         gc_threshold, psi_before, psi_after) = asyncio.run(_main())
        snapshot = heartbeat_monitor().snapshot()
        gap_records = _gap_records()
        gc_total = {}
        for (_t0, _t1, g, _c) in PROBE.gc_events:
            gc_total.setdefault(str(g), {"passes": 0, "ms": 0.0})
            gc_total[str(g)]["passes"] += 1
            gc_total[str(g)]["ms"] += (_t1 - _t0) * 1000.0
        for v in gc_total.values():
            v["ms"] = round(v["ms"], 3)
        history_len = {sid: len(manager.simulations[sid].metrics_history) for sid in sim_ids if sid in manager.simulations}
        slow_calls = sorted(PROBE.slow_calls, key=lambda c: -c[1])[:SLOW_CALL_KEEP]
        residual_max = round(
            max((c[1] - c[2] - c[3] for c in PROBE.slow_calls), default=0.0), 3)
        record = {
            "requirement": "FR-MS-006",
            "diagnostic": True,
            "engine": args.engine,
            "run_id": args.run_id,
            "started_utc": datetime.datetime.fromtimestamp(started, datetime.timezone.utc).isoformat(),
            "window_s": args.duration,
            "measured_wall_s": round(wall_s, 3),
            "window_start_perf": WINDOW_START["t"],
            "mitigations": {"gc_freeze_after_init": args.freeze, "gc_disabled_in_window": args.gc_off},
            "warm_import_ms": warm_import_ms,
            "cpu_count_os": os.cpu_count(),
            "cpu_count_affinity": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "cgroup_cpu_stat_before_all": cpu_before_all,
            "cgroup_cpu_stat_window_before": cpu_before,
            "cgroup_cpu_stat_window_after": cpu_after,
            "rusage_before_all": ru_before_all,
            "rusage_window_before": ru_before,
            "rusage_window_after": ru_after,
            "rusage_after_all": _rusage(),
            "step_calls_per_simulation": calls,
            "step_calls_total": sum(calls.values()),
            "parent_step_processing": {
                "completions": PROBE.step_total,
                "mean_ms": round(PROBE.step_proc_total_ms / max(PROBE.step_total, 1), 4),
                "max_ms": round(PROBE.parent_step_max_ms, 3),
                "metrics_phase_total_ms": round(PROBE.metrics_total_ms, 3),
                "metrics_phase_max_ms": round(PROBE.metrics_max_ms, 3),
                "hook_phase_total_ms": round(PROBE.hook_total_ms, 3),
                "hook_phase_max_ms": round(PROBE.hook_max_ms, 3),
                "residual_max_ms_slowest_calls": residual_max,
                "slow_calls_over_1ms": [dict(zip(
                    ("offset_ms", "total_ms", "metrics_ms", "hook_ms"), c)) for c in slow_calls],
            },
            "gc_threshold": gc_threshold,
            "gc_counts_window_before": gc_counts_before,
            "gc_counts_window_after": gc_counts_after,
            "psi_window_before": psi_before,
            "psi_window_after": psi_after,
            "gc_passes_in_window": gc_total,
            "gc_count_at_end": gc.get_count(),
            "metrics_history_len_at_end": history_len,
            "errors": errors[:20],
            "heartbeat": snapshot,
            "gaps_over_threshold_ms": GAP_LOG_MS,
            "gaps_over_threshold": gap_records[:200],
            "gaps_over_threshold_count": len(gap_records),
            "host": {"platform": platform.platform(), "python": sys.version.split()[0]},
        }
    finally:
        for sim_id in list(manager.simulations):
            manager.stop_simulation(sim_id)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    path = LOGS_DIR / f"diag-{stamp}-ms006-{args.run_id}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

    hist = snapshot["histogram_ms"]
    print(f"run={args.run_id} engine={args.engine} window_s={args.duration} samples={snapshot['samples']}")
    print(f"max_gap_ms={snapshot['max_gap_ms']} p99_ms={snapshot['p99_ms']} bound_ms={HEARTBEAT_BOUND_MS}")
    print(f"histogram_ms={hist}")
    print(f"gaps_over_{GAP_LOG_MS:g}ms={len(gap_records)} gc_in_window={gc_total}")
    print(f"parent_step_max_ms={record['parent_step_processing']['max_ms']} "
          f"nivcsw_delta={ru_after['nivcsw'] - ru_before['nivcsw']}")
    print(f"capture={path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
