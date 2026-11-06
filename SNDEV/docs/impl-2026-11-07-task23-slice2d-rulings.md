Title: Analytic-balance check, Okamura axial stiffness, cut-trigger ruling, and re-pilot with the pre-registered G2.3 gate (task 2.3 slice 2d)
Date: 2026-11-06T21:46:40Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: task 2.3 slice 2d, follow-up to slices 2, 2b, and 2c (`impl-2026-11-06-task23-slice2-cutting.md`, `impl-2026-11-06-task23-slice2b-fixes.md`, `impl-2026-11-06-task23-slice2c-checks-citations.md`). Owner rulings 2026-11-07 on the three calibration questions. Gate G2.3 status is recorded in the Gate section.
Summary: Replaces the episode check with an analytic-balance check, swaps the axial puncture stiffness for the Okamura 2004 liver polynomial (Liver 1 default, Liver 2 selectable), keeps the G_c times width cut trigger, retires the slice-2 release description in favor of the slice-2c signed-energy definition, re-runs the 100-trial pilot, and runs the pre-registered 1000-trial G2.3 gate.

## Owner rulings (2026-11-07)

1. The episode check becomes an analytic-balance check.
2. The axial puncture stiffness becomes the Okamura pre-puncture polynomial. Liver 1 is the default. Liver 2 is a selectable alternative. K_perp (430 N/m) is retired from the axial role and recorded as the Roesthuis lateral phantom value.
3. The cut trigger stays G_c times width at the published intercept (G_c = 164 J/m^2, width 1.0 mm, trigger 0.164 N).
4. The 1000-trial gate run threshold is raised: run it in the background as the 4.3 hour projection authorizes, once the re-pilot is clean.

## Task Reference

* Slice 2c log (`impl-2026-11-06-task23-slice2c-checks-citations.md`, commit 9160924): the episode rule, the signed-energy release, and the verified citations.
* Owner-supplied PDFs in `SNDEV/research/` (read-only, not committed).
* No edits to `DEVELOPMENT_PLAN.md`, `sim/SOUP.md`, `sim/segmentation/`, `sim/fmi/`, `sim/bridge/`, `env/`, `vv/`, or `SRS.md`.

## Implementation

### 1. Analytic-balance check

The scene (`contact_scene.py`) records, at every tick, the analytic contact sum (`analytic_fx`, `analytic_fy`, `analytic_fz`, the sum of the per-point forces `f_i = min(max(k pen_i - c vn_i, 0), F_cap) n_i`), the sum of the point magnitudes (`sum_abs_point_force_n`), and the largest single-point force (`max_point_force_n`). The runner (`run_contact_suite.py`, `check_trial`) recomputes the predicted tool force at each contact step as

    predicted = analytic - puncture_force_n * d,  d = (sin theta, -cos theta, 0)

and compares it with the recorded bridge force (columns `force_x`, `force_y`, `force_z`). The analytic_balance check passes when all of the following hold:

* every wrench value is finite, and every contact step (contact_points > 0) has recorded force within tolerance of the prediction, where the tolerance is `1e-6 N + 1e-6 x |predicted|`;
* every per-point force is at most `F_cap = 1.0 N` (with a 1e-9 N allowance);
* the summed force norm is at most the sum of the point magnitudes (1e-6 N allowance);
* every zero-peak contact episode (a maximal run of consecutive contact steps whose recorded wrench norm is zero) has a predicted force within the tolerance over that episode, so a zero recording passes only where the analytic model predicts zero.

Basis of the tolerance: the bridge capture writes 9 decimal places per component (absolute resolution about 1e-9 N), and the per-step sums are double precision. A 1e-6 N floor is therefore three orders of magnitude above the write resolution, and a 1e-6 relative term covers accumulated rounding in the sum. The torque is not in this check (the analytic torque is not recorded). The check does not test the contact model itself. It tests the path from the per-point analytic force to the recorded tool wrench, and it fails a broken path (zero recorded where the model predicts a non-zero force).

Former failures (T008 and T032 from slice 2c): the residuals for their zero-peak episodes are in each trial's `evidence.zero_peak_episode_residuals` (`tick`, analytic, recorded, predicted, residual, tolerance) and `evidence.max_balance_residual_n`. Values are in the re-pilot section below.

### 2. Okamura axial stiffness

Axial puncture force: F = (sin^2 phi + A cos^2 phi) (a1 s + a2 s^2), with s the depth past the entry point in mm and F in N (Okamura 2004, Eq. (3), p. 1709). Liver 1 default: a1 = 0.0480 N/mm, a2 = 0.0052 N/mm^2. Liver 2 alternative: a1 = 0.0020 N/mm, a2 = 0.0023 N/mm^2. Select with `--liver liver1|liver2`; the set is recorded in the summary (`liver_set`) and in `calibration.puncture_liver_set`.

The anisotropy factor A = 2.0 is kept as an uncited model choice. It multiplies the polynomial. The fiber direction is the x axis, so cos phi = sin theta for entry angle theta. At 0 degrees the factor is 1. At 30 degrees it is 1.25.

K_perp = 430 N/m is retired from the axial role. The model has no lateral term, so K_perp is unused in the model. It is recorded in the calibration table as the Roesthuis 2011 lateral phantom value (gelatine 35 kPa; Ke optimum, p. 2563), not deleted. The config key `puncture_k_perp` was removed from the scene and the runner.

### 3. Cut trigger and trigger depth

The trigger stays F_cut = G_c w = 164 J/m^2 x 1.0 mm = 0.164 N, with the minimum depth 1.0 mm. The trigger depth is the depth s at which the puncture force reaches 0.164 N (solved numerically on the polynomial with the anisotropy factor, since the force is nonlinear in depth):

| Parameter set | Angle (deg) | Anisotropy factor | Trigger depth (mm) | Force at 1 mm (N) |
|---|---|---|---|---|
| Liver 1 (a1 0.0480, a2 0.0052) | 0 | 1.00 | 2.654 | 0.053 |
| Liver 1 | 30 | 1.25 | 2.206 | 0.067 |
| Liver 2 (a1 0.0020, a2 0.0023) | 0 | 1.00 | 8.021 | 0.004 |
| Liver 2 | 30 | 1.25 | 7.130 | 0.005 |
| Old linear term (K_perp = 430 N/m, retired) | 0 | 1.00 | 0.381 (below the 1 mm minimum, so the effective trigger was 1.0 mm) | n/a |

Consequence for the 8 mm approach depth: with Liver 2 the trigger depth at 0 degrees (8.02 mm) lies beyond the 8 mm approach, so that geometry cannot trigger a cut. At 30 degrees (7.13 mm) it can, only in the last millimetres. With Liver 1 the trigger is reached in the first third of the approach. This is a real effect of the softer polynomial, and it is recorded here, not tuned away.

Cut trigger notes (owner ruling, recorded):

* The 1.0 mm width is outside Gokgol's tested range of 2 to 5 mm diameters. The 164 J/m^2 value is the zero-diameter intercept of the linear fit (Gokgol 2012, p. 885, Fig. 8, p. 886). Using it at 1 mm is an extrapolation. The measured 2 mm value is 110.83 J/m^2 (Table 2, p. 886), which would give 0.111 N at 1 mm of width, with no extrapolation of the width.
* Okamura's F_cutting = 0.94 +/- 0.36 N (p. 1712, Eq. (11)) is an empirical bevel cutting force that includes tip stiffness, for a 1.27 mm OD needle. Read linearly over the diameter, it is about 740 J/m^2. It is recorded as a cross-check and is not reconciled with the trigger.

### 4. Retired release description

The slice-2 release rule (one-ring rest reset of the neighborhood, `release_rings = 1`) is superseded by the slice-2c signed-energy definition: only the crossed tetrahedra are removed; their Neo-Hookean energy is the released energy (non-negative); the neighbor tetrahedra keep their rest configuration; and the total energy changes by exactly minus the released energy. The slice-2 description in `impl-2026-11-06-task23-slice2-cutting.md` and in the README cutting section is superseded by this note and by the README text updated in slice 2c. The rest reset is not used in any run in this slice.

### 5. Re-pilot

Command: `python sim/sofa/src/run_contact_suite.py --label pilot-slice2d --workers 3 --liver liver1`. Output: `SNDEV/logs/task23-cut-pilot-slice2d/`. The re-pilot uses the same 100-trial grid as slices 2 to 2c.

Per-check counts (100 trials, `SNDEV/logs/task23-cut-pilot-slice2d/summary.json`):

| Check | Pass | Fail |
|---|---|---|
| contact_detected | 100 | 0 |
| zero_tunneling | 100 | 0 |
| zero_missed_contacts | 100 | 0 |
| analytic_balance | 100 | 0 |
| topology_integrity | 100 | 0 |
| capture_schema | 100 | 0 |
| wrench_continuity | 100 | 0 |
| culling_reduction | 100 | 0 |
| exit_clean | 100 | 0 |

Trials passing all nine checks: 100 of 100. Cuts: 154. Tunneling steps: 0. Missed points: 0.

Analytic-balance residuals: the largest recorded-versus-predicted residual over all contact steps in all 100 trials is 1.5e-9 N, which is at the bridge write resolution and well inside the 1e-6 N tolerance.

Former failures (slice 2c): T008 and T032 are no longer failing. The Okamura stiffness changed their trajectories, and neither trial now contains a zero-peak contact episode. Their maximum balance residuals are 1.4e-9 N (T008) and 5.6e-17 N (T032). The residual evidence for zero-peak episodes is therefore empty for both. The slice-2c zero-net-force episodes are not reproduced under the Liver 1 stiffness. The change of trajectory is the cause, and it is recorded here, not a tuned check.

### 6. Gate G2.3 (pre-registered)

Pre-registration: this section is written before the gate run. The gate grid is 10 speeds (10, 20, 40, 60, 80, 100, 120, 150, 180, 200 mm/s), 10 entry angles (0, 3.33, 6.67, 10, 13.33, 16.67, 20, 23.33, 26.67, 30 degrees), and 10 entry offsets (z = 0 to 4.5 mm in 0.5 mm steps), giving 1000 trials (G0001 to G1000). The grid is set in `trial_plan(grid="gate")` (verified: 1000 trials). Liver set: Liver 1 default.

Pre-registered clauses. The gate passes only if all of the following hold across the 1000 trials:

* (a) zero tunneling events (no step has the tip inside the organ with zero contact points);
* (b) zero missed contacts (no tool point has a full-boundary swept hit without a contact record);
* (c) finite wrenches under the analytic-balance rule in every trial (the check of item 1);
* (d) topology integrity after every cut (every cut passes `check_integrity`, the driver's and scene's crossed sets agree, and the run exits cleanly).

Any other per-trial check failure is reported with its evidence. The verdict goes to the plan owner with the numbers. The checks are not changed after this section is written.

Quiet-host check before launch (2026-11-06T21:55Z, approximate): no runSofa, Warhammer, Roblox, colcon, Slicer, or other python processes running; CPU samples 0.5, 0.2, and 0 percent (three one-second samples). The host was quiet and the gate was launched.

Projected runtime: the 100-trial pilot took about 26 minutes on three workers (summed trial time about 4600 s). The 1000-trial gate projects to about 4.3 hours on the same three-worker pool. The owner authorized this runtime. The run is a background process.

Gate run status: in progress. Launched 2026-11-06T21:55Z (approximate) as a background process: `python sim/sofa/src/run_contact_suite.py --label gate-slice2d --grid gate --workers 3 --liver liver1`. Output: `SNDEV/logs/task23-cut-gate-slice2d/` (summary and per-trial files; gitignored captures). The gate verdict and per-trial evidence for any failure are appended in the second commit (`test(sim): G2.3 1000-trial gate suite run`).

### 7. Cut energy (distribution)

Per-trial sums of released energy over each trial's cuts, re-pilot (100 trials, 154 cuts): minimum 3.06e-6 J, median 1.24e-5 J, maximum 2.18e-4 J, total 2.43e-3 J. All values are non-negative (signed-energy definition of slice 2c). The total energy change at every cut equals minus the released energy by construction, which was verified in the slice-2c debug traces (identity error 0). Per-cut values are not kept in the pilot summary; the cut records are in each trial's cut list in the driver. The released total is higher than in slice 2c (7.7e-4 J over 155 cuts there). The cause is not analysed in this slice; the trajectories differ between the two re-pilots.

## Gate status

The re-pilot is clean (100 of 100 trials pass all nine checks), so the pre-registered gate was launched under the owner's authorization. Verdict pending (see the gate run status above).

## Plan consolidation (not edited here)

* Task 2.3 row: slice 2d adds the analytic-balance check, the Okamura Liver 1 axial law (K_perp unused), and the G_c times width trigger at the published intercept. Re-pilot 100 of 100 clean. G2.3 gate run in progress.
* Trigger depths: Liver 1 trigger at 2.65 mm (0 degrees) and 2.21 mm (30 degrees); Liver 2 at 8.02 mm and 7.13 mm. The Liver 2 set cannot cut at 0 degrees within the 8 mm approach. This is a consequence for any Liver 2 gate run and should be decided before a Liver 2 run.
* Cutting criterion: G_c times width at the intercept (164 J/m^2, 1 mm, 0.164 N) is an extrapolation beyond Gokgol's tested 2 to 5 mm. Okamura 0.94 N is recorded as a cross-check (about 740 J/m^2 read linearly), not reconciled.
* Plan items to update when consolidated: the gate verdict, the Liver 2 trigger issue, and the released-energy distribution.
* SOUP: no new dependency. Citations: Okamura 2004 (Eq. (3) and Table I, verified), Roesthuis 2011 (verified), Gokgol 2012 (verified), Jackson 2016 (structure support).

## Commit

Commit 1 (`fix(sim): analytic-balance check and Okamura axial stiffness (2.3 slice 2d)`): `sim/sofa/` (README, contact_scene.py, cut_topology.py, run_contact_suite.py including the gate grid option) and this log, with the gate in progress. Commit 2 (`test(sim): G2.3 1000-trial gate suite run`): this log with the gate verdict, if the run completes in this slice. Hashes are recorded in the commit messages.
