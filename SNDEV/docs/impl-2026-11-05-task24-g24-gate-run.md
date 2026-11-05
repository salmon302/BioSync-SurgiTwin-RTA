Title: G2.4 wrench publish-rate gate run, 600 s at 500 Hz (plan task 2.4 slice 2b)
Date: 2026-11-05T16:38:44Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.4 slice 2b, gate G2.4 (FR-MS-004)
Summary: Runs the 600 s, 500 Hz bridge capture at the rmw_fastrtps_cpp subscriber under the pre-registered acceptance clauses, and records the verdict and the test configuration.

## Task Reference

Plan task 2.4 in `DEVELOPMENT_PLAN.md`, slice 2b (the G2.4 gate run). Gate row G2.4 (Phase 2 gate table): a wrench publish rate of 500 Hz or higher sustained for 10 minutes, measured at the ROS 2 subscriber on the RoboStack Jazzy environment of task 2.0.3, with the CPython 3.12 subscriber and `.venv-qual311` driver split named in the test configuration record. VTM row FR-MS-004 (`vv/traceability/vtm.md`, line 12): 6-axis wrench publish rate of at least 500 Hz sustained for 10 minutes at the ROS 2 subscriber, with Cartesian tool-tip pose and mesh deformation state present on every publish tick. Predecessor logs: `SNDEV/docs/impl-2026-11-05-task24-slice1-bridge.md` and `SNDEV/docs/impl-2026-11-05-task24-slice2a-timing.md`.

Authorization: the document owner authorized the run on 2026-11-05 and confirmed the host is clear.

## Specification Summary

* Run: `sim/bridge/tools/run_smoke.ps1 -Rates 500 -Duration 600` with the default wait-mode subscriber and the high-resolution waitable timer (slice 2a configuration).
* Data source: the node's deterministic synthetic trajectories. This is a recorded boundary (see the verdict section).
* Scope: no code changes in `sim/bridge/` in this slice. A defect found during the run is reported, not fixed.

## Pre-registered acceptance (fixed before the run)

Gate clauses (these decide the verdict):

* G-a: sustained rate at or above 500 Hz over the full 600 s, measured at the subscriber. Rate definition (fixed here): `(N - 1) / (t_last - t_first)`, where N is the count of ticks with all three streams present, and `t_first` and `t_last` are the subscriber arrival times of the first and last complete tick. The value is reported with three decimals and is not rounded before the comparison. A value below 500.000 Hz fails G-a.
* G-b: pose and mesh deformation state present on every publish tick. Pass requires `ticks_with_all_three_streams` equal to the number of ticks published by the node (300000), with `ticks_with_partial_streams` equal to 0.
* G-c: zero missing ticks against 300000 expected (`missing_complete_ticks_vs_expected` equal to 0), and zero mesh tick-index gaps and duplicates.

Reported, not gated:

* Late ticks at the node (`late_ticks`, definition unchanged from slice 1: a publish that starts at least one period after its scheduled time). Baseline for comparison: 0 of 30000 at 500 Hz, 60 s, in slice 2a (high-resolution timer). The slice 1 sleep-path baseline (787 of 30000) is recorded for reference.
* Source-stamp interval statistics (mean, p50, p95, p99, min, max) per topic, from `header.stamp` on the node clock.
* Arrival interval statistics (mean, p50, p95, p99, min, max) per topic, from `time.perf_counter_ns()` at callback entry on the subscriber clock.
* Agreement check per topic (mean within 1 percent of the 2 ms period, p95 within 1.0 ms), as fixed in slice 2a. Reported only. A disagreement does not change the verdict and is recorded as a finding about the measurement method.
* Minimum 1-minute window rate. Pre-registered definition: non-overlapping 60 s windows from `t_first`, count of complete ticks per window divided by 60 s, minimum over the ten windows. Availability: the current capture (`measure_rate.py` schema v2) stores interval statistics and counts, not per-message timestamps, so this value cannot be computed from the JSON record. The gap is recorded in the run record below and is not fixed in this slice.

Verdict rule: PASS only if G-a, G-b, and G-c all pass. Any clause that fails gives FAIL for the cell, and the failure is recorded with its number.

## Implementation Notes

Quiet-host check (2026-11-05T16:38Z, read before the run): `Get-Process` found none of Warhammer, Roblox, RobloxPlayerBeta, runSofa, colcon, or Slicer. Three CPU counter samples (2 s apart): 0.7, 1.4, and 0.3 percent (total, 24 logical CPUs). The host is clear, and the run proceeds.

Run record.

Command (from the repository root, after `sim\bridge\build.ps1`):

```
powershell -NoProfile -ExecutionPolicy Bypass -File sim\bridge\tools\run_smoke.ps1 -Rates 500 -Duration 600
```

Defaults used: `-TimerMode high_resolution`, `-Spin wait`, `-LogDir` at `SNDEV/logs/`.

Start and end (UTC, from the JSON record and the node log): subscriber first arrival 2026-11-05T16:39:06.093Z. Node reports `matched subscribers on all three topics, starting tick schedule` at 16:39:06.093Z, and `publish loop finished: ticks=300000 late_ticks=0 elapsed_s=599.998` at 16:49:06.09Z. Subscriber record written 2026-11-05T16:49:09.686Z (stop reason `idle_timeout`, 3 s after the last message).

Exit codes: driver (`run_smoke.ps1`) exit 0. Node (`bridge_node`) exit 0. Subscriber (`measure_rate.py`) record written, exit status as recorded by the driver (its JSON exists).

Wall duration: 609.2 s for the driver call (includes the subscriber start, discovery, the 600 s publish loop, and the 3 s idle timeout). Publish loop: 599.998 s. Subscriber wrench wall duration (first to last complete tick): 599.998 s.

Ticks and counts (from the JSON record `SNDEV/logs/bridge-smoke-500hz-600s-timer-high_resolution-spin-wait-2026-11-05T163901Z.json`):

| Item | Value | Clause |
|:-----|:------|:-------|
| Ticks published by the node | 300000 | expected |
| Messages received: pose, wrench, mesh | 300000, 300000, 300000 | G-b |
| Ticks with all three streams (matched by `header.stamp`) | 300000 | G-b |
| Ticks with partial streams | 0 | G-b, G-c |
| Missing complete ticks against 300000 | 0 | G-c |
| Mesh tick-index range | 0 to 299999 | G-c |
| Mesh tick-index gaps | 0 | G-c |
| Mesh duplicate messages | 0 | G-c |
| Non-finite messages | 0 | reported |

Achieved rate (G-a, pre-registered definition `(N - 1) / (t_last - t_first)`, N = 300000 complete ticks): 299999 / 599.9976 s = 500.0003 Hz. Margin over 500 Hz: 0.0003 Hz. The node holds a 2 ms schedule from a fixed start with no drift, so the value is set by the schedule and the run length. A count-only definition (300000 / 600 s) gives exactly 500.000 Hz.

Minimum 1-minute window rate: not computed. The capture records interval statistics and counts, and it does not record per-message timestamps, so non-overlapping 60 s windows cannot be formed from the JSON. This is a finding about the capture (see Defects below), not a gate failure. It is a reported-not-gated item.

Late ticks (reported): 0 of 300000 (node log `late_ticks=0`). Slice 2a baseline at 500 Hz, 60 s, high-resolution timer: 0 of 30000. Slice 1 sleep-path baseline: 787 of 30000 (2.6 percent). Slice 2a sleep-path runs on the same host: 733 and 636 of 30000.

Interval statistics (milliseconds). Source stamps are the node clock (`header.stamp`). Arrival intervals are the subscriber clock (`time.perf_counter_ns()` at callback entry). Each row covers 299999 intervals.

| Topic | Clock | Mean | p50 | p95 | p99 | min | max |
|:------|:------|:-----|:----|:----|:----|:----|:----|
| Tool-tip pose | source stamp | 2.0000 | 2.0094 | 2.0816 | 2.2220 | 1.0602 | 2.9328 |
| Tool-tip pose | arrival | 2.0000 | 2.0094 | 2.1445 | 2.3029 | 0.3828 | 4.7163 |
| Wrench | source stamp | 2.0000 | 2.0094 | 2.0816 | 2.2220 | 1.0602 | 2.9328 |
| Wrench | arrival | 2.0000 | 2.0080 | 2.1881 | 2.3437 | 0.3880 | 6.2593 |
| Mesh deformation | source stamp | 2.0000 | 2.0094 | 2.0816 | 2.2220 | 1.0602 | 2.9328 |
| Mesh deformation | arrival | 2.0000 | 2.0060 | 2.2332 | 2.3907 | 0.3893 | 6.2729 |

The source-stamp rows are identical for the three topics because the node gives the three messages of a tick the same stamp.

Agreement check (slice 2a tolerances: mean within 1 percent of the 2 ms period, p95 within 1.0 ms), reported only:

* Pose: mean difference fraction 5.0e-7 of the period, p95 difference 0.063 ms. Pass.
* Wrench: mean difference fraction 6.5e-7, p95 difference 0.107 ms. Pass.
* Mesh: mean difference fraction 7.0e-7, p95 difference 0.152 ms. Pass.
* Message counts per topic match source-stamp interval counts on all three topics.

Arrival maxima of 4.7 ms to 6.3 ms are subscriber-side outliers. They do not move the p95 or the rate, because every tick was present and no tick was late at the node. They are recorded for the report.

Transcripts (in `SNDEV/logs/`): driver `bridge-g24-gate-2026-11-05-run-transcript.txt`; node `...T163901Z-node.txt` and `...-node-stderr.txt`; subscriber `...-subscriber.txt` and `...-subscriber-stderr.txt`; JSON `bridge-smoke-500hz-600s-timer-high_resolution-spin-wait-2026-11-05T163901Z.json`. The subscriber stderr file is empty.

Verdict (pre-registered rule): G-a PASS (500.0003 Hz is at or above 500.000 Hz). G-b PASS (300000 of 300000 ticks with pose and mesh present). G-c PASS (0 missing, 0 partial, 0 gaps, 0 duplicates). Verdict: PASS, with the boundaries below.

Defects and findings from the run (reported, not fixed, per scope):

* Capture gap: `measure_rate.py` (schema v2) does not persist per-message timestamps. The 1-minute window minimum (pre-registered as reported) cannot be computed. The planned test configuration statement that per-message timestamps are recorded in the capture is therefore not satisfied by the current capture. The fix belongs in a later slice that may change `sim/bridge/tools/measure_rate.py`.
* Rate margin: the pass margin on G-a is 0.0003 Hz because the node holds its schedule. A count-only definition gives exactly 500.000 Hz. The pre-registered definition was used.

## Test configuration record (G2.4)

* Deployment: single machine. Microsoft Windows 11 Pro, build 22621 (version 10.0.22621). Processor: 24 logical CPUs. Quiet-host check before the run: no Warhammer, Roblox, RobloxPlayerBeta, runSofa, colcon, or Slicer process. CPU total 0.3 to 1.4 percent.
* Topology: publisher `bridge_node` (package `srtra_bridge`, ament_cmake) and subscriber `tools/measure_rate.py`, both on one host, communicating over Fast DDS. The node is Release (`CMAKE_BUILD_TYPE=Release`) built with MSVC 14.44.35207 (Visual Studio 2022 Community) and Ninja 1.13.2 through colcon 0.21.3 and CMake 4.4.5, from `env/ros2-jazzy`.
* Middleware: `rmw_fastrtps_cpp` 8.4.4 (`RMW_IMPLEMENTATION=rmw_fastrtps_cpp`), Fast DDS 2.14.7, reliable, keep-last depth 100 on the publishers and 1000 on the subscriber. ROS 2 Jazzy `ros-jazzy-ros-base` 0.11.0 on the RoboStack `robostack-jazzy` channel.
* Environment lock: `env/ros2-jazzy/pixi.lock` (SHA-256 prefix `5149C2D2E93FD1E9`), manifest `env/ros2-jazzy/pixi.toml`.
* Interpreter split: the subscriber runs CPython 3.12.16 in the pixi environment (`env/ros2-jazzy`). The `.venv-qual311` OQ drivers (CPython 3.11.9) do not run the subscriber. They parse the JSON captures in `SNDEV/logs/` downstream, which is the split the G2.4 cell names. The two interpreters are separate, and no code in this run was executed under `.venv-qual311`.
* Measurement point: subscriber side. Arrival time is `time.perf_counter_ns()` at callback entry (QueryPerformanceCounter, 0.1 microsecond resolution). Source time is `header.stamp` from the node clock (system clock). The subscriber also sets a 1 ms `timeBeginPeriod` through `winmm`.
* Timer: node `timer_mode=high_resolution` (`CreateWaitableTimerExW` with `CREATE_WAITABLE_TIMER_HIGH_RESOLUTION`); the log line `tick timer mechanism: high_resolution_waitable_timer` confirms the mechanism that ran.
* Per-message timestamps: not recorded in the capture (see Defects). The capture records per-topic interval statistics, counts, and per-tick completeness.
* Data source: deterministic synthetic trajectories (`bridge_node` `fill_tick`). Each value is a function of the tick index. Tool-tip path 0.2 Hz Lissajous, wrench sinusoidal, mesh 8 modal coefficients (`mode_coefficients`, meters).
* Message contract: `/srtra/bridge/tool_tip_pose` (`geometry_msgs/PoseStamped`, meters and unit quaternion), `/srtra/bridge/tool_wrench` (`geometry_msgs/WrenchStamped`, newtons and newton-meters), `/srtra/bridge/mesh_deformation` (`srtra_bridge/MeshDeformationState`, `uint64 tick`, `float32[<=16] mode_coefficients`). Frame `srtra_world`.
* Code state at the run: the `sim/bridge/` sources in the working tree are the slice 2a state (SHA-256 prefixes: `bridge_node.cpp` A939C118B7610454, `bridge_node.hpp` 8A44939B7B9C089A, `measure_rate.py` 526F8511A5853E50, `run_smoke.ps1` EA1D27307090064A, `CMakeLists.txt` 24EF54D30D95D862, built `bridge_node.exe` 9316996AF590E351). Repository HEAD at the run: 4b18541. The `sim/bridge/` sources at the run match commit dbe923d (slice 2a, `feat(sim): high-resolution tick timer and arrival-method fix (2.4 slice 2a)`), which is an ancestor of HEAD at the run. The working-tree files were byte-identical to dbe923d when checked after the run (`git diff --quiet dbe923d -- sim/bridge` exit 0).

## Verdict and boundary

Verdict: PASS against G2.4 and FR-MS-004 for the clauses in scope of this run (rate at or above 500 Hz sustained for 600 s at the subscriber, pose and mesh deformation state present on every publish tick, zero missing ticks). Measured: 500.0003 Hz over 599.998 s, 300000 of 300000 complete ticks, zero missing, zero partial, zero index gaps.

Boundary text (recorded as part of the verdict, not as a caveat that is out of scope):

1. Data source: the node publishes the deterministic synthetic trajectories of `bridge_node`. The SOFA tool-tip, wrench, and modal mesh outputs replace them in a later slice, and this gate run is repeated on that data source at that time.
2. Structural coverage: the VTM row FR-MS-004 carries the coverage obligation of 100 percent statement, branch, and MC/DC on the C++ bridge code. That obligation is not met by this run and is tracked separately in the coverage work.
3. Minimum 1-minute window rate: not computed from this capture (see Defects). It is reported as not available.
4. Measurement host: one machine on Windows 11 Pro, with the Fast DDS loopback path. Network transport is not exercised.
5. The G2.4 cell names the CPython 3.12 subscriber and the `.venv-qual311` driver split. The split is recorded here. The `.venv-qual311` drivers are downstream of this capture.

Not changed in this slice: no code in `sim/bridge/`, no edits to `sim/segmentation/`, `env/`, `vv/`, `SRS.md`, or `sim/SOUP.md`. The VTM is not edited.
