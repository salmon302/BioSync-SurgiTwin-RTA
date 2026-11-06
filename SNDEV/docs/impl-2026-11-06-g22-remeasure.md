Title: G2.2 re-measurement on the G2.1 meshes (task 2.2 slice 3)
Date: 2026-11-06T12:02:27Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: task 2.2 slice 3, gate G2.2 re-measurement on the G2.1 meshes
Summary: Replaces the 1296-tet placeholder block of the G2.2 reference scene with a decimated G2.1 segmentation mesh, re-measures step time with the slice-1 harness, and records the 30-minute load case result or its deferral.

## Task Reference

* DEVELOPMENT_PLAN.md Phase 2, task 2.2 (remaining item): "re-measurement on the G2.1 meshes when they replace the placeholder block".
* Gate G2.2 (VAL-029 clauses, SRS v1.3.0): p95 at most 16.7 ms across a 30-minute load case, at most 0.1 percent of steps above 16.7 ms with the maximum step time recorded, no divergence in the load case.
* Predecessors: `SNDEV/docs/impl-2026-10-15-sofa-scene-slice1.md` (scene and harness), `SNDEV/docs/impl-2026-11-05-g22-30min-load-case.md` (placeholder-mesh 30-minute run, p95 12.430 ms, 0.079 percent over budget).
* G2.1 inputs: `sim/segmentation/output/tcia-hcc-tace-seg-hcc001/` (parenchyma_liver chain v4, vascular_keepout_bone_excluded chain v5 with the 1.0 mm margin, tumor_hypoattenuating empty).

## Specification Summary

* Write `sim/sofa/src/prepare_g21_meshes.py`, which converts the G2.1 labelmaps into SOFA Gmsh meshes at a documented resolution, with decimation parameters, source and output checksums, tool versions, and tet and triangle counts recorded.
* Keep the vascular keep-out as a region that survives decimation, and document which representation is used.
* Replace the placeholder block in `sim/sofa/src/reference_scene.scn`, keep the slice-1 solver chain and the material parameters, and keep the tumor node present.
* Run 1000 steps through `sim/sofa/src/run_reference_scene.py` first, then compare against the placeholder baseline.
* Run the 30-minute load case only on a quiet host, otherwise defer it and record the deferral.
* Update `DEVELOPMENT_PLAN.md` gate row G2.2, task row 2.2, and the VAL-032 figures in Section 6.3.

## Implementation Notes

### Mesh preparation (`sim/sofa/src/prepare_g21_meshes.py`)

Inputs are the G2.1 labelmaps and STL meshes under `sim/segmentation/output/tcia-hcc-tace-seg-hcc001/`. All three sidecars carry `is_g21_reference: false` and the source note "smoke dataset, not G2.1 reference data" (TCIA HCC-TACE-Seg HCC_001, CC BY 4.0). The meshes are therefore a timing reference geometry, not G2.1 reference data.

| Source segment | Labelmap SHA-256 | STL SHA-256 | STL triangles |
|---|---|---|---|
| parenchyma_liver (chain v4) | 1979e90418e7fd90d1a44bb90161769ed33718d6aa7394324921830bb23145e0 | f51ffecfa09300d50d64565c1943b5f0518633083aeaee7c29d007c5c78ad561 | 254616 |
| vascular_keepout_bone_excluded (chain v5, 1.0 mm margin) | 01a3c44aa475b3573286d829c63eca2b43f109343edf42959b57a5202ff3958d | a56fcfc9f81176f3e95e1c3a3603dd511179ceb9ede214b990fb714b78efd264 | 107226 |
| tumor_hypoattenuating (empty, zero voxels) | 92ca73aa18160d5f170a2d12f3fb749583c7a5d2e0718469f811100760369be5 | f6a500a0e00953f170c255908c54ba5dbf694740d48a47413b819be4eaf11001 | 0 |

The tetrahedra are built from the labelmap. The STL files are recorded for provenance and are not read by the script.

Decimation parameters (all recorded in `sim/sofa/src/meshes/g21_provenance.json`):

* Target grid cell: 16 mm. The liver envelope is sampled on an isotropic grid. A cell is occupied when at least half of its 4 by 4 by 4 sub-samples fall inside the labelmap (nearest voxel).
* Grid of 15 by 12 by 11 cells. Occupied cells before hole fill: 416. Holes filled: 0. Smaller face-connected components dropped: 1 cell. Occupied cells kept: 415.
* Each occupied cell is split into six tetrahedra around the 000-111 diagonal (the split of `generate_reference_mesh.py`, face-conforming).
* Vertices used by no tetrahedron are dropped. Node ids are 1 to 733.

Counts (16 mm level): 733 nodes, 2490 organ tetrahedra (2490 parenchyma, 0 tumor), 1112 boundary triangles. Every tetrahedron has the same volume, 6.8267e-7 m^3, because all cells are cubes. Total organ volume is 1.69984e-3 m^3, which gives 1.699840 kg at 1000 kg/m^3.

Target rationale: the stated range is 2000 to 8000 tets. The 16 mm level is its low end and the design target. Step cost scales with tet count (see the scaling table below), so the floor of the range is the level least likely to exceed the budget. Other levels scanned, all from the same script: 14 mm gave 3576 tets, 12 mm gave 5754, and 10 mm gave 10080 (above the range). An 18 mm scan gave 1656 tets; it is below the range and is reported as a scaling point, not as the reference.

Keep-out representation: a signed distance field, not tets. At the 16 mm grid the vessels (0.78 by 0.78 by 5 mm sampling, lumens of a few millimetres) are thinner than a cell, so a tet subset of the keep-out would drop them. The distance is evaluated at all 733 scene nodes against the centres of the 35169 keep-out boundary voxels. Negative values are inside the keep-out, which includes the 1.0 mm margin already in the labelmap. Results: 20 nodes inside the keep-out, distance range -4.91 mm to 131.34 mm. The distance is quantized to the 5 mm slice grid in z (recorded in the JSON `precision_note`). The keep-out node of the scene holds 1978 boundary points on a 5 mm lattice (geometry only).

Scene frame: RAS millimetres are rotated so that scene y is superior and scene z is posterior (determinant +1, orientation preserved), then shifted so the inferior node plane is at y = 0. Gravity stays along -y and the base fixation is the inferior node plane (21 nodes, box `-0.0005 -0.0005 -0.0005 0.2245 0.0005 0.1765`). This is the same analog as the placeholder base slab and is not a clinical attachment model.

Tools: Python 3.14.3, numpy 2.4.4 (pinned in `sim/sofa/requirements.txt`). The script is numpy only. The NRRD labelmaps are read with the standard library (gzip). No meshing library is added.

Output checksums (SHA-256, from `g21_provenance.json`):

| File | SHA-256 |
|---|---|
| reference_organ.msh | 11b099e1b8916e0ef927cc5f19f9251612335a43e09d7ab5a9a20be699d5f0e6 |
| reference_organ_parenchyma.msh | 11b099e1b8916e0ef927cc5f19f9251612335a43e09d7ab5a9a20be699d5f0e6 |
| reference_organ_tumor.msh | 9ac61afd87e61f72922daa7332b16918dc0e2af72b2bb4d53b774479660015e4 |
| vessel_keepout_points.msh | 7730f0598ecb6764b30344b5e11b83a136b1001c1a257cb41bb4d3f556b90cd5 |
| keepout_distance_nodes.json | e7523b2b4d4aa0ce260627b8e6bd439bf7e736d00fbdba862c10ec44b700fa16 |

### Scene swap

Changes to `sim/sofa/src/reference_scene.scn`:

* Organ mesh: `reference_organ.msh` now holds the G2.1 envelope (733 nodes, 2490 tets). Parenchyma subset file unchanged in name and now holds the same tets (the tumor is empty).
* Organ mass: `totalMass` changes from 0.064 kg (the 0.04 m placeholder cube) to 1.699840 kg (1000 kg/m^3 over the decimated envelope). The mass follows the geometry at the unchanged density.
* Base fixation: the BoxROI covers the inferior node plane only, from the provenance box.
* Keep-out node: the centerline placeholder is replaced by the keep-out boundary points (`vessel_keepout_points.msh`, type-15 point elements). No force field, mass, or mapping, as before.
* Tumor node: present with its topology container and an empty subset. Its `TetrahedronHyperelasticityFEMForceField` is omitted. On the first 1000-step attempt the force field logged `[ERROR] object must have a Tetrahedral Set Topology` on the empty subset. The run still produced 1000 steps and the divergence check passed, but the error is removed rather than carried in the capture. The field is inert on zero tets, so the omission changes no dynamics. The tumor ParameterSet is kept in a comment (5x the parenchyma).
* Unchanged: dt 0.001, gravity, EulerImplicitSolver (Rayleigh mass and stiffness 0.1), PCGLinearSolver (25 iterations, tolerance 1e-9), and the parenchyma ParameterSet 1785.714286 7142.857143 (the slice-1 placeholder values, kept for comparability; patient-specific parameterization is a later task).
* Removed: `sim/sofa/src/meshes/vessel_keepout_centerline.msh` (no longer referenced). `generate_reference_mesh.py` now refuses to run while `g21_provenance.json` exists, so it cannot overwrite the G2.1 meshes.

### Validation run: 1000 steps

Harness: `python sim/sofa/src/run_reference_scene.py --steps 1000 --label g21-16mm-1000steps`. Capture `SNDEV/logs/sofa-2026-11-06-g21-16mm-1000steps.json`. Exit code 0, 1000 of 1000 steps, PCG iterations 26 on every step, divergence ok True (finite outputs, no monotonic growth in the second half). Errors: the install-level `readBasicIniFile()` message only (benign, recorded in slice 1), after the tumor fix above.

Scaling comparison (same harness, same solver chain, 1000 steps each):

| Scene | Tets | Mean (ms) | p95 (ms) | Max (ms) | Steps over 16.7 ms | Divergence |
|---|---|---|---|---|---|---|
| Placeholder block (slice 1) | 1296 | 11.703 | 12.630 | 16.690 | 0 of 1000 | ok False (settling transient, recorded in slice 1) |
| G2.1, 18 mm grid (scaling point) | 1656 | 15.045 | 16.290 | 23.500 | 13 of 1000 | ok True |
| G2.1, 16 mm grid (reference, design target) | 2490 | 22.254 | 23.980 | 28.830 | 1000 of 1000 | ok True |
| G2.1, 12 mm grid (scaling point) | 5754 | 49.720 | 53.310 | 63.630 | 1000 of 1000 | ok True |

Captures: `sofa-2026-11-06-g21-18mm-scaling-1000steps.json` and `sofa-2026-11-06-g21-12mm-scaling-1000steps.json` (scratch scene directories under `SNDEV/logs/g21-scan-cell18/` and `g21-scan-cell12/`, which differ from the repo scene only in `totalMass` and the base box, taken from each level's provenance).

Scaling: the step time is close to linear in tet count, with a slope of about 8.6 to 8.9 microseconds per tetrahedron and an intercept near 0.2 ms. The p95 is about 1.08 times the mean at every level. On this fit the p95 reaches 16.7 ms at roughly 1,700 tets. The 18 mm point (1656 tets) meets the p95 limit at 1000 steps but has 1.3 percent of steps over 16.7 ms, and the 16 mm reference (2490 tets) does not meet it.

### 30-minute load case (16 mm reference, 2490 tets)

Quiet-host check before launch: `Get-Process` found none of Warhammer, Roblox, runSofa, colcon, Slicer, or python running, and a 3-sample `\Processor(_Total)\% Processor Time` counter read 3.6, 4.0, and 3.7 percent. The run was launched.

Count: `--steps 80900`, which is 1800 s (the 30-minute gate window) divided by the 1000-step mean of 22.254 ms. The previous placeholder run used 160000 steps, which measured 30.9 minutes of stepping; that count is not reused because the step time is now 1.9 times larger.

Command: `python sim/sofa/src/run_reference_scene.py --steps 80900 --label g21-16mm-30min-80900steps`

Capture: `SNDEV/logs/sofa-2026-11-06-g21-16mm-30min-80900steps.json` (gitignored). Exit code 0, 80900 of 80900 steps measured, wall-clock 2263.8 s (37.7 min for the process including the harness). No `[ERROR]` lines except the install-level `readBasicIniFile()` message, and 0 warnings.

VAL-029 clauses:

| Clause | Criterion | Result | Verdict |
|---|---|---|---|
| (a) p95 step time | at most 16.7 ms | 23.380 ms | FAIL |
| (b) steps above 16.7 ms | at most 0.1 percent | 80900 of 80900 (100.000 percent); the fastest step was 17.8 ms | FAIL |
| (b) maximum recorded | recorded | 53.300 ms (mean 21.738 ms, min 17.8 ms) | recorded |
| (c) divergence | no non-finite output and no monotonic growth | finite True, monotonic growth False, 8090 WriteState samples, strain energy flat at 1.544862855 over the tail | PASS |

PCG iterations: mean 25.93, min 2, max 26 (the placeholder run held 26 on every step). Over-budget steps by window: 1000 of the first 1000 steps and 10000 of the final 10000 steps, so the excess is not a start-up effect.

Anomalies (clause c of the gate harness): no process interruption, no warnings, exit code 0. Memory was not sampled (the harness does not record RSS), as in the 2026-11-05 run.

Gate verdict: G2.2 does not pass on the G2.1 reference scene at 2490 tets. The placeholder run (1296 tets) passed on the same criterion at 0.079 percent over budget; the G2.1 scene is about 1.9 times the tet count and about 1.9 times the step time.

### Verification

* `python -m py_compile` on `prepare_g21_meshes.py`, `generate_reference_mesh.py`, and `run_reference_scene.py`: PASS (no output, exit 0).
* `python -m pytest vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py -v`: FAIL. The test measures 2000 steps (capture `SNDEV/logs/sofa-2026-11-06-oq-fr-ms-002-solver-rate.json`): mean 21.699 ms, p95 23.350 ms, max 30.240 ms, 2000 of 2000 steps over budget, divergence True. The assertion `p95 <= 16.7` fails. The test is the slice-1 OQ check and was not edited, so this is the expected result for the G2.1 scene at 2490 tets.
* Decimated mesh checks: node ids are 1 to 733 and contiguous, every tet has positive volume, and the parenchyma and tumor subsets partition the organ tets (2490 plus 0 equals 2490).

Decision record: the 16 mm level is the pre-declared reference (lowest level in the stated range), and it was not changed after the 1000-step numbers were known. The owner decides whether the reference level moves below 2000 tets. The 18 mm capture is evidence for that decision, not a substitute gate run.
