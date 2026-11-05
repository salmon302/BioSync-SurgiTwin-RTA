Title: Plan task 2.1 slice 2, G2.1 Dice evaluation against held-out SEG reference labels
Date: 2026-11-05T16:28:28Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.1 slice 2, gate G2.1 measurement
Summary: Adds held-out SEG reference labelmaps, a documented tumor segmentation attempt, vascular bone exclusion, and the G2.1 Dice evaluation on the TCIA HCC-TACE-Seg HCC_001 series.

## Task Reference

Plan task 2.1, slice 2 (remaining work after slice 1 at commit 9aa90f5). Requirement FR-MS-001 in SRS.md v1.4.0. Gate G2.1 (proposed metric, unchanged): meshes for parenchyma, tumor, and vascular keep-out zones exported from the HCC_001 series with segmentation provenance, overlap with the expert SEG reference labels held out of pipeline inputs at a Dice score of 0.90 or higher. VAL-030 is applied in SRS v1.4.0 (commits 51608bc and d14c481), which names the TCIA HCC-TACE-Seg HCC_001 series as the G2.1 reference set.

## Specification Summary

Slice 2 scope, from the task brief:

1. Reference labelmaps: import the HCC-TACE-Seg SEG objects (liver, tumor, vessel) through Slicer DICOM SEG handling onto the CT grid. Export under `sim/segmentation/output/tcia-hcc-tace-seg-hcc001/reference/` with provenance sidecars (`is_g21_reference: true`, source SEG SOP instance UIDs, checksums). The segmentation pipeline must not read these files.
2. Real tumor segmentation replacing the `lesion_synthetic` sphere, documented effect chain. The synthetic sphere is never scored as G2.1 output.
3. Bone exclusion for the vascular segment (slice 1 threshold of 150 to 300 HU caught cancellous bone in the vertebral body).
4. `sim/segmentation/evaluate_g21.py`: Dice, Jaccard, volume in mL, and voxel counts per segment against the reference labelmap, `evaluation.json` output, printed summary table, alignment check recorded.
5. Run `run.ps1` end to end and the evaluation on this host. Record wall time and Slicer warnings. Report Dice per segment against 0.90 with PASS or FAIL.
6. Cleanups: `sim/segmentation/README.md` TAIR decision closed per VAL-030; `DEVELOPMENT_PLAN.md` Phase 2 header, G2.1 row, task 2.1 row, and Phase 2 status paragraph updated with the results.

Threshold 0.90 is the proposed value in SRS v1.4.0 and is not changed in this slice.

## Implementation Notes

Log created before any other change in this slice.

### Reference export (item 1)

Files: `sim/segmentation/export_reference_labels.py` (SPDX MIT, Slicer script) and `sim/segmentation/run_reference.ps1` (SPDX MIT, runner). Output: `sim/segmentation/output/tcia-hcc-tace-seg-hcc001/reference/`.

Inputs and findings from header-only probes (`SNDEV/logs/probe3-dicom-metadata-2026-11-05.log`, `probe5-sop-overlap-2026-11-05.log`, `probe6-z-alignment-2026-11-05.log`):

- SEG object `1.2.276.0.7230010.3.1.4.8323329.719.1600928570.399943` (SeriesUID `...399942`), 4 segments: 1 Liver, 2 Mass, 3 Portal vein, 4 Abdominal aorta. The Mass segment is the tumor reference. The vessel reference is the union of Portal vein and Abdominal aorta. The mapping is recorded in each reference sidecar.
- The SEG references 36 CT instances, which is the 36-slice acquisition used by the pipeline. Its z positions (-415.0 to -240.0 mm, 5 mm steps, 36 unique) equal the z set of the Slicer acquisition 2 volume exactly. In-plane origin, orientation, and 0.78125 mm pixel spacing match.
- Caveat: the two CT acquisitions overlap in z (28 z levels carry one file from each acquisition). The SEG references 21 AcquisitionNumber 2 instances and 15 AcquisitionNumber 1 instances. The pipeline uses the acquisition 2 files at all 36 levels. At the 15 levels where the reference slice is an acquisition 1 file, the reference was drawn on different pixel data than the pipeline input. This is recorded in the reference sidecar and is a limit on the Dice reading at those levels.
- The first export attempt compared SOP instance sets and failed on that caveat. The check was changed to compare z sets and record the acquisition tag mix. That change was made before any Dice was computed.
- Phase: the CT has no ContrastBolusAgent or acquisition time tags (blank). The montage (`SNDEV/logs/probe4-png/montage_axial_z4-34.png`, CT only, no SEG overlay) shows portal venous style enhancement (enhanced portal veins, nephrographic kidneys, moderately bright aorta). Phase is inferred from the image, not from tags.

Export run: `run_reference.ps1`, Slicer exit 0, wall 6.8 s, log `SNDEV/logs/reference-export-tcia-hcc-tace-seg-hcc001-20261105T163133Z.log`. Reference voxel counts: reference_liver 481125, reference_tumor 11715, reference_vessel 13265. The first attempt (log `reference-export-...-20261105T163040Z.log`) failed on the SOP check and wrote no outputs.

Tuning discipline: the tumor and vessel chains below were chosen from CT inputs only (montage and HU statistics of the CT). Reference labels were not used to pick a seed, threshold, or ROI. Each chain was fixed before its first Dice reading. Each chain was run once. No Dice-driven iteration was done in this slice.

### Holdout enforcement (item 1)

- `segment_reference.py` calls `assert_ct_only_input` on its input folder. It reads every `.dcm` header and aborts if any Modality is SEG. The SEG folder is not passed to `run.ps1`.
- `segment_reference.py` never opens `output/<dataset-id>/reference/`.
- `export_reference_labels.py` is the only code that reads the SEG object. It writes `reference/`.
- `evaluate_g21.py` is the only code that reads `reference/` besides the export. Each reference sidecar records `"holdout": "read only by evaluate_g21.py; never an input to segment_reference.py"`.
- The same statement is in `sim/segmentation/README.md`.

### Pipeline chains (items 2 and 3)

Parenchyma (`parenchyma_liver`, unchanged from slice 1 apart from the name): Threshold 40 to 200 HU, ROI clip (x 0.12 to 0.45, y 0.17 to 0.65), `sitk.BinaryMedian` 3 mm, keep largest component.

Tumor (`tumor_hypoattenuating`, replaces the `lesion_synthetic` sphere, which was removed from the code and from the output folder):

1. `sitk.BinaryErode` of the parenchyma mask by 10 mm (interior).
2. Background liver median HU inside the parenchyma mask: 130.0 HU.
3. Gaussian smoothing of HU, sigma 1.0 mm. Candidate is smoothed HU at or below 100.0 HU (background minus 30 HU) inside the interior.
4. `sitk.BinaryMorphologicalOpening` radius 1 voxel.
5. Keep largest connected component.

The phase is inferred as portal venous from the montage. Arterial hyperenhancement was not the chain used. The chain targets hypoattenuation because it is the enhancement contrast expected in this phase. Seeded region growing was not used because no seed could be placed from CT inspection with a verified tumor location.

Vascular (`vascular_keepout_bone_excluded`):

1. Threshold 150 to 300 HU (Segment Editor).
2. ROI clip (x 0.37 to 0.65, y 0.33 to 0.49).
3. Bone exclusion: HU at or above 250, keep largest connected component (48379 voxels), fill holes, dilate 3 mm (exclusion 191254 voxels). Vessel voxels inside the exclusion are removed.
4. `sitk.BinaryDilate` 2 mm, then subtract the bone exclusion again.

### Run results (items 4 and 5)

Pipeline: `run.ps1`, Slicer exit 0, wall 11.2 s, log `SNDEV/logs/segment-run-tcia-hcc-tace-seg-hcc001-20261105T163255Z.log`, `SURGITWIN_DONE` present, no traceback. Warnings are the same as slice 1: 11 `Unable to enumerate family` font lines and three `no main window` toolbar lines. No DCMTK warning.

Reference export: `run_reference.ps1`, Slicer exit 0, wall 6.8 s, log `SNDEV/logs/reference-export-tcia-hcc-tace-seg-hcc001-20261105T163133Z.log`. Warnings: none beyond the same font and toolbar lines.

Evaluation: `run_evaluation.ps1` with the Slicer bundled Python (SimpleITK 2.5.5), exit 0, wall 0.9 s, log `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261105T163339Z.log`, `output/tcia-hcc-tace-seg-hcc001/evaluation.json`.

Grid alignment check (origin, spacing, size, direction, pipeline versus reference labelmap, NRRD): all match for all three pairs. Reference labelmap SHA-256 matches its sidecar for all three pairs. SOP instance UID of the source SEG for all three: `1.2.276.0.7230010.3.1.4.8323329.719.1600928570.399943`.

| Segment | Reference | Dice (SimpleITK) | Dice (NumPy check) | Jaccard | Pipeline mL | Reference mL | Verdict (threshold 0.90) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| parenchyma_liver | reference_liver | 0.6745 | 0.674485 | 0.5088 | 1574.36 | 1468.28 | FAIL |
| tumor_hypoattenuating | reference_tumor | 0.0000 | 0.0 | 0.0000 | 0.18 | 35.75 | FAIL |
| vascular_keepout_bone_excluded | reference_vessel | 0.0449 | 0.044873 | 0.0230 | 524.53 | 40.48 | FAIL |

Voxel counts: liver pipeline 515885, reference 481125; tumor pipeline 59, reference 11715; vessel pipeline 171879, reference 13265. Voxel volume is 3.0518 mm^3.

Interpretation (measurement only, no iteration):

- Liver: the pipeline and reference volumes are close (about 7 percent apart) but the overlap is low. The mask boundary or extra structures inside the box are the likely cause. This was not isolated in this slice.
- Tumor: the hypoattenuation chain found 59 voxels in two slices, against a reference of 11715 voxels. The method does not reach the tumor at this threshold. The result is recorded as the best attempt. The tumor mask is not a G2.1 output.
- Vessel: the bone exclusion removed 191254 exclusion voxels but the vessel mask stayed at 171879 voxels (slice 1: 183017). The 150 to 300 HU window in the vessel ROI also catches non-bone tissue at this phase. The bone exclusion does not address that. The cause was not verified on the CT in this slice.

Slice 3 target if the document owner keeps the gate: (a) liver boundary and extra-structure check on the CT, with a vascular and organ separation method that does not use the reference; (b) a tumor method that reaches the lesion on the portal venous phase CT, with the lesion located by CT inspection rather than the SEG; (c) a vessel method that separates contrast-enhanced vessels from enhancing parenchyma and bone (for example a tubular filter inside a vessel-only ROI, or a segment-based vessel selection) instead of the HU window.

Outputs removed in this slice: `lesion_synthetic_*`, `parenchyma_liver_smoke_*`, and `vascular_keepout_contrast_*` (slice 1 names). The slice 1 run logs are kept as the audit record.

### Verification (item 6 and gates)

- Python syntax: `python -m py_compile` on `segment_reference.py`, `export_reference_labels.py`, and `evaluate_g21.py`: PASS. No lint or typecheck gate exists for `sim/`, so none was run (same gap as slice 1).
- Pipeline end to end: `run.ps1` PASS (`SURGITWIN_DONE`, Slicer exit 0).
- Reference export: `run_reference.ps1` PASS (`SURGITWIN_REF_DONE`).
- Evaluation: `run_evaluation.ps1` completes (exit 0). Verdicts are FAIL for all three segments against 0.90. This is the measurement, and the gate is not met.
- Style scan of the owned files for the banned word list, em dashes, en dashes, and curly quotes: no matches. The TCIA license text contains curly quotes, which is third-party text and is not edited.
- Git exclusions: `sim/segmentation/.gitignore` excludes `data/*` (except PROVENANCE and LICENSE) and `output/`. The reference labelmaps and the evaluation are under `output/`, so they are excluded from commits.
- Not changed in this slice: `SRS.md`, `vv/`, `sim/SOUP.md`, `sim/bridge/`, `env/`. The threshold 0.90 and the gate wording are unchanged.

### Commit plan

Commit A: `sim/segmentation/` changes and this log. Commit B: `DEVELOPMENT_PLAN.md` Phase 2 rows, with commit A's hash.
