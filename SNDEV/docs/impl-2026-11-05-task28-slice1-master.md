Title: FMI 3.0 co-simulation master core and measurement harness (plan task 2.8 slice 1)
Date: 2026-11-05T21:00:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.8 slice 1
Summary: Adds the FMI 3.0 co-simulation master core (C++17 ament package in sim/fmi/master/) with a scheduled-variable scheduler, a thermal_pennes FMU adapter, Catch2 unit tests, a master clock and participant state publisher over rmw_fastrtps_cpp, and an rclpy measurement harness, plus a single-node 10-minute skew and jitter run (result to be recorded below).

## Task Reference

Plan task 2.8 in `DEVELOPMENT_PLAN.md` (Phase 2 table row: "2.8 Build the FMI 3.0 co-simulation master with clocks and scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer (VAL-028), with the bounded 1 ms clock-skew and message-jitter measurement of VAL-005 and per-message timestamps recorded", `sim/fmi/master/`, 8.0 d). Requirement FR-MS-007 in `SRS.md` v1.2.0 (VAL-028). Gate G2.6 (later slice): all FMUs pass import checks, and measured clock skew and message jitter are each at most 1 ms across a 10-minute three-node Fast DDS run against a reference clock, with per-message timestamps recorded. This slice covers the master core, the unit tests, the single-node measurement harness, and a single-node 10-minute baseline. `DEVELOPMENT_PLAN.md` is not edited here (another builder holds it). The plan row is updated during consolidation.

## Specification Summary

* Master core in C++17 (`CMAKE_CXX_STANDARD 17`) as an ament_cmake package in `sim/fmi/master/`, built with colcon from `env/ros2-jazzy` (same pattern as `sim/bridge/build.ps1`, Release or RelWithDebInfo).
* Scheduler owns the shared timeline: a fixed master base step, a schedule table of participant step points, and variable exchange at scheduled points (read inputs, `fmi3DoStep`, publish outputs). The clock mapping of FMI 3.0 scheduled variables onto `fmi3DoStep` is documented in the README contract.
* Deterministic and allocation-stable after initialization.
* Catch2 unit tests (pinned, SHA-256 recorded) run with CTest against a fake FMU stub: schedule ordering, step-size enforcement, error propagation from `fmi3DoStep`, and the reset path (`fmi3Reset`), which was left untested in slice 1 of task 2.7. The reset path is also exercised against the real FMU in `sim/fmi/check_fmu.py`.
* ROS 2 layer: the master publishes the master clock and the participant state over Fast DDS (`rmw_fastrtps_cpp`) with per-message source stamps from a steady-clock anchor (bridge v3 pattern). An rclpy harness (CPython 3.12, pixi env) records per-message arrival and source stamps to a sidecar using the bridge v3 delta encoding.
* Single-node measurement: master, `thermal_pennes.fmu`, and the harness, 10 minutes at the master planned rate, against the reference clock. Report clock skew and message jitter with the 1 ms G2.6 bounds.
* README contract in `sim/fmi/master/README.md`: schedule semantics, clock mapping, the inter-node protocol sketch for the later three-node run, build and run commands.

## Design Decisions (fixed before the timing run)

* Master base step: 10 ms (planned publish rate 100 Hz). The thermal FMU's fixed step is 0.1 s, so the schedule steps the FMU at every tenth base tick. The publish rate is a master design choice. It gives 10 publish points per FMU step and 60000 ticks in 10 minutes, which resolves the p99 of the message distributions.
* Clock mapping: the thermal FMU declares no clock variables (it is Co-Simulation with a fixed internal step). The master drives a master-side periodic clock with interval 0.1 s for the FMU step points. The FMU is called with `fmi3DoStep(t, 0.1)` at each step point. Scheduled-variable exchange happens at step points, and outputs are held between step points (zero-order hold, as documented in the README).
* Stimulus: P_abl = 5 W for t < 30 s and 0 afterward (the scenario of `check_fmu.py` case B1), h_bc = 0, T_env = 310.15 K.
* Source stamp: `header.stamp` carries the master steady clock (ns since the steady clock epoch), taken immediately before publish. A wall-clock anchor pair (system clock and steady clock, read once at start) is recorded in the JSON. The harness reads `time.perf_counter_ns()` at callback entry. On Windows, MSVC `steady_clock` and CPython `perf_counter` both read QueryPerformanceCounter, so the two values share one epoch. The harness checks the epoch at the first message (the first arrival minus the first stamp must be within 50 ms).
* Clock skew (single node): for each message, skew = arrival (harness reference clock, perf_counter) minus source stamp (master steady clock). On a single node the reference and the master read the same hardware counter, so this value is the one-way DDS latency plus the epoch error. The record reports the distribution as skew. The three-node run separates the clocks.
* Message jitter: for each topic, the arrival interval minus the nominal period (10 ms). The source-stamp interval minus the nominal period is reported beside it, which separates publish pacing jitter from delivery jitter.
* Pass criteria, pre-registered: max |skew| at most 1 ms, and max |jitter| at most 1 ms for each topic (G2.6 "at most 1 ms" applied to the maximum). The p95 and p99 are reported in addition. A run that misses a bound is recorded as FAIL with the numbers.
* Timer: the master pacing loop uses the same high-resolution waitable timer as the bridge node (slice 2a), with `timeBeginPeriod(1)` as the fallback.
* Approval gate (AGENTS.md section 6): this slice adds more than 5 files and more than 200 lines and a new public interface. The parent session assigned the file set and the scope. The work proceeds on that direct instruction.

## Host State Before the Timing Run

Checked 2026-11-05 before any timing run (Get-Process and a 5 s CPU sample, 24 logical processors):

* Warhammer3 (pid 15780) is running with 114 threads. Its CPU share over 5 s was 4.2 percent of total host CPU (about one core).
* Slicer is not running (0 processes at check time).
* Roblox, runSofa, and colcon were not running at check time. Total host CPU was 3.4 to 4.1 percent.

Decision: the timing run is allowed because the host is quiet by total CPU. The Warhammer3 presence is a known contender for the timer and the GPU, so the host state is recorded before and after the run, and the numbers are flagged if the state changes.

## Implementation Notes

Files (all new unless noted; sim/fmi/master/ is new):

* `sim/fmi/master/CMakeLists.txt`, `package.xml`: ament_cmake package `srtra_fmi_master`. C++17. Catch2 v3.9.1 is fetched with a recorded SHA-256 (`URL_HASH`) and built as a static library.
* `sim/fmi/master/msg/MasterClock.msg`, `ParticipantState.msg`.
* `sim/fmi/master/include/srtra_fmi_master/`: `participant.hpp` (interface), `scheduler.hpp`, `fmu_participant.hpp` (no FMI types in public headers), `tick_waiter.hpp` (bridge node timer pattern).
* `sim/fmi/master/src/scheduler.cpp`, `fmu_participant.cpp` (the only file that includes the FMI 3.0.2 headers), `master_node.cpp`.
* `sim/fmi/master/tests/test_scheduler.cpp`.
* `sim/fmi/master/build.ps1`, `sim/fmi/master/tools/measure_master.py`, `tools/run_measure.ps1`, `sim/fmi/master/README.md`.
* `sim/fmi/check_fmu.py` (modified): case R1 (fmi3Reset) added.
* `sim/fmi/README.md` (modified): reset case recorded.
* `sim/SOUP.md`: Catch2 row added.

Scheduler design. Integer-nanosecond timeline, base step 10 ms. A schedule table of participant step points (period equal to the FMU fixed step, offset a multiple of the base step). At each tick, due participants run in index order: stimuli, wired inputs from the producer cache (zero-order hold), `fmi3DoStep(t, h)`, then the output cache refresh. Failures latch until reset. Configuration errors throw in the constructor. `advance_to` does not allocate. Full semantics and the clock mapping (the thermal FMU declares no clocks, so the master maps each step point to `fmi3DoStep` at the CS fixed step) are in `sim/fmi/master/README.md`.

Catch2 unit tests. `SNDEV/logs/fmi-master-catch2-2026-11-05.txt`: "All tests passed (112 assertions in 10 test cases)". Test cases (fake FMU, no DLL, no ROS): step point ordering with index tie break; step size and grid enforcement (throws for mismatched fixed step, period not on grid, negative or misaligned offset, zero base, empty participant list, out-of-range wire); fmi3DoStep failure latches and is returned later; initialization failure latches; consecutive ticks and initialize-first; wiring with zero-order hold; stimulus evaluation at the step point; reset restores the timeline and reproduces the run exactly; failing reset is reported; ten-minute run at 100 Hz steps the 0.1 s participant 6000 times.

Real FMU reset path. Check case R1 in `sim/fmi/check_fmu.py` (new): 200 steps at defaults, w_b set to 0, `fmi3Reset`, re-initialization without setting parameters, 200 steps. The second run must equal the first exactly. Result: PASS (max deviation 0). This exercises the `set_defaults` path added in task 2.7. The five-case check record is `SNDEV/logs/fmi-thermal-pennes-check-task28-2026-11-05.json` (A1, A2, B1, N1, R1: all PASS).

Build. `sim/fmi/master/build.ps1` (Release, colcon from env/ros2-jazzy, Ninja, MSVC 14.44): package finished; CTest passed. One warning: CMake `CMAKE_OBJECT_PATH_MAX` for generated ROS type support (object path 162 characters; the repository path is long). Attempt logs `SNDEV/logs/fmi-master-build-attempt1-2026-11-05.txt` (test failed with exit 0xc0000135 because Catch2 was built as a shared library under the ROS `BUILD_SHARED_LIBS` setting; fixed by `BUILD_SHARED_LIBS OFF` in the CMake file) and `...attempt2-2026-11-05.txt` (pass).

Smoke run. 5 s run (`SNDEV/logs/fmi-master-measure-5s-high_resolution-2026-11-06T015300Z.json`, a smoke run, not part of the baseline). The FMU values match the check case B1 at 5 s (T_max 355.21 K, V60 136 mm3). The smoke run already showed the arrival-minus-stamp median near 0.6 ms, which is delivery latency, so the single-node skew definition is documented as an upper bound that includes delivery time.

Host state before the timing run (recorded in `SNDEV/logs/fmi-master-measure-600s-high_resolution-2026-11-06T015357Z-host-before.txt`): total CPU 4.1 percent over 5 s, 24 logical processors, Warhammer3 running (pid 15780, 114 threads), no Slicer, runSofa, colcon, or Roblox. The timing run was started with Warhammer3 present and is recorded as contended (see results). I did not stop Warhammer3, because it is a user process.

Single-node 10-minute baseline. Run: `sim/fmi/master/tools/run_measure.ps1 -Duration 600`, 100 Hz planned publish rate, high-resolution waitable timer, FMU stepped at 0.1 s. Record: `SNDEV/logs/fmi-master-measure-600s-high_resolution-2026-11-06T015357Z.json`, sidecar `...messages.json` (2.85 MB), launcher transcript `SNDEV/logs/fmi-master-measure-600s-launcher-2026-11-05.txt`, master and harness transcripts in the same directory. Note that the run timestamps are UTC on 2026-11-06 (the run started 01:53 UTC), and the file names keep that date.

| Measure (ms) | Clock topic | State topic | Bound |
|:---|---:|---:|---:|
| Skew (arrival minus source stamp), p50 / p95 / p99 | 0.430 / 0.624 / 0.765 | 0.538 / 0.780 / 0.945 | 1 |
| Skew, max absolute | 5.592 | 5.750 | 1 |
| Skew variation about median, p99 / max | 0.334 / 5.161 | 0.407 / 5.212 | 1 |
| Arrival-interval jitter, p50 / p95 / p99 | 0.029 / 0.354 / 0.519 | 0.027 / 0.383 / 0.570 | 1 |
| Arrival-interval jitter, max absolute | 4.923 | 4.962 | 1 |
| Source-stamp interval jitter, max absolute | 4.526 | 4.526 | 1 |
| Publish pacing (stamp minus schedule), mean / p99 / max | 0.297 / 0.637 / 4.864 | not recorded | not applicable |

Verdict (pre-registered criteria, unchanged): skew FAIL (max 5.75 ms, bound 1 ms); arrival jitter FAIL (max 4.96 ms, bound 1 ms); message counts and tick sequences PASS (60000 per topic, consecutive); epoch check PASS (0.43 ms). The run is contended by Warhammer3 and is not a quiet-host measurement. Six clock ticks were late by more than 1 ms, with the worst at 4.86 ms. The skew bound as defined is not a clock-skew measurement on one node, because the 0.5 ms median is delivery time. The three-node run with a separate reference clock is needed for the G2.6 skew clause.

Decisions and deviations.

* The timing run was not deferred, because the host was not idle by total CPU and Warhammer3 was running at about one core for the whole run. The result is labeled contended. Deferring until Warhammer3 exits would have been the stricter choice; the instruction left that decision to the measurement owner, and I did not stop a user process.
* The source stamp is the master steady clock (not wall time). The anchor pair is recorded, and the epoch is checked at run time.
* Skew is defined as arrival minus source stamp. The reference clock and the master share one counter on one node, so the definition is an upper bound that includes delivery time. The skew variation about the median is reported as a diagnostic only. The pass rule was not changed after the run.
* The FMU has no clock variables. The master maps step points to `fmi3DoStep` at the CS fixed step (see the README).
* The publish path (rclcpp and Fast DDS) allocates inside the middleware. The scheduler and the FMU path do not allocate after initialization.
* The approval gate (AGENTS.md section 6) applies because this slice adds a public interface and more than 5 files. The parent session assigned the scope.

Open items.

* G2.6 is not closed. The three-node run with an independent reference clock is needed (sketch in the master README).
* The skew and jitter bounds are not met on this host in this run. The late-tick tail is the first thing to address (timer behavior under contention, the publish path, or the pacing loop).
* The single-node skew definition cannot separate clock error from delivery time. The three-node protocol addresses that.
* `DEVELOPMENT_PLAN.md` task 2.8 row is not updated (the consolidation step records the status).
* Coverage of the master code (100 percent statement, branch, and MC/DC for the task 2.8 code, per the plan CSA annotation) is not measured.
* Catch2 license is recorded as BSL-1.0 (confirm).
