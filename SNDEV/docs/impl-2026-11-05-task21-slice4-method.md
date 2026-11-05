Title: Plan task 2.1 slice 4, G2.1 method iteration for vessels, tumor, and liver
Date: 2026-11-05T17:04:16Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.1 slice 4, gate G2.1 method iteration
Summary: Quantifies contrast phase from CT HU measurements, runs the documented method variants for the vessel, tumor, and liver segments (at most three per structure), and reports the final scoring chain numbers against the unchanged 0.90 Dice metric.

## Task Reference

Plan task 2.1, slice 4 (remaining method iteration after slice 3a at commit 3fa1868). Gate G2.1 metric is unchanged: per-segment Dice of 0.90 or higher against the held-out TCIA HCC-TACE-Seg HCC_001 SEG reference labels, until VAL-031 is applied by the document owner. The VAL-031 metric restatement is a separate action and is not drafted in this log.

## Specification Summary

Slice 4 scope, from the mission of 2026-11-05:

1. Phase quantification: measure aorta and liver parenchyma HU on both acquisitions with a short script writing JSON to `SNDEV/logs/`, and record the phase determination with numbers.
2. Tumor: re-inspect both acquisitions with intent (soft-tissue and liver windows), looking for a 35.75 mL (about 4 cm) mass, hyperattenuating on late arterial (acquisition 1) and hypo- or isoattenuating on portal venous (acquisition 2). If located, record coordinates and reasoning and run a seeded chain. If not, record the not-locatable finding with evidence and score the best documented attempt.
3. Vessels: build a vessel-targeting chain (Hessian tubularness or seeded growth from aorta and portal-vein landmarks found by CT inspection), keep the bone exclusion, target recall first (from 0.3098), then shrink the false-positive volume toward the 40.5 mL reference.
4. Liver: seed-based region growing plus closing and organ-minus-vessel separation, targeting the 0.189 Dice gap (mask inflated by about 277 mL).
5. Bound: at most three documented variants per structure, every variant logged with Dice, Jaccard, recall, and volumes. The final scoring chain is what gets reported. Headless Slicer crash falls back to the SimpleITK path.
6. Final full run (`run.ps1` then `run_evaluation.ps1`), variant table filled with every variant.
7. DEVELOPMENT_PLAN.md Phase 2 edits (in commit B).

## Implementation Notes

Log created before any other change in this slice (this file, 2026-11-05T17:04:16Z).

### Holdout discipline for this slice

Seeds, thresholds, and ROI choices come from CT inspection and CT pixel statistics only. No reference labelmap, SEG pixel data, or SEG geometry was read by any script in this slice. Variant numbers are measured by `evaluate_g21.py`, the single reader of `reference/`, through `run_evaluation.ps1`. `segment_reference.py` refuses SEG input and never opens `reference/` or `input_selection.json`. The per-slice acquisition numbers used for the phase-aware bounds come from the staged CT headers (`assert_ct_only_input`), which is CT input inspection.

### 1. Phase quantification

Scripts: `SNDEV/logs/probe9-phase-hu-2026-11-05.py` (candidate points with zoomed crops) and `SNDEV/logs/probe9b-phase-hu-2026-11-05.py` (refined points after crop calibration). JSON: `SNDEV/logs/probe9b-phase-hu-2026-11-05.json`. Values are 7x7 pixel ROI means (5.5 by 5.5 mm) at z -320 mm unless noted; coordinates are array pixels (x column, y row) of the 512 by 512 slices, origin top-left.

| Point | Acquisition 1 (HU) | Acquisition 2 (HU) |
| --- | --- | --- |
| aorta lumen (x 271, y 224) | 224.65 | 160.59 |
| aorta lumen (x 275, y 228) | 224.10 | 165.47 |
| liver parenchyma (x 135, y 195) | 54.33 | 94.22 |
| liver parenchyma (x 110, y 225) | 74.31 | 134.45 |
| liver parenchyma (x 95, y 240) | 73.24 | 138.82 |
| main portal vein lumen (x 228, y 215, z -300) | 113.23 | 188.62 |
| spleen (x 430, y 260) | 135.80 | 152.57 |

Structure identity is confirmed on the zoomed crops in `SNDEV/logs/probe8-png/` (the aorta is the round prevertebral structure with a calcified wall visible on acquisition 2; the portal vein is the rounded contrast-filled structure at the porta within the liver). Kidney morphology on the full-slice montages (`SNDEV/logs/probe12-png/`, `SNDEV/logs/probe7-png/`) shows corticomedullary differentiation on acquisition 1 and nephrographic enhancement on acquisition 2.

Determination: acquisition 1 is late arterial (aorta 225 HU against liver 54 to 74 HU) and acquisition 2 is portal venous (liver 94 to 139 HU at liver peak, aorta 163 HU). The CT carries no contrast phase tags (blank), so the determination is from image HU and organ enhancement. This supersedes the slice-2 qualitative reading ("inferred as portal venous") for acquisition 2 and confirms it; acquisition 1 is now quantified as late arterial.

### 2. Tumor re-inspection and attempt

Second full inspection pass (the first was the slice-2 montage pass):

- Visual: every staged slice (z -415 to -240 mm, 36 slices, 21 acquisition 2 and 15 acquisition 1) at soft-tissue window (WL 50 WW 350 in `SNDEV/logs/probe8-png/`, WL -50 WW 450 in `SNDEV/logs/probe7-png/`) and liver window (WL 100 WW 200, 3x3 montages in `SNDEV/logs/probe12-png/`, single slices in `SNDEV/logs/probe8-png/`), plus zoomed crops at 2x to 4x scale.
- Quantitative: compact deviation scans against a 3 mm Gaussian background (`SNDEV/logs/probe10b-tumor-scan-2026-11-05.py`, `SNDEV/logs/probe13-tumor-scan-bodymask-2026-11-05.py`), deviation 10 to 15 HU, components 2 to 500 mL, restricted to the body (HU above -300, eroded 5 mm) and to soft tissue (mean HU -50 to 250). The only components found were the spinal canal (mean 13.3 HU, identified on the crop as CSF) and a chest-wall edge band. No soft-tissue focus in the liver matched a 4 cm mass on either acquisition.
- Final chain search (variant V1): compact hyper foci on acquisition 1 slices and hypo foci on acquisition 2 slices relative to a 10 mm background, inside the liver eroded 8 mm, components 2 to 150 mL. Candidates (recorded in `tumor_hypoattenuating_provenance.json`): 13.26 mL at (x 121, y 222, z -270), 9.12 mL at (x 153, y 279, z -305), 4.77 mL at (x 126, y 263, z -290), 3.16 mL at (x 246, y 115, z -315). None of these lies in a rounded mass on the rendered slices; they sit at vessel-adjacent and liver-edge locations. Under the chain's confirmation rule (a focus enters the segment only when confirmed by CT inspection) the segment is empty.

Finding, stated plainly: the 35.75 mL reference mass is not detectable by inspection on the available phases. What was seen instead: homogeneous liver parenchyma with normal portal and hepatic vessel structures on both acquisitions, and dark areas near the gallbladder and the duodenum that read as bowel and biliary. An isoattenuating lesion on both available phases would evade both the visual pass and the 10 HU deviation scan; the available data (late arterial and portal venous only) cannot exclude that.

Seeds: none placed (no confirmed lesion). No seeded chain was run for the tumor.

### 3. Vessel chain

Seeds from CT inspection (slice index k of the 36-slice staged volume, z = -415 + 5*k mm):

- Aorta: (k 19, y 224, x 271) and (k 23, y 232, x 272). Round prevertebral structure anterior-left of the vertebral body, lumen 224.7 HU on acquisition 1 and 160.6 to 165.5 HU on acquisition 2, calcified wall plaque visible on the acquisition 2 crop (`SNDEV/logs/probe8-png/zoom2_acq2_z-320.0_aorta_c1_x271_y224.png`).
- Main portal vein: (k 23, y 215, x 228) and (k 19, y 215, x 228). Rounded contrast-filled structure at the porta within the liver, 188.6 HU on acquisition 2 and 113.2 HU on acquisition 1 (`SNDEV/logs/probe8-png/zoom3_acq2_z-300.0_round_obj_A_x228_y215.png`).

Method (variants V1 and V2 in `sim/segmentation/segment_reference.py`, function `chain_vessel_v1`):

1. Phase-aware brightness on HU smoothed with sigma 1 mm (V1: acquisition 1 85 to 285, acquisition 2 140 to 285; V2: 100 to 285 and 150 to 285).
2. Multi-scale Frangi bright-tube vesselness (max over sigma 1.5, 3, 6 mm), from SimpleITK RecursiveGaussian second derivatives in physical units and numpy eigenvalues of the symmetric Hessian (beta 0.5, c 6 HU, S floor 4 HU; threshold 0.5 for V1 and 0.6 for V2).
3. Candidate region: liver mask dilated 8 mm union the aorta box (x 235 to 335, y 170 to 300). V2 also excludes calcified components of 20000 voxels or more filled and dilated 3 mm (vertebral bodies, which otherwise leak the internal venous plexus through lumbar connections) and the kidney ROIs (right x 115 to 245, y 255 to 380; left x 325 to 445, y 240 to 355; the renal arteries connect the aorta tree to the kidney vasculature).
4. Seed-connected components with 15 by 15 pixel seed patches (a component is kept when it covers 5 or more patch voxels).
5. Bone exclusion kept: HU at or above 250, holes filled, dilated 3 mm, minus a 1 mm protection zone around the vessel core (a circumferentially calcified aortic wall would otherwise have its lumen filled by the bone hole fill and kill the seeds). Margin dilation 2 mm (V1) or 1 mm (V2), then the bone exclusion subtracted again.

Recall moved first as scoped: 0.3098 (V0) to 0.7169 (V1). V2 trades recall down to 0.5676 while cutting the mask from 648.48 mL to 182.25 mL, which is the better Dice. Residual false positives: perivascular partial-volume rinds, mesenteric branches of the portal tree (SMV), intercostal and lumbar artery branches from the aorta, and small vertebral plexus remnants.

### 4. Liver chain

Seeds from CT inspection:

- Right-lobe parenchyma (k 19, 23, 13, 25; y 195, x 135): verified parenchyma on the probe9b zoom crops (94.2 HU on acquisition 2, 54.3 HU on acquisition 1).
- Medial parenchyma (k 19 and 23; y 115, x 240): liver tissue on the probe16 renders of the medial region.

Method (variants V1 and V2, functions `chain_liver_v1` and `organ_minus_vessel`):

1. Phase-aware HU bounds on sigma 1 mm smoothed HU (acquisition 1: 50 to 95, acquisition 2: 80 to 150) inside the liver ROI (x 30 to 350, y 50 to 350) and z range -390 to -238 mm, minus the bone exclusion (HU at or above 250, holes filled, dilated 3 mm).
2. Thin-bridge opening (3 mm for V1, 2 mm for V2) to cut organ-contact bridges such as the gastric wall to the spleen, then seed-connected components (15 by 15 seed patches).
3. Closing 3 mm, hole fill, keep largest.
4. Organ-minus-vessel separation: V1 subtracts the vessel core dilated 3 mm, V2 subtracts the vessel core eroded 1.5 mm (lumen centers only), then fills holes.

The V1 measurement drove the V2 change: V1 recall fell to 0.5968 with the 3 mm dilated subtraction, which shows the reference liver includes vessel lumens, so V2 limits the separation to lumen cores. Component inspection (`SNDEV/logs/probe17-liver-components-2026-11-05.py`) shows the growth reaches one liver component of 1471.84 mL (bbox x 51 to 336, y 91 to 316, z -390 to -250) and correctly excludes the duodenum and pancreatic head (24.75 mL at x 267, y 260, z -355) and the pancreatic tail (20.75 mL at x 332, y 299, z -295).

### Variant iteration log

Development iterations before the scored runs are recorded in `SNDEV/logs/dev-chains-2026-11-05.py` and its log (loose phase bounds leaked through muscle and organ contacts at 3647 mL; a 3 mm opening on a speckled candidate ate the seeds; a missing hole fill in the bone exclusion leaked the vertebral body; a component-statistics bug is fixed in probe17). Two capture bugs are annotated in place: probe10 (component geometry without volume spacing) and probe11 (air outside the body dominating the top components); probe14 stacked both acquisitions at 28 duplicated z levels and was superseded by probe14b, which matches labelmap slices by geometry.

Scored variants (every variant run through `run.ps1` and `run_evaluation.ps1`; V0 rows are the slice-2 chains on the confound-fixed input from `SNDEV/docs/impl-2026-11-05-task21-slice3-method.md`):

| Structure | Variant | Method chain | Dice | Jaccard | Recall | Pipeline mL | Reference mL | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| parenchyma_liver | V0 | Threshold 40 to 200 HU, ROI clip, BinaryMedian 3 mm, keep largest | 0.7108 | 0.5514 | 0.7778 | 1745.15 | 1468.28 | slice 2 chain on confound-fixed input |
| parenchyma_liver | V1 | Seeded growth (phase bounds 50 to 95 / 80 to 150 HU, opening 3 mm), closing, fill, keep largest, minus vessel core dilated 3 mm | 0.7225 | 0.5656 | 0.5968 | 957.28 | 1468.28 | subtraction cost recall (reference liver includes vessel lumens) |
| parenchyma_liver | V2 (final) | Seeded growth (same bounds, opening 2 mm, medial seeds), closing, fill, keep largest, minus vessel core eroded 1.5 mm | 0.8915 | 0.8042 | 0.9290 | 1591.81 | 1468.28 | final scoring chain |
| tumor_hypoattenuating | V0 | Erode parenchyma 10 mm, smoothed HU at or below background minus 30 HU, opening 1 voxel, keep largest | 0.0000 | 0.0000 | 0.0000 | 1.72 | 35.75 | slice 2 chain; blind background-median artifact |
| tumor_hypoattenuating | V1 (final) | Compact phase-specific focus search inside liver eroded 8 mm; none confirmed by inspection; empty | 0.0000 | 0.0000 | 0.0000 | 0.00 | 35.75 | final scoring chain; candidates recorded in provenance |
| vascular_keepout_bone_excluded | V0 | Threshold 150 to 300 HU, ROI clip, bone exclusion, dilate 2 mm | 0.0543 | 0.0279 | 0.3098 | 421.13 | 40.48 | slice 2 chain on confound-fixed input |
| vascular_keepout_bone_excluded | V1 | Vesselness seed growth (broad bright bounds 85 to 285 / 140 to 285 HU, threshold 0.5), dilate 2 mm | 0.0842 | 0.0440 | 0.7169 | 648.48 | 40.48 | recall priority run |
| vascular_keepout_bone_excluded | V2 (final) | Vesselness seed growth (bright bounds 100 to 285 / 150 to 285 HU, threshold 0.6, vertebral and kidney exclusions), dilate 1 mm | 0.2063 | 0.1150 | 0.5676 | 182.25 | 40.48 | final scoring chain |

### Final chain and results

Final run 2026-11-05: `run.ps1` (defaults liver V2, tumor V1, vessel V2), Slicer exit 0, wall 42.6 s, log `SNDEV/logs/segment-run-tcia-hcc-tace-seg-hcc001-20261105T184041Z.log`; `run_evaluation.ps1`, exit 0, log `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261105T184142Z.log`. The V1 scored run logs are `SNDEV/logs/segment-run-tcia-hcc-tace-seg-hcc001-20261105T182720Z.log` and `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261105T182838Z.log`.

| Segment | Reference | Dice | Jaccard | Recall | Pipeline mL | Reference mL | Verdict (0.90) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| parenchyma_liver | reference_liver | 0.8915 | 0.8042 | 0.9290 | 1591.81 | 1468.28 | FAIL |
| tumor_hypoattenuating | reference_tumor | 0.0000 | 0.0000 | 0.0000 | 0.00 | 35.75 | FAIL |
| vascular_keepout_bone_excluded | reference_vessel | 0.2063 | 0.1150 | 0.5676 | 182.25 | 40.48 | FAIL |

All three segments FAIL the proposed 0.90 threshold. The liver result is 0.0085 short. The gate is not met; the numbers are the input for the VAL-031 metric restatement by the document owner.

### What a slice 5 would need per segment

- parenchyma_liver (0.8915): about 75000 false-positive voxels (228 mL) and 34000 false-negative voxels (104 mL) remain. The gap is boundary-level and convention-level: sub-voxel boundary refinement (level-set or shape prior), agreement on what the liver label includes at the porta, the gallbladder bed, and the caudate, and a single-phase or registered dual-phase input so the phase-aware bounds do not straddle two breath-hold positions. Cutting 30 mL of false positives without losing intersection reaches 0.90.
- tumor_hypoattenuating (0.0000): the lesion is not detectable on the available phases. A slice 5 needs an acquisition where the lesion is visible (for example the delayed phase of the TACE-Seg multiphase set), or a documented dataset note that locates the mass for a seeded chain under a holdout ruling. No CT-only method on the late arterial and portal venous pair can segment a mass that shows no measurable contrast against liver.
- vascular_keepout_bone_excluded (0.2063): recall is 0.5676 against a 40.48 mL reference, and the mask is 182 mL. A slice 5 needs the convention of the SEG Portal vein segment (main trunk versus full tree) before precision work can pay off, a smaller vesselness scale range for 2 to 4 mm branches, and removal of the mesenteric and lumbar branches by seed-subtree selection. The 1 mm keep-out margin is a safety choice and dilates the mask against a margin-free reference.

### Verification

- Input selection: `select_seg_input.py` PASS (`SELECT_DONE 36 instances`), exit 0.
- V1 pipeline run: PASS (`SURGITWIN_DONE`, Slicer exit 0, wall 61.8 s). Final pipeline run: PASS (`SURGITWIN_DONE`, Slicer exit 0, wall 42.6 s).
- Evaluation runs: exit 0, `EVALUATION_DONE` present for both. Verdicts FAIL for all three segments on both runs (a measurement, not a script error).
- `py_compile` on `sim/segmentation/segment_reference.py`: PASS (Slicer Python).
- Provenance and manifest record the variants (liver v2, tumor v1, vessel v2), the per-slice acquisition list, the phase determination with its evidence file, the seeds, and the effect chains with parameters and library versions. `is_g21_reference: false` on all pipeline outputs.
- Holdout: the pipeline input is the 36 SEG-referenced CT instances; `assert_ct_only_input` refuses SEG objects; no script in this slice opened `reference/` or SEG label content. Style constraints (straight quotes, no em dashes) applied to the new and changed files.

### Commit plan

Commit A: `sim/segmentation/` changes and this log. Commit B: `DEVELOPMENT_PLAN.md` Phase 2 edits, with commit A's hash.
