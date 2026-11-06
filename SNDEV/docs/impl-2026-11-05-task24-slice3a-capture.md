Title: Per-message capture timestamps and SOFA replay source contract (plan task 2.4 slice 3a)
Date: 2026-11-06T01:28:15Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.4 slice 3a, closes the capture-timestamp defect recorded in the G2.4 gate run (`SNDEV/docs/impl-2026-11-05-task24-g24-gate-run.md`)
Summary: Adds per-message arrival and source timestamps to the subscriber capture (schema v3) so the 1-minute window minimum is computable, and adds a CSV replay source to the node as the SOFA integration contract.

## Task Reference

Plan task 2.4, slice 3a. Two defects from the G2.4 gate-run record (`SNDEV/docs/impl-2026-11-05-task24-g24-gate-run.md`, Defects section):

1. Capture gap: `tools/measure_rate.py` (schema v2) stores interval statistics and counts, not per-message timestamps. The pre-registered 1-minute window minimum could not be computed.
2. Data source: the node publishes synthetic trajectories. The SOFA outputs need an integration contract. Replay is the testable SIL path.

The 600 s gate re-run on the new capture is a later slice and is not run here. `DEVELOPMENT_PLAN.md` is not edited in this slice. Results are reported to the plan owner for consolidation.

Predecessor logs: `SNDEV/docs/impl-2026-11-05-task24-slice1-bridge.md`, `SNDEV/docs/impl-2026-11-05-task24-slice2a-timing.md`.

## Specification Summary

Defect 1, capture:

* Each message carries its arrival timestamp (`time.perf_counter_ns()` at callback entry) and its source stamp (`header.stamp` in ns).
* One wall-clock anchor is recorded once per run, paired with the perf-counter value taken at the same moment.
* The record can be re-aggregated into non-overlapping 60 s windows from `t_first`.
* Encoding is compact (delta-encoded integers per topic). The size budget is recorded below.
* The 1-minute window minimum is recomputed from the new format for a run of at least 60 s.

Defect 2, replay source:

* The node reads a capture file (documented schema: tick index, time, tool-tip pose, wrench, modal deformation coefficients on the 500 Hz grid) and publishes it at real-time rate, with a loop option, instead of the synthetic generator.
* `timer_mode` behavior is kept. No allocation in the publish loop: the file is parsed and preallocated at load.
* One replay capture is generated from a synthetic run of the project generator. It is recorded as synthetic, not SOFA data.
* Verification: the node publishes the replay capture back with zero missing ticks over 60 s at 500 Hz.

Scope: `sim/bridge/` and `SNDEV/logs/` captures, plus this log. No edits to `sim/segmentation/`, `sim/fmi/`, `env/`, `vv/`, `SRS.md`, `sim/SOUP.md`, or `DEVELOPMENT_PLAN.md`. No push.

## Implementation Notes

Quiet-host checks before each verification run (Get-Process for Warhammer, Roblox, RobloxPlayerBeta, runSofa, colcon, Slicer; three CPU samples): no listed process in any check. CPU total 3 to 6.5 percent (24 logical CPUs). The 500 Hz runs proceeded. The 100 Hz deferral was not needed.

### Files changed

* `sim/bridge/src/bridge_node.cpp`, `sim/bridge/include/srtra_bridge/bridge_node.hpp`: replay source. New parameters `source`, `replay_file`, `replay_loop`. The CSV is read in two passes at load, validated, and stored in a reserved `std::vector<ReplayRow>`. Synthetic mode and the timer code are unchanged.
* `sim/bridge/tools/measure_rate.py`: schema `srtra-bridge-rate-measure/3`. Writes the per-message sidecar, the clock anchor, the window statistic, and (with `--expect-csv`) a per-message value check.
* `sim/bridge/tools/window_min.py` (new, SPDX MIT): sidecar codec, window statistic, and a re-check command.
* `sim/bridge/tools/make_replay_capture.py` (new, SPDX MIT): generator for a synthetic replay capture.
* `sim/bridge/tools/run_smoke.ps1`: `-Source synthetic|replay`, `-ReplayFile`, `-ReplayLoop`. The tag now includes the source.
* `sim/bridge/README.md`: replay schema (the SOFA interface contract), parameters, capture schema v3, size budget, and the window statistic.

### Capture schema (defect 1)

Record: `srtra-bridge-rate-measure/3`, with `clock_anchor` (one `time.time_ns()` and one `perf_counter_ns()` taken together at subscriber start), `data_source`, `window_statistic`, `per_message` (file name, SHA-256, bytes), and `value_check` when replay is checked.

Sidecar: `<tag>.messages.json`, schema `srtra-bridge-messages/1`, compact JSON. Per topic: `arrival_perf_ns` and `source_stamp_ns` as `{"first": int, "delta": [int]}`. The mesh topic also has `tick` in the same form. The arrival wall-clock time of a message is `wall_utc_ns + (arrival_perf_ns - perf_counter_ns)`.

Size budget: 16.7 bytes per message (measured: 1,499,730 bytes for 90,000 messages in a 60 s run). Projections: 60 s at 500 Hz, three topics, about 1.5 MB. 600 s at 500 Hz, three topics (900,000 messages), about 15 MB. The record file stays a few kB. Captures are written to `SNDEV/logs/`, which is gitignored, so they are not committed.

### Window statistic

Definition (pre-registered in the G2.4 gate run): tick complete when pose, wrench, and mesh share a source stamp. Tick time is the wrench arrival. `t_first` is the first complete tick. Windows of 60 s from `t_first`. Window count is `floor(span / 60 s) + 1`, which gives ten windows for a 600 s run. The statistic is the minimum of count / 60 s over the windows.

For the 60 s run, the single window holds all 30000 complete ticks, so the value is 500.000 Hz. The 600 s value needs the gate re-run (later slice).

`window_min.py <record.json>` recomputes the statistic from the sidecar, checks the SHA-256, and compares the result with the stored value. It matched on the 60 s run.

### Replay source (defect 2) and the interface contract

The contract is in `sim/bridge/README.md`, section "Replay source (SOFA integration contract)". Columns: `tick`, `time_s`, `pos_x..pos_z`, `quat_x..quat_w`, `force_x..force_z`, `torque_x..torque_z`, then `mode_0..mode_(M-1)` with M from 1 to 16. The loader rejects: a wrong header, a tick that is not consecutive from 0, a `time_s` off the `rate_hz` grid by more than 1 us, a quaternion norm off 1 by more than 1e-6, a non-finite value, and a field count that does not match the header. Each error carries the line number.

The loader accepts a leading UTF-8 byte-order mark. The first version of the loader rejected one, which the off-grid test found. The fix is in the build recorded in `SNDEV/logs/bridge-build-2026-11-06-slice3a-bom.txt`, and runs R2 and R3 used that build.

Generated capture: `SNDEV/logs/replay-synthetic-500hz-60s.csv` (30000 rows, 10,356,310 bytes, SHA-256 `e9e7260e44c20aa8cb18a6784f08b28efb9f0cc21d37c41af2933567c6e1b114`). Provenance sidecar `replay-synthetic-500hz-60s.meta.json` states `source: synthetic`. The generator is `tools/make_replay_capture.py`, which mirrors the synthetic formulas of `fill_tick`. This is synthetic data, not SOFA output.

### Verification runs

Command for the reported runs: `sim\bridge\tools\run_smoke.ps1 -Rates 500 -Duration 60 -Source replay -ReplayFile SNDEV\logs\replay-synthetic-500hz-60s.csv`. Node timer `high_resolution`, subscriber `wait` spin.

Build: `sim\bridge\build.ps1` exit 0 with no warning or error lines (logs `SNDEV/logs/bridge-build-2026-11-06-slice3a.txt` and `...-slice3a-bom.txt`).

| Run (JSON in `SNDEV/logs/`) | Binary | Ticks published | Complete ticks | Missing | Gaps | Late ticks (node) | Achieved rate (wrench, (N-1)/span) | 1-minute window min | Value mismatches (pose, wrench, mesh) |
|:----|:----|:----|:----|:----|:----|:----|:----|:----|:----|
| R1 `...-source-replay-...-2026-11-06T013215Z.json` | before BOM fix | 30000 | 30000 | 0 | 0 | 0 | 500.00188 Hz | 500.000 Hz | 0, 0, 0 |
| R2 `...-source-replay-...-2026-11-06T013532Z.json` | final | 30000 | 30000 | 0 | 0 | 91 | 500.00143 Hz | 500.000 Hz | 0, 0, 0 |
| R3 `...-source-replay-...-2026-11-06T013703Z.json` | final | 30000 | 30000 | 0 | 0 | 35 | 500.01614 Hz | 500.000 Hz | 0, 0, 0 |

Reported run for the verification: R2 and R3 are the final-binary runs. R1 is kept because it was taken before the BOM change and it matched on every other count.

Per-topic source-versus-arrival agreement (run R2, same check as slice 2a: mean within 1 percent of the 2 ms period, p95 within 1.0 ms). Mean fraction of the period and p95 difference are: pose 6.9e-6 and 0.132 ms; wrench 8.7e-6 and 0.177 ms; mesh 9.5e-6 and 0.234 ms. All three pass. Message counts match the source stamps on all three topics. Arrival maximum is 25.7 to 25.8 ms on all three topics in R2 (one host scheduling outlier at the subscriber side), and the source-stamp interval p95 is 2.13 ms.

Pre-registered rate definition `(N - 1) / (t_last - t_first)`: R2 gives 29999 / 59.9978 s, which is 500.0014 Hz. R3 gives 500.0161 Hz.

Late ticks: the replay runs show 0, 91, and 35 late ticks of 30000 (R1, R2, R3). The 60 s synthetic control on the final binary (`bridge-smoke-500hz-60s-source-synthetic-timer-high_resolution-spin-wait-2026-11-06T013823Z.json`) shows 0. A manual replay control without the subscriber value check (`bridge-control-replay-noexpect-500hz-60s.json`, same binary and node settings) shows 0. The subscriber value check is one candidate cause for the replay late ticks, and it is not confirmed: the sample is one run per arm. This is recorded as a finding. The late-tick count is repeated in the 600 s gate re-run.

Loop test (run `bridge-smoke-500hz-6s-source-replay-...-2026-11-06T013356Z.json`, before the BOM change, replay file `replay-loop-test-synthetic-500hz-2s.csv`, 1000 rows): 3000 complete ticks over 6 s with the capture repeated three times, 0 missing, 0 gaps, 0 value mismatches. The mesh tick index runs to 2999, so the tick index keeps counting in loop mode.

Load-time rejection: a copy of the 2 s capture with the time of tick 5 moved to 0.0101 s is rejected with `bridge_node failed: replay line 7 time_s is off the 500 Hz grid` (exit 1), file `replay-bad-offgrid-test.csv`, transcript `replay-bad-err.txt`.

Synthetic regression (final binary, 60 s, 500 Hz): 30000 complete ticks, 0 missing, 0 gaps, achieved 499.99917 Hz, window minimum 500.000 Hz, late ticks 0. The v3 record is written for the synthetic source too.

Subscriber stderr files were empty for the replay and synthetic runs listed above. The node stderr files contain only rclcpp log lines.

### Not changed in this slice

No edits to `DEVELOPMENT_PLAN.md` (plan rows are for consolidation). No edits to `sim/segmentation/`, `sim/fmi/`, `env/`, `vv/`, `SRS.md`, or `sim/SOUP.md`. No 600 s gate re-run. No push. The untracked `SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md` and the modified `sim/segmentation/` files belong to other work and are not staged.

### Open items for the plan

* The 600 s gate re-run on the new capture (window minimum over ten windows, late-tick count, and the value check on a 600 s replay). A 600 s replay capture is 300000 rows, about 104 MB as CSV at the 60 s density, and it is not generated in this slice.
* Late ticks on the replay path (0, 91, 35 in three runs) need a repeat set (for example, value check on and off, several runs each) before the replay path is used as a timing baseline.
* SOFA-side capture production is the SOFA builder's task. The contract is fixed in `sim/bridge/README.md`.
