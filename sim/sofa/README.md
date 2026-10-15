# SOFA FEM Scenes and Plugins

Task 2.2 output (SRS FR-MS-002, FR-MS-003). Pinned install: SOFA v26.06.00 at
`C:\Users\salmo\SOFA\v26.06.00` (row and evaluation record in `sim/SOUP.md`).

## Contents

* `src/reference_scene.scn` - THE pinned G2.2 reference scene: hyperelastic
  parenchymal organ (NeoHookean `TetrahedronHyperelasticityFEMForceField` on
  disjoint parenchyma/tumor subsets of a shared mechanical state), implicit
  solver chain (`EulerImplicitSolver` + `PCGLinearSolver`), fixed base slab,
  gravity `0 -9.81 0`, and a `VasculatureKeepOut` centerline node with no
  material coupling yet (coupling is a later task for FR-RTA-003).
* `src/generate_reference_mesh.py` + `src/meshes/` - deterministic mesh
  generator (organ block, tumor/parenchyma subsets, keep-out centerline).
  Regenerate with `python sim/sofa/src/generate_reference_mesh.py`.
  Placeholder meshes until gate G2.1 segmentation meshes land.
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
python sim\sofa\src\run_reference_scene.py --steps 1000 --label run
python -m pytest vv\tests\OQ\test_oq_fr_ms_002_solver_rate.py -v
cmake -S . -B build\sofa-check -DSRTA_BUILD_SOFA=ON -DSofa_DIR=C:\Users\salmo\SOFA\v26.06.00\lib\cmake\Sofa.Framework
```

`runSofa.exe` is resolved from `SRTA_RUN_SOFA` or the pinned install path;
the pytest test skips with a clear reason when it is absent. Captures land in
`SNDEV/logs/sofa-*.json` (gitignored). Changing `src/reference_scene.scn`
re-opens gate G2.2.