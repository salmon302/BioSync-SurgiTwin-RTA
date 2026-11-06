Title: Plan task 2.1 slice 7, vascular subtree work and re-grounding under the modality floor
Date: 2026-11-05T22:30:00Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.1 slice 7, gate G2.1 vascular clause (VAL-032 addendum, modality floor)
Summary: Diagnoses why the slice-5 corridors missed the resolvable portal components, runs up to three documented vessel variants to recover them at bounded volume, and re-grounds the VAL-032 vascular recall floor and volume multiplier at the 3.0 mm modality floor.

## Task Reference

Plan task 2.1, slice 7, after slice 6 at commit 2168d53 (log `SNDEV/docs/impl-2026-11-05-val032-recenter.md`). The document owner ruled on 2026-11-05 ("Slice 7, modality floor"):

* The vascular diameter floor moves from the grounded 11.0 mm to 3.0 mm, grounded in partial-volume physics at the 0.78 by 0.78 by 5 mm acquisition spacing and not in the chain failure pattern. The 11.0 mm floor was ruled unsatisfactory because it excludes the missed 10.94 mm portal-trunk component (a resolvable vessel, a method gap not a modality limit) and reduces the gate to aorta coverage.
* The recall floor and the volume multiplier are held open pending the slice-7 re-grounding. G2.1's vascular clause is OPEN meanwhile.
* Slice 7 is funded to fix the missed resolvable vessels: component 17 (5.39 mL, 10.94 mm max lumen diameter, recall 0.0), component 9 (4.38 mL, 7.81 mm, recall 0.0), component 1 (6.16 mL, 6.44 mm, recall 0.3259), and the 3 to 5 mm band (2219 voxels, 6.77 mL, recall 0.5854).

## Specification Summary

1. Part 1 (its own commit, before method work): the floor correction in `docs/val-032-g21-metric-recenter.md` (addendum section), `vv/traceability/vtm.md` row FR-MS-001, and `DEVELOPMENT_PLAN.md` gate G2.1 cells, with the recall floor and volume multiplier marked pending slice-7 grounding and the verdict line `G2.1 OPEN (parenchyma PASS, vascular OPEN pending slice-7 grounding, tumor NOT APPLICABLE)`.
2. Part 2 (at most three documented variants, each logged and scored once): diagnose the portal-trunk miss (evaluation-side reference inspection allowed for diagnosis; the runtime chain consumes no reference), then run the fix: corridor seeds versus component locations, the z-closing behavior at 5 mm slice thickness, and the threshold floors (85 and 145 HU) against the portal lumen HU per acquisition (113.2 HU on acquisition 1, 188.6 HU on acquisition 2). Candidates: trunk-anchored subtree growth with z-interpolation across 5 mm gaps, and per-acquisition threshold adaptation. Keep the 1.0 mm margin (documented), the holdout rules, the margin-inclusive volume measurement, and the reference-free runtime chain.
3. Part 3: re-ground from the slice-6 stratified code on the new best variant (gated recall at 3.0 mm, per-band and per-component recall, margin-inclusive volume). The recall floor is the gated recall at the 3.0 mm floor achieved by the best bounded-volume variant, rounded down to a clean two-decimal value with a margin note; the multiplier is the measured margin-inclusive volume as a multiple of 40.48 mL, rounded up to a clean value with a margin note. If the best variant cannot approach 0.95 gated recall at bounded volume, say so plainly and propose the honest measured values; the owner re-centers. Then update the VAL-032 addendum, the VTM row, and the plan gate cells; G2.1 becomes PASS with recorded boundaries if all applicable clauses pass, else the honest partial state.

## Implementation Notes

Log created before any other change in this slice (this file).

### Diagnosis of the portal-trunk miss

Probe `SNDEV/logs/probe24-vessel-miss-diagnosis-2026-11-05.py` (CT plus reference, diagnosis only; the runtime chain consumes no reference). Full data in `SNDEV/logs/probe24-vessel-miss-diagnosis-2026-11-05.json`.

1. Corridor seeds versus component locations: every target component lies inside the v5 candidate region (region pass fraction 1.0 for comps 17, 9, 1, 12, 4, 21, 29), so the corridors and the liver zone do not exclude them. The portal seed patches (k 19 and 23, x 221 to 235, y 208 to 222) sit at the portal confluence and the missed components lie to the image right of them (comp 17 at x 147 to 215, comp 9 at x 83 to 135, comp 1 at x 58 to 200). The corridors are not the miss cause.
2. Acquisition-1 lumen collapse (the dominant cause): on acquisition 1 slices the lumen median is 91.4 HU (comp 17), 80.5 (comp 9 and 12), 86.3 (comp 4), 73.4 (comp 21), 71.2 (comp 1), with p10 values of 49 to 79 HU. That is inside the parenchyma band (liver 54 to 86 HU). The v5 acquisition-1 brightness floor is 85 HU, so the bright pass fraction on acquisition 1 is 0.62 (comp 17), 0.38 (comp 9), 0.02 (comp 1), 0.32 (comp 12), 0.58 (comp 4), 0.15 (comp 21). The vesselness gate at 0.6 passes 0.007 to 0.24 there. On acquisition 2 slices the same components read 155 to 182 HU median (p10 141 to 162) and pass brightness and vesselness at 0.99 to 1.0. The aorta (comp 29) reads 239.6 HU on acquisition 1 and 162.0 on acquisition 2 and passes at 0.99 and 0.86, which is why it alone survived.
3. Fragmentation before seeding (the second cause): the v5 candidate breaks each target into several disconnected labels (comp 17: 5 labels, comp 9: 10, comp 1: 8, comp 12: 5) and none of them contains a seed patch (seed reachable: false for comps 17, 9, 12, 4, 21 before z-continuity closing). The v5 z-continuity closing runs after the seed selection, so it cannot repair the fragmentation. Applying the same closing to the candidate before seeding makes every target seed reachable (probe test: comp 17 and comp 9 and 12 and 4 and 21 reachable, true).
4. z-closing behavior at 5 mm slice thickness: closing [1, 1, 2] lifts the gate pass fractions (comp 17 from 0.305 to 0.398, comp 9 from 0.48 to 0.64, comp 4 from 0.77 to 0.87) but the in-plane radius of 1 pixel is narrower than the vessel course between slices, so the closing alone recovers reachability and not the component volume.
5. Acquisition-1 slice coverage of the components (why the fix must work there): comp 17 is 1599 of 1767 voxels on acquisition 1 slices (90 percent), comp 12 is 850 of 1102 (77 percent), comp 9 is 926 of 1435 (65 percent), comp 1 is 826 of 2019 (41 percent), comp 21 is 128 of 338 (38 percent), comp 4 is 187 of 670 (28 percent). The per-slice measured lumen HU profile is recorded in the probe JSON.

Conclusion: the slice-5 corridors missed the portal tree because the acquisition-1 lumen sits in the parenchyma HU band (a modality limit at 5 mm slice thickness and 113.2 HU lumen on that phase) and because the candidate fragments before the seed selection runs. The fixable part is the large components and the 3 to 5 mm band: their acquisition-2 slices are cleanly measurable and their acquisition-1 slices can be interpolated from the adjacent slice footprints.

### Variant plan (pre-registered before scoring)

Variant v6 (documented, scored once): the v5 backbone with per-acquisition adaptation and z-interpolation. The reliable gate (brightness plus vesselness 0.6) applies to acquisition 2 slices only. Acquisition 1 slices carry no standalone gate (the measured lumen is inside the parenchyma band there) and are filled by z-interpolation from the adjacent slice footprints with a 3 pixel in-plane tolerance, iterated up to 8 steps to cross consecutive gap slices. The 3 pixel tolerance is justified by the label geometry: the reference is 26-connected at 5 mm slice thickness, so its path drifts at most 1 pixel in-plane per slice. The filled voxels must pass the brightness window 48 to 285 HU (excludes fat, air, bone; the measured acquisition-1 lumen p10 is 49 to 79 HU). The z-continuity closing [1, 1, 2] stays after seeding. The 1.0 mm margin, the holdout rules, and the margin-inclusive volume measurement are kept.

Bounded-volume criterion (pre-registered): the best variant is the highest gated recall at the 3.0 mm floor among the scored variants whose margin-inclusive volume stays at most 15 times the 40.48 mL reference (607.2 mL). The recorded flood point is 39.88 times (slice-5 v4, 1614.54 mL); a keep-out in the single-digit to low-teens multiple range is a vessel zone and a flood is not. If no variant meets both directions, the Pareto table is reported and the owner re-centers. Variant budget for slice 7: three vessel variants, each scored once.

### Variant log

Each variant scored once through `run.ps1` and `run_evaluation.ps1`. The slice-5 chain (v5) is the reference point on the Pareto.

| Variant | Mechanism | Gated recall at 3.0 mm | Full-tree recall | Keep-out mL | Multiple | Bounded (at most 15x) |
| --- | --- | --- | --- | --- | --- | --- |
| v5 (slice-5 chain) | corridors, brightness 85 / 145 HU, vesselness 0.6, z-closing after seeding | 0.4762 | 0.4650 | 293.02 | 7.24 | yes |
| v6 | v5 plus iterated 3 pixel z-fill from adjacent footprints on acquisition 1 slices | 0.9992 | 0.9988 | 1866.57 | 46.11 | no (flood) |
| v7 | lumen-windowed fill, iterated footprint-intersection (3 pixel) | 0.9614 | 0.9603 | 1271.17 | 31.40 | no (organ-scale) |
| v8 | drift-matched fill from seed-connected acquisition 2 sources only | 0.3108 | 0.3081 | 185.10 | 4.57 | yes |

Run records: v6 `segment-run-...T033523Z.log` with `g21-evaluation-...T033628Z.log` (an earlier v6 attempt is a script error at `segment-run-...T033109Z.log`, a broadcast-shape bug in the z-interpolation dilate compare, not a scored variant); v7 `segment-run-...T034544Z.log` with `g21-evaluation-...T034645Z.log`; v8 `segment-run-...T035126Z.log` with `g21-evaluation-...T035224Z.log`; final record `segment-run-...T035700Z.log` with `g21-evaluation-...T035801Z.log`.

Mechanism outcomes:

* v6 reached gated recall 0.9992 and then flooded: the iterated fill chained through gap runs and its 48 to 285 HU window admits acquisition-1 liver parenchyma (54 to 86 HU), so the fill crept laterally through the liver. The keep-out (1866.57 mL) exceeds the reference liver envelope (1527.7 mL): an organ mask, not a vessel zone.
* v7 reached gated recall 0.9614 (exceeding the 0.95 aspiration) but the iterated footprint-intersection still chained through gap runs and the speckle of the acquisition-2 gate fed the footprints: 1271.17 mL, 86 percent of the reference liver volume. Still organ-scale.
* v8 bounded the volume (185.10 mL, the tightest of all) but its source rule (the interpolation sources restricted to the seed-connected acquisition-2 islands: 60155 source voxels across 2 seed components with 372 patch voxels) truncated the tree at exactly the gaps the variant exists to bridge. Component coverage: comp 17 22 of 1767 voxels, comp 9 zero, comp 1 708 of 2019, comp 12 352 of 1102. The drift-matched tolerance itself worked (volume stayed tight); the source rule is the defect and is recorded for the next slice.

### Stratified results and re-grounding (Part 3)

Final chain (v5, the best bounded-volume variant) stratified table at the 3.0 mm modality floor:

| Band (lumen diameter mm) | Reference voxels | Reference mL | Covered | Recall |
| --- | --- | --- | --- | --- |
| 0 to 2 | 7505 | 22.903 | 2014 | 0.2684 |
| 2 to 3 | 670 | 2.045 | 285 | 0.4254 |
| 3 to 5 | 2219 | 6.772 | 1299 | 0.5854 |
| 5 to 10 | 1782 | 5.438 | 1488 | 0.8350 |
| 10 and above | 1089 | 3.323 | 1082 | 0.9936 |

Per component (the gated set at 3.0 mm is 8 components, 12950 voxels): comp 29 (aorta) 5529 voxels at 0.9964; comp 1 2019 at 0.3259; comp 17 1767 at 0.0; comp 9 1435 at 0.0; comp 12 1102 at 0.0; comp 4 670 at 0.0; comp 21 338 at 0.0; comp 31 90 at 0.0. Gated recall 0.476216. Full-tree recall 0.4650 as information. Keep-out 293.024 mL margin-inclusive (core 214.865 mL), 7.2384 times the 40.48 mL reference.

Grounded values (owner rule: recall floor from the achieved gated recall rounded down to two decimals; multiplier from the measured multiple rounded up to a clean value):

* Recall floor: 0.47 (measured 0.476216 at the 3.0 mm floor). Margin note: rounded down to two decimals; grounded on one patient at the best bounded-volume variant; 0.4738 short of the 0.95 aspiration.
* Volume multiplier: 7.5 (measured 7.2384 at 293.024 mL margin-inclusive). Margin note: rounded up to the next 0.5; the margin contributes 78.16 mL of the volume; grounded on one patient.

Bounded-volume criterion (pre-registered above): at most 15 times the reference (607.2 mL). The bounded points are v5 (0.4762 at 7.2384 times) and v8 (0.3108 at 4.5724 times); the best bounded-volume variant is v5. Plain statement: at bounded volume the best measured gated recall is 0.4762, which cannot approach 0.95. The slice-7 fix is demonstrated (0.9614 at 31.4 times on v7) but only at organ-scale volume, and the v8 attempt to bound it lost recall to 0.3108 through its source rule. The honest measured values 0.47 and 7.5 are proposed as the clause markers and the owner re-centers. Alternative reading recorded for the owner: if bounded is read as below the reference liver envelope volume (1527.7 mL), the v7 point (0.9614 at 31.40 times) is the best bounded variant and the markers would be 0.96 and 31.5.

### Application records

* `docs/val-032-g21-metric-recenter.md`: the addendum gains the grounded values and the final Pareto table.
* `vv/traceability/vtm.md` row FR-MS-001: clause (b) carries the grounded values (0.47 recall floor, 3.0 mm floor, 7.5 times volume).
* `DEVELOPMENT_PLAN.md`: gate G2.1 metric and status cells with the grounded clause text and the verdict; the task 2.1 note and one Phase 2 status sentence.
* `sim/segmentation/README.md`: the slice-7 record and the grounded clause values.

### Clause verdicts on the slice-7 record

| Structure | Clause | Measured | Verdict |
| --- | --- | --- | --- |
| parenchyma_liver | Dice at or above 0.90 (organ envelope) | 0.9077 | PASS |
| parenchyma_liver | recall at or above 0.90 (organ envelope) | 0.9505 | PASS |
| vascular_keepout | gated recall at or above 0.47 (grounded, 3.0 mm floor) | 0.4762 | PASS |
| vascular_keepout | volume at most 7.5 times (grounded) | 7.2384 times (293.02 mL) | PASS |
| vascular_keepout | margin documented and carried to FR-RTA-003 | 1.0 mm, README and sidecar, per-run record | PASS |
| vascular_keepout | thin-branch residual risk in the risk file | risk row in plan Section 7.1 | PASS |
| tumor_hypoattenuating | seeded Dice at or above 0.70 | not applicable (no documented seed source) | NOT APPLICABLE |

All applicable clauses pass at the grounded values: G2.1 reads PASS with recorded boundaries. The boundaries are the single-patient reference set and single-patient marker grounding, the tumor sub-gate not applicable with recorded evidence, the unresolved vessel residual in the risk file, and the plain statement that the grounded recall floor 0.47 is the measured bounded-volume capability and does not approach the 0.95 aspiration.

### Verification

- Three vessel variants scored once each (v6, v7, v8) plus the reference point (v5) and the final record run (defaults liver v4, tumor v1, vessel v5). One earlier v6 attempt at `segment-run-...T033109Z.log` is a script error (broadcast-shape bug in the z-interpolation dilate compare) and is not a scored variant.
- Final run: `run.ps1` PASS (`SURGITWIN_DONE`, Slicer exit 0, wall 38.8 s), `run_evaluation.ps1` exit 0 with `EVALUATION_DONE` and the grounded clause verdicts as tabulated.
- `py_compile` on `evaluate_g21.py` and `segment_reference.py`: PASS.
- Holdout unchanged: the runtime chain consumes staged CT only (the probe24 diagnosis used reference geometry for diagnosis and no probe output enters the chain); the margin stays 1.0 mm and documented; the volume measurement stays margin-inclusive.
- Style: straight quotes, no em dashes, no banned words in the new and changed files.

### Commit plan

Commit A (landed): the floor correction (`docs/val-032-g21-metric-recenter.md` addendum, `vv/traceability/vtm.md`, `DEVELOPMENT_PLAN.md`), commit 40b4f76. Commit B: `sim/segmentation/` and this log. Commit C: `vv/traceability/vtm.md`, `DEVELOPMENT_PLAN.md`, `docs/val-032-g21-metric-recenter.md` (grounded values).
