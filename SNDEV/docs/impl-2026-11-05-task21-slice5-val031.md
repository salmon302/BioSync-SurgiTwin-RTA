Title: Plan task 2.1 slice 5, G2.1 clause work under VAL-031 (vessel recall, liver boundary, tumor seed search)
Date: 2026-11-05T19:05:00Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.1 slice 5, gate G2.1 under the VAL-031 per-structure clauses
Summary: Measures the SEG label conventions in the evaluation step, runs three vessel variants and one liver variant against the VAL-031 clauses, records the clinical-annotation search trail for the operator-seeded tumor clause, and records the vascular clause-tension finding with the measured Pareto points.

## Task Reference

Plan task 2.1, slice 5, after slice 4 at commit 9d2b770. The G2.1 metric is restated by VAL-031 (applied at 3e57002 and 134ed09; clause text in `docs/val-031-g21-metric-proposal.md` Section 3, VTM row FR-MS-001). The clauses are: (a) parenchyma Dice at or above 0.90 and recall at or above 0.90; (b) vascular keep-out recall at or above 0.95, keep-out volume at most 3 times the 40.48 mL reference (121.44 mL), and the keep-out safety margin documented and carried into the FR-RTA-003 envelope parameters; (c) tumor, operator-seeded with detection excluded, a documented seed source (image inspection or clinical annotation, never the SEG reference labels) and Dice at or above 0.70, or the sub-gate recorded not applicable with the non-detectability evidence when no documented seed source exists. Each run records the SEG label-convention notes.

## Specification Summary

Slice 5 scope, from the mission of 2026-11-05:

1. Vessels first: recall 0.5676 to at or above 0.95 and volume 182.25 mL to at or above 121.44 mL. Levers named in slice 4: seed-subtree selection to drop mesenteric and lumbar branches, smaller vesselness scales for 2 to 4 mm branches, and a measured accounting of the 1 mm keep-out margin against the volume bound. The margin stays; if the margin alone breaks the bound, record a clause-tension finding. Resolve or document the SEG "Portal vein" convention (main trunk versus full tree) by geometric inspection of the reference in the evaluation step only.
2. Liver: remove about 29 mL of false positives with recall held at or above 0.90 (sub-voxel boundary refinement, porta hepatis and gallbladder-bed conventions). At most three documented variants.
3. Variant discipline unchanged: every variant logged with Dice, Jaccard, recall, volumes; the final chain scored once; no post-score tuning.
4. Clarification note in this log (audit trail): the vascular Dice 0.0449 in the old plan status is the slice-2 measurement on the mixed-acquisition input, and 0.0543 is the slice-3a V0 measurement on the SEG-referenced input after the confound fix. Both are correct for their inputs.
5. Final run (`run.ps1` then `run_evaluation.ps1`) and evaluation under the VAL-031 clauses with per-structure clause verdicts.
6. DEVELOPMENT_PLAN.md (Phase 2 and gate row only): slice-5 clause verdicts in the G2.1 status cell, slice 5 done at its commit hash in the task 2.1 note, one appended sentence in the Phase 2 status paragraph. The metric text itself is not restated.

## Implementation Notes

Log created before any other change in this slice (this file, 2026-11-05T19:05:00Z).

### Audit-trail clarification (item 4)

The plan gate G2.1 status cell previously carried vascular Dice 0.0449 (slice 2, mixed-acquisition input: all 36 acquisition 2 files, 15 contested z levels mismatched to the reference). The slice-3a V0 measurement on the SEG-referenced input is 0.0543. The two values measure different pipeline inputs and both are correct for their inputs. The replacement of 0.0449 by the slice-5 numbers in the plan is a supersession by newer runs on the corrected input, not a correction of a wrong reading. The same holds for the parenchyma and tumor V0 rows.

### Holdout discipline for this slice

The scoring chain reads staged CT only. `evaluate_g21.py` inspects the reference labels for the label-convention measurement that VAL-031 requires with each run, for the coverage attribution, and for the disagreement profiles; that inspection is evaluation-side and never enters the scoring chain. Chain parameters and seeds come from CT inspection (`SNDEV/logs/probe9b`, `probe16`, `probe20`, `probe22`, `probe23` are CT-only). Variants are scored once each through `run.ps1` and `run_evaluation.ps1` and are logged below.

### Tumor annotation search (clause (c))

Search trail:

1. `sim/segmentation/data/`: PROVENANCE.md and two LICENSE files plus the CT and SEG zips. The zips hold DICOM files and LICENSE files only (PROVENANCE.md verification section). No clinical spreadsheet and no text annotation was present.
2. TCIA collection page `https://www.cancerimagingarchive.net/collection/hcc-tace-seg/` (fetched 2026-11-05): the Data Access table lists a "Clinical data with description" XLSX (125.5 KB, CC BY 4.0) at `https://www.cancerimagingarchive.net/wp-content/uploads/HCC-TACE-Seg_clinical_data-V2.xlsx`. Downloaded to `sim/segmentation/data/HCC-TACE-Seg_clinical_data-V2.xlsx` (128507 bytes, SHA-256 E9D2683DC907819AA08E4027E085854F46464BEC834A09E80FC83B19A89E092B, recorded in `data/PROVENANCE.md`).
3. Spreadsheet parsed with `SNDEV/logs/probe18-clinical-xlsx-2026-11-05.py` (zipfile and xml.etree only; logs `probe18-clinical-xlsx-2026-11-05.log` and `probe18b-clinical-xlsx-glossary-2026-11-05.log`). The "data table" sheet has 57 columns and 105 subject rows. The HCC_001 row records: Tr_Size 0.8, tumor_nodul multinodular, T_involvment "< or = 50%", Pathology "Moderately differentiated", AFP 5, BCLC Stage-A, and treatment and response columns. The glossary sheet defines Tr_Size as "tumor size (cm)", tumor_nodul as "tumor nodularity (uninodular, multinodular)", and T_involvment as "tumor involvement ( <= 50% , >50% )". No column carries a lesion location: no lobe, no segment, no coordinate, no laterality.
4. TCIA collection description and the linked dataset paper (Moawad et al., Scientific Data 2023, and Morshid et al., Radiology AI 2019) describe the collection and the segmentation workflow; neither publishes a per-patient lesion location. A web search for a public HCC_001 lesion location returned the collection page, the papers, and dataset summaries only (`SNDEV/logs` capture of the search is the terminal transcript).

Finding: no annotation documents a lesion location. The clinical data documents tumor characteristics only, and its Tr_Size of 0.8 cm does not match the 35.75 mL labeled mass (about 4 cm across), so the annotation cannot localize the labeled lesion either. Under VAL-031 clause (c) the tumor sub-gate is recorded not applicable on HCC_001, with the two-pass non-detectability evidence of slice 4 (`SNDEV/docs/impl-2026-11-05-task21-slice4-method.md`, tumor section). No seed was placed and no seeded chain was run. The tumor segment stays empty (tumor v1 chain unchanged).

### Vessel convention measurement (evaluation step, item 1)

`export_reference_labels.py` now also exports `reference_portal_vein` and `reference_aorta` (split SEG labels, for this measurement only; the scored union `reference_vessel` is unchanged). `evaluate_g21.py` measures the geometry with each run (log `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261106T013713Z.log`, `seg_label_convention_notes` in `evaluation.json`):

- The SEG labels are disjoint. Overlap shares are 0.0 for Mass inside Liver, Portal vein inside Liver, Abdominal aorta inside Liver, and vessel inside Liver. The Liver label carves out the Mass and the vessel labels. The parenchyma chain therefore subtracts the segmented vessel tree and keeps vessel holes open (liver v3).
- "Portal vein" is the full intrahepatic tree, not the main trunk: 7736 voxels (23.61 mL) in 35 connected components over slices 2 to 31 (z -405 to -260), branch volume share 0.739 (74 percent of the volume outside the largest component), largest components 6.16, 5.39, 4.38, 3.36, and 2.05 mL, max lumen radius 5.49 mm, in-plane bbox x 58 to 241, y 116 to 305.
- "Abdominal aorta" is one component of 5529 voxels (16.87 mL) over slices 21 to 29 (z -310 to -270) only, bbox x 261 to 297, y 222 to 275, max lumen radius 10.9 mm (the label lumen). The aorta is visible over the full scan (z -415 to -240) and the keep-out covers it for safety (FR-RTA-003); the unlabeled extent is part of the volume accounting below.
- Coverage attribution on the slice-4 masks (before the chain changes): aorta recall 0.898 (562 voxels missed), portal recall 0.331 (5174 missed). The missed portal voxels were entirely on acquisition 1 slices (0 missed on every acquisition 2 slice): the late-arterial portal tree partial-volumes into the parenchyma HU range.

### Vessel chain work (item 1)

Mechanism measurements (CT only, `SNDEV/logs/probe22-*` and `probe23b-*`):

- The blob-style Frangi measure used in slice 4 is degenerate at 0.78 by 0.78 by 5 mm: the 5 mm z sampling gives every voxel a flat axis, so plain parenchyma reads V 0.96 and above at sigma 3 (probe23b percentiles). This is why any permissive threshold floods the liver.
- The classic Frangi line-term (Ra = |lambda2|/|lambda3|) suppresses the flood but does not separate either: the portal lumen reads V_ra 0.26 against a parenchyma 95th percentile of 0.34 to 0.45 (probe23b).
- The measurable discriminator is brightness: the acq2 parenchyma tops out at 139 HU and acq1 at about 86 HU (probe20), while the tree lumens read 113 (acq1) and 189 (acq2). The 2 to 4 mm branches partial-volume to 125 to 145 (acq2) and 85 to 105 (acq1), which overlaps the parenchyma range (probe23b brightness bands, and the v4 versus v5 recall difference).

Scored variants (each run once; v0 to v2 are the slice-4 rows):

| Variant | Method chain | Dice | Jaccard | Recall | Keep-out mL | Reference mL | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V0 | Threshold 150 to 300 HU, ROI clip, bone exclusion, dilate 2 mm | 0.0543 | 0.0279 | 0.3098 | 421.13 | 40.48 | slice 3a on the SEG-referenced input |
| V1 | Vesselness seed growth, broad bounds | 0.0842 | 0.0440 | 0.7169 | 648.48 | 40.48 | slice 4 recall-priority run |
| V2 | Vesselness seed growth, tight bounds 100 / 150 HU, threshold 0.6, vertebral and kidney exclusions, dilate 1 mm | 0.2063 | 0.1150 | 0.5676 | 182.25 | 40.48 | slice 4 final; best volume point |
| V3 | Seed-subtree corridors, small scales (0.75 mm), threshold 0.35, bounds 85 / 125 HU | 0.0544 | 0.0280 | 0.7869 | 1131.00 | 40.48 | parenchyma flood (probe22b mechanism) |
| V4 | Seed-subtree corridors, z-continuity closing, threshold 0.5, bounds 78 / 125 HU | 0.0466 | 0.0239 | 0.9534 | 1614.54 | 40.48 | only point passing the recall sub-clause (0.9534 vs 0.95); flood |
| V5 (final) | Seed-subtree corridors, z-continuity closing, threshold 0.6, bounds 85 / 145 HU, sigma 1.5 / 3 / 6 mm | 0.1129 | 0.0598 | 0.4650 | 293.02 | 40.48 | balanced point; aorta recall 0.996, portal recall 0.085 |

The v4 and v5 runs also record per-label coverage: v4 aorta 0.998 and portal 0.921 (union 0.9534); v5 aorta 0.996 and portal 0.085 (the 85 / 145 bounds cut the thin branches and the subtree no longer reaches the tree).

### Vascular clause-tension finding

The two sub-clauses of VAL-031 (b) are mutually exclusive on HCC_001 at 0.78 by 0.78 by 5 mm with CT-intensity methods:

- The reference vessel is the full intrahepatic tree (23.61 mL in 35 components) plus a short aorta segment (16.87 mL). The tree's 2 to 4 mm branches partial-volume to HU values that overlap the parenchyma range on both acquisitions (probe23b), and the Frangi measures degenerate at this anisotropy (probe23b), so covering them admits parenchyma.
- Measured Pareto points (recall, keep-out volume): v2 (0.5676, 182.25 mL = 4.50x bound), v3 (0.7869, 1131.00 mL = 27.94x), v4 (0.9534, 1614.54 mL = 39.88x), v5 (0.4650, 293.02 mL = 7.24x). No tested setting satisfies both sub-criteria. The only recall-passing point (v4) reaches 39.9x the bound; the volume-closest point (v2, 4.5x) fails recall by 0.38.
- The margin is not the binding item: at the final point the margin adds 78.16 mL (core 214.865 mL to margin-inclusive 293.024 mL, 36 percent) and the margin-free core alone is 5.31x the bound. Removing the margin would not meet the bound. Per the mission the margin stays (1.0 mm, documented and carried into FR-RTA-003) and the tension is recorded for the owner, who listed both the 3x multiplier and the 0.95 recall floor among the adjustable values (VAL-031 Section 5).
- The aorta extent adds to the tension: the SEG aorta label covers z -310 to -270 only (16.87 mL) while the keep-out covers the full visible aorta for safety (about 55 to 65 mL of the core). The label-convention note is recorded with each run.

### Liver chain work (item 2)

Design (liver v3) follows the measured conventions and the evaluation-side disagreement profiles (FP distance to the reference surface: 67 percent of the slice-4 FP sat 8 mm and farther from the reference, so the residual is structural, not boundary-scale; the 29 mL boundary-trim lever is exhausted at 0 to 1 mm where 9790 FP voxels mix with the boundary TP layer):

- Global hole fill replaced by a small-hole fill (at most 100 voxels): the lung-base pockets (HU -160 to 12), the gallbladder fluid (3 HU), and the porta region (37 HU) were being filled as liver (probe20 band HU). Vessel holes stay open per the disjoint-label convention.
- Spine-centered bone exclusion (keep largest calcified component, fill, dilate 2 mm): the all-components dilation of v2 cut dome and lateral liver against the ribs (FN at slices 32 to 33 and the lateral rim).
- z range extended to the full staged extent (-416 to -238 mm): the v2 cut at -390 cost the inferior liver tip (FN 10782 voxels at slices 0 to 4).
- Organ-minus-vessel: subtract the vessel core as segmented (the reference carves the labeled tree out of the liver label).

Scored: liver v3 with the vessel v3 core 0.6490 (Dice) / 0.5573 (recall) (the v3 flood was subtracted raw and ate the liver); with the vessel v4 core 0.4107 / 0.2926 (flood); with the vessel v5 core 0.8853 / 0.9362 (final). The liver chain is one variant; its score moves with the vessel core (documented interdependency, as in slice 4). Against the clause: Dice 0.8853 vs 0.90 FAIL (slice-4 chain read 0.8915 on the v2 core), recall 0.9362 vs 0.90 PASS. The remaining FP (262.52 mL) is 71 percent at 8 mm and farther from the reference: the tumor carve-out (35.75 mL, undetectable and therefore unsubtracted), the labeled vessel tree inside the liver (23.61 mL, only partly covered by the v5 core), and convention differences at the dome and medial boundary. No boundary trim can close a 0.015 Dice gap that is 71 percent structural, so the remaining slice-5 liver budget (2 further variants) is held and the gap is reported.

### Variant iteration log (all scored rows)

Parenchyma:

| Variant | Method chain | Dice | Jaccard | Recall | Pipeline mL | Reference mL | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V0 | Threshold 40 to 200 HU, ROI clip, median, keep largest | 0.7108 | 0.5514 | 0.7778 | 1745.15 | 1468.28 | slice 3a |
| V2 | Slice-4 final (growth, fill-holes, minus eroded core) | 0.8915 | 0.8042 | 0.9290 | 1591.81 | 1468.28 | slice 4, scored on the vessel v2 core |
| V3 (final) | Conventions: small-hole fill, spine bone exclusion, full z range, minus vessel core | 0.8853 | 0.7942 | 0.9362 | 1637.19 | 1468.28 | final, scored on the vessel v5 core |

Tumor:

| Variant | Method chain | Dice | Jaccard | Recall | Pipeline mL | Reference mL | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V0 | Erode, background median minus 30 HU, keep largest | 0.0000 | 0.0000 | 0.0000 | 1.72 | 35.75 | slice 2 blind artifact |
| V1 (final) | Compact focus search, none confirmed by inspection, empty | 0.0000 | 0.0000 | 0.0000 | 0.00 | 35.75 | sub-gate not applicable (no documented seed source) |

Vascular: the V0 to V5 table is in the vessel section above.

### Final chain and clause verdicts

Final run 2026-11-05: `run.ps1` (defaults liver v3, tumor v1, vessel v5), Slicer exit 0, wall 45.1 s, log `SNDEV/logs/segment-run-tcia-hcc-tace-seg-hcc001-20261106T013605Z.log`; `run_evaluation.ps1`, exit 0, log `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261106T013713Z.log`. Variant runs: v3 `segment-run-...T004438Z.log` with `g21-evaluation-...T004558Z.log`; v4 `segment-run-...T005601Z.log` with `g21-evaluation-...T005718Z.log`; v5 `segment-run-...T012624Z.log` with `g21-evaluation-...T012730Z.log`. Reference export with the split labels: `reference-export-...T000849Z.log`.

| Structure | Clause | Measured | Verdict |
| --- | --- | --- | --- |
| parenchyma_liver | Dice at or above 0.90 | Dice 0.8853 (Jaccard 0.7942) | FAIL (short 0.0147) |
| parenchyma_liver | recall at or above 0.90 | recall 0.9362 | PASS |
| vascular_keepout_bone_excluded | recall at or above 0.95 | recall 0.4650 (aorta 0.996, portal 0.085) | FAIL (clause-tension finding) |
| vascular_keepout_bone_excluded | volume at most 3x reference (121.44 mL) | 293.02 mL margin-inclusive (7.24x), core 214.87 mL | FAIL (clause-tension finding) |
| vascular_keepout_bone_excluded | margin documented and carried to FR-RTA-003 | 1.0 mm, README and sidecar carry-forward note, evaluation `margin_documented_verdict` PASS | PASS |
| tumor_hypoattenuating | seeded Dice at or above 0.70 | not applicable: no documented seed source (clinical annotation has no lesion location; inspection found no lesion on the named phases) | NOT APPLICABLE |

Supporting numbers: parenchyma 1637.19 mL against 1468.28 mL (FP 262.52 mL, FN 93.61 mL); tumor 0.00 mL against 35.75 mL; vascular 293.02 mL against 40.48 mL (FP 274.20 mL, FN 21.66 mL). The named phases (clause (c)) are late arterial (acquisition 1) and portal venous (acquisition 2), as recorded in the run provenance.

### What a slice 6 would need per structure

- Parenchyma: the residual is structural (tumor carve-out 35.75 mL is subtractable only with a lesion detector, which is out of gate scope; the labeled tree carve-out depends on vessel coverage). The 0.015 Dice gap closes with a vessel core that covers the labeled tree (v4-level recall) used as the subtraction input without the flood, or with a boundary-scale refinement after the structural items are settled.
- Vascular: the clause-tension needs an owner decision on the adjustable values (VAL-031 Section 5 lists the 3x multiplier and the 0.95 recall floor as adjustable). The measured Pareto points let the owner pick an operating point. A resolution upgrade (thinner slices) is the data-side fix for the partial-volume overlap.
- Tumor: the sub-gate stays not applicable until a documented seed source exists (a delayed-phase acquisition or a location-bearing annotation).

### Verification

- Reference export with split labels: PASS (`SURGITWIN_REF_DONE`, Slicer exit 0).
- Pipeline runs v3, v4, v5 and the final run: PASS (`SURGITWIN_DONE`, Slicer exit 0; walls 57.9, 55.4, 45.3, and 45.1 s).
- Evaluation runs: exit 0 with `EVALUATION_DONE` and the clause verdicts for each run. FAIL verdicts are measurements.
- `py_compile` on `sim/segmentation/segment_reference.py` and `sim/segmentation/evaluate_g21.py`: PASS.
- Provenance records the variants, the margin (1.0 mm) and its FR-RTA-003 carry-forward note, the per-slice acquisitions, and the phase determination. The evaluation records the label-convention notes and the coverage attribution with each run.
- Style: straight quotes, no em dashes, no banned words in the new and changed files.

### Commit plan

Commit A: `sim/segmentation/` changes and this log. Commit B: `DEVELOPMENT_PLAN.md` Phase 2 and gate row edits, with commit A's hash.
