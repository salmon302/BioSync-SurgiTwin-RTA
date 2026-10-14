Title: Phase 2 kickoff: tooling preflight, SOUP inventory, Pulse worker delegation (task 2.5), and FR-MS-006 verification surface (task 2.6)
Date: 2026-10-14T20:51:05Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 2 kickoff (task 2.5, task 2.6 surface, VAL-012 SOUP inventory)
Summary: Opens Phase 2 with a tooling preflight and the SOUP inventory in sim/SOUP.md, and implements the long-lived Pulse worker process model with an event-loop heartbeat-gap metric and the FR-MS-006 harness. The real-engine run is pending the pinned Pulse build.

## Task Reference

* DEVELOPMENT_PLAN.md Phase 2, task 2.5 (Pulse step delegation: one long-lived worker per engine instance, step kept off the event loop, heartbeat-gap metric) and task 2.6 (IQ-4, OQ-16, and the FR-MS-006 verification surface).
* DEVELOPMENT_PLAN.md Section 6.2 VAL-012 (SOUP inventory, version pinning, evaluation, anomaly response) and VAL-007 (the 50 ms heartbeat-gap observable proxy for "zero main-loop blocking").
* DEVELOPMENT_PLAN.md gates G2.5 (Pulse worker) and G2.1, G2.2, G2.3, G2.4, G2.6 (not in this increment, listed for the Phase 2 exit record).
* VTM row FR-MS-006 in `vv/traceability/vtm.md`: IQ-4, OQ-16, and the fail-closed OQ pass on the pinned Pulse build, and the maximum event-loop heartbeat gap is at most 50 ms during a 10-minute run with 10 concurrent physiological simulations (proposed).
* Scope approved by the user on 2026-10-14.

## Specification Summary

* FR-MS-006 (SRS.md Section 3): the middleware integrates the Kitware Pulse Physiology Engine and runs concurrent patient simulations without blocking the telemetry event loop. The SRS names a `ProcessPoolExecutor` as the mechanism.
* The native Pulse engine object cannot be pickled. A process pool therefore cannot pass it as an argument. The design rule (DEVELOPMENT_PLAN.md Section 3.3) is one long-lived worker per engine instance, with the engine created inside the worker.
* Open debt before this increment: `SimulationManager.step_simulation` was synchronous and the `ProcessPoolExecutor` scaffold in `middleware/engine/pulse.py` was not on the step path (docs/migration-map.md, open item "ProcessPoolExecutor delegation for Pulse steps").
* Out of scope for this record: tasks 2.1, 2.2, 2.3, 2.4, 2.7, 2.8, and gates G2.1 through G2.4 and G2.6. Those tasks are blocked by the preflight results below.

## Implementation Notes

### Tooling preflight (host state observed 2026-10-14)

Host: AMD Ryzen 9 3900X (12 cores, 24 logical processors), 48 GB RAM, Windows (build 10.0.22621). Shell: PowerShell. Repository root: `I:\Documents\GitHub\BioSync\BioSync-SurgiTwin-RTA` (git, branch with commits through `39931bd`).

| Tool | Host state | Phase 2 tasks blocked | Precondition |
|:-----|:-----------|:----------------------|:-------------|
| SOFA (framework and SofaPython3) | Not installed. No `Sofa*` executable on the search path or under `C:\Program Files`. No `Sofa` Python module in `.venv-qual311`. The PyPI name `sofa` (0.7.6) is an unrelated package and was not installed. | 2.2 (scene and implicit solver), 2.3 (contact, cutting), 2.7 (SOFA FMU) | Source or binary build of one tagged SOFA release, pinned in `sim/sofa/`. Large build, not attempted in this increment. |
| 3D Slicer | Not installed. `Slicer` is not on the search path. | 2.1 (DICOM segmentation) and 2.4 (SlicerROS2 bridge) | Install of one tagged Slicer release, pinned in `sim/bridge/`. |
| SlicerROS2 | Not installed. | 2.4 | Build or install against the pinned Slicer and ROS 2 versions. SlicerROS2 license is (confirm). |
| ROS 2 | Not installed. `ros2` is not on the search path. | 2.4, 2.8 (FMI-LS-BUS over ROS 2 transport) | One ROS 2 distribution, pinned with its matching Fast DDS version. |
| Fast DDS | Not installed. No eProsima directory under `C:\Program Files`. | 2.4, 2.8 | Pinned release that matches the ROS 2 distribution. |
| Kitware Pulse Python bindings (`pulse`, `Pulse`) | Not importable. `python -c "import pulse"` in `.venv-qual311` fails with `ModuleNotFoundError: No module named 'pulse'`. | 2.5 real-engine run, 2.6 (IQ-4 and OQ-16 on the pinned build) | Build from the `.pulse/` source prerequisite via `middleware/Dockerfile.pulse`, or build from the pinned tag `REL_4_3_2` in the container. |
| `.pulse/` source tree | Absent at the repository root. It is gitignored and is an external prerequisite. | 2.6 (engine source provenance record) | Vendor the engine source at the pinned commit or use `VARIANT=git` in the Dockerfile. |
| FMI master and FMI tooling | None selected. No FMI library or master tool is present on the host. | 2.7 (FMU packaging), 2.8 (master, clocks, scheduled variables) | Select and pin an FMI 3.0 toolchain. DEVELOPMENT_PLAN.md Section 2 states the master is built in Phase 2. |
| MSVC | Visual Studio 2022 Community, `cl.exe` from toolset 14.44.35207 (compiler 19.44). | Not blocking. C++ safety cores (`rta/`) build here. | None. |
| CMake | 3.31.6 at `C:\Program Files\CMake\bin\cmake.exe`. | Not blocking. | None. |
| Docker | Client and server 25.0.3. The `biosync-surgitwin-rta-postgres-1` container (`postgres:15`) is healthy. | Not blocking for Python tests. Needed for the Pulse image build (task 2.6). | Pulse source prerequisite (above). |
| Python venvs | `.venv-qual311` is Python 3.11.9. `.venv-pq-load` is Python 3.11.9 with Locust 2.46.7. The system Python is 3.14.3 at `C:\Python314`. | Not blocking. | None. |
| Ruff and mypy | Not present in `.venv-qual311` before this increment. Installed at the pins in `middleware/requirements-test.txt`: `ruff==0.8.4`, `mypy==1.13.0`. | Quality gates (task 1.12 and the Phase 2 exit) | None. |

Preflight result: no Phase 2 task on the M&S tier can start its tool-dependent work on this host except task 2.5 (the delegation code runs against a stub on this host) and the non-engine parts of task 2.6. The real-engine run is pending.

### Baseline before changes

Recorded on the unmodified code, same interpreter (`.venv-qual311`, Python 3.11.9, pytest 8.3.4):

| Run | Command | Result |
|:----|:--------|:-------|
| Pulse IQ and OQ subset | `pytest vv/tests/IQ/test_iq4_pulse_engine_init.py vv/tests/OQ/test_oq16_pulse_state_serialization.py vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py -q` | 3 passed, 2 skipped (IQ-4 and OQ-16 skip: `could not import 'pulse'`) |
| Middleware subset | `pytest middleware/tests -q` | 157 passed, 59 skipped (DB-dependent tests skip without `BIOSYNC_TEST_DATABASE_URL`) |

### SOUP inventory

Recorded in `sim/SOUP.md` (new, same commit as this log). Version pins observed on this host are listed there. Items with no tagged release yet are marked as preconditions.

Gap found during inventory: `websockets` 17.2 and Locust 2.46.7 are used by the Phase 1 harnesses but are not pinned in `middleware/requirements.txt` or `middleware/requirements-test.txt`. `websockets` arrives transitively through `uvicorn[standard]`, which is not an exact pin. Locust is installed only in `.venv-pq-load`. Both are recorded as pin gaps in `sim/SOUP.md`. This increment does not change the pin files for them, because that is not a new dependency.

### Design: Pulse worker model (task 2.5)

* One worker process per engine instance. Each `PulseWorker` owns a `ProcessPoolExecutor(max_workers=1)` created with the `spawn` start method. `spawn` is used on all platforms so that a native engine is never created in a forked copy of a process that runs the FastAPI event loop and threads.
* The native engine lives only in that worker process. The child holds a module-level dictionary keyed by a per-worker id (a uuid4 hex string). The parent never receives the engine object. `PulseWorker.engine` stays non-None after a successful initialize (the IQ-4 suite asserts it) and holds the worker id as an opaque handle.
* The heavy `import pulse` moves into the child-side adapter `_NativeEngineAdapter`. The parent process never imports `pulse` on the production path. `engine/pulse_bridge.real_pulse_available()` switches from `import pulse` to `importlib.util.find_spec("pulse")` so that the parent does not load the native extension just to check availability.
* Child-side functions are module-level and picklable: `_child_initialize`, `_child_step`, `_child_serialize`, `_child_ping`, and `_child_close`. Arguments and results are plain values (int, float, str, list, dict).
* Fail-closed initialization is unchanged in meaning. When the engine import fails in the child, `_child_initialize` returns `{"ok": False, "error": ...}`, `PulseWorker.initialize()` returns False, the state becomes ERROR, and the worker process is released. No synthetic mock is used on the production path.
* Step calls run in the worker process, so the event loop never executes a native step. `PulseWorker.step_async` awaits `loop.run_in_executor(executor, _child_step, ...)` wrapped in `asyncio.wait_for(..., step_timeout_s)`. The synchronous `step` uses `future.result(timeout=step_timeout_s)`.
* Bounded timeouts: a timed-out step or a crashed worker (`BrokenProcessPool`) moves the worker to ERROR, releases the executor, and terminates the process best-effort. The failure raises `TimeoutError` or `RuntimeError`. A native crash in the child cannot take down the parent process.
* Step timing (`record_pulse_step`) and the metric history stay in the parent. The registry in `api/middleware/response_time.py` is per process, so recording in the child would lose the samples.
* `SimulationManager` drops the shared process pool. Each simulation gets its own worker. `create_simulation` enforces `max_concurrent`. Async variants (`create_simulation_async`, `step_simulation_async`, `pause_simulation_async`, `stop_simulation_async`) keep blocking database writes and native initialization off the event loop. Database writes use `asyncio.to_thread`, and steps use the worker future.
* The SRS and DEVELOPMENT_PLAN wording remains "ProcessPoolExecutor". The implementation uses one `ProcessPoolExecutor` per engine, which is the mechanism the plan names.

### Design: heartbeat-gap metric (task 2.5 and VAL-007)

* Sample source: `time.perf_counter()` read after each `asyncio.sleep(interval)` in a heartbeat coroutine on the FastAPI event loop. The nominal interval is 10 ms.
* Gap definition: the observed wall time between two consecutive heartbeat wakeups, in milliseconds. The raw interval is recorded, not the excess over the nominal interval. This is stricter than a stall measure, so the 50 ms bound applies to the raw gap.
* Statistics: sample count, maximum gap, p50, p95, and p99 over the most recent 200,000 samples, and a histogram with upper edges at 10, 20, 50, 100, and 250 ms plus an open last bucket. `passed` is true when the maximum gap is at most 50 ms and the sample count is non-zero.
* Exposure: a process-wide `HeartbeatMonitor` singleton (`heartbeat_monitor()`), read through `SimulationManager.stats()` and `pulse_bridge.pulse_engine_stats()`.
* Negative control: the unit test blocks the loop with `time.sleep` for 120 ms and checks that the monitor reports a maximum gap of at least 100 ms. This shows the metric detects loop blocking.

### Test double disclosure

* Test doubles live in test files only. The production path has no stub.
* `_NativeEngineAdapter` is the production adapter. Tests replace the module-level name `_ENGINE_FACTORY` with a stub class through `monkeypatch`. The stub implements the same three methods (`advance`, `pull`, `serialize`).
* Tests that need an in-process worker pass `executor_factory=ThreadPoolExecutor(max_workers=1)` to `PulseWorker`. The factory parameter is a seam for tests. The production default is the spawn process pool.
* Process-level tests (worker reuse by pid, crash isolation, and fail-closed initialization without bindings) use the real spawn process and do not need a stub. They run on this host because the import failure is real.

### Files changed

* `SNDEV/docs/impl-2026-10-14-phase2-kickoff.md` (new in commit `fd5e111`; results appended in the second commit)
* `sim/SOUP.md` (new, commit `fd5e111`)
* `middleware/engine/pulse.py` (rewritten around the worker model: spawn worker per engine, native adapter inside the worker, async step with bounded wait, fail-closed initialization, `HeartbeatMonitor`, `SimulationManager` limit, stats, and async entry points; the module-level `_step_worker_sync` scaffold and the shared `ProcessPoolExecutor` on `SimulationManager` were removed)
* `middleware/engine/pulse_bridge.py` (`real_pulse_available` uses `importlib.util.find_spec`; `pulse_engine_stats()` added; per-call workers are closed in `finally`; the `BIOSSYNC_SYNTHETIC` semantics are unchanged)
* `middleware/tests/test_pulse_worker.py` (new: 28 unit tests, stub-backed except the real-process tests)
* `vv/tests/PQ/test_pq_fr_ms_006_heartbeat_gap.py` (new: FR-MS-006 harness, real-engine test skipped without `pulse`, stub self-check always runs)
* Not changed, by design: `middleware/requirements.txt` and `middleware/requirements-test.txt` (no new dependency), `SRS.md`, `DEVELOPMENT_PLAN.md`, `vv/traceability/vtm.md`, `docs/migration-map.md` (owned by other agents this round), `vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py` (outside this increment's ownership; its docstring still says the delegation is not active).

### Defect fixed on the way

`SimulationMetrics` had required metric fields without defaults. The original `_extract_metrics` built the no-data case as `SimulationMetrics(timestamp=time.time())`, which raises TypeError. The metric fields now default to 0.0, so the no-data case returns zeros as the original intent specified.

### Heartbeat sampling finding

The first measurement of the stub self-check produced about 4,500 samples in a 3-second window and a p50 near 0.15 ms, against a nominal 10 ms interval. A standalone probe showed the cause. On this host, asyncio clamps timer deadlines to the monotonic clock resolution (`time.get_clock_info("monotonic").resolution`, about 15.6 ms here). A 10 ms sleep returns after about 15 ms when the loop is idle and returns early when the loop is busy with executor completions. The docstring of `HeartbeatMonitor` records this limit. The snapshot reports `clock_resolution_ms`. The maximum gap remains a valid stall detector: a loop blocked for T ms shows a gap of at least T ms, and the gap exceeds T by at most one heartbeat period plus the clock resolution. The unit test `test_heartbeat_detects_blocked_event_loop` checks this with a 120 ms block.

### Verification

Interpreter `.venv-qual311` (Python 3.11.9, pytest 8.3.4, ruff 0.8.4, mypy 1.13.0). The `pulse` package is not installed on this host, so the engine-dependent suites skip with the reason recorded below.

| Run | Command | Result |
|:----|:--------|:-------|
| Pulse IQ-4, OQ-16, fail-closed OQ (baseline) | `pytest vv/tests/IQ/test_iq4_pulse_engine_init.py vv/tests/OQ/test_oq16_pulse_state_serialization.py vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py -q` | 3 passed, 2 skipped (before the change) |
| Pulse IQ-4, OQ-16, fail-closed OQ (after) | same command | 3 passed, 2 skipped. Skip reason: `could not import 'pulse': No module named 'pulse'` |
| Worker lifecycle and heartbeat unit tests | `pytest middleware/tests/test_pulse_worker.py -v` | 28 passed, 0 failed (real spawn process used by 3 tests: fail-closed initialization, worker reuse, and worker loss) |
| FR-MS-006 PQ harness | `pytest vv/tests/PQ/test_pq_fr_ms_006_heartbeat_gap.py -v` | 1 passed (stub self-check, 3 s window); 1 skipped (real engine: `native Pulse bindings not importable on this host; ... pending the pinned Pulse build (DEVELOPMENT_PLAN.md task 2.6)`) |
| Middleware full suite (baseline) | `pytest middleware/tests -q` | 157 passed, 59 skipped |
| Middleware full suite (after) | `pytest middleware/tests -q` | 185 passed, 59 skipped (157 baseline plus 28 new; no regression) |
| vv full suite (after) | `pytest vv/tests -q` | 88 passed, 369 skipped, 1 failed. The failure is `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py::test_1m_rows_hash_chain_under_60s` (see the defect note below). This file is unchanged by this increment. |
| Ruff (pinned 0.8.4) | `ruff check middleware/engine/pulse.py middleware/engine/pulse_bridge.py middleware/tests/test_pulse_worker.py vv/tests/PQ/test_pq_fr_ms_006_heartbeat_gap.py` | All checks passed |
| Mypy (pinned 1.13.0) | `mypy middleware/engine/pulse.py middleware/engine/pulse_bridge.py --ignore-missing-imports` | 0 errors in the two files. Three errors remain in `middleware/engine/signal.py` (2) and `middleware/models.py` (1), outside this increment. |
| Stub heartbeat self-check (informational, three 3 s runs) | harness with stub engine, default settings | max gap 10.05, 10.89, and 13.23 ms against the 50 ms bound; samples 4573, 4532, and 4487. The p50 values (about 0.15 ms) reflect the clock clamp above and do not measure responsiveness. |

Real-engine evidence status: PENDING. IQ-4 and OQ-16 did not run. The 10-minute, 10-simulation heartbeat measurement did not run because the native engine is absent. The 3-second stub self-check is plumbing evidence only and is not evidence for FR-MS-006.

Defect note (pre-existing, not in this increment): `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py` applies its `skipif` on the helper `_recreate_database` rather than on `test_1m_rows_hash_chain_under_60s`. With `BIOSYNC_PQ3_DATABASE_URL` unset, the test runs, connects with an empty URL, and fails with `psycopg2.OperationalError`. The file is unchanged in git (`git diff --stat` is empty). The owner should move the decorator.

### Coverage status for `pulse.py` and `pulse_bridge.py`

Not measured. No coverage tool is pinned in `middleware/requirements-test.txt`, and this increment did not add one. The Phase 2 obligation of 100% statement and branch coverage on both modules (DEVELOPMENT_PLAN.md Section 5.2 and the VTM row for FR-MS-006) is OPEN. Code that runs only in the spawned worker process (`_NativeEngineAdapter`, `_child_*`) is not visible to a parent-process coverage run without a subprocess hook, so the obligation needs that decision as well.

## Follow-ups

* Phase 2 tasks blocked by the preflight: 2.1 (3D Slicer), 2.2 and 2.3 (SOFA), 2.4 (SlicerROS2, ROS 2, Fast DDS), 2.7 (SOFA FMU and FMI tooling), 2.8 (FMI master, FMI-LS-BUS, Fast DDS). Each needs the precondition in the preflight table before its work starts.
* Real-engine run pending the pinned Pulse build: IQ-4, OQ-16, the 10-minute heartbeat measurement (`BIOSYNC_PQ_MS006_DURATION_S=600`, run id recorded in the capture name), and the `.pulse/` provenance record (task 2.6). The fail-closed path, the worker reuse, and the timeout paths are verified against real processes or stubs on this host.
* Coverage: decide the tool and the subprocess coverage approach, then measure `pulse.py` and `pulse_bridge.py` against the 100% statement and branch obligation.
* Migration-map debt row: `docs/migration-map.md` still lists "ProcessPoolExecutor delegation for Pulse steps" as OPEN, and the FR-MS-006 `pulse.py` row describes the Gateway persistence only. That file is owned by another agent this round. The documentation owner should close the row and cite this record.
* Stale docstring: `vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py` still states that the ProcessPoolExecutor delegation is not active. Owner should update it.
* Defect: `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py` skip guard placement (see the verification note).
* Pin gaps listed in `sim/SOUP.md`: `websockets` (transitive through `uvicorn[standard]`) and Locust 2.46.7 (not in a tracked requirements file).
