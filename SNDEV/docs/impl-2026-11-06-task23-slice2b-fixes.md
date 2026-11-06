Title: Pilot tunneling and missed-contact fixes, citation verification, and re-pilot (task 2.3 slice 2b)
Date: 2026-11-06T20:20:21Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: task 2.3 slice 2b, follow-up to slice 2 (`SNDEV/docs/impl-2026-11-06-task23-slice2-cutting.md`). Gate G2.3 is not closed; the 1000-trial gate run stays deferred.
Summary: Diagnoses the two slice-2 pilot failures (a penalty force with no bound and a damping term that cancels the penalty in penetration), changes the contact force and record rules, verifies the calibration citations against the available sources, and re-runs the 100-trial pilot.

## Task Reference

* Slice 2 log: `SNDEV/docs/impl-2026-11-06-task23-slice2-cutting.md` (commit 17d17a1).
* Follow-up brief: fix T081 (tunneling) and T099 (missed contact), verify citations, re-pilot.
* DEVELOPMENT_PLAN.md, sim/SOUP.md, sim/bridge, env, vv, SRS.md were not edited.

## Specification Summary

* T081 (tunneling, 180 mm/s): diagnose the 70 N transient, fix with the smallest honest change, and do not weaken the zero-tunneling check.
* T099 (missed contact, 200 mm/s): confirm or refute the cut-face culling hypothesis, then fix.
* Verify K_perp = 430 N/m and G_c = 164 J/m^2 against the full texts. Record the limitation when a full text cannot be fetched.
* Re-run the 100-trial pilot on the same grid plus the two failing trials. Report per-check counts.

## Implementation Notes

### T081 diagnosis

Instrumentation added to `contact_scene.py` writes `evidence_segNN.json` per segment: per-point records for large forces (above 1 N) and missed points, and a tick-level record for every tick that is inside the organ with zero contact points (nearest full-boundary face, whether it is in the culled set). The T081 and T099 trials were rerun with this capture (`SNDEV/logs/debug_pilot_failures.py`, output `SNDEV/logs/task23-cut-slice2b-debug/`). Both reproduced the slice-2 results exactly (same ticks and counts).

Findings for T081:

* Tick 180 is the first tick of segment 2 (restart after the cut at tick 179). Seventeen tool points each carry about 4.15 N. All of them choose candidate face 35, whose plane is 41 mm from the point. The top faces near the tip do not contain its projection, because the top surface was displaced locally.
* The checkpoint written at the tick-179 cut holds node velocities up to 9.23 m/s (`SNDEV/logs/task23-cut-slice2b-debug/T081/checkpoint_in_seg02.json`). The 5 mm rise of the organ top between ticks 179 and 180 (0.160282 to 0.165251 m) is the first-step response to those velocities.
* The velocities come from the penalty force. The per-point force is unbounded: `f = k pen - c vn` grows with penetration depth, and a deep candidate yields a large force. On organ nodes of about 4 g each (total mass 1.64 kg over 405 nodes), a 1 to 4 N force gives a velocity change of order metres per second per millisecond step.
* The cut-energy record (`total_energy_jump_j`, added in `cut_topology.apply_cut`) shows that the release rule is not the cause of the T081 transient. Four cuts in T081 change total energy by -2.0e-6, -6.1e-4, +3.7e-3, and -5.9e-3 J. The +3.7e-3 J rise at the tick-181 cut is a real spurious energy input from the release rule (second-ring tetrahedra carry a mixed rest configuration). It is recorded here, but it does not explain the tick-180 transient, which comes before that cut. This is a separate open item.

Mechanism (confirmed for the transient, not for the tunneling tick alone): unbounded per-point penalty force, carried into the restart as node velocity, distorts the top surface, and the tip then projects outside the culled top triangles.

### T081 fix

`contact_scene.py`: per-point normal force is capped at `contact_force_cap_n = 1.0 N` (uncited model choice, recorded in `run_contact_suite.py` CALIBRATION and in `sim/sofa/README.md`). The cap bounds the transient. The tunneling definition is unchanged: a step is tunneling when the raw tetrahedron-containment inside state holds and the contact record count is zero.

Debug result after the fix: T081 passes all nine checks (tunneling 0, two cuts instead of four, because the trajectory changed).

### T099 diagnosis (hypothesis refuted)

Hypothesis from slice 2: cut-created faces lie outside the static culled set. Refuted. The evidence (`SNDEV/logs/task23-cut-slice2b-debug/T099/evidence_seg01.json`, ticks 185) shows the four missed points at tick 185 each choose candidate face (nodes 336, 394, 383), which is in the culled set (`in_culled = True`). Their signed distance to the face is 0.06 to 0.09 mm, inside the 0.5 mm margin, with penalty depth 0.41 to 0.44 mm. The net normal force is -0.0028 N, because the damping term `c vn` (vn about 0.09 m/s) exceeds the penalty `k pen` (0.041 N). Under the slice-2 rule, a point with a negative net force gets no contact record, so it counts as missed although its candidate is active.

Mechanism (confirmed): the missed-contact count reflected the force sign, not the absence of a candidate.

### T099 fix

Contact record rule: a candidate with `pen > 0` is a contact record, and the record's net normal force is `min(max(k pen - c vn, 0), F_cap)`. The check counts missed points as full-boundary swept hits without a contact record. This changes the definition of a contact record (it no longer requires a positive net force) and is flagged for owner review (see Plan consolidation).

### Citation verification

| Value | Source | What was checked | Result |
|---|---|---|---|
| G_c = 164 J/m^2 (bovine liver) | Gokgol C, Basdogan C, Canadinc D. Estimation of fracture toughness of liver tissue: experiments and validation. Med Eng Phys. 2012;34(7):882-891. DOI 10.1016/j.medengphy.2011.09.030. PMID 22024208. | Europe PMC record (REST API, `ebi.ac.uk/europepmc`): abstract text reads "A unique value for fracture toughness (J=164±6 J/m(2)) was obtained for the bovine liver by fitting a line to the toughness values estimated from the set of insertion experiments." | Abstract verified against the primary record. Full text NOT verified: the open-access HAL copy (hal.science/hal-03177362 and hal.archives-ouvertes.fr) returns a proof-of-work page; the KU PDF and ScienceDirect return an error. Value stands as abstract-verified. Pending: full-text check of the Table with the 164 value. |
| K_perp = 430 N/m (Ke, gelatine phantom) | Roesthuis RJ, van Veen YRJ, Jahya A, Misra S. Mechanics of needle-tissue interaction. IROS 2011. | Full-text PDF at surgicalroboticslab.nl (roesthuis11-iros.pdf) and the "come" variant: fetch tool returns "Unsupported fetched file content type: application/pdf". Publication page (surgicalroboticslab.nl/publications/mechanics-needle-tissue-interaction/) has only a "Read full-text" link. Search excerpts show "Simulation (Ke = 430 N/m)" in a Fig. 12 label and a sentence about an optimal interaction stiffness. | NOT verified. Value kept as a provisional, phantom-derived placeholder, marked unverified in the calibration table. Pending: read Fig. 12 and the simulation section of the full text. If the full text gives a different optimum, adjust K_perp and re-run. |
| Okamura structure (capsule stiffness, friction, cutting) | Okamura AM, Simone C, O'Leary MD. Force modeling for needle insertion into soft tissue. IEEE Trans Biomed Eng. 2004;51(10):1707-1716. DOI 10.1109/TBME.2004.831542. | PubMed abstract (Europe PMC): model structure stated; no numeric cutting constant in the abstract. DOI landing page returns only a citation string. | Structure verified from the abstract. No numeric value is taken from this paper. Full text pending. |

The searches for the Roesthuis friction values (0.0265 N/mm at 10 mm/s and 0.0339 N/mm at 20 mm/s) rest on search excerpts of the paper's conclusions. They are not used in the model, and they are unverified against the full text.

### Re-pilot

Command: `python sim/sofa/src/run_contact_suite.py --label pilot-slice2b --workers 3`. Outputs: `SNDEV/logs/task23-cut-pilot-slice2b/` (`summary.json`, per-trial `T###/diagnostics.csv`, `bridge_capture.csv`, segment files, `evidence_segNN.json`, `checkpoint_inNN.json`). Wall time: about 26 minutes on the three-worker pool (summed trial wall time 4623 s). Also run: the two failing trials alone (`SNDEV/logs/task23-cut-slice2b-debug/`), both passing all nine checks.

Per-check counts, 100 trials:

| Check | Pass | Fail |
|---|---|---|
| contact_detected | 100 | 0 |
| zero_tunneling | 100 | 0 |
| zero_missed_contacts | 100 | 0 |
| finite_wrench | 84 | 16 |
| topology_integrity | 100 | 0 |
| capture_schema | 100 | 0 |
| wrench_continuity | 100 | 0 |
| culling_reduction | 100 | 0 |
| exit_clean | 100 | 0 |

Trials passing all nine checks: 84 of 100. Cuts: 160 total. Tunneling steps: 0. Missed points: 0. Largest contact peak: 17 N. Largest puncture peak: 1.87 N.

Remaining failures (16 trials, all `finite_wrench`): each has 1 to 6 contact steps whose net wrench is exactly zero. In every case the tip is outside the organ (`inside = 0`), and each zero-force step has one or more contact records from candidates in penetration whose damping term cancels the penalty. The trials are T011, T024, T026, T028, T032, T038, T040, T042, T048, T050, T054, T056, T060, T066, T074, and T094. Evidence: `SNDEV/logs/task23-cut-pilot-slice2b/<trial>/diagnostics.csv` (filter `contact_points > 0` and `contact_force_n = 0`). The checks were not changed.

### Interpretation

The two slice-2 failure modes are closed in the pilot: zero tunneling and zero missed contacts in 100 trials, and T081 and T099 pass in the debug runs. A new check failure appeared with the record rule change: contact steps with zero net force. Whether such a step should count as contact in the wrench check is an owner decision. The gate G2.3 is not closed, and the 1000-trial gate run stays deferred until the owner decides the record rule and the wrench-check meaning.

The cut wrench non-separability finding from slice 2 stands: the median wrench step at a cut was 2.30 N against a 99th percentile of 3.54 N for other ticks in the slice-2 pilot. It has not been recomputed for slice 2b.

Penalty parameters (k = 100 N/m, c = 0.5 N s/m, F_cap = 1.0 N) remain uncited model choices.

### Plan consolidation (not edited here)

* Task 2.3 row: slice 2b fixes applied, citations partly verified (Gokgol abstract only), Roesthuis unverified, pilot 84 of 100 trials passing all checks, G2.3 open.
* G2.3 gate: open. Tunneling 0 and missed 0 in the 100-trial pilot. Owner decision needed on the contact-record rule (zero-net-force contact records) before the 1000-trial run.
* Cut energy finding: the release rule adds spurious energy at some cuts (T081 cut at tick 181, +3.7e-3 J). This needs a fix before the gate run.
* SOUP: no new dependency. Citations for `sim/SOUP.md` or the plan: Gokgol 2012 (abstract verified), Roesthuis 2011 (unverified), Okamura 2004 (structure, abstract).

### Commit

Pending (see the commit message).
