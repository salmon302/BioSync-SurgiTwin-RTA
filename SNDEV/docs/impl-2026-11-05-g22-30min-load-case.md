Title: G2.2 30-minute load case measurement on the reference scene (task 2.2 slice 2)
Date: 2026-11-05T02:54:46Z
Author: Seth Nenninger (Builder_Int29 Agent)
Contribution Type: Implementation
Ticket/Context: task 2.2 slice 2, gate G2.2 measurement
Summary: Measurement-only run of the pinned G2.2 reference scene through the slice-1 step-timing harness over a 30-minute wall-clock stepping window, recording step-time statistics, the budget count, and the divergence verdict.

## Task Reference

* DEVELOPMENT_PLAN.md Phase 2, task 2.2 slice 2: run the 30-minute G2.2 divergence load case on the reference scene and record the result. The plan file is not edited.
* SRS FR-MS-002 and gate G2.2 (proposed): "Solver step completes within the 16.7 ms frame budget of 60 FPS on the reference scene, with no divergence over a 30-minute load case." Divergence (SRS Section 5) is non-finite output or a monotonically growing strain-energy norm.
* Predecessor: `SNDEV/docs/impl-2026-10-15-sofa-scene-slice1.md` (commit `3beb6f0`).

## Specification Summary

* Measure the per-step animation wall time of `sim/sofa/src/reference_scene.scn` headless with `sim/sofa/src/run_reference_scene.py`, over at least 30 minutes of measured stepping.
* Apply the three clauses of the G2.2 metric: (a) step within the 16.7 ms budget, judged on the max statistic and on the p95 statistic reported separately; (b) no divergence over the load case; (c) anomalies (process interruption, memory growth, disk).
* The gate wording question (max or p95) is an open decision for the document owner. This log reports the numbers for both readings and does not decide the gate.
* Measurement only. No source, scene, mesh, plan, or existing log is changed. No commit is made.

## Implementation Notes

### Harness invocation

The harness accepts a step count only (`--steps`), not a duration. Step count is sized from the slice-1 mean of about 11.7 ms per step: 30 minutes is 1800 s, and 1800 s divided by 11.7 ms is about 153,850 steps, so 160,000 steps gives about 31.2 min of stepping at the slice-1 mean. The scene dt is 0.001 s, so 160,000 steps is 160 s of simulated time; the 30-minute figure in the gate refers to wall-clock stepping as stated in the task.

Command: `python sim/sofa/src/run_reference_scene.py --steps 160000 --label g22-30min-160000steps`

### Host state before the run

* Quiet-host check run at 2026-11-05T02:54:46Z: no runSofa.exe process was running. An `opencode` process (PID 29404) and several VS Code Insiders processes were resident, and about 32.9 GB of 50.3 GB physical memory was free. These are the session host and editor, and were not stopped.

### Capture

* Capture file: `SNDEV/logs/sofa-2026-11-05-g22-30min-160000steps.json` (schema `g22-step-timing-v1`, 2,225,169 bytes, gitignored).
* Exit code 0; steps measured 160000 of 160000 requested.
* Wall-clock duration of the runSofa process and harness: 2420.7 s (40.3 min).
* Measured stepping (sum of per-step animation times): 160000 times 11.604 ms, about 1856.7 s (30.9 min). This exceeds the 30-minute stepping window of the gate wording.
* PCG iterations constant at 26 on every step (count 160000, min 26, max 26).
* Scene `[WARNING]` count 0. Two `[ERROR]` lines, both the install-level `readBasicIniFile()` message already recorded as benign in slice 1.

### Step-time statistics (160000 steps)

| Statistic | Value (ms) |
|---|---|
| Mean | 11.604 |
| p95 (nearest rank) | 12.430 |
| Max | 41.520 |
| Min | 10.830 |
| Mean, steps 1 to 1000 | 11.652 |
| Mean, final 10000 steps | 11.527 |
| p95, final 10000 steps | 12.330 |

### Budget against 16.7 ms

* Over-budget steps: 127 of 160000 (0.079 percent). The harness does not store wall-clock timestamps per step, so each over-budget step is identified by its step index (1-based) in the run.
* Over-budget steps are spread across the run. The first five 1000-step blocks have none. Over-budget steps occur in 72 of the 160 blocks, with the largest block count 7 (steps 153001 to 154000). The final 10000 steps are not free of over-budget steps.
* 12 of the 127 over-budget steps fall on a WriteState dump index (step divisible by 10). About 13 would be expected by chance, so the dump period does not explain the over-budget steps.
* Worst 20 steps (step index, ms): 5320 (41.52), 5321 (33.43), 54569 (30.84), 107154 (28.33), 103915 (27.62), 153595 (24.62), 107155 (22.80), 54570 (22.78), 39477 (22.66), 153596 (22.16), 54571 (21.78), 48161 (21.38), 54551 (21.09), 152724 (20.56), 16601 (19.99), 153598 (19.69), 138333 (19.55), 121666 (19.32), 21836 (19.31), 153597 (19.20).
* The two worst steps (5320, 5321) are adjacent, which suggests one stall event rather than two independent jitter events.

### Divergence check (harness definition)

* Samples: 16000 (WriteState every 10 steps). Finite outputs: True (no non-finite sample).
* Monotonic growth on the second half (samples 8000 to 15999): False. The series is flat at 2.22939e-4 to the printed precision. Zero successive increases occur in the second half, and the growth clause requires every successive value to increase and a total growth over 1 percent, so the clause does not trigger.
* Divergence verdict: OK (finite and not growing). Result: PASS on clause (b) under the harness definition.

### Load-on transient

* Slice 1 flagged monotonic growth on the 1000-step run because the second half of a 1.0 s window still contained the settling transient (1.30 percent rise).
* This run: the energy series reaches within 1 percent of its final plateau by sample 53, which is step 530. The harness flag is evaluated only on the second half (steps 80000 to 160000), so the start-up phase is not evaluated by the flag itself. The flag is False here because the window is 160 s long and the second half is already on the plateau, not because the start-up transient was excluded.
* Consequence: the 1000-step flag from slice 1 is a short-window artifact. It does not recur at 30-minute scale and does not persist past the settling time (about 0.3 s of simulated time per slice 1).
* Step-time transient: the first 1000 steps average 11.652 ms, close to the run mean. The single largest outlier (41.52 ms) is at step 5320, after warm-up, so start-up does not account for the max.

### Anomaly check (clause c)

* Process interruption: none. Exit code 0, full step count produced, no timeout.
* Memory growth: not sampled during the run. The harness does not record RSS. No symptom of growth was visible in the step-time series (final 10000 steps mean 11.527 ms, below the run mean).
* Disk: capture file 2.2 MB. No disk error reported.
* Host: an `opencode` process (PID 29404) and VS Code Insiders processes were resident before the run and were not stopped. No other runSofa or heavy process was started during the run by this agent.

### Gate reading (not decided here)

Numbers for the two readings of the G2.2 budget clause:

* Max reading: 41.520 ms against 16.7 ms. FAIL (127 steps over budget, 0.079 percent).
* p95 reading: 12.430 ms against 16.7 ms. PASS, margin 4.27 ms (p95 over the final 10000 steps is 12.330 ms).

Divergence clause (b): PASS under the harness definition over 160000 steps (about 160 s of simulated time, 30.9 min of measured wall-clock stepping).

Whether G2.2 asserts on max or on p95 is an open decision for the document owner.
