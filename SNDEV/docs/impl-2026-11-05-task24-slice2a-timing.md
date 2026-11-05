Title: ROS 2 bridge timing fixes (plan task 2.4 slice 2a): high-resolution waitable timer and subscriber arrival method
Date: 2026-11-05T16:19:14Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.4 slice 2a (follows slice 1, `SNDEV/docs/impl-2026-11-05-task24-slice1-bridge.md`)
Summary: Replaces the node's 1 ms sleep timer with a high-resolution waitable timer (fallback kept), and reworks the rclpy subscriber arrival capture so arrival intervals agree with source-stamp intervals at 500 Hz.

## Task Reference

Plan task 2.4, slice 2a, as scoped by the parent session: the two timing-method fixes from slice 1 (late-tick remediation in `bridge_node.cpp`, and the subscriber arrival-method fix in `sim/bridge/tools/measure_rate.py`), plus verification runs. Requirement FR-MS-004 (SRS v1.2.0). Not in this slice: the 600 s G2.4 gate run, the SOFA source integration, and the test configuration record (slice 2b or later, quiet host).

## Specification Summary

* Late ticks at 500 Hz must drop well below the slice 1 baseline of 787 of 30000 (2.6 percent). The definition of a late tick is unchanged from slice 1: a tick whose publish starts at least one period after its scheduled time.
* Mechanism: high-resolution waitable timer (`CreateWaitableTimerExW` with `CREATE_WAITABLE_TIMER_HIGH_RESOLUTION`) where the OS supports it, fallback to the slice 1 path (`timeBeginPeriod(1)` plus `sleep_until`). C++17, no heap allocation in the publish loop.
* Subscriber: per-message arrival time captured at callback entry with `time.perf_counter_ns()`. The batching artifact seen in slice 1 is removed. Source-stamp intervals and arrival intervals are reported per topic in the same run, and they must agree within a stated tolerance at 500 Hz.
* Verification: one 60 s run at 500 Hz with `rmw_fastrtps_cpp`, if host state allows. Otherwise 100 Hz, and the 500 Hz verification is deferred to the quiet-host slice.
* Style and reproducibility: straight quotes, no em dashes, new code carries `// SPDX-License-Identifier: MIT`, no floating pins, no secrets.

## Implementation Notes

Log created before any change in this slice (the slice 1 log is not appended to, so each slice has its own record).

Host state (2026-11-05, read before any run): `Get-Process` found none of Warhammer, Roblox, RobloxPlayerBeta, runSofa, colcon, Slicer, or bridge_node running. The top CPU consumers were Chrome, AUEPMaster, nvcontainer, VS Code Insiders, steamwebhelper, Discord, and opencode (background applications, each with low sustained CPU). Total processor time sampled with `Get-Counter` (three samples, 2 s apart): 0.2, 0.5, and 1.4 percent over 24 logical CPUs. Decision: the 500 Hz verification runs in this slice.

Host OS: Microsoft Windows 11 Pro, build 22621 (version 10.0.22621). The high-resolution waitable timer requires Windows 10 version 1803 (build 17134) or later, so it is supported on this build.

### Item 1: late-tick remediation (`sim/bridge/src/bridge_node.cpp`, `include/srtra_bridge/bridge_node.hpp`)

Change. The slice 1 `TimerResolutionGuard` is replaced by `TickWaiter`, an anonymous-namespace class:

* Preferred mechanism: `CreateWaitableTimerExW(nullptr, nullptr, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS)` created once in the constructor of `TickWaiter` (once per `run()`, before the loop). Each tick re-arms the timer with `SetWaitableTimer` using a relative due time in 100 ns units, then `WaitForSingleObject`. The wait loop repeats until the target time, so an early wake does not start a tick early. No allocation occurs in the loop.
* Fallback: if the timer cannot be created, `timeBeginPeriod(1)` is called for the lifetime of the object and `std::this_thread::sleep_until` is used (the slice 1 path). `timeEndPeriod(1)` runs in the destructor.
* Non-Windows builds use `sleep_until` only. The `#ifdef _WIN32` blocks are the only platform code.
* Parameter `timer_mode` (string): `high_resolution` (default) or `sleep` (forces the fallback). Any other value throws `std::invalid_argument`.
* The mechanism that took effect is logged at start (`tick timer mechanism: ...`) and at exit (`publish loop finished: ... timer=...`).
* Language and build: C++17 pin kept (`CMAKE_CXX_STANDARD 17`), Release build (`build.ps1`), no changes to `CMakeLists.txt`, `package.xml`, or the message definition. `winmm` stays linked for the fallback.

Late-tick definition (unchanged from slice 1). A tick is late when the publish starts at least one period after its scheduled time, that is `Clock::now() - next >= period` checked after the wait, counted in `late_ticks_`. At 500 Hz the period is 2 ms.

Build. Two compile attempts before the successful build. The first failed with C2662 (`wait_until` called on a `const` waiter). The fix marks `wait_until` `const`, since it does not modify the object. The transcript `SNDEV/logs/bridge-build-2026-11-05-slice2a.txt` holds the last attempt (the failed transcript was overwritten). The successful build is EXIT 0 with no CMake or compiler warnings, Release, Ninja, MSVC 14.44.35207. The first pretest of this slice ran against the stale slice 1 binary because the build had failed. Its output (`late_ticks=61` in 5 s) is not a result of this change, and the run was repeated after the build passed.

Mechanism verified. Pretest at 500 Hz for 5 s (scratch directory `sim/bridge/build/pretest2`): node log `tick timer mechanism: high_resolution_waitable_timer`, `late_ticks=0` over 2500 ticks. The fallback did not run.

### Item 2: subscriber arrival method (`sim/bridge/tools/measure_rate.py`)

Change. Each callback takes `time.perf_counter_ns()` as its first statement. The executor loop is `rclpy.spin_once` with timeout 0.05 s (`--spin wait`, default) or timeout 0 in a loop (`--spin poll`, one core busy, kept for comparison). The JSON now reports, per topic, arrival-interval statistics, source-stamp interval statistics, the agreement check, and a message-count match. The JSON schema is `srtra-bridge-rate-measure/2`. The clock implementation and resolution are recorded.

Root cause of the slice 1 batching (correction to the slice 1 record). The slice 1 log attributed the 16 ms arrival steps to rclpy executor batching. That attribution is wrong. The slice 1 subscriber stamped arrivals with `time.monotonic_ns()`. On this build, `time.get_clock_info('monotonic')` reports `implementation='GetTickCount64()'` with `resolution=0.015625` s, and `time.get_clock_info('perf_counter')` reports `implementation='QueryPerformanceCounter()'` with `resolution=1e-07` s. The 15 and 16 ms arrival steps were that clock quantization. Run D below reproduces the slice 1 executor pairing (sleep node, wait subscriber) with the `perf_counter` stamp, and the batching does not appear.

Agreement tolerance (fixed before the verification run). For each topic, `passed` requires both:

* the absolute difference between the arrival-interval mean and the source-stamp-interval mean is at most 1 percent of the nominal period (0.02 ms at 500 Hz), and
* the absolute difference between the arrival-interval p95 and the source-stamp-interval p95 is at most 1.0 ms.

Validation runs at 500 Hz, 60 s each, `rmw_fastrtps_cpp`. Transcripts and JSON are in `SNDEV/logs/`:

| Run | Node timer | Subscriber | Transcript | JSON (timestamp suffix) | Late ticks | Complete ticks | Agreement (pose, wrench, mesh) |
|:----|:----------|:-----------|:-----------|:------------------------|:-----------|:---------------|:-------------------------------|
| A | sleep (slice 1 path) | poll | `bridge-smoke-2026-11-05-slice2a-A-sleep-poll-500hz.txt` | `...-timer-sleep-spin-poll-2026-11-05T162150Z.json` | 733 | 30000 of 30000 | pass, pass, pass |
| B | high_resolution | poll | `...-B-highres-poll-500hz.txt` | `...-timer-high_resolution-spin-poll-2026-11-05T162306Z.json` | 0 | 30000 of 30000 | pass, pass, pass |
| C | high_resolution | wait | `...-C-highres-wait-500hz.txt` | `...-timer-high_resolution-spin-wait-2026-11-05T162418Z.json` | 0 | 30000 of 30000 | pass, pass, pass |
| D | sleep (slice 1 path) | wait | `...-D-sleep-wait-500hz.txt` | `...-timer-sleep-spin-wait-2026-11-05T162540Z.json` | 636 | 30000 of 30000 | pass, pass, pass |
| E (verification) | high_resolution (default) | wait (default) | `...-E-verification-highres-wait-500hz.txt` | `...-timer-high_resolution-spin-wait-2026-11-05T162726Z.json` | 0 | 30000 of 30000 | pass, pass, pass |

Note on runs B and C: the JSON `schema` is `srtra-bridge-rate-measure/2` and the `arrival_method` block lists `spin` explicitly. Run C predates the default change and the clock metadata fields. Its measurement logic is the same as run E. Run E was run with the final script and is the verification record.

Run E (verification, the fixed subscriber with the high-resolution timer):

* Ticks published by node: 30000. Ticks with all three streams (matched by `header.stamp`): 30000. Partial ticks: 0. Missing complete ticks against 30000 expected: 0. Mesh tick-index gaps: 0. Duplicate mesh messages: 0. Message counts per topic: 30000 each.
* Achieved mean rate over the wrench stream: 500.002 Hz over a wall duration of 59.998 s.
* Late ticks: 0 of 30000 (node log `publish loop finished: ticks=30000 late_ticks=0 elapsed_s=59.998 timer=high_resolution_waitable_timer`).
* Source-stamp interval (node clock): mean 2.0000 ms, p50 2.008 ms, p95 2.072 ms, p99 2.224 ms, max 2.559 ms (wrench).
* Arrival interval (perf_counter clock): mean 2.0000 ms, p50 2.005 ms, p95 2.174 ms, p99 2.326 ms, max 2.838 ms (wrench).
* Agreement (wrench): mean difference 5e-6 of the period (tolerance 1e-2); p95 difference 0.102 ms (tolerance 1.0 ms). Pose: p95 difference 0.056 ms. Mesh: p95 difference 0.144 ms. All pass.

Late ticks before and after (same host class, 500 Hz, 60 s):

* Slice 1 baseline (slice 1 log, `sleep_until` with `timeBeginPeriod(1)`): 787 of 30000 (2.6 percent).
* Same host, this slice, slice 1 path (runs A and D): 733 and 636 of 30000 (2.4 percent and 2.1 percent). The two counts show the run-to-run spread of the fallback path.
* After, high-resolution waitable timer (runs B, C, and E): 0 of 30000 in each run.

Host state. Before the runs, `Get-Process` found none of Warhammer, Roblox, RobloxPlayerBeta, runSofa, colcon, Slicer, or bridge_node. Processor time sampled before each run was 0 to 1.4 percent. The host was quiet for all five runs. The 500 Hz verification ran in this slice, so it is not deferred.

Interpretation. The high-resolution timer removes the late ticks in this set. The subscriber fix did not change the arrival numbers after the clock change, and the slice 1 batching came from the clock, not the executor. The `poll` mode is not needed. The 600 s G2.4 run is a separate slice and must repeat the late-tick count, because a 60 s run is a short sample.

Limits of this record:

* 60 s runs only. The late-tick result is not a 600 s result.
* The agreement test compares interval statistics from two clocks. It does not compare individual messages, because the two clocks do not share an origin. A per-message comparison would need the subscriber to record `header.stamp` against its own arrival time, and the clock offset would dominate.
* The node and subscriber run on one machine. Network transport is not exercised.

Files changed in this slice:

* `sim/bridge/src/bridge_node.cpp` (rewritten: `TickWaiter` replaces `TimerResolutionGuard`, `timer_mode` parameter)
* `sim/bridge/include/srtra_bridge/bridge_node.hpp` (`prefer_high_resolution_` member)
* `sim/bridge/tools/measure_rate.py` (rewritten: perf_counter arrival stamp, spin mode, per-topic agreement)
* `sim/bridge/tools/run_smoke.ps1` (`-TimerMode`, `-Spin` parameters, default `wait`)
* `sim/bridge/README.md` (parameters, measurement method, slice 2 timing item)
* `SNDEV/docs/impl-2026-11-05-task24-slice2a-timing.md` (this log, new)
* `SNDEV/logs/` (new captures: build transcript, runs A to E, JSON records, node and subscriber transcripts)
* `sim/bridge/build/` (gitignored build output, rebuilt)

Not changed: `sim/SOUP.md`, `DEVELOPMENT_PLAN.md`, `env/`, `sim/segmentation/`, `vv/`, `SRS.md`. Nothing was committed.

Verification gates (slice 2a):

* Build: PASS (EXIT 0, no warnings).
* Pretest 5 s at 500 Hz: PASS (0 late ticks, 2500 of 2500 complete).
* Run E 60 s at 500 Hz: PASS (30000 of 30000 complete, 0 missing, 0 late ticks, agreement pass on all three topics).
* Banned-character scan (em dash, en dash, curly quotes, listed vocabulary) over `sim/bridge/` and this log: see the final check below.

Open items for the 600 s G2.4 slice (quiet host): repeat run E for 600 s and record late ticks, complete ticks, achieved rate, and agreement. Do not treat the 60 s numbers as the gate.
