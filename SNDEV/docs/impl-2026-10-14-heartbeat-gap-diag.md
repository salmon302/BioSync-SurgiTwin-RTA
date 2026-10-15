Title: FR-MS-006 heartbeat-gap failure diagnosis and fix
Date: 2026-10-15T00:00:00Z
Author: Seth Nenninger (MiMo-V2.6-Flash Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc (FR-MS-006 gate G2.5 failure, run vtm-600s, 2026-10-14)
Summary: Attributed the FR-MS-006 heartbeat-gap failure to a lazy first-step metrics-hook
import (parent event loop) plus generational GC cost over long runs, and fixed the import on
the production path with an off-loop warm-up.

## Task Reference

Handoff prompt of 2026-10-15: diagnose and, if possible, fix the FR-MS-006 event-loop
heartbeat-gap failure in run `vtm-600s` (stub self-check 73.225 ms, real engine 239.357 ms,
bound 50 ms). Author of `middleware/engine/pulse.py` and `pulse_bridge.py` (commit 5fb26a3).
Documentation files (`sim/SOUP.md`, `docs/procurement-guide.md`, `DEVELOPMENT_PLAN.md`,
`docs/migration-map.md`) are owned by a parallel agent and were not touched.

## Specification Summary

SRS v1.1.0 FR-MS-006 metric: maximum event-loop heartbeat gap at most 50 ms during a
10-minute run with 10 concurrent physiological simulations, measured by
`engine.pulse.HeartbeatMonitor` (raw wall time between wakeups of a 10 ms heartbeat on the
loop that runs the simulations). Gate G2.5.

## Implementation Notes

### Environment artifacts (not committed)

* Helper image `biosync-pulse-test` (FROM `biosync-pulse`, pip-installs
  `middleware/requirements-test.txt` once) for iteration without the per-run pip overhead.
  Decision: kept out of the repo. The procurement guide's run command pip-installs
  requirements inside the container at run time; committing a second Dockerfile would fork
  the documented path for no reuse value. Recorded here as an environment artifact.
* Docker Desktop started on demand; container sees 24 CPUs, cgroup reports no throttling
  (`nr_throttled=0` for all measured windows).

### Diagnostic harness

`SNDEV/scripts/ms006_heartbeat_diag.py` (new): runs the FR-MS-006 window with gc.callbacks
attribution, per-phase timing inside `PulseWorker._record_step`, gap-to-window offsets, and
cgroup/rusage snapshots. Captures land in `SNDEV/logs/diag-<date>-ms006-<run id>.json`.

### Findings (evidence in SNDEV/logs)

1. Stub self-check failure reproduces in-image (max gap 54-85 ms depending on run).
   In every run the single largest gap contains exactly one `PulseWorker._record_step` call
   of 45-48 ms that starts 7.8 ms after the first heartbeat tick (`offset_ms` ~0: it is the
   first heartbeat gap of the window). Phase timing: metrics parse 0.015 ms, hook phase not
   yet imported; residual 48.4 ms = the lazy
   `from api.middleware.response_time import record_pulse_step` inside `_record_step`.
   Cold import of `api.middleware.response_time` measured in the image: 111.7 ms.
2. Controlled experiment: same stub window with the import pre-warmed off-loop
   (`--warm-import`) drops the max gap from 57.3 ms to 11.3 ms and the worst `_record_step`
   from 48.4 ms to 0.65 ms. Cause of the stub failure confirmed.
3. Container CPU throttling ruled out: 24 CPUs visible, `nr_throttled=0`, no CFS quota;
   involuntary context switches during windows are small (nivcsw delta 109 over 30 s).
4. Real engine 30 s diagnostic: max gap 49.2 ms, single gap, same first-step import shape
   (39.8 ms `_record_step` inside it); no gen-2 GC pass inside the window at 30 s.
5. Generational GC in the parent: gen-0 passes ~0.1 ms, gen-1 ~0.5 ms, one gen-2 pass of
   23.7 ms observed in the 30 s stub window (attributed to a 28.5 ms gap). `metrics_history`
   grows without bound (one `SimulationMetrics` per step call; ~62k entries per simulation
   by the end of a 600 s run), which makes gen-2 pauses grow with run length.
6. Real engine 600 s baseline diagnostic (`real-600s-baseline`): 56,052 samples,
   max gap 224.089 ms, 9 gaps above 20 ms, every one attributed with zero unexplained
   outliers:
   * 8 gaps are gen-2 GC passes growing linearly with `metrics_history`: 37.4, 67.4, 77.9,
     91.9, 121.4, 148.7, 176.2, 219.1 ms at window offsets 44, 95, 150, 203, 266, 344, 439,
     555 s (histogram `<=20`: 56043, `<=50`: 1, `<=100`: 3, `<=250`: 5). This reproduces
     the user's `vtm-600s` failure shape (239.357 ms, 6 samples above 20 ms).
   * 1 gap (59.740 ms) is the lazy metrics-hook import on the first heartbeat tick
     (offset 0.124 ms; the 49.558 ms `_record_step` inside it has a 49.532 ms residual,
     i.e. the import).
   * Container CPU throttling and scheduler pressure remain ruled out: `nr_throttled=0`,
     nivcsw delta 1934 over 600 s (3.2/s), PSI files were empty in this container
     (not mounted).

### Changes

1. `middleware/engine/pulse.py`
   * Added `_warm_metrics_hook()`: imports `api.middleware.response_time` once, with the
     same `(ImportError, AttributeError)` guard the per-step path already uses. Called
     from `PulseWorker.__init__`, which runs in the parent before any measurement window
     starts, and from `SimulationManager.__init__` before the GC freeze so the warmed
     modules are frozen with the rest. Per-step cost stays a `sys.modules` lookup; the
     lazy import in `_record_step` remains as the fallback.
   * Added `METRICS_HISTORY_MAX = 2000`: `metrics_history` is now a bounded deque per
     simulation instead of an unbounded list. All consumers read only `[-1]`
     (`serialize_state`, `pulse_bridge.pulse_baseline`) or a small length in tests
     (`test_pulse_worker.py` asserts 3 and 1). This caps the long-lived objects that
     generation-2 GC must scan, which is what produced the 37-219 ms loop-visible
     pauses. The same unbounded-list-to-bounded-window adaptation is already recorded
     for `api/middleware/response_time.py` in this repository.
   * Added `_freeze_gc_once()`, called from `SimulationManager.__init__`: `gc.collect()`
     then `gc.freeze()`, once per process. Pre-existing objects (module graphs,
     codecaches, the warmed metrics hook) are untracked so gen-2 passes scan only the
     bounded runtime set. Process-wide side effect: objects that exist at the first
     manager construction are never collected afterward; they are import-time state that
     lives for the process anyway. Later managers are not frozen again, so their worker
     objects stay collectable. Worker processes are not frozen: their Python heap is
     small and worker-side GC never blocks the measured loop.
2. `vv/tests/PQ/test_pq_fr_ms_006_heartbeat_gap.py`
   * Stub self-check redesigned per the diagnosis: phase 1 asserts plumbing only (heartbeat
     samples while stepping, all simulations complete steps, no errors); phase 2 injects a
     deliberate 300 ms loop stall and asserts it is detected (max gap >= stall), binned into
     the `>250` bucket, and that the 50 ms bound assertion raises on the stalled data. The
     SRS 50 ms assertion remains exclusively in the real-engine test, unchanged. Disclosed
     in the test docstring and module docstring.

### Verification

| Gate | Command (in image, repo at /repo) | Result |
| --- | --- | --- |
| Stub self-check (redesigned) | `pytest vv/tests/PQ/test_pq_fr_ms_006_heartbeat_gap.py -k self_check` | PASS (1 passed) |
| Pulse worker unit suite | `pytest middleware/tests/test_pulse_worker.py` | PASS (26 passed, 2 skipped) |
| Ruff on changed files | `ruff check middleware/engine/pulse.py vv/tests/PQ/... ms006_heartbeat_diag.py` | PASS (all checks passed) |
| Stub diagnostic, cold vs warm import | `ms006_heartbeat_diag.py --engine stub --duration 3` | PASS: 57.292 ms -> 11.257 ms max gap |
| Real 600 s diagnostic baseline | `--engine real --duration 600 --run-id real-600s-baseline` | FAIL by design (baseline): max 224.089 ms, 9 gaps fully attributed (8 gen-2, 1 import) |
| Real 90 s diagnostic with fixes | `--engine real --duration 90 --run-id real-90s-fixed` | PASS: max gap 16.179 ms, no gap above 20 ms, `_record_step` max 0.459 ms, history capped at 2000, no gen-2 pass in window (gen-0 57 passes/8.9 ms total, gen-1 5 passes/3.9 ms total) |
| Real 600 s SRS run after fix | pytest PQ file, `BIOSYNC_PQ_MS006_RUN_ID=heartbeat-diag-1` | PASS (2 passed in 861.76 s): max gap 16.778 ms against the 50 ms bound, 55,846 samples all in the `<=20` bucket (zero samples above 20 ms), p50 10.652 ms, p95 11.652 ms, p99 12.418 ms, no step errors, 452,460 step calls over 10 simulations. Capture: `SNDEV/logs/pq-2026-10-15-fr-ms-006-heartbeat-diag-1.json` |
| Engine suites (IQ-4, OQ-16, fail-closed OQ) | `pytest vv/tests/IQ/test_iq4... vv/tests/OQ/test_oq16... vv/tests/OQ/test_oq_fr_ms_006...` | PASS (11 passed, 1 skipped, same as the pre-change baseline) |
| Middleware suite | `pytest middleware/tests/` | PASS (183 passed, 61 skipped) |

### Outcome

Gate G2.5 heartbeat clause: PASS on the rerun. The failing `vtm-600s` shape (239.357 ms
max, 6 samples above 20 ms) is replaced by 16.778 ms max with zero samples above 20 ms in
`heartbeat-diag-1`, in the same image with the same PYTHONPATH, 10 concurrent simulations,
600 s, 10 ms interval. The stub self-check now asserts harness mechanics deterministically
(300 ms injected stall detected, binned, and caught by the bound assertion) and no longer
asserts the 50 ms bound on ambient load; the real-engine test keeps the SRS assertion
unchanged.