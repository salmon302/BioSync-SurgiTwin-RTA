Title: SOFA hyperelastic implicit reference scene and step-timing harness (task 2.2 slice 1)
Date: 2026-10-15T17:32:32Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: task 2.2 slice 1
Summary: Builds the hyperelastic FEM reference scene under sim/sofa/src with an implicit solver chain, opens the task 2.2 CMake find check, and adds a headless step-timing harness plus the FR-MS-002 OQ test; this scene is the pinned G2.2 reference scene.

## Task Reference

* DEVELOPMENT_PLAN.md Phase 2, task 2.2: "Build the hyperelastic FEM scene with an implicit solver in SOFA, pin the SOFA release, and open the SOUP inventory", output `sim/sofa/` with scene sources under `sim/sofa/src/`.
* SRS FR-MS-002: the physics backend uses the SOFA engine in C++ for real-time non-linear FEM on hyper-elastic soft tissues with implicit equation solvers for large geometric deformations.
* Gate G2.2 (proposed): solver step within the 16.7 ms frame budget of 60 FPS on the reference scene, with no divergence over a 30-minute load case. Divergence (SRS Section 5) is non-finite output or a monotonically growing strain-energy norm over successive steps.
* docs/procurement-guide.md Section 2 (CMake find check, open bundled-Python check) and Section 7 item 2 (status text).
* Scope approved by the user: 6 to 10 files, slice 1 only; the 30-minute G2.2 load case is slice 2.

## Specification Summary

* FR-MS-002 requires hyper-elastic tissue, non-linear FEM, and an implicit solver. The scene therefore uses `TetrahedronHyperelasticityFEMForceField` with `materialName="NeoHookean"` and an `EulerImplicitSolver` plus a `PCGLinearSolver` (the direct `SparseLDLSolver` chain was probed first and measured over budget; see verification 2 and the deviations list), following component usage copied from scenes bundled in the installed tree.
* The tumor must be measurably stiffer than the parenchyma. The supported construct is per-tetra-subset force fields on a shared mechanical state: two child nodes, each with a `TetrahedronSetTopologyContainer` listing a disjoint tetra subset, each with its own hyperelastic force field, both acting on the parent `MechanicalObject`.
* The vascular keep-out zone is scene geometry with no material coupling. Coupling feeds FR-RTA-003 later; that is a later task.
* The gate statistic is the per-step animation wall time measured headless on this scene. This scene is THE pinned reference scene for G2.2; changing it re-opens the gate.

## Implementation Notes

### SOFA install layout (observed 2026-10-15)

Root: `C:\Users\salmo\SOFA\v26.06.00`.

* Executable: `collections\bin\runSofa.exe`. Plugin and component DLLs are also in `collections\bin`, with the auto-load list `collections\bin\plugin_list.conf` (71 plugins, including `Sofa.Component.SolidMechanics.FEM.HyperElastic` and `Sofa.GUI.Batch`).
* Plugins: `plugins\` (one directory per plugin, for example `plugins\SofaPython3`).
* Scenes and meshes: `share\sofa\examples` (bundled scenes) and `share\sofa\mesh` (bundled meshes).
* CMake package configs: per-module files under `lib\cmake\<Module>\<Module>Config.cmake`. There is no `SofaConfig.cmake` or `SofaFrameworkConfig.cmake` anywhere in the tree. The top-level package config file is `lib\cmake\Sofa.Framework\Sofa.FrameworkConfig.cmake` with `Sofa.FrameworkConfigVersion.cmake` reporting `PACKAGE_VERSION 26.06.00` under an ExactVersion strategy. The procurement guide's `-DSofa_DIR` check therefore points at `lib\cmake\Sofa.Framework`, and `sim/sofa/CMakeLists.txt` accepts that value.

### Bundled Python finding (procurement guide Section 2 open check, resolved)

Recorded before any scene scripting was written:

* The bundled `SofaPython3` bindings target CPython 3.12: every binding module is tagged `cp312-win_amd64.pyd`, and `dumpbin /dependents plugins\SofaPython3\bin\SofaPython3.dll` lists `python312.dll`.
* No `python312.dll` exists anywhere in the install tree, and the host has no CPython 3.12 (`py -0p` lists 3.9, 3.10, 3.11, and 3.14 only). Loading the plugin fails: `runSofa.exe -l SofaPython3` reports `Plugin loading failed (SofaPython3.dll): The specified module could not be found`.
* Consequence: a Python scene is not viable with the bundled interpreter, and the bundled interpreter (3.12) would not match the Phase 2 venv (3.11.9) either. The reference scene is authored in SOFA XML `.scn` format instead, and the harness drives `runSofa.exe` in batch mode rather than embedding SofaPython3 scripts.

### Files changed

* `SNDEV/docs/impl-2026-10-15-sofa-scene-slice1.md` (this log, created before code).
* `sim/sofa/src/generate_reference_mesh.py`: deterministic generator for the reference scene meshes. Regenerate with `python sim/sofa/src/generate_reference_mesh.py`. It emits four Gmsh 2.2 ASCII files under `sim/sofa/src/meshes/`: `reference_organ.msh` (structured grid, each hex cell split into six tetrahedra, negative-volume tets reoriented, all volumes asserted positive), `reference_organ_tumor.msh` and `reference_organ_parenchyma.msh` (same node list, disjoint tetra subsets split by tumor-sphere centroid at (0.02, 0.02, 0.02) with radius 0.007 m, asserted to partition the 1296 tetrahedra into 36 tumor and 1260 parenchyma), and `vessel_keepout_centerline.msh` (9 points, 8 two-node line elements beside the tumor). No random input; a re-run reproduced `reference_organ.msh` byte-identically (SHA256 `141141D5FFBF74517BB2D77E3A5A4F71C11899BB771398D198354F5B68CE9274` before and after).
* `sim/sofa/src/meshes/`: generated placeholder meshes (the parenchymal organ block, its tumor split, and the keep-out centerline). Placeholder until gate G2.1 segmentation meshes land.
* `sim/sofa/src/reference_scene.scn`: the pinned G2.2 reference scene. Root at `dt=0.001` with gravity `0 -9.81 0`; organ node with `MeshGmshLoader` from the repo mesh (scene-relative path), `TetrahedronSetTopologyContainer`, `TetrahedronSetGeometryAlgorithms`, `MechanicalObject`, `MeshMatrixMass` (totalMass 0.064 kg, parenchyma density over the 0.04 m cube), `EulerImplicitSolver` (Rayleigh 0.1/0.1) plus `PCGLinearSolver` (25 iterations, tolerance 1e-9), `BoxROI` plus `FixedProjectiveConstraint` on the base slab (y in [0, 0.001]) so the scene deforms under gravity without drifting, and `WriteState` dumping positions every 10 ms for the harness divergence check; two child nodes `Parenchyma` and `Tumor`, each with its own `MeshGmshLoader` and `TetrahedronSetTopologyContainer` listing a disjoint tetra subset of the same node numbering and its own `TetrahedronHyperelasticityFEMForceField` (`NeoHookean`) acting on the shared parent `MechanicalObject`, tumor `ParameterSet` five times the parenchyma `ParameterSet` in both Lame constants (mu 1785.714286 and lambda 7142.857143 versus 8928.571429 and 35714.285714); a `VasculatureKeepOut` node holding the vessel centerline point set with no force field, no mass, and no mapping, so there is no material coupling yet (coupling feeds FR-RTA-003 in a later task). The component list follows the bundled examples in the pinned install; the scene runs with zero warnings.
* `sim/sofa/src/run_reference_scene.py`: step-timing harness (recorded location: `sim/sofa/src/`, alongside the scene). Runs `runSofa.exe -g batch -n <steps> --computationTimeSampling 1` on the reference scene in a temporary working directory, parses the per-step `Steps Duration Statistics` rows for animation-step wall times, parses the `WriteState` dump, computes the strain-energy series, checks finiteness and monotonic growth, and writes a JSON capture to `SNDEV/logs/`.
* `sim/sofa/CMakeLists.txt` with `sim/sofa/cmake/FindSOFA.cmake`: placeholder replaced with find logic behind `SRTA_BUILD_SOFA` (default OFF in the root). `FindSOFA.cmake` (MODULE mode) accepts `Sofa_DIR` (the guide's variable), `SRTA_SOFA_ROOT`, or the `SOFA_ROOT` environment variable, validates the shipped `Sofa.FrameworkConfig.cmake`, reads `Sofa.FrameworkConfigVersion.cmake` for the version, locates `runSofa.exe` in the observed layout, and reports the found version and paths through `find_package_handle_standard_args`. A plain `find_package(Sofa.Framework 26.06.00 CONFIG QUIET)` was probed first and aborts on this install (verification 1). Configuration fails only when `SRTA_BUILD_SOFA=ON` and the install is absent.
* `sim/sofa/README.md`: placeholder replaced with the directory contents and run instructions.
* `vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py`: runs the harness for 1000 steps against the reference scene, asserts the 16.7 ms budget on the reported maximum step time, and reports mean, p95, and the divergence verdict. Skips with a clear reason when `runSofa.exe` is not found, following the repo skip precedent.
* `sim/SOUP.md`: SOFA row Evaluation record cell updated with the CMake find check result and the bundled scene run evidence. No other row changed.
* `docs/procurement-guide.md`: Section 7 item 2 trailing status text updated for the bundled scene run. No other text in the row changed.

### Verification steps and evidence

Verification results are recorded below.

#### 1. CMake find check (procurement guide Section 2)

Config-mode probe (2026-10-15): the first implementation ran `find_package(Sofa.Framework 26.06.00 CONFIG QUIET)` with `-DSofa_DIR=C:\Users\salmo\SOFA\v26.06.00\lib\cmake\Sofa.Framework` and aborted inside `Sofa.ConfigTargets.cmake`, whose imported-target check verifies `C:/Users/salmo/SOFA/v26.06.00/bin/Sofa.Config.dll` while the installer collects the binaries under `collections\bin` (there is no `bin\` directory at the install root, re-checked). `SofaConfig.cmake` and `SofaFrameworkConfig.cmake` do not exist anywhere in the tree (re-checked). The find logic therefore moved to `sim/sofa/cmake/FindSOFA.cmake`, MODULE mode, which validates the shipped `Sofa.FrameworkConfig.cmake` and reads its shipped version file instead of loading the imported targets.

Final check, exit code 0:

```text
cmake -S . -B build\sofa-check -DSRTA_BUILD_SOFA=ON -DSofa_DIR=C:\Users\salmo\SOFA\v26.06.00\lib\cmake\Sofa.Framework

-- Found SOFA: C:\Users\salmo\SOFA\v26.06.00\lib\cmake\Sofa.Framework (found version "26.06.00")
-- SOFA found: version 26.06.00 (package dir C:\Users\salmo\SOFA\v26.06.00\lib\cmake\Sofa.Framework)
-- SOFA runSofa: C:/Users/salmo/SOFA/v26.06.00/collections/bin/runSofa.exe
-- SurgiTwin-RTA: SOFA 26.06.00 at C:/Users/salmo/SOFA/v26.06.00
-- Configuring done (3.1s)
-- Generating done (0.1s)
```

Default path check: `cmake -S . -B build\sofa-off` with `SRTA_BUILD_SOFA` at its default OFF configures and builds with exit code 0; the find logic is not entered. PASS.

#### 2. Headless reference-scene runs

Run A, primary timing capture, 1000 steps (`SNDEV/logs/sofa-2026-10-15-g22-slice1-1000steps.json`):

* mean 11.703 ms, p95 12.630 ms, max 16.690 ms, median 11.540 ms, stdev 0.525 ms;
* 0 of 1000 steps over the 16.7 ms budget; PCG iterations constant at 26; exit code 0; scene warnings 0;
* budget on this run: PASS on the max statistic, margin 0.010 ms;
* divergence: flagged (`monotonic_growth=True`) because the whole 1.0 s window is dominated by the load-on transient: strain energy rises 1.30 percent over the second half (clause threshold 1 percent) while successive differences decay from about 1.07e-5 to 2e-9 per sample. The series settles to a plateau near 2.229e-4; this is a settling transient, not runaway.

Run B, divergence settling, 2000 steps (`SNDEV/logs/sofa-2026-10-15-g22-slice1-2000steps.json`):

* mean 11.769 ms, p95 12.650 ms, max 23.910 ms, median 11.580 ms, stdev 0.705 ms;
* 7 of 2000 steps over the budget (16.84 to 23.910 ms, steps 316, 317, 647, 1270, 1637, 1782, 1860; no over-budget step coincides with a WriteState dump step); PCG iterations constant at 26; exit code 0;
* divergence check: PASS (finite outputs over 200 samples, no monotonic growth over the second half once the transient settles);
* budget on this run: FAIL on the max statistic (23.910 ms against 16.7 ms).

Slice-1 budget status: FAIL on the max statistic, borderline. Mean and p95 pass with margin in every run, but rare jitter steps cross the budget at about 0.35 percent incidence and the 1000-step runs passed max by 0.010 and 0.110 ms. The numbers are real; the tuning work still needed is listed under open items.

#### 3. OQ test and lint

```text
python -m pytest vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py -v

FR-MS-002 solver rate: max=16.590 ms, p95=12.650 ms, mean=11.757 ms over 1000 steps (budget 16.7 ms); divergence_ok=False; capture: SNDEV/logs/sofa-2026-10-15-oq-fr-ms-002-solver-rate.json
1 passed in 15.35s
```

PASS on this run (max 16.590 ms against 16.7 ms). The `divergence_ok=False` in the test capture is the 1.0 s window transient from run A; the test asserts the budget only.

`python -m ruff check sim/sofa/src/generate_reference_mesh.py sim/sofa/src/run_reference_scene.py vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py` (ruff 0.8.4 in `.venv-qual311`): All checks passed.

### Divergence check definition used by the harness

SRS Section 5 defines divergence as non-finite output or a monotonically growing strain-energy norm over successive steps. Slice 1 operationalizes this on the sampled series (positions dumped each `WriteState` period, strain energy computed per sample as the NeoHookean energy of every tetrahedron with the parenchyma Lamé constants):

* finite outputs: every dumped position parses as a finite float;
* monotonically growing: over the second half of the sampled strain-energy series, every successive value increases and the total growth over that half exceeds 1 percent.

A converging load response plateaus within tolerance and passes; a diverging solve grows without bound and fails both clauses. The sampling window must span several settling time constants for the growth clause to mean what it says: on this scene the settling time is about 0.3 s, so a 1.0 s window (1000 steps) still trips the clause on the residual transient (1.30 percent over the second half) while a 2.0 s window (2000 steps) passes. Both captures are recorded in verification 2. The 30-minute load case that the full gate requires is slice 2 and is not run here.

### Deviations and limitations

* The bundled-Python check from the procurement guide resolved to "not viable": the scene is `.scn` XML, not a SofaPython3 script, as recorded above (re-verified 2026-10-15: `py -0p` lists 3.9, 3.10, 3.11, and 3.14 only; no `python312.dll` exists anywhere in the install; `runSofa.exe -l SofaPython3` reports `Plugin loading failed (SofaPython3.dll): The specified module could not be found`).
* `find_package(Sofa.Framework CONFIG)` cannot be used on the pinned install: the shipped imported-target files verify `<root>\bin\*.dll` while the binaries are collected under `<root>\collections\bin`, so the config include aborts. `sim/sofa/cmake/FindSOFA.cmake` (MODULE mode) reads the shipped `Sofa.FrameworkConfig.cmake` presence and `Sofa.FrameworkConfigVersion.cmake` version instead. The version and path evidence is unaffected; the anomaly is recorded in the SOFA row of `sim/SOUP.md`.
* The installed components provide no `CylinderROI` (string scan of `Sofa.Component.Engine.Select.dll` and a scan of all collection DLLs found no such component), so the keep-out zone uses the alternative the task names: a vessel centerline point set (`meshes/vessel_keepout_centerline.msh`, 9 points, 8 line elements, at x 0.030 through the organ beside the tumor) in the `VasculatureKeepOut` node. It has no force field, no mass, and no mapping, so there is no material coupling yet; coupling feeds FR-RTA-003 in a later task.
* The tumor split is precomputed by `generate_reference_mesh.py` into two disjoint subset mesh files instead of being evaluated in-scene from a `SphereROI`: the installed ROI engines output index lists, and no installed component maps an index list onto a subset `TetrahedronSetTopologyContainer`. The split is deterministic and asserted by the generator (36 tumor and 1260 parenchyma tetrahedra, a disjoint cover of the 1296).
* The solver chain is `EulerImplicitSolver` plus `PCGLinearSolver`, not the `SparseLDLSolver` direct chain the first draft of this log described. Probes on the same scene: the direct chain measured 17.2 to 19.6 ms mean per step (about 9 ms in `ComputeRHTerm` and 6.5 ms in the LDL numeric factorization per step), the iterative chain measured about 11.7 ms mean. The change matters because it changes what G2.2 measures, and it is recorded here for that reason.
* `WriteState` lives in `Sofa.Component.Playback` in this release; the install ships no `SofaExporter` plugin.
* The line `[ERROR] [Utils::readBasicIniFile()] ... C:/Users/salmo/SOFA/v26.06.00/collections` appears on every `runSofa.exe` launch including bundled scenes. It is install-level and benign; the scene itself runs with zero warnings and zero scene errors.
* The budget status in verification 2 is a max-statistic FAIL driven by rare jitter steps while mean and p95 pass with margin. Whether gate G2.2 asserts on max, on p95, or on a warmup-excluded max is a gate-definition question for the plan owner.
* The organ mesh is a generated block, a placeholder until gate G2.1 exports real segmentation meshes. When those land, the scene switches mesh file and the G2.2 gate is re-measured on the new pinned scene.
* Slice 2 still owes the 30-minute load case for full G2.2; it is not run in this slice, per the slice scope.

### Open items for slice 2

* Run the 30-minute G2.2 divergence load case on this scene and record the result.
* Re-measure the gate against G2.1 meshes when they replace the placeholder block.
* Tune the tail of the step-time distribution: 7 of 2000 steps crossed 16.7 ms with a maximum of 23.910 ms while mean and p95 sit near 11.8 and 12.65 ms. Candidate work is CPU affinity or process priority for `runSofa.exe`, solver tolerance and iteration cap, placeholder or G2.1 mesh density, and agreement with the plan owner on whether the gate statistic is max or p95.
* Add cutting and contact behavior (task 2.3) on top of this scene without changing the pinned solver chain silently.
* Grow the `VasculatureKeepOut` centerline into the FR-RTA-003 keep-out envelope; this slice adds no coupling to it.

### Commit

One commit, subject `feat(sim): hyperelastic implicit SOFA scene with step-timing harness (2.2)`, links this log, and carries the DCO sign-off.