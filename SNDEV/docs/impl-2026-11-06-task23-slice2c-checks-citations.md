Title: Episode-level wrench rule, cut-energy accounting, verified calibration citations, and re-pilot (task 2.3 slice 2c)
Date: 2026-11-06T21:31:16Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: task 2.3 slice 2c, follow-up to slices 2 and 2b (`impl-2026-11-06-task23-slice2-cutting.md`, `impl-2026-11-06-task23-slice2b-fixes.md`). Owner ruling 2026-11-06: contact-record semantics unchanged; the wrench check becomes episode-level. Gate G2.3 is not closed.
Summary: Changes the wrench check to an episode rule, retires the one-ring rest reset in favor of a signed energy accounting that removes only the crossed tetrahedra, verifies the calibration citations against the owner-supplied full texts, and re-runs the 100-trial pilot.

## Task Reference

* Owner ruling (2026-11-06): episode-level `finite_wrench`; contact-record semantics stay as the slice-2b T099 fix left them.
* Owner-supplied PDFs in `SNDEV/research/` (read-only, not committed): `roesthuis11-iros.pdf`, `gokgol2011.pdf`, `okamura2004.pdf`, `jackson2016.pdf`.
* The 1000-trial gate run (G2.3) is conditional on a clean re-pilot. It is deferred (see Gate status).

## Specification Summary

* Episode rule: wrench finite at every contact step, and the peak wrench norm of each contact episode is strictly positive.
* Cut energy: fix the accounting so the released energy is physically signed and bounded.
* Citations: verify each value against the full texts, record figure and page, material and rate context, and the model role. Map the cutting criteria and the stiffness honestly. Add the transfer-limitation note.
* Re-pilot: 100 trials, same grid, all nine checks.
* Conditional: 1000-trial gate run with pre-registered clauses, only if the re-pilot is clean.

## Implementation Notes

### 1. Episode-level wrench check

`run_contact_suite.py` `check_trial`: contact steps are grouped into episodes (maximal runs of consecutive contact steps). Pass when every wrench value is finite at every contact step, and every episode has a peak 6-vector wrench norm strictly greater than zero. Episode lists (start tick, length, peak norm) are in each trial's `evidence.episodes`. The check definition was not changed for contact records, tunneling, or missed contacts.

### 2. Cut-energy accounting

Diagnosis (slice 2b, T081 cut at tick 181): the slice-2 release rule reset the rest configuration of the one-ring neighborhood to the current positions. Tetrahedra in the second ring then have mixed rest configurations (some nodes reset, some not), which store strain that the original rest did not. The total Neo-Hookean energy rose by +3.7e-3 J at that cut. This was an accounting artifact, not a physical release.

Fix (`cut_topology.apply_cut`): only the crossed tetrahedra are removed. Their Neo-Hookean energy (with the ParameterSet values taken as the Lame pair; a monitor convention) is the released energy, always non-negative. The neighbor rest configuration is unchanged, so the neighbor strain relaxes through the solver. The total energy change equals minus the released energy exactly.

Verification: the cut records of T081 and T099 in the slice-2c debug run (`SNDEV/logs/task23-cut-slice2c-debug/*/cuts.json`) satisfy `total_energy_jump_j + released_energy_j = 0` to machine precision (T081 cuts at ticks 174 and 179; T099 cut at tick 156; released 6.7e-7, 1.25e-4, and 3.7e-7 J).

Re-pilot distribution (per-trial sums of released energy over the trial's cuts, 100 trials, 155 cuts): minimum 3.67e-7 J, median 2.46e-6 J, maximum 1.75e-4 J, total 7.67e-4 J. All values are non-negative and bounded. Per-cut values are in the debug `cuts.json` files for the two debug trials only (the pilot summary keeps per-trial sums).

### 3. Citation verification (full texts)

All four PDFs were read in full. Journal page numbers are printed on each page.

Roesthuis RJ, van Veen YRJ, Jahya A, Misra S. Mechanics of needle-tissue interaction. Proc IEEE/RSJ IROS 2011, pp. 2557-2563.
* Ke = 430 N/m is the optimum of the interaction stiffness, "found to be 430 N/m, the corresponding error is 0.179 mm" (p. 2563, Sec. VI-adjacent text; Fig. 12 caption p. 2563). The error-versus-Ke curve, with its minimum near 430 N/m, is Fig. 11 (p. 2562). Verified.
* Material: gelatine phantom at 35 kPa, uniaxial compression (Sec. V, p. 2560). Needle: stainless steel, 1 mm diameter, 30 degree bevel (Table I, p. 2560). Insertion at 10 and 20 mm/s (p. 2560). Verified.
* Friction 0.0265 N/mm (10 mm/s) and 0.0339 N/mm (20 mm/s): Table II, p. 2560 (averages over 20, 30, 40, 50 mm phantoms); restated in the Conclusions (p. 2563). Verified.
* Mapping: Ke is the stiffness of springs supporting a cantilever needle, per insertion step, in a lateral deflection model. It is not an axial puncture stiffness.

Gokgol C, Basdogan C, Canadinc D. Estimation of fracture toughness of liver tissue: experiments and validation. Med Eng Phys. 2012;34(7):882-891. DOI 10.1016/j.medengphy.2011.09.030. PMID 22024208.
* Abstract, p. 882: J = 164 +/- 6 J/m^2 for bovine liver, "by fitting a line to the toughness values estimated from the set of insertion experiments."
* Fit y = -29x + 164 (R^2 = 0.981) on needle diameter x in mm, text p. 885, Fig. 8 p. 886. The intercept at zero diameter is the reported value. Verified.
* Table 2, p. 886: diameter-dependent averages 2 mm 110.83 +/- 4.32, 3 mm 70.63 +/- 4.32, 4 mm 45.88 +/- 2.83, 5 mm 22.33 +/- 2.10 J/m^2. Verified.
* Context: fresh whole livers from 3 animals, tested within 2 h of harvest (p. 884); insertion at 3 mm/s to 20 mm depth (p. 885); needles 2, 3, 4, 5 mm diameter with entry angles 12, 18, 24, 30 degrees (p. 884). Verified.
* Discrepancy with the slice-2 log: the earlier reference to "Fig. 8 p. 887" is corrected to p. 886. The fit text is on p. 885.

Okamura AM, Simone C, O'Leary MD. Force modeling for needle insertion into soft tissue. IEEE Trans Biomed Eng. 2004;51(10):1707-1716. DOI 10.1109/TBME.2004.831542.
* Decomposition F_needle = F_stiffness + F_friction + F_cutting (Eq. (1), p. 1708). Verified.
* Stiffness: f(z) = a1 z + a2 z^2 (Eq. (3), p. 1709). Liver 1: a1 = 0.0480 N/mm, a2 = 0.0052 N/mm^2. Liver 2: a1 = 0.0020 N/mm, a2 = 0.0023 N/mm^2 (p. 1709). Verified.
* Pre-puncture peak 2.3040 +/- 0.8286 N at 16.6514 +/- 3.5470 mm (19 insertions, capsule intact; p. 1709). Verified.
* Friction (Karnopp, per unit length): Table I, p. 1712: D_p 18.45 N/m, D_n -18.23 N/m, b_p 212.31 N s/m^2, b_n -293.08 N s/m^2, C_p 10.57 N/m, C_n -11.96 N/m. Verified. Note these are the same order as Roesthuis (26.5 and 33.9 N/m).
* Cutting: F_cutting = 0.94 +/- 0.36 N (5 insertions at 3 mm/s; Eq. (11) and text, p. 1712). Verified.
* Context: bovine liver, room temperature, 3 to 6 h post-mortem (p. 1709); 3 mm/s; 1.27 mm OD bevel needle (p. 1709). Verified.
* Limitation statement (p. 1715): "vascular pressure, bleeding, and temperature will affect the tool-tissue interaction forces." Verified.

Jackson RC, Desai V, Castillo JP, Cavusoglu MC. Needle-tissue interaction force state estimation for robotic surgical suturing. Proc IEEE/RSJ IROS 2016, pp. 3659-3664.
* Content: an unscented Kalman filter that segments the tissue sweep (deformation) force from friction and cutting in the needle body frame for a semicircular suture needle (CT-1). Validation on ex vivo angus beef with a 3-DOF benchtop stage and a 6-DOF sensor at 2 kHz (Sec. V, p. 3662).
* Parameters: friction parameter mu_s in N/mm (Eq. (3), p. 3660); stiffness K for the sweep term with a range of about 0.015 to 0.032 N/mm^2 for K_x, K_y, K_z (Sec. IV, p. 3661); cutting terms set to zero, alpha = beta = 0, because the sharp suture needle makes cutting negligible (Sec. IV, p. 3662).
* Relevance: structure support for a per-length friction term and for the decomposition. The needle is circular and the sweep term has no counterpart in the straight bevel puncture model. No value from this paper is used for calibration. It remains a supporting reference for the friction term, which is not yet implemented.

Calibration table, verified (also in `sim/sofa/README.md`, Verified citations):

| Model parameter | Verified value | Figure or table, page | Material and rate | Model role |
|---|---|---|---|---|
| K_perp | 430 N/m | Roesthuis, p. 2563 (text and Fig. 12), Fig. 11 p. 2562 | gelatine 35 kPa, 10 and 20 mm/s | Lateral interaction stiffness mapped to axial puncture stiffness (mapping limit) |
| G_c | 164 J/m^2 (zero-diameter intercept) | Gokgol, abstract p. 882; fit p. 885; Fig. 8 p. 886; Table 2 p. 886 | bovine liver, 3 mm/s | Fracture-energy trigger F_cut = G_c w |
| w | 1.0 mm | model choice | n/a | Tool width in the trigger |
| Friction per length (not implemented) | 0.0265 and 0.0339 N/mm | Roesthuis Table II p. 2560 | gelatine, 10 and 20 mm/s | Future friction term |
| Friction per length (comparison) | D_p 18.45 N/m, C_p 10.57 N/m, b_p 212.31 N s/m^2 | Okamura Table I p. 1712 | bovine liver, sinusoidal 0.2 Hz | Comparison |
| Pre-puncture stiffness (comparison) | a1 = 0.0480 N/mm, a2 = 0.0052 N/mm^2 (liver 1); a1 = 0.0020, a2 = 0.0023 (liver 2) | Okamura p. 1709 | bovine liver, 3 mm/s | Comparison |
| Cutting force (comparison) | 0.94 +/- 0.36 N | Okamura p. 1712, Eq. (11) | bovine liver, 3 mm/s, 1.27 mm bevel | Comparison; not the trigger |

Cutting criteria, the relationship: the model trigger G_c w = 0.164 N is an energy-per-width fracture criterion. The Okamura 0.94 N value is a measured total cutting force constant for a bevel needle, which includes tip stiffness. The two are different constructs. A linear reading of 0.94 N over the 1.27 mm diameter gives about 740 J/m^2, which is far above 164 J/m^2 and is not reconciled. The model keeps the G_c w trigger.

Stiffness, the relationship: the Okamura polynomial gives 0.72 N at 8 mm (liver 1) and 0.16 N at 8 mm (liver 2). The model gives 3.44 N at 8 mm (430 N/m times 8 mm). The model is stiffer by about 4.8 (liver 1) and 21 (liver 2). K_perp is not replaced in this slice. This is an owner decision.

Transfer limitations (README): no perfusion or vascular pressure, no bile duct or vessel turgor, boundary constraints and post-mortem degradation (3 to 6 h), and temperature and fluid loss. None of the values was measured in human tissue.

### 4. Re-pilot

Command: `python sim/sofa/src/run_contact_suite.py --label pilot-slice2c --workers 3`. Output: `SNDEV/logs/task23-cut-pilot-slice2c/` (`summary.json`; per-trial `diagnostics.csv`, `bridge_capture.csv`, segment files, `evidence_segNN.json`). Wall time: summed trial time about 26 min on three workers, as in slice 2b.

Per-check counts (100 trials):

| Check | Pass | Fail |
|---|---|---|
| contact_detected | 100 | 0 |
| zero_tunneling | 100 | 0 |
| zero_missed_contacts | 100 | 0 |
| finite_wrench (episode rule) | 98 | 2 (T008, T032) |
| topology_integrity | 100 | 0 |
| capture_schema | 100 | 0 |
| wrench_continuity | 100 | 0 |
| culling_reduction | 100 | 0 |
| exit_clean | 100 | 0 |

Trials passing all nine checks: 98 of 100. Cuts: 155. Tunneling steps: 0. Missed points: 0.

Episode-peak evidence for the 16 trials that failed the slice-2b per-step rule (T011, T024, T026, T028, T032, T038, T040, T042, T048, T050, T054, T056, T060, T066, T074, T094):
* 15 of 16 now pass. Each has no zero-peak episode. Minimum episode peaks range from 1.0 N (T024, T026, T028, T038, T040, T042) to 8.07 N (T094). Several minimum peaks are exactly 1.0 N, which is the per-point force cap (F_cap = 1.0 N). The wrench norm of a single capped point is 1.0 N, so the minimum peak in those episodes is one capped point.
* T032 still fails. It has 8 episodes, one with a zero peak (start tick 553, length 5). The tip is outside the organ in that episode.
* The two failing trials are T008 (new; one zero-peak episode, start tick 3724, length 2) and T032 (former failure; the zero-peak episode above). Each zero-peak episode is a run of contact records in which the net wrench is exactly zero, consistent with the slice-2b pattern (candidate in penetration, damping cancels the penalty). They are reported, not tuned.

### 5. Gate status (G2.3)

The conditional gate run requires a fully clean re-pilot. The re-pilot has two episode-rule failures, so the 1000-trial gate run is not started in this slice. Projected runtime, from the 100-trial pilot wall time (about 26 min on three workers): about 4.3 hours for 1000 trials, which exceeds the 3-hour threshold in the brief. Pre-registered clauses for the gate run, to be applied when it runs: (a) zero tunneling events across 1000 trials, (b) zero missed contacts across 1000 trials, (c) finite wrenches under the episode rule in every trial, (d) topology integrity after every cut. Quiet-host check: not run, because the gate run is deferred.

The gate verdict is not issued. The plan owner decides whether the two zero-force episodes (the contact-record rule for zero-net-force candidates) are accepted under the episode rule before the 1000-trial run.

### Interpretation

Tunneling and missed contacts are zero in 100 trials. The episode rule clears 15 of the 16 slice-2b failures. T032 is one of the 16 and still fails. T008 is a new failure. Both are zero-net-force episodes at contact records. The cut energy is now signed (non-negative released energy, total change equal to minus the release) and bounded. The calibration citations are verified against the full texts. Two construct mismatches (cutting criterion, stiffness mapping) are recorded and remain owner decisions.

### Plan consolidation (not edited here)

* Task 2.3 row: slice 2c complete as a checks and citations slice. Re-pilot 98 of 100 trials pass all nine checks. G2.3 not closed. The 1000-trial run is deferred pending the owner decision on zero-net-force episodes.
* Owner decision needed: (i) accept zero-net-force contact episodes under the episode rule, or change the record rule; (ii) whether K_perp is replaced by the Okamura pre-puncture polynomial (stiffer model by about 5 and 21 at 8 mm); (iii) the G_c w trigger versus the Okamura cutting constant.
* Gokgol G_c is an extrapolated intercept. The model width of 1.0 mm is outside the tested 2 to 5 mm range.
* SOUP: no new dependency. Citations for `sim/SOUP.md` or the plan: Roesthuis 2011 (Table II, Fig. 11, Fig. 12, verified), Gokgol 2012 (verified), Okamura 2004 (verified), Jackson 2016 (structure support).
* Release-rule change: the slice-2 one-ring rest reset is retired. The released energy definition changed (signed, bounded). Flag for the owner, because the slice-2 log described the reset.

### Commit

Pending (see the commit message).
