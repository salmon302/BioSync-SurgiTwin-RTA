Title: G2.2 budget-fit reference scene and PCG margin work (task 2.2 slice 4)
Date: 2026-11-06T12:56:59Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: task 2.2 slice 4, gate G2.2 closure on a budget-fit reference scene (owner ruling 2026-11-06, "Budget-fit scene + margin")
Summary: Selects the highest G2.1 decimation level whose 1000-step run predicts both VAL-029 clauses, tests two PCG configurations at that level, runs the 30-minute load case and the OQ short-mode test on the final scene, and corrects the segmentation provenance flag.

## Task Reference

* DEVELOPMENT_PLAN.md Phase 2, task 2.2 and gate G2.2 (VAL-029 clauses, SRS v1.3.0): p95 at most 16.7 ms across a 30-minute load case, at most 0.1 percent of steps above 16.7 ms with the maximum recorded, no divergence.
* Predecessor: `SNDEV/docs/impl-2026-11-06-g22-remeasure.md` (commit 909c1d6). At the 16 mm level (2490 tets) the 30-minute run FAILED clauses (a) and (b): p95 23.380 ms, 80900 of 80900 steps over budget.
* Owner ruling 2026-11-06 ("Budget-fit scene + margin"): fix the reference scene at the highest decimation level that meets both clauses, record the resolution as a documented design parameter, keep full-resolution G2.1 geometry in the offline and reduced-order path, and run one preconditioner slice to widen the margin.
* Segmentation provenance correction: the owner-directed flag fix for `is_g21_reference` in `sim/segmentation/` (item 4 of the ruling).

## Specification Summary

* Level scan at 17 mm and 15 mm (1000 steps each, same harness and chain), with 16 mm and 18 mm already measured. Selection criterion is fixed before the 30-minute run.
* At most two PCG configuration variants at the chosen level. Keep a variant only if it widens the margin and leaves the static solution unchanged.
* 30-minute VAL-029 load case on the final scene, under the quiet-host check. Then the OQ short-mode test as the verification pass; the test is not edited.
* Segmentation: `is_g21_reference: true` for the HCC_001 evaluation outputs; the SEG-derived `reference/` labelmaps keep their own flag.
* `DEVELOPMENT_PLAN.md`: gate G2.2 status, task row 2.2 note, and one Phase 2 Status sentence.

## Implementation Notes

### Level scan (current chain: EulerImplicitSolver + PCGLinearSolver, 25 iterations, tolerance 1e-9)

Each level was run with `run_reference_scene.py --steps 1000` on a scratch scene directory under `SNDEV/logs/g21-scan-cell<mm>/scene/` (the repo scene differs only in `totalMass` and the base box, taken from that level's provenance). Mesh provenance is in each `meshes/g21_provenance.json`.

| Cell (mm) | Tets | Mean (ms) | p95 (ms) | Max (ms) | Steps over 16.7 ms | PCG min/mean/max | Divergence (1000 steps) |
|---|---|---|---|---|---|---|---|
| 20 | 1230 | 11.026 | 11.940 | 12.910 | 0 of 1000 | 26 / 26.00 / 26 | ok True |
| 19 | 1422 | 11.572 | 12.640 | 13.930 | 0 of 1000 | 1 / 8.32 / 26 | ok False: 70 of 100 samples non-finite from sample 30 |
| 18 | 1656 | 15.045 | 16.290 | 23.500 | 13 of 1000 | 26 / 26.00 / 26 | ok True |
| 17 | 2010 | 17.683 | 19.110 | 23.690 | 1000 of 1000 | 26 / 26.00 / 26 | ok True |
| 16 | 2490 | 22.254 | 23.980 | 28.830 | 1000 of 1000 | 26 / 26.00 / 26 | ok True |
| 15 | 2982 | 23.452 | 25.670 | 28.390 | 1000 of 1000 | 1 / 5.45 / 26 | ok False: 82 of 100 samples non-finite from sample 18 |

Failure analysis of the 15 mm and 19 mm runs: the positions dump is finite, so the non-finite samples are element inversion. In the 15 mm probe (300-step rerun) the minimum det J falls to 0.42 by step 150, then 46 tets invert at step 180 and 1100 or more invert by step 240, with det J reaching about -7e11 by step 290. The PCG iteration count falls to 1 on some steps, which indicates solver breakdown at the 25-iteration cap, not a converged solution. The 19 mm run has the same signature. Levels 16, 17, 18, and 20 stay at the cap of 26 iterations and do not diverge. The default chain is therefore not stable across mesh sizes, and the margin is thin.

### Selection criterion (fixed before the 30-minute run)

Among the scanned levels, select the finest (most tets) level for which the 1000-step run predicts both VAL-029 clauses can hold, with the criterion:

* p95 at most 16.7 ms with margin, and
* zero steps over 16.7 ms in the 1000-step run (projected over-budget fraction at or below 0.1 percent of steps, cap of 80.9 steps in 80900), and
* divergence check ok True with no non-finite sample and no PCG breakdown.

Result: 16 mm, 17 mm, and 15 mm fail the p95 clause. 18 mm meets p95 (16.29 ms) but projects 1.3 percent of steps over budget, so it fails the 0.1 percent clause. 19 mm meets timing but fails divergence. 20 mm (1230 tets) is the only level that meets every criterion.

Selected level: 20 mm cell, 1230 tets, 405 nodes. Predicted margins from the 1000-step run: p95 11.940 ms, a headroom of 4.76 ms (28.5 percent below the 16.7 ms limit); over-budget projection 0 of 1000 steps (0 percent against the 0.1 percent cap); divergence ok. These are 1000-step predictions. The 30-minute run is the gate measurement.

Caveat recorded before the run: the 19 mm divergence shows that a level can pass a 1000-step timing check and still lose solver stability later in the run. The 30-minute run and the OQ short mode are the checks for the selected level.

Because the selection is made on the default chain, the preconditioner slice (below) runs on the selected 20 mm scene and is not used to re-select the level.

### Preconditioner slice (20 mm scene, two variants)

Build notes from the pinned SOFA v26.06.00 install. The bundled examples `share/sofa/examples/Component/LinearSolver/Preconditioner/FEMBAR_PCG_*Preconditioner.scn` use `PCGLinearSolver preconditioner="@..."`. On the default assembled system, both `JacobiPreconditioner` and `BlockJacobiPreconditioner` log `[WARNING] A linear system has been found, but not the expected type`, and the bundled block example logs the same warning, so the warning is a build-level property. Templates offered by the default system were `FullVector` (block) and `DiagonalMatrix` (Jacobi), so a `MatrixLinearSystem` component was added to make the system explicit. The `PCGLinearSolver` still logs the same type warning with the explicit system, and its iteration count changes, which shows the preconditioner is applied.

Variant A, `BlockJacobiPreconditioner` with `MatrixLinearSystem` (scene `SNDEV/logs/g22-pcg/t_matlin_block/scene/`).
Variant B, `JacobiPreconditioner` with `MatrixLinearSystem template="DiagonalMatrix"` (scene `SNDEV/logs/g22-pcg/t_matlin_jacobi/scene/`).

Both variants were measured with the same 1000-step harness at the 20 mm level:

| Configuration | PCG min/mean/max | Mean (ms) | p95 (ms) | Max (ms) | Steps over 16.7 ms | Divergence |
|---|---|---|---|---|---|---|
| Default chain (baseline, 20 mm) | 26 / 26.00 / 26 | 11.026 | 11.940 | 12.910 | 0 of 1000 | ok True |
| Variant A, block Jacobi | 19 / 22.99 / 26 | 11.753 | 12.710 | 13.830 | 0 of 1000 | ok True |
| Variant B, Jacobi | 19 / 23.86 / 26 | 11.520 | 12.520 | 14.630 | 0 of 1000 | ok True |

Both variants cut the mean PCG iteration count (from 26 to 22.99 and 23.86), but the per-step preconditioner cost is larger than the saving, so the p95 is worse (12.71 and 12.52 ms against 11.94 ms). Neither variant widens the margin, so the keep rule (widens the margin and leaves the static solution unchanged) rejects both. The default chain is kept.

Static-solution check: not run. The keep rule is conjunctive, and the margin condition already rejects both variants, so the displacement comparison is not needed for the decision. No preconditioner is added to `reference_scene.scn`.

Final scene: the default chain at 20 mm (no preconditioner). The repo scene was updated to the 20 mm meshes (405 nodes, 1230 tets, mass 1.640000 kg, base box `-0.0005 -0.0005 -0.0005 0.2005 0.0005 0.1805`). The regenerated repo meshes are byte-identical (SHA-256 checked) to the scratch copy used for the 30-minute run, so that run covers the final scene.

Note on the default chain: at 20 mm the 25-iteration PCG reaches its cap on every step and never reaches the 1e-9 tolerance. The solution is therefore a capped-iteration approximation. This is recorded as a boundary of the chain, not corrected here.

### 30-minute VAL-029 load case on the budget-fit scene (20 mm, default chain)

Quiet-host check before launch: `Get-Process` found none of Warhammer, Roblox, runSofa, colcon, or Slicer; the 3-sample CPU counter read 0.7, 0, and 0 percent.

Count: 163250 steps, which is 1800 s divided by the 20 mm 1000-step mean of 11.026 ms. Command: `python sim/sofa/src/run_reference_scene.py --steps 163250 --label g22-20mm-30min-163250steps --scene-dir SNDEV/logs/g21-scan-cell20/scene`. Capture: `SNDEV/logs/sofa-2026-11-06-g22-20mm-30min-163250steps.json` (gitignored). Exit code 0, 163250 of 163250 steps measured, wall-clock 2346.5 s, 0 warnings, no errors beyond the install-level `readBasicIniFile()` message.

| VAL-029 clause | Criterion | Result | Verdict |
|---|---|---|---|
| (a) p95 step time | at most 16.7 ms | 11.920 ms | PASS (4.78 ms headroom) |
| (b) steps above 16.7 ms | at most 0.1 percent (cap 163.25 steps) | 20 of 163250 (0.0123 percent) | PASS |
| (b) maximum recorded | recorded | 28.740 ms (mean 11.001 ms, min 8.83 ms) | recorded |
| (c) divergence | no non-finite output, no monotonic growth | finite True, monotonic growth False, 16325 WriteState samples, strain energy flat at 1.307931246 over the tail | PASS |

Over-budget steps by window: 1 in the first 1000 steps, 1 in the final 10000 steps, 20 across the run, so the excess is not a start-up effect. PCG iterations: mean 25.89, min 2, max 26.

Predicted against measured: the 1000-step prediction was p95 11.940 ms with 0 of 1000 over budget. The 30-minute measurement is p95 11.920 ms and 0.0123 percent over budget. Both clauses hold on the full run.

### Provenance flag correction (`sim/segmentation/`, item 4 of the ruling)

Change scope: three tracked source files and the README. The generating scripts and README were changed, the pipeline was rerun, and the sidecars were regenerated.

* `segment_reference.py`: the per-segment pipeline sidecar `is_g21_reference` changed from `False` to `True`, and the manifest flag changed from `False` to `True`. The reference exporter `export_reference_labels.py` already wrote `True` and is unchanged, so the reference-label provenance keeps its own flag.
* `run.ps1`: the `SURGITWIN_SOURCE_NOTE` changed from "smoke dataset, not G2.1 reference data" to "G2.1 reference set (SRS v1.4.0, VAL-030 to VAL-032)".
* `sim/segmentation/README.md`: the flag semantics are stated (HCC_001 is the G2.1 reference set; pipeline sidecars and manifest true; reference sidecars true with the holdout statement and SEG-derived fields keeping the reference-label provenance distinct). The provenance-rule line for the pipeline sidecars now says `true`.
* `sim/sofa/src/prepare_g21_meshes.py`: the scene-mesh provenance top-level flag and source note were updated to match.

Pipeline rerun: `powershell -ExecutionPolicy Bypass -File sim\segmentation\run.ps1` on the pinned Slicer 5.12.4, exit 0, wall 64.3 s, log `SNDEV/logs/segment-run-tcia-hcc-tace-seg-hcc001-20261106T144015Z.log`.

Output verification: the regenerated labelmaps and meshes are byte-identical to the previous outputs (SHA-256 unchanged: parenchyma_liver_labelmap.nrrd 1979E90418E7FD90, vascular_keepout_bone_excluded_labelmap.nrrd 01A3C44AA475B357, tumor_hypoattenuating_labelmap.nrrd 92CA73AA18160D5F, and the three STL meshes). The scene-mesh provenance checksums therefore still hold. The regenerated pipeline sidecars and manifest now carry `is_g21_reference: true` and the new source note. `evaluation.json` has no flag and is unchanged in hash. `input_selection.json` and the provenance sidecars changed only in their timestamps and flag fields.

Scene meshes regenerated after the flag edit (20 mm): all five `src/meshes/` outputs are byte-identical to the scratch copy used for the 30-minute run, and the scene provenance top-level flag reads `true`.

Left unchanged, outside the bounded scope: `sim/segmentation/data/PROVENANCE.md` still says "SMOKE dataset. This is not G2.1 reference data." The ruling covered the generating scripts and README only, so this file is reported for the owner to decide. The output sidecars under `sim/segmentation/output/` are gitignored and are not committed.

### OQ short-mode verification (`vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py`, not edited)

Before the repo scene was updated, the OQ test failed on the 16 mm scene (2000 steps, p95 23.240 ms against 16.7 ms). This is the expected result for the older scene and is recorded here, not hidden.

After the repo scene and meshes were updated to 20 mm: PASSED. The test reports mode short, max 14.470 ms, p95 11.930 ms, mean 11.008 ms over 2000 steps, 0 of 2000 steps over budget (0.000 percent), divergence_ok True. Capture `SNDEV/logs/sofa-2026-11-06-oq-fr-ms-002-solver-rate.json`.
