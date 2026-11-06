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
* `src/contact_scene.py`, `src/cut_topology.py`, `src/run_contact_suite.py` -
  task 2.3 contact, cutting, and the parameterized suite (see the sections below).

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
* Penalty normal force (slice 2b): `f = min(max(k pen - c (v . n), 0), F_cap) n`, with
  `F_cap = 1.0 N` per tool point (uncited model choice). A candidate with `pen > 0`
  is a contact record even when the net force is zero (see the missed-contact
  definition below). `pen = 0.5 mm - sd`,
  `k = 100 N/m`, `c = 0.5 N s/m`, and `n` the outward face normal.
* Reaction: distributed to face nodes by barycentric weights through a
  `ConstantForceField` with a fixed node index set.
* Wrench on the tool: summed contact force and torque, minus the puncture force.

The SOFA collision pipeline (`CCDTightInclusionIntersection`, or
`LocalMinDistance`, with `RuleBasedContactManager` and `TriangleCollisionModel`)
was configured in this build and produced no contact response, so it is not used
in the scene.

### Puncture resistance (first model, calibrated in slice 2)

Directional resistance along the insertion direction, driven by the depth `s`
of the tip past its entry point:

    K(phi) = K_perp (sin^2 phi + A cos^2 phi),    F_p = K(phi) s

* `phi` is the angle between the insertion direction and the fiber direction
  (fixed to the x axis).
* `K_perp = 430 N/m` (cited, see Calibration). `A = 2.0` is an uncited model
  choice.
* The force acts opposite the insertion on the tool and is distributed to the
  four organ nodes nearest the entry region.

### Cutting model (task 2.3 slice 2)

The tip is inside the organ when it lies in a tetrahedron of the current mesh
(barycentric containment, `cut_topology.tets_containing`). The entry point is set
at the first inside tick and reset only after 50 consecutive ticks outside
(`EXIT_HYSTERESIS_TICKS`, uncited choice). The raw inside state gates the puncture
force and the cut. The slice-1 ray-parity test is kept only for the contact
fallback. The ray-parity state flickered at the top face in the slice-2 debug
trials, which kept the depth below 1 mm at 10 mm/s.

A cut is requested by the scene controller at tick t when all of these hold:

* the tool tip is inside the organ (above),
* the penetration `s` past the entry point is at least `cut_min_depth_mm` (1.0 mm,
  uncited choice),
* the axial puncture force `F_p = K(phi) s` is at least `cut_force_n`, which is
  `G_c w` with `G_c = 164 J/m^2` (cited) and `w = 1.0 mm` (the tool width,
  uncited choice). This gives `F_cut = 0.164 N`,
* the tip path from tick t-1 to tick t crosses at least one tetrahedron. The path
  is sampled at 9 points, and a tetrahedron is crossed when a sample lies inside it
  (barycentric test).

Topology change. SOFA's `TetrahedronSetTopologyModifier.removeTetrahedra` exists in
the pinned build, but SofaPython3 does not bind it (the modifier exposes only
its Data fields), and an in-process rebuild of the organ subgraph failed in a
probe (`Cannot find triangle ... in tetrahedron`). A cut therefore uses a
checkpoint and restart:

1. The controller writes the segment captures and `checkpoint.json` (node
   positions and velocities, the rest configuration, tetrahedra, base flags, and
   the controller resume values), then exits with code 10 (`os._exit`; the
   process exit code is 10, and SOFA prints a backtrace banner on the way out).
2. The driver (`run_contact_suite.py`) recomputes the crossed set from the tip
   path with `cut_topology.tets_containing` and compares it with the scene's set.
3. `cut_topology.apply_cut` removes the crossed tetrahedra and applies the
   release rule (below), then compacts the node numbering. Orphaned nodes are
   removed and the references are renumbered.
4. `cut_topology.check_integrity` runs on the new state. The next runSofa segment
   starts at tick t+1 from the edited state, with the same capture file series.

Release rule (slice 2c). Only the crossed tetrahedra are removed. Their stored
strain energy is the compressible Neo-Hookean energy, with the ParameterSet values
(mu = 1785.714286 Pa, lambda = 7142.857143 Pa) taken as the Lame pair (a monitor
convention, not verified against the SOFA parameter definition). This energy is the
released energy, recorded as `released_energy_j` and always non-negative. The total
energy changes by exactly minus that amount (`total_energy_jump_j`). The neighbor
tetrahedra keep their rest configuration, and their strain relaxes through the
solver. The slice-2 rule reset the rest positions of a one-ring neighborhood. It
created energy in the second ring (a mixed rest configuration), up to +3.7e-3 J at
one cut, and it is retired. The mass is recomputed from the surviving rest volume
(the total mass scales with the rest volume).

Integrity checks after every cut (`cut_topology.check_integrity`): every
tetrahedron references four distinct valid nodes, no node is orphaned, no
tetrahedron is inverted in the current or the rest configuration (sign equal to
the reference mesh orientation), no face is shared by more than two tetrahedra,
there is at least one boundary face, the tetrahedra form one connected component,
and all values are finite. A failed check ends the trial with the failure recorded.

Contact after a cut. The culled candidate set is recomputed from the current
boundary and the same corridor on every segment, so the cut faces are candidates
from the next segment on.

### Contact fallback correction (slice 2)

The nearest-culled-face fallback (a tool point inside the organ with no candidate)
ranked faces by distance to their planes. It now uses the point-to-triangle
distance (plane distance inside the projection, else the nearest edge), and the
reaction weights are clamped to the face and renormalized. The slice-1 smoke
trials are not rerun with this change, so their recorded values stand as slice-1
results. In the slice-2 debug trial, this change did not alter the 28 N contact
transient at cavity re-entry, which comes from the candidate path (points deep in
the tissue under the penalty term). That transient is a penalty-model artifact and
is recorded as such.

### Smoke suite

Ten approaches at 10, 20, 40, 60, 80, 100, 120, 150, 180, and 200 mm/s, with
impact angles 0, 15, and 30 degrees cycled across them. Checks per approach:
contact detected, zero tunneling steps (tip inside the organ with no contact
point), wrench finite and non-zero on every contact step, bridge schema and
timing checks, and culling reduction. This is a smoke suite, not the G2.3 gate
suite (1000 trials, with dissection and cutting in slice 2).

### Calibration (slice 2)

| Parameter | Value | Status | Source |
|---|---|---|---|
| `puncture_k_perp` (K_perp) | 430 N/m | cited, verified against the full text (Roesthuis 2011, p. 2563); a lateral phantom stiffness used as an axial stiffness (mapping limit, see Verified citations) | Roesthuis RJ, van Veen YRJ, Jahya A, Misra S. Mechanics of needle-tissue interaction. IROS 2011. Ke = 430 N/m in the gelatine phantom simulation (Fig. 12 label, from a search excerpt only). |
| `contact_force_cap_n` | 1.0 N per tool point | uncited model choice (slice 2b) | none |
| `puncture_anisotropy` (A) | 2.0 | uncited model choice | none |
| `contact_stiffness` (k) | 100 N/m | uncited model choice | none found |
| `contact_damping` (c) | 0.5 N s/m | uncited model choice | none found |
| `contact_m` (margin) | 0.5 mm | uncited model choice | none |
| Fracture toughness G_c | 164 J/m^2 | cited, bovine liver; verified against the full text (Gokgol 2012, p. 885 and Fig. 8, p. 886; intercept of the diameter fit) | Gokgol C, Basdogan C, Canadinc D. Estimation of fracture toughness of liver tissue: experiments and validation. Med Eng Phys. 2012;34(7):882-891. Abstract: "J=164±6 J/m(2)" for bovine liver. |
| Cut width w | 1.0 mm | uncited geometry choice | twice the 0.5 mm shaft radius |
| Cut force F_cut = G_c w | 0.164 N | derived from the two rows above | none |
| `cut_min_depth_mm` | 1.0 mm | uncited model choice | none |
| `release_rings` | 1 | uncited model choice | none |
| NeoHookean (mu, lambda) | 1785.714286, 7142.857143 Pa | reference scene ParameterSet, monitor only | `src/reference_scene.scn` |
| Shaft friction | not implemented | cited value 0.0265 N/mm (10 mm/s), 0.0339 N/mm (20 mm/s), gelatine phantom | Roesthuis et al. 2011 (above) |

Notes on the sources:

* The Okamura model structure (capsule stiffness, friction, cutting) is cited from
  Okamura AM, Simone C, O'Leary MD. Force modeling for needle insertion into soft
  tissue. IEEE Trans Biomed Eng. 2004;51(10):1707-1716 (DOI 10.1109/TBME.2004.831542).
  No numeric cutting constant is taken from it, because the full text was not read.
* The Ke and friction values were read from the paper's Fig. 12 label and
  conclusions in the search index. The PDF could not be fetched in this session, so
  the values are recorded from those excerpts, and the paper should be checked
  against the full text before the G2.3 closure.
* The stiffness value is for a bevel-tip needle in gelatine, not liver. Its use as
  K_perp for liver is a transfer assumption.
* No citable source was found for the penalty stiffness, damping, or the
  anisotropy ratio A in the time available. These stay as uncited model choices.

### Verified citations (slice 2c)

The four papers were checked against the full texts (owner-supplied PDFs in
`SNDEV/research/`, read-only, not committed). Page numbers are the journal page
numbers printed on each page.

| Value | Source (full bibliographic) | Location | Context | Model role |
|---|---|---|---|---|
| Ke = 430 N/m, optimum of the interaction stiffness | Roesthuis RJ, van Veen YRJ, Jahya A, Misra S. Mechanics of needle-tissue interaction. Proc IEEE/RSJ IROS 2011, pp. 2557-2563. | Sec. VI and Fig. 12 caption, p. 2563 ("found to be 430 N/m, the corresponding error is 0.179 mm"); error curve Fig. 11, p. 2562 | Gelatine phantom, Young's modulus 35 kPa (Sec. V, p. 2560), bevel-tip stainless steel needle, 1 mm diameter, 30 degree bevel (Table I, p. 2560), insertion 10 and 20 mm/s (p. 2560) | Lateral interaction stiffness of a cantilever-on-springs model (per insertion step, N/m). Not an axial puncture stiffness. Used as K_perp (see mapping note). |
| Friction 0.0265 N/mm (10 mm/s), 0.0339 N/mm (20 mm/s) | Roesthuis et al. 2011 | Table II, p. 2560 (averages over 20, 30, 40, 50 mm phantoms); Conclusions p. 2563 | Gelatine phantom | Not implemented in slice 2c (known limit) |
| Fracture energy J = 164 +/- 6 J/m^2 (intercept) | Gokgol C, Basdogan C, Canadinc D. Estimation of fracture toughness of liver tissue: experiments and validation. Med Eng Phys. 2012;34(7):882-891. DOI 10.1016/j.medengphy.2011.09.030. | Abstract, p. 882; linear fit y = -29x + 164 (R^2 = 0.981) on p. 885 and Fig. 8, p. 886; intercept stated p. 885 | Fresh whole bovine livers, 3 animals, tested within 2 h of harvest (p. 884); needle insertion at 3 mm/s to 20 mm depth (p. 885); needles 2, 3, 4, 5 mm diameter with entry angles 12, 18, 24, 30 degrees (p. 884) | G_c in the cut criterion F_cut = G_c w |
| Gokgol measured diameter dependence | Gokgol et al. 2012 | Table 2, p. 886 (average over 3 animals): 2 mm 110.83 +/- 4.32; 3 mm 70.63 +/- 4.32; 4 mm 45.88 +/- 2.83; 5 mm 22.33 +/- 2.10 J/m^2 | as above | Shows that G_c is an extrapolation. The model cut width (1.0 mm) is outside the tested 2 to 5 mm range. |
| Stiffness polynomial f(z) = a1 z + a2 z^2 (N, z in mm) | Okamura AM, Simone C, O'Leary MD. Force modeling for needle insertion into soft tissue. IEEE Trans Biomed Eng. 2004;51(10):1707-1716. DOI 10.1109/TBME.2004.831542. | Eq. (2)-(3), p. 1709; liver 1 a1 = 0.0480 N/mm, a2 = 0.0052 N/mm^2; liver 2 a1 = 0.0020 N/mm, a2 = 0.0023 N/mm^2 (p. 1709) | Bovine liver, ex vivo, room temperature, 3 to 6 h post-mortem (p. 1709), 3 mm/s, 1.27 mm OD bevel needle (p. 1709) | Comparison only. Not used as a parameter (see the mapping note). |
| Peak pre-puncture force 2.3040 +/- 0.8286 N at 16.6514 +/- 3.5470 mm (19 insertions, capsule intact) | Okamura et al. 2004 | p. 1709 | as above | Comparison only |
| Friction (Karnopp model, per unit length) D_p 18.45 N/m, D_n -18.23 N/m, b_p 212.31 N s/m^2, b_n -293.08 N s/m^2, C_p 10.57 N/m, C_n -11.96 N/m | Okamura et al. 2004 | Table I, p. 1712 | bovine liver, sinusoidal motion 0.2 Hz, 20 mm/s amplitude (p. 1710) | Comparison only; same order as the Roesthuis friction values (26.5 to 33.9 N/m) |
| Cutting force F_cutting = 0.94 +/- 0.36 N (5 insertions at 3 mm/s) | Okamura et al. 2004 | Eq. (11) and text, p. 1712 | bovine liver, 1.27 mm OD bevel needle | Comparison only (see the cut-criterion mapping) |
| Insertion force decomposition F_total = F_stiffness + F_friction + F_cutting | Okamura et al. 2004 | Eq. (1), p. 1708 | as above | Model structure |
| Friction parameter mu_s (N/mm, per unit length) and swept-force term | Jackson RC, Desai V, Castillo JP, Cavusoglu MC. Needle-tissue interaction force state estimation for robotic surgical suturing. Proc IEEE/RSJ IROS 2016, pp. 3659-3664. | Sec. III, p. 3660 (friction wrench with mu_s in N/mm); Sec. IV, p. 3661 (stiffness K range 0.015 to 0.032 N/mm^2 for K_x, K_y, K_z); Sec. IV p. 3662 (cutting terms set to zero, alpha = beta = 0) | Semicircular CT-1 suture needle, ex vivo beef, 2 kHz force data | Structure support only. The needle geometry (circular) and the swept-area term are not in the straight-needle puncture model. No value from this paper is used. |

Cut criterion mapping. The model criterion is F_cut = G_c w with G_c = 164 J/m^2 and
w = 1.0 mm, which gives 0.164 N. This is a fracture-energy trigger: a crack advancing
across a width w releases G_c w of energy. Okamura's F_cutting = 0.94 N is a measured
force constant for a 1.27 mm bevel needle that includes tip stiffness, and it is not a
threshold on the same quantity. The model uses the G_c w trigger. The Okamura value is
a comparison only. A linear reading of the F_cutting constant (0.94 N divided by the
1.27 mm diameter) would give about 740 J/m^2, which is far above the Gokgol value. The
two constructs are not reconciled in this slice.

Stiffness mapping. K_perp = 430 N/m is a lateral interaction stiffness from a
phantom simulation (Roesthuis). The model applies it as an axial puncture stiffness
(F_p = K_perp s). The Okamura polynomial is the measured liver pre-puncture force
(N) against tip displacement (mm). At 8 mm, the polynomial gives 0.72 N for liver 1
(a1 z + a2 z^2 = 0.384 + 0.333) and 0.163 N for liver 2 (0.016 + 0.147). The model
gives 3.44 N at 8 mm (430 N/m times 8 mm). The model is therefore stiffer than the
liver polynomial by a factor of about 4.8 (liver 1) and 21 (liver 2) at that depth. The
liver polynomial is the closer construct for the axial case. Replacing K_perp is an
owner decision, and it is not made in this slice.

Transfer limitations. The gelatine and ex vivo bovine values transfer to in vivo human
liver with documented limits: no perfusion or vascular pressure (Okamura 2004, p. 1715,
"vascular pressure, bleeding, and temperature will affect the tool-tissue interaction
forces"); no bile duct or vessel turgor; boundary constraints and post-mortem
degradation (tests at 3 to 6 h post-mortem, p. 1709); temperature and fluid loss (tests
at room temperature, p. 1709). The gelatine phantom of Roesthuis is a single homogeneous
material at 35 kPa and has no organ structure. The Gokgol fracture values come from
whole bovine livers tested within 2 h, and the Gokgol paper states that the
bounds of its values are tighter than earlier reports (p. 888). None of these values
was measured in human tissue.

### Suite harness and checks (slice 2)

`src/run_contact_suite.py` runs the grid and writes
`SNDEV/logs/task23-cut-<label>/` (per-trial segment files, `T###/bridge_capture.csv`,
`T###/diagnostics.csv`, and `summary.json`). Grid: 10 speeds (10, 20, 40, 60, 80,
100, 120, 150, 180, 200 mm/s), 5 entry angles (0, 10, 15, 20, 30 degrees), and 2 entry
points (the top-surface point, and the same point offset 3 mm in z). That is 100
trials. The cut parameters are the calibrated values above (the runner builds them
from `CALIBRATION` in the script).

```powershell
python sim\sofa\src\run_contact_suite.py --label <label> [--limit N] [--workers N]
```

Per-trial checks (a trial passes when all nine pass):

* `contact_detected`: at least one contact step.
* `zero_tunneling`: no step has the tip inside the organ with zero contact points.
* `zero_missed_contacts`: no tool point has a full-boundary swept hit without a contact
  record at that tick. The full-boundary test is independent of the culled candidate
  set.
* `finite_wrench` (episode rule, owner ruling 2026-11-06): the wrench is finite at
  every contact step, and the peak 6-vector wrench norm of each contact episode is
  strictly positive. An episode is a maximal run of consecutive contact steps. Episode
  peaks are in each trial's evidence (`episodes`).
* `topology_integrity`: every cut passes `check_integrity`, and the driver's crossed set
  equals the scene's crossed set.
* `capture_schema`: exact header, consecutive ticks from 0 across all segments, row count
  equal to the trial steps, time_s on the 1 kHz grid, unit quaternions, finite values.
* `wrench_continuity`: a capture row exists on both sides of every cut, and the wrench is
  finite there.
* `culling_reduction`: the culled set is smaller than the full boundary in every segment.
* `exit_clean`: the last segment exits with code 0 and no `[ERROR]` line other than the
  install-level `readBasicIniFile()` message.

### Known limits (slices 1 and 2)

* Gravity is 0 in the contact scene. With gravity on, the reference base fixation
  does not hold the organ (the organ sinks through its own fixed face). The same
  defect applies to `reference_scene.scn`, and the G2.2 timing result does not
  validate the physical state.
* The swept test samples the tool points only. Edges between points are not swept.
* Peak contact forces are penalty transients, not calibrated needle forces. In the
  slice-2 pilot the largest contact peak was 70.7 N (T081, 180 mm/s), against a
  largest puncture peak of 3.6 N. The penalty stiffness and damping are uncited.
  The transients displace the organ top by several millimetres (T081 at tick 180).
* The wrench step at a cut is not a separate cutting signature in this model. In the
  pilot, the median absolute step in the wrench at a cut tick is 2.30 N (198 cut
  events), while the 99th percentile over all other ticks is 3.54 N, and the median
  over all other ticks is 0. Cut steps lie inside the ordinary tick distribution.
* Slice 2b pilot (100 trials, `pilot-slice2b`): tunneling 0 steps, missed-contact 0
  points. Trials passing all nine checks: 84 of 100. All 16 failures are
  `finite_wrench`, caused by contact steps whose net force is exactly zero (1 to 6
  steps per trial, tip outside the organ). Under the slice-2b record rule, a
  candidate in penetration is a contact record even when damping cancels the
  penalty force. This changes the meaning of "contact record" and is an owner
  decision (see the slice-2b log). The checks were not changed.
* The T081 and T099 failure modes from slice 2 are addressed (see the slice-2b log).
  Their root causes were a per-point penalty force with no bound (organ nodes of about
  4 g each received velocities near 9 m/s at a cut restart) and a damping term that
  cancels the penalty at a point in penetration.
* The gate G2.3 is not closed. The slice-2b pilot is not the 1000-trial gate run.
* The cut is an approximation. Removing whole tetrahedra on the coarse 20 mm mesh
  (element size of a few millimetres) removes a channel several elements wide
  relative to the 1 mm tool. The mesh resolution is the main limit on cut geometry.
* Topology change uses checkpoint and restart, not an in-process topology edit (see
  the cutting model). Each cut is a process restart, so trial time grows with the
  number of cuts.
* Shaft friction is not in the wrench model, although a cited value exists.
* The puncture anisotropy ratio A is an uncited placeholder.
* The 1000-trial G2.3 suite is not run. The pilot validates the harness and the checks
  only.
