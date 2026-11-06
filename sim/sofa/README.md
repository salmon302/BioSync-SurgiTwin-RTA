# SOFA FEM Scenes and Plugins

Task 2.2 output (SRS FR-MS-002, FR-MS-003). Pinned install: SOFA v26.06.00 at
`C:\Users\salmo\SOFA\v26.06.00` (row and evaluation record in `sim/SOUP.md`).

## Contents

* `src/reference_scene.scn` - THE pinned G2.2 reference scene: hyperelastic
  liver parenchyma (NeoHookean `TetrahedronHyperelasticityFEMForceField` on the
  G2.1 envelope, with a disjoint tumor subset that is empty on HCC_001), implicit
  solver chain (`EulerImplicitSolver` + `PCGLinearSolver`), a fixed inferior
  node plane, gravity `0 -9.81 0`, and a `VasculatureKeepOut` node with the
  keep-out boundary points and no material coupling yet (coupling is a later
  task for FR-RTA-003).
* `src/prepare_g21_meshes.py` + `requirements.txt` - converts the G2.1
  labelmaps under `sim/segmentation/output/tcia-hcc-tace-seg-hcc001/` into the
  scene meshes in `src/meshes/`: the liver envelope decimated to a 20 mm grid
  (405 nodes, 1230 tets; the budget-fit level), the keep-out boundary points, and the keep-out
  signed distance at every scene node. Provenance (source and output
  checksums, tool versions, decimation parameters, counts) is in
  `src/meshes/g21_provenance.json`. Regenerate with
  `python sim\sofa\src\prepare_g21_meshes.py`, optionally `--cell-mm <mm>`.
* `src/generate_reference_mesh.py` - retired slice-1 placeholder generator
  (1296 tets). It refuses to run while `src/meshes/g21_provenance.json` exists,
  so it cannot overwrite the G2.1 meshes.
* `src/run_reference_scene.py` - headless step-timing harness. Runs the scene
  through `runSofa.exe -g batch -n <steps> --computationTimeSampling 1`,
  reports mean/p95/max step time against the 16.7 ms frame budget, runs the
  strain-energy divergence check, and writes a JSON capture to `SNDEV/logs/`.
* `cmake/FindSOFA.cmake` with `CMakeLists.txt` - find check behind
  `-DSRTA_BUILD_SOFA=ON` (root option, default OFF). Reports the found SOFA
  version and `runSofa.exe` path.
* `vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py` - the G2.2 slice-1 OQ test.

## How to run

```powershell
python -m pip install -r sim\sofa\requirements.txt
python sim\sofa\src\prepare_g21_meshes.py
python sim\sofa\src\run_reference_scene.py --steps 1000 --label run
python -m pytest vv\tests\OQ\test_oq_fr_ms_002_solver_rate.py -v
cmake -S . -B build\sofa-check -DSRTA_BUILD_SOFA=ON -DSofa_DIR=C:\Users\salmo\SOFA\v26.06.00\lib\cmake\Sofa.Framework
```

`runSofa.exe` is resolved from `SRTA_RUN_SOFA` or the pinned install path;
the pytest test skips with a clear reason when it is absent. Captures land in
`SNDEV/logs/sofa-*.json` (gitignored). Changing `src/reference_scene.scn`
re-opens gate G2.2.

## Tool-tissue contact (task 2.3 slice 1, FR-MS-003)

Files: `src/contact_scene.py` (SOFA Python scene and `ContactController`) and
`src/run_contact_suite.py` (scripted smoke suite). The reference scene
`src/reference_scene.scn` is unchanged; the contact scene is a separate scene on
the same 20 mm organ mesh, the same parenchyma material, and the same solver
chain (EulerImplicitSolver, PCG with 25 iterations).

Runtime: SofaPython3 is built for CPython 3.12. The suite uses the pinned
conda-forge CPython 3.12.16 from the repository's pixi default environment
(`env/ros2-jazzy/.pixi/envs/default`) through PATH and PYTHONPATH. Run from the
repository root:

```powershell
python sim\sofa\src\run_contact_suite.py --label <label>
```

Outputs: `SNDEV/logs/task23-smoke-<label>/` (per-trial `bridge_capture.csv`,
`diagnostics.csv`, `scene_build.json`, `runSofa.log`, and `summary.json`), and
copies of each trial's bridge capture as `SNDEV/logs/contact-smoke-<label>-T*-bridge.csv`.

### Tool model

* Rigid needle: shaft radius 0.5 mm, tip cone half-angle 15 degrees (cone length
  1.866 mm), shaft length 40 mm, 8 segments, 25 surface points and 24 triangles.
* Scripted trajectory: tip starts 30 mm above the organ top, advances at the
  trial speed along `d = (sin theta, -cos theta, 0)` to 8 mm below the top, then
  holds for 500 ms.
* Bridge replay capture (`sim/bridge/README.md` schema): `tick`, `time_s`
  (tick x 0.001, rate 1000 Hz), tip position, unit quaternion (x, y, z, w) of the
  tool axis, tool wrench (force and torque), and `mode_0 = 0.0` (a placeholder,
  because slice 1 has no modal reduction; the schema requires one to sixteen mode
  columns).

### Culling

Candidate organ triangles are the boundary triangles whose three vertices lie
in the corridor: the vertices within 12 mm of the insertion segment, grown by
three rings of boundary-mesh adjacency. The culling set is fixed per run.
Full boundary: 684 triangles. Culled: 51 triangles, so candidate pairs (tool
triangles times organ triangles) fall from 16416 to 1224.

### Contact algorithm (ContactController)

* Swept test: each tool point segment from the previous tick to the current tick
  is tested against the culled triangles (Moeller-Trumbore, t in [0, 1]).
* Proximity: a point is a candidate on the triangle whose projection contains the
  point and whose signed distance satisfies sd < 0.5 mm. The nearest candidate
  face (smallest |sd|) is used.
* Fallback: a point inside the organ (full-boundary ray parity) with no candidate
  uses the nearest culled face.
* Penalty normal force: `f = k pen n - c (v . n)`, with `pen = 0.5 mm - sd`,
  `k = 100 N/m`, `c = 0.5 N s/m`, and `n` the outward face normal.
* Reaction: distributed to face nodes by barycentric weights through a
  `ConstantForceField` with a fixed node index set.
* Wrench on the tool: summed contact force and torque, minus the puncture force.

The SOFA collision pipeline (`CCDTightInclusionIntersection`, or
`LocalMinDistance`, with `RuleBasedContactManager` and `TriangleCollisionModel`)
was configured in this build and produced no contact response, so it is not used
in the scene.

### Puncture resistance (first model)

Directional resistance along the insertion direction, driven by the depth `s`
of the tip past its entry point:

    K(phi) = K_perp (sin^2 phi + A cos^2 phi),    F_p = K(phi) s

* `phi` is the angle between the insertion direction and the fiber direction
  (fixed to the x axis).
* `K_perp = 100 N/m`, `A = 2.0`. The anisotropy ratio A is a model placeholder
  with no literature source in this slice. It is unvalidated.
* The force acts opposite the insertion on the tool and is distributed to the
  four organ nodes nearest the entry region.

### Smoke suite

Ten approaches at 10, 20, 40, 60, 80, 100, 120, 150, 180, and 200 mm/s, with
impact angles 0, 15, and 30 degrees cycled across them. Checks per approach:
contact detected, zero tunneling steps (tip inside the organ with no contact
point), wrench finite and non-zero on every contact step, bridge schema and
timing checks, and culling reduction. This is a smoke suite, not the G2.3 gate
suite (1000 trials, with dissection and cutting in slice 2).

### Known limits (slice 1)

* Gravity is 0 in the contact scene. With gravity on, the reference base fixation
  does not hold the organ (the organ sinks through its own fixed face). The same
  defect applies to `reference_scene.scn`, and the G2.2 timing result does not
  validate the physical state.
* The swept test samples the tool points only. Edges between points are not swept.
* Peak contact forces (up to 65 N at 60 mm/s) exceed realistic needle forces. The
  penalty stiffness and damping are not calibrated.
* The puncture anisotropy ratio and the resistance constants are placeholders.
* Dissection, cutting, and the 1000-trial G2.3 suite are slice 2.
