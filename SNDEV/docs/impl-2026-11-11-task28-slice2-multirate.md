Title: Multi-rate co-simulation master and three-node G2.6 run (plan task 2.8 slice 2)
Date: 2026-11-11T09:00:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.8 slice 2
Summary: Extends the slice-1 master to schedule the thermal, mechanical, and Pulse FMUs at their own rates on a 1 ms master step, measures the master loop wall time, re-runs the single-node skew and jitter on a quiet host, and runs the three-node G2.6 measurement over the pinned ROS 2 Fast DDS layer on one host.

## Task Reference

Plan task 2.8 in `DEVELOPMENT_PLAN.md` (Phase 2 row "2.8 Build the FMI 3.0 co-simulation master with clocks and scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer (VAL-028), with the bounded 1 ms clock-skew and message-jitter measurement of VAL-005 and per-message timestamps recorded", `sim/fmi/master/`, 8.0 d). Requirement FR-MS-007 in `SRS.md` v1.2.0 (VAL-028). Gate G2.6 (SRS): all FMUs pass FMI 3.0 import checks, and measured clock skew and message jitter are each at most 1 ms across a 10-minute three-node Fast DDS co-simulation run against a reference clock, with per-message timestamps recorded.

Prior records: slice 1 `SNDEV/docs/impl-2026-11-05-task28-slice1-master.md` (master core, single node, contended baseline: skew max 5.592 ms, jitter max 4.923 ms). FMU import-check evidence: thermal `SNDEV/logs/fmi-thermal-pennes-check-slice2-2026-11-07.json` (five cases, PASS); mechanical `SNDEV/logs/fmi-mechanical-check-2026-11-07.json` (five cases, PASS); Pulse `SNDEV/logs/fmi-pulse-check-pao2-fix-final-2026-11-07.json` (six cases, PASS).

## Specification Summary

1. Multi-rate schedule on a 1 ms master step: mechanical every master step (its 0.001 s DoStep), Pulse every 10 master steps (0.01 s), thermal every 100 master steps (0.1 s). Document the FMI 3.0 clock mapping and the exchange points in the master README. Record the master loop wall time against the mechanical DoStep budget.
2. Quiet-host single-node re-run of the skew and jitter measurement with the three-FMU schedule. This replaces the contended baseline as the reference number.
3. Three-node G2.6 run: participants on three nodes over `rmw_fastrtps_cpp` on this host (loopback, recorded as a single-host boundary). Ten minutes, all three FMUs stepping per the schedule, against the reference clock, per-message timestamps recorded.
4. If a bound fails, report the numbers and the located failure. Do not tune to pass. Record each attempt.
5. Report-only for the plan.

## Preflight (2026-11-11)

* Host (Get-Process and a 5 s CPU sample, 24 logical processors): Docker Desktop running; `python` (C:\Python314\python.exe) running; no Warhammer, Roblox, runSofa, colcon, Slicer, or ninja process. Total CPU 4.6 to 5.1 percent. The `pulse-fmi-worker` container is up (the expected Pulse precondition, unhealthy by the image HEALTHCHECK, as recorded in slice 3).
* Repo: master core at commit `762954f` (slice 1). Scheduler already supports several participants with periods, offsets, and wires (`sim/fmi/master/include/srtra_fmi_master/scheduler.hpp`). The node `fmi_master_node` hard-wires one thermal participant, so the node must be extended.
* FMU builds: `sim/fmi/build.ps1` builds thermal, mechanical, and Pulse FMUs with zero warnings (2026-11-11 run `SNDEV/logs/fmi-build-task28-s2-2026-11-11.txt`).

## Finding: the 1 ms master step is not real time with the mechanical FMU

Probe (`multirate-probe.py`, no ROS, FMPy 0.3.32, 3000 master ticks at 1 ms, thermal every 100 ticks, Pulse every 10 ticks, mechanical every tick; host CPU quiet):

| Measure (ms) | mean | p50 | p95 | p99 | max |
|:--|--:|--:|--:|--:|--:|
| mechanical DoStep (every master tick) | 11.839 | 11.782 | 12.190 | 12.484 | 18.109 |
| Pulse DoStep (every 10 ticks, n = 300) | 3.219 | 2.686 | 4.550 | 4.854 | 5.154 |
| thermal DoStep (every 100 ticks, n = 30) | 0.157 | 0.140 | 0.154 | 0.491 | 0.491 |
| master tick, all due FMUs | 12.166 | 11.854 | 15.440 | 16.273 | 18.118 |

Consequence. The mechanical FMU needs about 11.8 ms per call, and it is called on every 1 ms master step. The master therefore advances about 80 master ticks per wall second, not 1000. The schedule is exact in simulation time, but a wall-clock publish of one clock message per 1 ms master tick cannot happen on this host. This is a physical limit of the mechanical FMU at dt 0.001 s, not a tuning problem.

Effect on the G2.6 clause. The clause measures skew and jitter of the clock and state messages against a reference clock. If the master publishes each 1 ms tick as its own message, the wall-clock publish interval is about 12 ms, and the jitter of that interval is measured against a 1 ms nominal period that the master cannot meet. The publish design must be decided before the run, and the choice is recorded in the README and in the report.

Bring-up defects found during the slice (fixed before the reference run; recorded here, not hidden):

1. The FMU wrapper passed an empty resource path to `fmi3InstantiateCoSimulation`, so the mechanical worker script was not found (SOFA log: "Cannot load file 'mechanical_worker.py'"). Fixed: `FmuParticipant::create` takes a `resource_dir` (default empty, so the slice-1 call is unchanged), and the multirate node passes each FMU's `resources/` directory.
2. The node read `pulse_port` as a `std::string` parameter. A numeric string on the command line faulted the process in `ucrtbase.dll` (exception 0xC0000409, Windows event log 2026-11-11 20:25). Fixed: the parameter is an integer (`std::int64_t`), and a non-default port is refused.
3. The launcher ran the node without the pixi library directory and the package bin directory on PATH, so the process exited 0xC0000135 (missing DLL) with no output. Fixed in `run_multirate.ps1`.
4. The reference run was launched in the foreground and the tool call timed out at 30 minutes, so the launcher's after-run host snapshot and the node's summary line were lost. The run record and the sidecar were written. The after snapshot was taken 12 minutes later and is labelled as late.

Run-definition finding (changes the reference run). The node runs `duration_s * 1000` master ticks. At the measured wall pace (about 84 ticks per second, probe and reference run), 600000 ticks take about 2 hours of wall time, not 10 minutes. The 600 s reference run therefore measured the first 60234 ticks (720 s of wall time, stopped by the harness collect limit). The per-message data are valid (60234 ticks with consecutive sequence numbers, no duplicates, no gaps), but the run is not "10 minutes of co-simulation". The G2.6 clause defines the run by wall time, so the node must stop on a wall-clock duration. The reference run is therefore recorded as an interrupted run, and the wall-duration run is the one that counts. This is a defect in the run definition, not a tuning choice, and it is recorded before the wall-duration run.

Additional bring-up defects (fixed before the reference and the three-node runs):

5. The node's run length was in ticks (`duration_s * 1000`), not wall time, so a 600 s run stopped at 720 s of wall time, and the first wall-clock fix compared the scheduled target and not the real clock, which made the 10 s smoke run for 119 s of wall time. The loop now compares the real steady clock to the wall end. Verified: the 10 s smoke has an arrival span of 9.99 s and 840 ticks (84 Hz).
6. The three-node launcher started the single-node node binary (`fmi_multirate_node`) instead of the three-node master, so the participants never received a request (steps 0). Fixed: the launcher starts `fmi_three_node_master`.
7. The three-node master exposed no split of the round trip. Added the participant stamps (request received, step done) and the master send stamp, so the round trip is split into request transit, FMU step, and reply transit.
8. The three-node launcher could not read exit codes from the process objects under Windows PowerShell 5 (the fields came back empty). The launcher now takes its verdict from the master's own summary line (`"exit_code":0`) and the written record.

Reference run (single node, quiet host, wall-clock 600 s): record `SNDEV/logs/fmi-multirate-single-node-quiet-600s-2026-11-12T021833Z.json`, sidecar `.messages.json`, launcher `fmi-multirate-single-node-quiet-launcher-2026-11-11.txt`. Host before: total CPU 0.8 percent, no watched process (`...-host-before.txt`). Host after (taken 10 minutes late, 0.2 percent CPU, no watched process; the launcher's own after snapshot was not written): `...-host-after.txt`. Result: 50224 master ticks in 600 s (83.7 Hz); each of the four streams has 50224 messages with consecutive sequences; epoch check passed (0.44 ms). Skew (p50, p95, p99, max absolute, ms): clock 0.214, 0.392, 0.464, 1.680; thermal 0.301, 0.514, 0.614, 1.842; mechanical 0.378, 0.640, 0.811, 1.926; Pulse 0.586, 0.843, 0.953, 2.001. Jitter (arrival interval minus 1 ms, p50, p95, p99, max absolute, ms): clock 10.613, 14.103, 14.916, 21.576; thermal 10.624, 14.083, 14.923, 21.583; mechanical 10.633, 14.052, 14.932, 21.583; Pulse 10.660, 14.000, 14.978, 21.336. Verdict: FAIL on both bounds (skew max above 1 ms on every stream; jitter max above 1 ms on every stream, with the median jitter at 10.6 ms). Located cause: the master loop at 11.95 ms per tick (the mechanical DoStep, 11.8 ms, on every master tick). The 1 ms grid is not held. The reference numbers replace the contended baseline of slice 1.

Three-node G2.6 attempt 1 (10 minutes, nodes on one host over rmw_fastrtps_cpp, loopback): record `SNDEV/logs/fmi-three-node-g26-attempt1-600s-2026-11-12T024234Z.json`, sidecar `.messages.json` (1.40 MB), per-node transcripts `...-node1-master.txt`, `...-node2-mechanical.txt`, `...-node3-pulse.txt`, launcher `fmi-three-node-g26-attempt1-launcher-2026-11-12.txt`. Host snapshots were not written for this run (the three-node launcher does not produce them); the quiet state before the run was checked by hand (0.22 percent CPU, no watched process) and is recorded here, not as a file. Topology: node 1 is `fmi_three_node_master` (clock, scheduler, thermal FMU); node 2 is `fmi_participant_node` running `mechanical_sofa`; node 3 is `fmi_participant_node` running `pulse_physiology` (container worker on 127.0.0.1:5055 as precondition). Protocol: at each master tick, the master publishes a StepRequest to each remote participant that is due (mechanical every tick, Pulse every 10 ticks), waits for the matching StepReply (zero timeouts over 19245 round trips), then advances the scheduler. Result: 17495 master ticks in 600 s (29.2 Hz); each stream 17495 messages with consecutive sequences (the Pulse and mechanical participant node summaries report 1750 and 17495 steps). Skew (p50, p95, p99, max absolute, ms): clock 0.264, 0.441, 0.553, 1.387; thermal 0.364, 0.580, 0.717, 1.538; mechanical 0.492, 0.744, 0.886, 1.640; Pulse 0.664, 0.885, 1.047, 1.819. Jitter (arrival interval deviation from 1 ms, p50, p95, p99, max absolute, ms): clock 30.2, 61.3, 62.4, 77.1; thermal 30.2, 61.3, 62.4, 77.1; mechanical 30.2, 61.3, 62.4, 77.3; Pulse 30.2, 61.2, 62.3, 76.9. Round-trip split (mean, ms): master wait 31.06 (max 47.8); request transit 15.47; FMU step 10.64; reply transit 4.98. Verdict: FAIL on both bounds, on every stream. Located failure: the master-to-participant request/reply loop (the wait is 31 ms against a 1 ms step); the FMU step itself is 10.6 ms (the mechanical DoStep), and the rest of the round trip is the DDS transit on the single host. The failure is recorded as found. It is not tuned.

Decision for this slice (recorded before any timing run, and not changed afterwards): the clause metric is kept as written. The master publishes one clock message per 1 ms master tick on its own schedule. Skew is the arrival stamp minus the source stamp against the reference clock. Jitter is the deviation of each message's wall-clock publish time from its scheduled wall time on the 1 ms grid. A master that cannot hold the 1 ms grid on this host fails the jitter bound, and the run reports that failure with its location (the master loop, the mechanical DoStep). The metric is not redefined to fit the host. A separate diagnostic (the mechanical-paced interval) may be reported beside it, labelled as a diagnostic and not as the G2.6 measure.
