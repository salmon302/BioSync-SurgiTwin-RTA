Title: Dissection and cutting with cited calibration and suite pilot (task 2.3 slice 2)
Date: 2026-11-06T18:35:49Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: task 2.3 slice 2, FR-MS-003 second half (dissection and cutting). Gate G2.3 is not closed in this slice; the 1000-trial gate run is a separate package.
Summary: Adds a tissue cutting model (tip-path tetrahedra removal with a documented release rule and topology integrity checks), replaces the slice-1 placeholder constants with cited values where a source exists, and adds a parameterized suite runner with per-trial checks and a 100-trial pilot.

## Task Reference

* DEVELOPMENT_PLAN.md Phase 2, task 2.3 (slice 2). The plan is not edited in this slice (a parallel builder may be editing it).
* SRS FR-MS-003: connectivity-based culling and CCD pipelines for multi-point tool-to-tissue contact, anisotropic needle puncture resistance, dissection, and cutting.
* Predecessor: `SNDEV/docs/impl-2026-11-06-task23-slice1-contact.md` (commit efd5a8e). Slice 1 left cutting, the calibration, and the 1000-trial suite for this slice.
* Gate G2.3 (proposed): zero tunneling events and zero missed contacts across a 1000-trial needle puncture and cutting suite. This slice runs a 100-trial pilot to validate the harness and the checks only.

## Specification Summary

* Cutting: when the tool path crosses tissue with sufficient penetration and axial force, remove the crossed tetrahedra (SOFA topology change), release the stored strain in the cut neighborhood by a documented rule, and verify topology integrity after each cut (no inverted or orphaned elements). Wrench capture keeps recording through a cut.
* Calibration: replace the placeholder constants (K_perp 100 N/m, A = 2.0, penalty stiffness 100 N/m) with cited values or justified ranges. Uncited values stay as placeholders and are marked as uncited model choices.
* Suite harness: parameterized over speed (10 to 200 mm/s), entry angle, entry point, and cut parameters. Per-trial checks: zero tunneling, zero missed contacts, finite wrench, topology integrity after cuts, capture schema validity. Pilot of 100 trials across the grid.
* README updates in `sim/sofa/` (cutting model, calibration sources, harness and checks, known limits).

## Pre-work Decisions

### Topology change mechanism

The SOFA topology modifier components exist in the pinned build (`Sofa.Component.Topology.Container.Dynamic.dll` exports `removeTetrahedra`). The SofaPython3 binding does not expose the method: `TetrahedronSetTopologyModifier` lists only the base Data (`bbox`, `componentState`, `listening`, `propagateToDOF`, `removeIsolated`, `printLog`, `tags`, `name`). A probe scene (`SNDEV/logs/probe-topo/probe_scene.py`) confirmed this.

An in-process rebuild of the organ subgraph was then probed (`SNDEV/logs/probe-topo/probe_rebuild.py`): `root.removeChild` followed by a new organ node and `Sofa.Simulation.init` in the animate-end event. It failed with `[TetrahedronSetTopologyContainer(topo)] Cannot find triangle 0 [1, 2, 3] in tetrahedron 0` and runSofa exited with code 3.

Decision: the cut is a checkpoint and restart. The scene controller detects the cut criterion at tick t, writes the post-step state (positions, velocities, rest configuration, tetrahedra, base flags, controller state) to a checkpoint, writes the segment capture, and exits with code 10. The driver (numpy, `cut_topology.py`) edits the mesh, checks integrity, and starts the next runSofa segment at tick t+1 from the checkpoint. The mesh rebuild is a fresh SOFA load, which the probe showed initializes correctly. This is a deviation from the brief's "SOFA topology modification in the scene controller": the topology edit is performed in numpy and the SOFA scene is rebuilt.

### Calibration sources (verified this session)

| Parameter | Value | Source | Use in slice 2 |
|---|---|---|---|
| Fracture toughness G_c | 164 +/- 6 J/m^2 (bovine liver) | Gokgol C, Basdogan C, Canadinc D. Estimation of fracture toughness of liver tissue: experiments and validation. Med Eng Phys. 2012;34(7):882-891 (PMID 22024208). Abstract states "J = 164 +/- 6 J/m2" for bovine liver. | Cut criterion (below) |
| Interaction stiffness Ke | 430 N/m (simulation of a bevel-tip needle in a gelatine phantom) | Roesthuis RJ, van Veen YRJ, Jahya A, Misra S. Mechanics of needle-tissue interaction. IROS 2011. Fig. 12 caption and text: "Simulation (Ke = 430 N/m)". | K_perp (phantom to liver transfer, flagged) |
| Shaft friction per unit length | 0.0265 N/mm (10 mm/s), 0.0339 N/mm (20 mm/s), gelatine phantom | Roesthuis et al. 2011, Conclusions | Not implemented in slice 2 (known limit) |
| Insertion force decomposition | capsule stiffness, friction, cutting | Okamura AM, Simone C, O'Leary MD. Force modeling for needle insertion into soft tissue. IEEE Trans Biomed Eng. 2004;51(10):1707-1716. DOI 10.1109/TBME.2004.831542. Abstract. | Model structure only; the numeric cutting constant was not read from the full text, so no number is taken from it |

The following remain uncited model choices (placeholders): anisotropy ratio A = 2.0, penalty contact stiffness 100 N/m, penalty damping 0.5 N s/m, minimum penetration for cutting, the release neighborhood depth, and the tool shaft width used in the cut force.

Status of each item is recorded in the Implementation Notes below as the work proceeds.

## Implementation Notes

### Files changed

* `sim/sofa/src/cut_topology.py` (new, MIT): tetrahedron containment, Neo-Hookean monitor energy, release rule, integrity checks, checkpoint I/O.
* `sim/sofa/src/contact_scene.py` (rewritten from slice 1): organ built from a state dict (fresh or checkpoint), cut trigger, checkpoint and exit code 10, full-boundary swept check, per-segment outputs, fallback correction, tetrahedron-containment inside state with 50-tick exit hysteresis.
* `sim/sofa/src/run_contact_suite.py` (rewritten): 100-trial grid, segment driver, cut application, nine per-trial checks, summary.
* `sim/sofa/README.md`: cutting model, calibration table with sources, harness and checks, known limits.
* No change under `sim/bridge/` (the capture schema is unchanged). No change to `DEVELOPMENT_PLAN.md`, `sim/SOUP.md`, `sim/segmentation/`, `sim/fmi/`, `env/`, `vv/`, or `SRS.md`.

### Topology change (deviation from the brief)

The brief asked for SOFA topology modification in the scene controller. This build exposes `removeTetrahedra` in the DLL, but SofaPython3 does not bind it (probe: `SNDEV/logs/probe-topo/probe_scene.py`). An in-process subgraph rebuild failed with `Cannot find triangle 0 [1, 2, 3] in tetrahedron 0` (probe: `SNDEV/logs/probe-topo/probe_rebuild.py`). The implemented path is a checkpoint and restart: the controller writes the state and exits with code 10; numpy applies the cut; the next runSofa segment starts from the edited state. The exit code was confirmed as 10 by a probe (`probe_exit.py`); `sys.exit` returns 0 and is not used.

### Cutting model

* Cut criteria (all required): tip inside a tetrahedron; penetration at least 1.0 mm past the entry point (uncited choice); axial puncture force at least `G_c w = 164 J/m^2 x 1.0 mm = 0.164 N`; the tip path (9 samples from tick t-1 to t) lies in at least one tetrahedron.
* Removal: all tetrahedra containing a path sample (usually one per cut on this mesh).
* Release rule: one-ring neighbors of the removed tetrahedra have their rest positions reset to their current positions. The neighborhood Neo-Hookean energy before the reset is recorded as released energy; after the reset it is about 1e-18 J.
* Integrity after each cut: valid, distinct node indices; no orphan nodes; no inversion in current or rest configuration; no non-manifold face; one connected component; finite values. The driver also checks that its recomputed crossed set equals the scene's crossed set.

### Calibrated parameter table

| Parameter | Value | Status | Source or basis |
|---|---|---|---|
| `puncture_k_perp` | 430 N/m (was 100) | cited, phantom transfer | Roesthuis RJ et al., IROS 2011, Ke = 430 N/m (gelatine phantom, Fig. 12 label) |
| `puncture_anisotropy` | 2.0 | uncited placeholder | none |
| `contact_stiffness` | 100 N/m | uncited placeholder | none found in this session |
| `contact_damping` | 0.5 N s/m | uncited placeholder | none found |
| `contact_m` | 0.5 mm | uncited choice | none |
| G_c | 164 J/m^2 | cited, bovine liver | Gokgol C et al., Med Eng Phys 2012, PMID 22024208 |
| cut width | 1.0 mm | uncited geometry choice | twice shaft radius |
| `cut_min_depth_mm` | 1.0 mm | uncited choice | none |
| `release_rings` | 1 | uncited choice | none |
| exit hysteresis | 50 ticks | uncited choice | none |
| friction | not implemented | cited value 0.0265 N/mm at 10 mm/s (Roesthuis 2011) | out of scope for this slice |

Source verification: the G_c value was read from the PubMed index entry and the search excerpt ("J = 164 +/- 6 J/m2" for bovine liver). The Ke value and friction values were read from search excerpts of the Roesthuis paper. The PDF could not be fetched (content type application/pdf). The Okamura 2004 structure is cited, and no numeric cutting value is taken from it. Both Roesthuis values and the Gokgol value should be checked against the full texts before G2.3 closure.

### Defects found and fixed during the slice

1. The slice-1 nearest-culled-face fallback ranked faces by plane distance. Replaced by point-to-triangle distance. This did not change the 28 N transient (candidate path, see Known limits).
2. The tip inside state was flickering. The three-direction ray test and then the tetrahedron containment both alternated about every 20 ticks at the top surface. At 10 mm/s the depth never reached 1 mm, and the first pilot had zero cuts in all 10 mm/s trials (run `pilot-20261106` was stopped after 15 trials for this reason; its partial output is discarded). Fix: tetrahedron containment for the inside state plus 50-tick exit hysteresis on the entry point. After the fix the 10 mm/s debug trial (`D010`) made two cuts. The residual flicker (84 transitions in D010 before hysteresis) suggests the top surface oscillates under the penalty and puncture forces. This is not resolved.
3. The runner's numpy linalg call failed (exit 0xC06D007F, a delay-load "module not found") when the pixi library directory was not on PATH. The runner now sets PATH before numpy loads.

### Harness and checks

`run_contact_suite.py --label pilot-20261106-r2 --workers 3`. Grid: 10 speeds x 5 angles (0, 10, 15, 20, 30 degrees) x 2 entry points (top point, and offset 3 mm in z), 100 trials. Outputs: `SNDEV/logs/task23-cut-pilot-20261106-r2/` (`summary.json`, `T###/` with `bridge_capture.csv`, `diagnostics.csv`, segment files, `checkpoint.json`, `runSofa_seg##.log`). Captures are in SNDEV/logs (gitignored, not committed); the summary and this log are the committed evidence.

Quiet-host check before the run: recorded in `summary.json` (`quiet_host_before`).

### Pilot results (100 trials)

| Check | Pass | Fail |
|---|---|---|
| contact_detected | 100 | 0 |
| zero_tunneling | 99 | 1 (T081) |
| zero_missed_contacts | 99 | 1 (T099) |
| finite_wrench | 100 | 0 |
| topology_integrity | 100 | 0 |
| capture_schema | 100 | 0 |
| wrench_continuity | 100 | 0 |
| culling_reduction | 100 | 0 |
| exit_clean | 100 | 0 |

Trials passed: 98 of 100. Cuts: 198 total (every trial has at least one cut; 27 trials with 1 cut, 58 with 2, 6 with 3, 8 with 4, 1 with 5). Segments: 298. Integrity failures: 0. Summed released energy: 0.043 J (per-trial sums). Wall time: 4729 s total over the three workers.

Failures, with evidence:

* T081 (180 mm/s, 0 degrees, top entry point): tunneling step at tick 181 (`inside=1`, `contact_points=0`). That tick is also a cut tick. The previous tick (180) had 17 contact points and a 70.7 N contact force, and the organ top rose from 0.160 m to 0.1652 m. At tick 181 the top was at 0.1661 m, about 9 mm above the tip (0.1574 m). The tip was inside the tetrahedra but ray-parity found no inside, so the fallback did not engage. Cause: uncalibrated penalty transient, plus the inside-state inconsistency between tetrahedron containment and ray parity once the organ is strongly displaced. Evidence files: `SNDEV/logs/task23-cut-pilot-20261106-r2/T081/diagnostics_seg02.csv` (ticks 177 to 183).
* T099 (200 mm/s, 30 degrees, offset entry point): four missed tool points at tick 185 (full-boundary swept hits at ticks 184 and 185, no contact record). The tip was 6 mm below the top, outside the tetrahedra, in the cut channel from the cut at tick 156. Cause not confirmed. Working hypothesis: faces created by the cut lie outside the static corridor-culled set. Evidence: `SNDEV/logs/task23-cut-pilot-20261106-r2/T099/diagnostics_seg01.csv`, ticks 183 to 187.

Wrench continuity and step signature: capture rows exist on both sides of all 198 cuts in all 100 trials, and the wrench is finite there. The median absolute wrench step at a cut tick is 2.30 N, against a median of 0 and a 99th percentile of 3.54 N over the other ticks (140822 ticks, `SNDEV/logs/pilot_wrench_stats.py`). The cut step is not separable from ordinary ticks in this model.

Peak forces: largest contact peak 70.7 N (T081), largest puncture peak 3.6 N. The contact peaks are penalty transients.

### Interpretation

The harness runs, the per-trial checks fire on real events (two trials fail with traceable evidence), and the cut and integrity path works over 198 cuts. The G2.3 gate is not met by this model: the pilot has one tunneling and four missed-contact events, and the gate requires zero of each over 1000 trials. The uncited penalty parameters and the penalty transients are the leading cause in T081. The cut-channel culling is the leading candidate for T099, unconfirmed.

Slice-1 smoke logs (`task23-smoke-slice1-*`) were produced by the earlier code. The current scene changes the fallback, the inside state, and the exit hysteresis, so those logs no longer reproduce with the current code.

### Plan consolidation (for the later package, not edited here)

* Task 2.3 row: slice 2 done as a cutting model, cited partial calibration, and a 100-trial pilot. The SOFA topology path changed to checkpoint and restart. The 1000-trial gate run is not run.
* G2.3 gate: open. Pilot shows 1 tunneling and 4 missed-contact events in 100 trials.
* SOUP: SofaPython3 and the pixi CPython 3.12.16 runtime remain the same as slice 1. No new dependency was added. numpy is used through the pixi environment (version 2.5.4 as reported by its interpreter).
* Sources for `sim/SOUP.md` or the plan citation list: Gokgol 2012, Roesthuis 2011, Okamura 2004.

### Commit

Pending (see the commit message and the report).
