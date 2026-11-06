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
  scene meshes in `src/meshes/`: the liver envelope decimated to a 16 mm grid
  (733 nodes, 2490 tets), the keep-out boundary points, and the keep-out
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
