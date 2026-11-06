Title: G2.4 600 s re-run on the v3 capture and replay late-tick isolation (plan task 2.4 slice 3b)
Date: 2026-11-06T18:02:48Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.4 slice 3b, follows slice 3a (`SNDEV/docs/impl-2026-11-05-task24-slice3a-capture.md`) and the G2.4 gate run (`SNDEV/docs/impl-2026-11-05-task24-g24-gate-run.md`, commit 819081c)
Summary: Isolates the replay-path late ticks (value check against arm without the check) and re-runs the 600 s G2.4 gate on the schema v3 capture with the ten-window minimum.

## Task Reference

Plan task 2.4, slice 3b. Two items from the slice 3a open list:

1. Replay late-tick isolation. Slice 3a recorded 91 and 35 late ticks on replay runs against 0 on synthetic, with the subscriber value check as the leading suspect and one run per arm.
2. The 600 s G2.4 gate re-run on the schema v3 capture (per-message timestamps), which computes the pre-registered 1-minute window minimum over ten windows. This re-run supersedes the window-statistic gap of the gate run at commit 819081c.

Gate text (read from the live cells): `DEVELOPMENT_PLAN.md` G2.4 row (500 Hz or higher sustained for 10 minutes at the ROS 2 subscriber, CPython 3.12 subscriber and `.venv-qual311` driver split named in the test configuration record) and `vv/traceability/vtm.md` FR-MS-004 row (6-axis wrench at least 500 Hz sustained for 10 minutes at the ROS 2 subscriber, with Cartesian tool-tip pose and mesh deformation state present on every publish tick). `DEVELOPMENT_PLAN.md`, `vv/`, `SRS.md`, `sim/SOUP.md`, `sim/sofa/`, `sim/segmentation/`, `sim/fmi/`, and `env/` are not edited in this slice.

## Specification Summary

* Isolation: alternating order, three runs with the subscriber value check enabled (replay capture, `--expect-csv`) and three with it disabled. Node settings identical across arms: replay source, `replay_loop=false`, `timer_mode=high_resolution`, 500 Hz, 60 s, `wait` subscriber.
* Gate: `run_smoke.ps1 -Rates 500 -Duration 600`, synthetic source, `timer_mode=high_resolution`, `wait` subscriber. The data source is the synthetic trajectory, because the SOFA replay integration is a later slice and the replay capture covers 60 s only.
* Acceptance (fixed before the gate run, the same clauses as the gate run record): sustained rate at or above 500 Hz over the full 600 s at the subscriber, using the pre-registered definition `(N - 1) / (t_last - t_first)` with N the complete ticks; pose and mesh deformation state present on every publish tick; zero missing ticks (N equal to 300000) and zero partial ticks.
* Reported, not gated: the ten-window minimum (count divided by 60 s, non-overlapping windows from `t_first`, computed with `tools/window_min.py` from the v3 sidecar), late ticks at the node, source-stamp and arrival interval statistics per topic, and source-versus-arrival agreement under the slice 2a tolerances.
* Scope limits, recorded as boundaries: synthetic trajectory source, loopback single host, structural coverage obligation (100 percent statement, branch, and MC/DC on the C++ bridge) not met and tracked in the coverage work.

## Implementation Notes

Pre-run tooling change (bounded, in `sim/bridge/tools/run_smoke.ps1` only): a `-NoValueCheck` switch that suppresses `--expect-csv` on a replay run. It is needed to build the disabled arm. The node-side arguments do not change. The switch is added before any isolation run and is recorded in the run tag as `valuecheck-off`.

Quiet-host discipline: each run is preceded by a `Get-Process` check for Warhammer, Roblox, RobloxPlayerBeta, runSofa, colcon, Slicer, and python, and three CPU counter samples. A run is deferred if any listed process is present. The check results are recorded in the run table.

### Quiet-host checks and run conditions

Before the first run, `Get-Process` found none of the listed processes (python and python3 included). Three CPU counter samples, 2 s apart, read 0.39, 0.42, and 0.00 percent of 24 logical CPUs. Before each of the six isolation runs and the 600 s run, the same process guard ran in the launch command and would have deferred the run if a listed process was present. No run was deferred. No docs-only builder ran in parallel, and no other load was applied. The runs started at 18:09:07Z (first isolation run) and 18:17:11Z (gate run).

Interrupted attempt: the session cancelled earlier in this slice left `SNDEV/logs/bridge-smoke-500hz-60s-source-replay-timer-high_resolution-spin-wait-2026-11-06T180343Z-*` (ready flag and transcripts, no record JSON). It is excluded from every count in this log. The captures in `SNDEV/logs/` are gitignored and are kept.

Code state: `sim/bridge/` is commit 93f436b (slice 3a) plus the `-NoValueCheck` switch in `tools/run_smoke.ps1` (`git diff --stat 93f436b -- sim/bridge` lists only that file). The subscriber runs in the pixi environment `env/ros2-jazzy` (CPython 3.12), as in the gate run. The `window_min.py` re-check ran in the same environment.

### Replay late-tick isolation (work item 1)

Settings in all six runs: replay capture `replay-synthetic-500hz-60s.csv` (30000 rows), `replay_loop=false`, `timer_mode=high_resolution`, 500 Hz, 60 s, `wait` subscriber. The arm differs only in `--expect-csv` on the subscriber. Order: ON, OFF, ON, OFF, ON, OFF.

| Run (record `SNDEV/logs/bridge-smoke-500hz-60s-source-replay-timer-high_resolution-spin-wait[-valuecheck-off]-...json`) | Order | Subscriber value check | Complete ticks | Late ticks (node) | Source-stamp excursions of 2 ms or more | Largest excursion (ms) | Value mismatches (pose, wrench, mesh) |
|:----|:----|:----|:----|:----|:----|:----|:----|
| `...T180907Z.json` | 1 | on | 30000 | 0 | 0 | 1.09 | 0, 0, 0 |
| `...valuecheck-off-...T181019Z.json` | 2 | off | 30000 | 0 | 0 | 0.54 | not checked |
| `...T181128Z.json` | 3 | on | 30000 | 0 | 0 | 1.07 | 0, 0, 0 |
| `...valuecheck-off-...T181239Z.json` | 4 | off | 30000 | 0 | 0 | 1.11 | not checked |
| `...T181350Z.json` | 5 | on | 30000 | 0 | 0 | 1.00 | 0, 0, 0 |
| `...valuecheck-off-...T181501Z.json` | 6 | off | 30000 | 8 | 8 | 9.61 | not checked |

The excursion column comes from the per-message sidecar (`*.messages.json`). The check computes each source stamp's offset from the 2 ms grid, takes the median offset as the band, and counts the ticks at least 2 ms above it. The check script is kept outside the repository (`%TEMP%\opencode\grid-check.ps1`). Its excursion count equals the node late count in every run.

Earlier replay runs with the check on (slice 3a, same binary): R2 91 late ticks, R3 35 late ticks. Earlier control with the check off (slice 3a, same binary): 0 late ticks. Pooled by arm: check on 91, 35, 0, 0, 0 (median 0); check off 0, 0, 0, 8 (median 0). Both medians are 0.

Cause verdict: the subscriber value check is not confirmed as the cause, and the cause is not isolated by this experiment. The check-off arm produced the largest count of the fresh runs (8), and the check-on arm produced the two largest counts of slice 3a. The arms are small (three to five runs each), the counts vary from 0 to 91 across runs with the same binary and node settings, and the medians are equal, so no difference between the arms is separable from noise. The host-side driver of the late wakes is not recorded in this slice (no scheduler trace was taken), so it is not identified.

Mechanism (from `run()` in `src/bridge_node.cpp`): each tick waits until its scheduled time `next`, and the tick is counted late when the wake is at least one period (2 ms) after `next`. `next` advances by exactly one period per tick with no catch-up. The source stamp is read after the wait. A late wake therefore gives that tick a late source stamp and a late arrival, and the next tick is on its scheduled time. Answer to the grid question: the node-side schedule stays on grid, and the source and arrival sides of the late tick are both displaced by the lateness, for that tick only. The drift from the first to the last 1000 ticks is -0.008 ms on run 181501Z and -0.042 ms on the gate run, so there is no accumulation.

Fix decision: no fix in this slice. The cause is not established, the rate clause passes with the late ticks present, and the evidence does not support a bounded change. The finding is recorded for the plan owner. A larger repeat set (for example, 10 runs per arm) with a scheduler trace would be needed to separate the arms.

### G2.4 600 s re-run on the v3 capture (work item 2)

Command: `powershell -NoProfile -ExecutionPolicy Bypass -File sim\bridge\tools\run_smoke.ps1 -Rates 500 -Duration 600` (synthetic source, `timer_mode=high_resolution`, `wait` subscriber). Start 2026-11-06T18:17:11Z (tag `181711Z`). Driver exit 0, node exit 0, subscriber record written with stop reason `idle_timeout`. Driver wall time 609.8 s. Node log: `tick timer mechanism: high_resolution_waitable_timer`, `publish loop finished: ticks=300000 late_ticks=5 elapsed_s=599.998`. Subscriber stderr is empty. Node stderr contains only the rclcpp INFO lines, wrapped by PowerShell as a `NativeCommandError` record, which is the same wrapping seen in the earlier runs.

Record: `SNDEV/logs/bridge-smoke-500hz-600s-source-synthetic-timer-high_resolution-spin-wait-2026-11-06T181711Z.json` and `...181711Z.messages.json` (15,000,582 bytes, schema v3 sidecar, SHA-256 checked by `window_min.py`).

Counts:

| Item | Value | Clause |
|:-----|:------|:-------|
| Ticks published by the node | 300000 | expected |
| Messages received: pose, wrench, mesh | 300000, 300000, 300000 | G-b |
| Complete ticks (all three streams, matched by source stamp) | 300000 | G-b |
| Partial ticks | 0 | G-b, G-c |
| Missing complete ticks against 300000 | 0 | G-c |
| Mesh tick-index range and unique indices | 0 to 299999, 300000 unique | G-c |
| Mesh tick-index gaps and duplicate messages | 0, 0 | G-c |
| Non-finite messages | 0 | reported |
| Late ticks at the node | 5 | reported |

Rate, pre-registered definition `(N - 1) / (t_last - t_first)` with N = 300000: `t_first` to `t_last` is 599.997757 s, so the value is 299999 / 599.997757 = 500.000203 Hz. The record field `wrench_achieved_mean_rate_hz` gives 500.000203 as well.

One-minute window minimum (pre-registered: non-overlapping 60 s windows from `t_first`, complete ticks per window divided by 60 s, minimum over ten windows; computed by `tools/window_min.py` from the sidecar, stored value matches the recomputed value):

| Window | Start (s) | Complete ticks | Rate (Hz) |
|:----|:----|:----|:----|
| 0 | 0 | 30001 | 500.017 |
| 1 to 8 | 60 to 480 | 30000 each | 500.000 |
| 9 | 540 | 29999 | 499.983 |

The ten-window minimum is 499.983 Hz (window 9). It is 500.000 minus one tick over the 60 s window. The window total is 300000, so the one-tick shortfall in window 9 is matched by the one extra tick in window 0. The run span of 599.997757 s is 2.2 ms shorter than the 600 s window cover. This is consistent with an edge placement effect, not a rate deficit, but the per-tick arrival times at the edges were not inspected. The statistic is applied as pre-registered and is not corrected for edge placement. The 60 s runs gave 500.000 Hz exactly.

Per-topic interval statistics (milliseconds). Source stamps are `header.stamp` on the node clock. Arrival intervals are `time.perf_counter_ns()` at callback entry on the subscriber clock. Each row covers 299999 intervals.

| Topic | Clock | Mean | p50 | p95 | p99 | min | max |
|:------|:------|:-----|:----|:----|:----|:----|:----|
| Tool-tip pose | source stamp | 2.0000 | 2.0084 | 2.0782 | 2.1743 | 0.0176 | 6.6204 |
| Tool-tip pose | arrival | 2.0000 | 2.0089 | 2.1266 | 2.2398 | 0.3957 | 8.9984 |
| Wrench | source stamp | 2.0000 | 2.0084 | 2.0782 | 2.1743 | 0.0176 | 6.6204 |
| Wrench | arrival | 2.0000 | 2.0075 | 2.1734 | 2.2992 | 0.3933 | 9.0614 |
| Mesh deformation | source stamp | 2.0000 | 2.0084 | 2.0782 | 2.1743 | 0.0176 | 6.6204 |
| Mesh deformation | arrival | 2.0000 | 2.0054 | 2.2182 | 2.3528 | 0.2328 | 9.0986 |

The source-stamp rows are identical because the node gives the three messages of a tick the same stamp. The source-stamp maximum of 6.62 ms and minimum of 0.018 ms are one late tick seen as a long interval and the following short interval (about 2 + 4.6 ms and 2 - 1.98 ms). The arrival maxima of 9.0 ms are subscriber-side outliers that do not move the p95 or the rate.

Source-versus-arrival agreement (slice 2a tolerances: mean difference within 1 percent of the 2 ms period, p95 difference within 1.0 ms; reported only):

* Pose: mean difference fraction 5.9e-7 of the period, p95 difference 0.048 ms. Pass.
* Wrench: mean difference fraction 9.6e-7, p95 difference 0.095 ms. Pass.
* Mesh: mean difference fraction 1.1e-6, p95 difference 0.140 ms. Pass.
* Message counts per topic match the source-stamp interval counts on all three topics.

Late ticks and stamp excursions: 5 late ticks at the node. The sidecar grid check finds 5 source-stamp excursions of 2 ms or more above the median band, the largest 4.77 ms, with drift -0.042 ms over the run. The late ticks are the same mechanism as in work item 1 (schedule on grid, one-tick displacement).

### Verdict

Verdict against the G2.4 clauses for the 600 s synthetic run (pre-registered rule: PASS only if G-a, G-b, and G-c all pass):

* G-a (sustained rate at or above 500 Hz at the subscriber, `(N - 1) / (t_last - t_first)`): PASS. 500.000203 Hz over 599.997757 s, margin 0.0002 Hz.
* G-b (pose and mesh state present on every publish tick, 300000 with all three streams, zero partial): PASS. 300000 of 300000.
* G-c (zero missing against 300000, zero mesh index gaps and duplicates): PASS. 0 missing, 0 gaps, 0 duplicates.
* Reported, not gated: 1-minute window minimum 499.983 Hz (window 9). The minimum is below 500.000 Hz by one tick. This is reported as a finding and is not a gate failure under the pre-registered rule. The plan owner decides whether the window statistic should gate in a later slice. Late ticks at the node: 5.

Overall: PASS for G-a, G-b, and G-c, with the boundaries below. This re-run supersedes the window-statistic gap of the gate run at commit 819081c. The window statistic is now computed from the v3 capture and reads 499.983 Hz.

Boundaries, recorded as part of the verdict:

1. Data source: the node publishes the deterministic synthetic trajectories of `bridge_node`. The SOFA outputs replace them in the SOFA replay integration slice, and this gate is repeated on that data then.
2. Structural coverage: FR-MS-004 carries the obligation of 100 percent statement, branch, and MC/DC coverage on the C++ bridge. That obligation is not met by this run and is tracked in the coverage work.
3. Measurement host: one Windows 11 Pro machine, with the Fast DDS loopback path. Network transport is not exercised.
4. Late ticks: 5 at the node in this run and 0 to 91 in the replay runs. The cause is not isolated (work item 1).

### Files changed and not changed

Changed in this slice: `sim/bridge/tools/run_smoke.ps1` (the `-NoValueCheck` switch, recorded in the run tag as `valuecheck-off`) and this log. Captures in `SNDEV/logs/` are gitignored and not committed.

Not changed: `DEVELOPMENT_PLAN.md`, `sim/SOUP.md`, `SRS.md`, `vv/`, `sim/sofa/`, `sim/segmentation/`, `sim/fmi/`, and `env/`. No push.
