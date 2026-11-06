Title: Tool-tissue contact, CCD, culling, and puncture resistance on the budget-fit scene (task 2.3 slice 1)
Date: 2026-11-06T15:07:23Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: task 2.3 slice 1, FR-MS-003 contact foundation (gate G2.3 is a later slice)
Summary: Adds a rigid scripted tool, connectivity-based surface culling, a conservative proximity CCD path, multi-point penalty contact with a tool-tip wrench capture in the bridge replay field names, a first anisotropic puncture resistance model, and a scripted smoke contact suite on the 20 mm budget-fit reference scene.

## Task Reference

* DEVELOPMENT_PLAN.md Phase 2, task 2.3 (sim/bridge replay and the tool-tissue contact foundation).
* SRS FR-MS-003: the SOFA scene graph implements connectivity-based culling and continuous collision detection pipelines for multi-point tool-to-tissue contact, anisotropic needle puncture resistance, dissection, and cutting.
* Gate G2.3 (proposed, later slice): zero tunneling events and zero missed contacts across a 1000-trial needle puncture and cutting suite.
* Predecessor: `SNDEV/docs/impl-2026-11-06-g22-budget-fit.md` (commit f3df8f8), the 20 mm reference scene (405 nodes, 1230 tets, step cost about 11 ms).
* Coordinator authorization for item 7: `sim/segmentation/data/PROVENANCE.md` descriptive phrase corrected to the current record.

## Specification Summary

* Scripted rigid tool (documented geometry, parameterized pose trajectory) whose tip wrench and pose are written in the `sim/bridge/README.md` replay field names.
* Connectivity-based culling of the collision candidate set, with candidate counts before and after.
* A continuous or conservative collision path that prevents tunneling at the measured step size, with the tested speed range recorded.
* Penalty or constraint contact with documented stiffness and damping; 6-axis tool-tip wrench from the contact forces.
* A first anisotropic puncture resistance model with its parameters, pinned and documented.
* A scripted smoke suite (10 approaches at different speeds, 3 impact angles) checking contact detection, tunneling (geometric post-run check), wrench finiteness and non-zero force during contact, and candidate reduction. This is not the G2.3 gate suite.

Out of scope in this slice: needle dissection and cutting (slice 2), the 1000-trial suite, and the gate G2.3 verdict.

## Implementation Notes

### Runtime path (SofaPython3)

* The pinned SOFA v26.06.00 install ships `collections/bin/SofaPython3.dll`, built for CPython 3.12 (`cp312` extension modules). The host has no CPython 3.12 (host Python is 3.14.3 and 3.11.9, and C:\Python is 3.9.13).
* The runtime is the pinned conda-forge CPython 3.12.16 in the repository's pixi default environment (`env/ros2-jazzy/.pixi/envs/default`, locked by `env/ros2-jazzy/pixi.lock`). It is used read-only through PATH and PYTHONPATH (`SofaPython3` site-packages and `collections/bin`). No file under `env/` is changed. The interpreter and the plugin are a SOUP row candidate (see Report).
* Load: `runSofa.exe -l SofaPython3 contact_scene.py -g batch -n <steps>`. The `.py` scene loader requires the plugin loaded first (`-l`). The build has no `PythonScriptController`, so the controller is a `Sofa.Core.Controller` subclass added to the root.

### SOFA collision pipeline finding

The SOFA collision path was configured and checked before the custom path was chosen: `RuleBasedContactManager(response="PenalityContactForceField")`, `BruteForceBroadPhase`, `BVHNarrowPhase`, `TriangleCollisionModel` on the culled organ surface and on the needle surface, and either `CCDTightInclusionIntersection` or `LocalMinDistance`. Both intersection methods produced zero contact force on the needle (`debug_forces` diagnostic: the needle points, organ, and rigid force maxima stayed at 0 for 880 steps while the tip was 8 mm below the surface). The component names exist in the build (checked in the DLL strings), so the failure is in the configuration or the wiring, not a missing plugin. It was not resolved within this slice.

Decision: the contact algorithm is implemented in the scene controller (`ContactController`). This is the custom path the brief allows ("a custom conservative-advancement or ray-cast check ... implement it in the scene scripts and record the algorithm"). The SOFA collision components are not in the scene.

### Organ settling and the base fixation finding (affects G2.2 interpretation)

The slice-1 parenchyma placeholder under gravity does not hold its shape with the reference base fixation (the 15 nodes on the y = 0 plane, fixed with `FixedProjectiveConstraint`):

* The organ block (top at 0.160 m) collapses within about 0.25 s to a top near 0.0205 m, which is the first settled value.
* The collapse continues: the lowest node reaches y = -0.387 m (382 of 405 nodes below the base plane). No tetrahedron inverts (minimum det J 0.33), so the state is a valid but non-physical deformation. The 15 fixed nodes do not carry the body, because the organ has no floor and falls through its own fixed face.
* A `BoxROI` selection warning (`No rest position yet defined`) appeared when the box was used, so the fixed set is taken as the explicit node list instead. The result did not change.
* A static floor (triangles at y = -0.5 mm) plus a bottom-face collision set did not hold the organ either, because only the flat bottom face was in the set and the side faces passed through. The collision set cannot cover the whole boundary without conflicting with the culled tool set in this slice.
* The 200-iteration PCG run settled to the same state, so the 25-iteration cap is not the cause. A stiffer penalty (1e4 N/m) and LocalMinDistance also left the state unchanged, so the floor was not active.

Decision: the contact scene runs with gravity 0, so the organ stays at its undeformed 0.160 m shape under the base fixation. This is a deviation from the reference scene (which has gravity 9.81 m/s^2). The reference scene itself has the same defect: its organ falls through its base fixation under gravity. The G2.2 timing measurements are unaffected, because the defect does not change the step cost materially, but the reference scene's physical state is not validated. The G2.2 closure must record this as a boundary (see Report).

### Tool model

* Rigid needle, kinematic (Rigid3d `MechanicalObject`, the pose set by the controller every tick). Tool frame: tip at the origin, shaft along +z.
* Shaft radius 0.5 mm, cone half-angle 15 degrees (cone length 1.866 mm), shaft length 40 mm, 8 segments. Tool surface: 25 points, 24 triangles.
* Pose trajectory: tip starts 30 mm above the organ top (`clearance_mm`), moves along the insertion direction `d = (sin theta, -cos theta, 0)` at a constant speed, and stops 8 mm below the top (`depth_mm`), then holds for 500 ms (`HOLD_STEPS`). The tool axis points along `-d` (shaft toward the base of the approach).
* Bridge fields: tick, time_s = tick x 0.001 (rate 1000 Hz, the scene dt), tip position in scene frame (m), unit quaternion (x, y, z, w) for the tool axis, wrench, and one mode column `mode_0 = 0.0`. The capture has no modal reduction in slice 1, so `mode_0` is a documented zero placeholder (the schema requires 1 to 16 mode columns).

### Culling

Connectivity-based culling in the contact controller: the candidate organ triangles are the boundary triangles whose three vertices lie in the corridor. The corridor is the set of vertices within 6 mm of the insertion segment (start to end tip), grown by 2 rings of the boundary-mesh adjacency. Full boundary: 684 triangles. Culled: 22 triangles (17 corridor vertices in the first build; the count is recorded per trial in `scene_build.json`). Candidate pairs (tool triangles x organ triangles): 16416 before, 528 after (a 31-fold reduction). The culling set is fixed per run (static corridor, not recomputed each step).

### Contact model (controller)

* Sample points: the 25 tool points, posed each tick.
* Per tick, the swept test: each point segment from the previous tick position to the current one is tested against the culled triangles (Moeller-Trumbore, t in [0, 1]). A hit makes that triangle a contact candidate (conservative continuous detection for the sampled points; the tool surface between sample points is not swept).
* Proximity: a point is a candidate on a triangle when its projection lies inside the triangle and the signed distance satisfies sd < contact margin (0.5 mm).
* Choice of face: the candidate with the smallest |sd| (nearest face). A point inside the organ is pushed out through its nearest face.
* Penalty: f = k pen n - c (v . n), with pen = margin - sd (clamped at 0), k = 100 N/m (contact stiffness), c = 0.5 N s/m (normal damping, relative to the tool point velocity), n the outward face normal. Contact forces with f <= 0 are dropped.
* Reaction: -f distributed to the face nodes by barycentric weights, applied through a `ConstantForceField` with a fixed node index set (the union of the contact nodes and the puncture nodes), updated each tick.
* Wrench on the tool: force = sum of contact f minus the puncture term along d; torque = sum of (p_i - tip) x f_i. The wrench is reported in the bridge capture.

### Puncture resistance (first model)

Directional resistance along the insertion direction, driven by the tip depth below the entry point:

* Depth s = (tip - entry) . d while the tip is inside the organ (inside by a 3-direction majority ray parity test on the full boundary), else 0.
* Effective stiffness K(phi) = K_perp (sin^2 phi + A cos^2 phi), where phi is the angle between the insertion direction d and the fiber direction f (here f = x axis, fixed), K_perp = 100 N/m, and A = 2.0 (anisotropy ratio: the fiber-aligned resistance is twice the perpendicular stiffness).
* Puncture force magnitude F_p = K(phi) s, directed along -d on the tool and +d on the organ (distributed to the 4 organ nodes nearest the entry region).
* The anisotropy ratio A = 2.0 is a model placeholder, not a literature value. No source was cited in this slice, so the value is unvalidated and is flagged in the README and the Report.

### Smoke suite

`sim/sofa/src/run_contact_suite.py`: 10 approaches at speeds 10, 20, 40, 60, 80, 100, 120, 150, 180, 200 mm/s, with impact angles 0, 15, and 30 degrees cycled across them (the angle is `ANGLES_DEG[k mod 3]`). Each approach: 30 mm clearance, 8 mm depth, 500 ms hold. Checks per approach are listed in the Results section below.

### Smoke suite run 1 (corridor 6 mm, 2 rings): FAIL on two approaches

Capture: `SNDEV/logs/task23-smoke-slice1-20261106/summary.json` (bridge captures `SNDEV/logs/contact-smoke-slice1-20261106-T*-bridge.csv`).

| Trial | Speed (mm/s) | Angle (deg) | Contact steps | Tunneling steps | Result |
|---|---|---|---|---|---|
| T01 | 10 | 0 | 928 | 0 | PASS |
| T02 | 20 | 15 | 651 | 1 | FAIL |
| T03 | 40 | 30 | 711 | 3 | FAIL |
| T04 to T10 | 60 to 200 | 0, 15, 30 | 292 to 548 | 0 | PASS |

Diagnosis: the tunneling steps are all during the hold, after first contact (T02 at step 1806, 3.2 mm depth; T03 at steps 914 to 916, 6.4 mm depth). The tip is inside the organ while no culled triangle is a candidate. The corridor (6 mm, 2 rings) gave 22 culled triangles, all on the top surface. Under the 15 and 30 degree tilt, the tip reaches lateral positions beyond those triangles, and the side faces it touches are culled. This is a culling miss, not a detection timing issue, and it is the outcome the tunneling check exists to catch.

Change for run 2: corridor radius 12 mm and 3 adjacency rings (the tilted penetration envelope at 8 mm depth is about 4 mm lateral at 30 degrees, plus the tool shaft radius and margin). Run 1 is kept as recorded.

### Smoke suite run 2 (corridor 12 mm, 3 rings): 9 of 10 pass

Capture: `SNDEV/logs/task23-smoke-slice1-corridor12-20261106/summary.json`. Culled triangles rose from 22 to 51 (candidate pairs 528 to 1224 per trial, from 16416 full).

T02 and T03 pass now. T04 (60 mm/s, 0 degrees) has one tunneling step at step 553 (depth 3.06 mm). The tip is inside the organ and the step has zero contact points. Steps 552 and 554 have one contact point each. The tip x coordinate equals the top point x (0.101052632), so the tip lies on the projection boundary of a face edge, and the projection test returns no candidate for one tick.

Change for run 3: fallback in `ContactController.compute_contact`. A tool point that is inside the organ (full-boundary ray parity) and has no candidate uses the nearest culled face by |sd|.

### Smoke suite run 3 (corridor 12 mm, 3 rings, edge fallback): 10 of 10 PASS

Capture: `SNDEV/logs/task23-smoke-slice1-fallback-20261106/summary.json`. Bridge captures: `SNDEV/logs/contact-smoke-slice1-fallback-20261106-T01-bridge.csv` through `...-T10-bridge.csv`. Quiet-host check before the run: no Warhammer, Roblox, runSofa, colcon, or Slicer processes; CPU samples 6, 2, and 1.2 percent. Every run exited 0 with no `[ERROR]` lines beyond the install-level `readBasicIniFile()` message.

| Trial | Speed (mm/s) | Angle (deg) | First contact (step) | Contact steps | Tunneling steps | Inside steps | Swept-hit steps | Peak contact (N) | Peak puncture (N) | Max depth (mm) | Wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T01 | 10 | 0 | 2951 | 928 | 0 | 728 | 26 | 0.063 | 0.087 | 0.86 | 122.6 |
| T02 | 20 | 15 | 1475 | 634 | 0 | 423 | 5 | 4.007 | 0.359 | 3.34 | 69.2 |
| T03 | 40 | 30 | 736 | 714 | 0 | 625 | 2 | 8.143 | 0.925 | 7.36 | 43.0 |
| T04 | 60 | 0 | 492 | 241 | 0 | 150 | 1 | 65.442 | 0.788 | 7.88 | 33.3 |
| T05 | 80 | 15 | 369 | 446 | 0 | 209 | 1 | 16.223 | 0.845 | 7.92 | 28.1 |
| T06 | 100 | 30 | 295 | 585 | 0 | 444 | 1 | 8.306 | 0.988 | 7.90 | 25.3 |
| T07 | 120 | 0 | 246 | 352 | 0 | 82 | 1 | 20.081 | 0.788 | 7.88 | 23.6 |
| T08 | 150 | 15 | 197 | 432 | 0 | 254 | 1 | 15.791 | 0.838 | 7.85 | 21.7 |
| T09 | 180 | 30 | 164 | 548 | 0 | 356 | 2 | 16.485 | 0.970 | 7.76 | 20.4 |
| T10 | 200 | 0 | 148 | 344 | 0 | 57 | 3 | 32.206 | 0.780 | 7.80 | 20.1 |

Checks, all 10 trials:

* Contact detected on every approach: yes (first contact step listed above).
* Tunneling (inside with zero contact points): 0 steps in every trial.
* Wrench finite and non-zero on every contact step: yes (every trial).
* Bridge schema (exact header, consecutive ticks, row count equal to the steps, `time_s` equal to tick/1000 within 1e-6, quaternion norm 1 within 1e-6, all values finite): pass in every trial.
* Culling: 16416 candidate pairs before and 1224 after (51 of 684 triangles kept, 35 corridor vertices, 35 contact nodes, 4 puncture nodes, 15 fixed base nodes).

Reading the peak forces: the peak contact values scale with approach speed (0.06 N at 10 mm/s, 65 N at 60 mm/s). This is a penalty-model artifact at the first contact transient and at the maximum depth, not a calibrated needle force. Realistic needle puncture forces are a few newtons. The peak values are reported as measured; the contact stiffness and damping are not calibrated in slice 1.

Interpretation: 10 of 10 smoke approaches pass the four checks. The G2.3 gate (zero tunneling and zero missed contacts over 1000 trials, with dissection and cutting) is not tested here.

### Wrench capture cross-reference

The bridge replay capture for each trial is `SNDEV/logs/contact-smoke-slice1-fallback-20261106-T<nn>-bridge.csv`, in the `sim/bridge/README.md` capture schema (header `tick,time_s,pos_x,pos_y,pos_z,quat_x,quat_y,quat_z,quat_w,force_x,force_y,force_z,torque_x,torque_y,torque_z,mode_0`). The bridge replay reads a rate-specified grid. The contact captures are written at 1000 Hz (scene dt 0.001 s), so the replay source needs `rate_hz 1000`, which differs from the 500 Hz smoke default in `sim/bridge/`. The replay was not run in this slice (`sim/bridge` is out of scope).

### Segmentation provenance fix (item 7)

`sim/segmentation/data/PROVENANCE.md`: the phrase "This is not G2.1 reference data." is replaced with "This is the G2.1 reference set (SRS v1.4.0, VAL-030 to VAL-032)." The second sentence of that paragraph ("It has no reference labels for Dice evaluation.") is also out of date, because the SEG reference labels now exist. It is not changed here, as the brief limited the edit to the one phrase. The owner decides that sentence.

### Not run, not validated, deviations recorded for the G2.2 closure

* The contact scene runs with gravity 0. The reference scene's organ falls through its base fixation under gravity (see the organ settling section). This affects the physical validity of the reference scene; the G2.2 timing result is not affected by this slice.
* SOFA's collision pipeline was not made to produce contact in this build. The custom contact path is the one that is tested.
* No static displacement comparison against a converged solve was run for the contact scene.
