# sim/segmentation

Segmentation pipeline for FR-MS-001 (SRS.md v1.4.0): DICOM volume ingest, segment export on the native Windows 3D Slicer install (SOUP pin in sim/SOUP.md), and the G2.1 evaluation against held-out expert labels under the VAL-032 re-centered clauses (VTM row FR-MS-001).

Status: plan task 2.1, slice 7. The pipeline runs end to end on the TCIA HCC-TACE-Seg HCC_001 series. The 2026-11-05 final run is evaluated against the VAL-032 clauses with the slice-7 grounded values: parenchyma PASS against the liver envelope (Dice 0.9077, recall 0.9505), vascular keep-out PASS at the grounded 0.47 recall floor and 7.5 times volume bound (gated recall 0.4762 at the 3.0 mm modality floor, volume 7.2384 times the reference), tumor not applicable. Gate G2.1 reads PASS with recorded boundaries (boundaries in `DEVELOPMENT_PLAN.md` gate G2.1).

## Pinned environment

- 3D Slicer 5.12.4, revision 4e21c19 (as recorded in the output sidecars), installed at `I:\Library\3D Slicer 5.12.4` (the path in sim/SOUP.md; the path `C:\Users\salmo\AppData\Local\NA-MIC\Slicer 5.12.4` does not exist on this host)
- Slicer bundles SimpleITK 2.5.5 and VTK, used through Slicer's Python. No additional packages are installed. Both are recorded in the output sidecars. The evaluation uses the same bundled SimpleITK through `bin\PythonSlicer.exe`.

## Scripts

| Script | Role | Reads | Writes |
| --- | --- | --- | --- |
| `run.ps1` | Runs `select_seg_input.py` then `segment_reference.py` | `data/` CT folder, SEG headers for selection | `output/<dataset-id>/` segments, sidecars, manifest |
| `select_seg_input.py` | Stages the SEG-referenced CT instances | CT, SEG `ReferencedSOPInstanceUID` only | `output/<dataset-id>/input/`, `input_selection.json` |
| `segment_reference.py` | Pipeline (Slicer) | staged CT only | segments |
| `run_reference.ps1` | Runs `export_reference_labels.py` | CT and SEG folders | `output/<dataset-id>/reference/` |
| `export_reference_labels.py` | Exports held-out labelmaps from the SEG object | CT and SEG | `reference/` |
| `run_evaluation.ps1` | Runs `evaluate_g21.py` with Slicer's Python | `output/` segments and `reference/` | `output/<dataset-id>/evaluation.json` |
| `evaluate_g21.py` | VAL-031 clause verdicts, Dice, Jaccard, recall, volumes, alignment, SEG label-convention notes | segments and `reference/` | `evaluation.json`, summary table |

## One-command runs

From the repository root:

    powershell -ExecutionPolicy Bypass -File sim\segmentation\run.ps1
    powershell -ExecutionPolicy Bypass -File sim\segmentation\run_reference.ps1
    powershell -ExecutionPolicy Bypass -File sim\segmentation\run_evaluation.ps1

Run order: the pipeline first, then the reference export, then the evaluation. The reference export only needs to run once per dataset. Each runner captures stdout and stderr to `SNDEV\logs\`. `run.ps1` exits non-zero unless the log contains `SURGITWIN_DONE`.

Method variants are selected per structure with environment variables `SURGITWIN_LIVER_VARIANT`, `SURGITWIN_TUMOR_VARIANT`, `SURGITWIN_VESSEL_VARIANT` (liver v0 to v4, tumor v0 to v1, vessel v0 to v5; the default is the final chain: liver v4, tumor v1, vessel v5). Variant v0 is the slice-2 chain and needs the Segment Editor Threshold effect; v1 and above are numpy and SimpleITK chains.

## Holdout of the reference labels

The expert SEG labels are the G2.1 reference. They are kept out of pipeline inputs as follows:

- `select_seg_input.py` (slice 3a) opens the SEG object only to read the `ReferencedSOPInstanceUID` list and the series and study identifiers needed for selection. It writes `output/<dataset-id>/input/` (the SEG-referenced CT files) and `output/<dataset-id>/input_selection.json` (selection provenance). No SEG pixel data, label data, or geometry enters the pipeline or any output other than that provenance file.
- `segment_reference.py` reads only the staged `input/` folder. Before import, it reads every DICOM header in that folder and aborts if any object has Modality SEG. It never opens the SEG object, `input_selection.json`, or `output/<dataset-id>/reference/`. The per-slice `AcquisitionNumber` values from those same CT headers drive the phase-aware HU bounds; this is CT input inspection and is recorded in the sidecars.
- `export_reference_labels.py` is the only code that reads SEG label content. It writes `reference/` (scored labelmaps plus the split `reference_portal_vein` and `reference_aorta` labelmaps used by the evaluation for the label-convention measurement).
- `evaluate_g21.py` is the only code that reads `reference/`, apart from the export. Its reference inspection (label-convention geometry, coverage attribution, disagreement profiles and overlays) is evaluation-side and never enters the scoring chain.
- Ruling of 2026-11-05 (document owner): the `select_seg_input.py` SEG read is approved under the constraint above. Any change that lets the pipeline consume SEG content or `reference/` at run time requires a new ruling.
- The reference sidecars carry `is_g21_reference: true` and the holdout statement. The pipeline sidecars and manifest carry `is_g21_reference: false`.

Tuning of thresholds, seeds, and ROI boxes used CT inputs only (CT montages, zoomed crops, and CT HU statistics, recorded in `SNDEV/logs/` probes). A clinical annotation is a legitimate operator-seed source under VAL-031 clause (c); SEG reference labels never are. Each method variant is scored once through `evaluate_g21.py` and the numbers are recorded in `SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md`.

## Dataset

TCIA HCC-TACE-Seg, patient HCC_001. Details, checksums, and licenses are in `data/PROVENANCE.md`.

- CT series `1.3.6.1.4.1.14519.5.2.1.1706.8374.302065206690360709343725942120`, "C-A-P". Two acquisitions share this series UID: acquisition 2 (36 slices, z -415 to -240 mm) and acquisition 1 (30 slices, z -375 to -230 mm). The pipeline input is the 36 SEG-referenced instances (21 acquisition 2 and 15 acquisition 1), selected by `select_seg_input.py`.
- SEG series `1.2.276.0.7230010.3.1.3.8323329.719.1600928570.399942`, one object, SOP instance `1.2.276.0.7230010.3.1.4.8323329.719.1600928570.399943`, with four segments: Liver, Mass, Portal vein, and Abdominal aorta.
- The CT has no contrast phase tags. Measured HU (7x7 pixel ROIs, `SNDEV/logs/probe9b-phase-hu-2026-11-05.json`): acquisition 1 aorta 225 HU against liver 54 to 74 HU (late arterial), acquisition 2 aorta 163 HU against liver 94 to 139 HU (portal venous).
- Clinical data: `HCC-TACE-Seg_clinical_data-V2.xlsx` (TCIA collection page, CC BY 4.0, checksummed in `data/PROVENANCE.md`). For HCC_001 it records tumor characteristics (Tr_Size 0.8 cm, multinodular, T_involvment <= 50%, moderately differentiated) and no lesion location. The tumor sub-gate of VAL-031 clause (c) is therefore not applicable on this patient.

## SEG label conventions (measured, evaluation-side)

Measured by `evaluate_g21.py` from the reference labelmaps and recorded with each run (VAL-032 requires the notes):

- The SEG labels are disjoint: the Liver label excludes the Mass and both vessel labels (overlap 0.0 on every pair). The parenchyma chain fills the segmented vessel carve-outs into the organ (VAL-032 envelope convention, liver v4); the subtracting chain (v3) is retained as a scored variant.
- The "Portal vein" label is the full intrahepatic tree: 23.61 mL in 35 connected components over slices 2 to 31, branch volume share 0.74, max in-plane lumen radius 2.34 mm.
- The "Abdominal aorta" label is one component of 16.87 mL over slices 21 to 29 (z -310 to -270) only, max in-plane lumen diameter 19.58 mm, while the aorta is visible over the full scan. The keep-out covers the full visible aorta for safety (FR-RTA-003) and the extra extent is part of the volume accounting in the slice-5 and slice-6 logs.
- Lumen diameter is the per-slice in-plane in-sphere diameter (the SimpleITK 2.5.5 Maurer filter returns squared distances; the true distance is the square root, verified on a synthetic disk). The slice-5 records of 5.49 mm portal radius and the 67 percent FP distance share used the squared values and are superseded.

## Pipeline

1. `DICOMUtils.importDicom` imports the staged CT folder into a temporary Slicer database. `loadPatientByUID` loads the series. Staged instance count, z order, and the per-slice acquisition numbers are verified against the loaded volume.
2. A segmentation node is created with the selected volume as reference geometry.
3. Three segments are produced (final chains; variant chains in `SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md`):
   - `vascular_keepout_bone_excluded` (vessel v5): phase-aware brightness on HU smoothed with sigma 1 mm (acquisition 1: 85 to 285 HU, acquisition 2: 145 to 285 HU), multi-scale Frangi bright-tube vesselness (sigma 1.5, 3, 6 mm; SimpleITK RecursiveGaussian derivatives and numpy eigenvalues), seed-subtree selection (aorta subtree in the aorta corridor x 250 to 305, y 195 to 285; portal subtree in the liver zone dilated 8 mm), z-continuity closing (1, 1, 2 voxels) across the under-opacified acquisition 1 slices, bone exclusion with a 3 mm protection zone around the vessel core, and the keep-out margin.
   - `parenchyma_liver` (liver v4): phase-aware HU bounds (acquisition 1: 50 to 95, acquisition 2: 80 to 150) on smoothed HU in the liver ROI and z range, spine-centered bone exclusion, thin-bridge opening 2 mm, seed-connected components from CT-inspected parenchyma seed patches, closing 3 mm, small-hole fill (at most 100 voxels), keep largest, and organ-envelope fill (the segmented vessel carve-outs are filled into the organ per the VAL-032 envelope convention; the v3 chain subtracts the vessel core per the superseded disjoint convention and is retained as a scored variant).
   - `tumor_hypoattenuating` (tumor v1): documented detection attempt (compact phase-specific foci inside the liver eroded 8 mm). A focus enters the segment only when confirmed by CT inspection. No focus is confirmed on the available phases and no clinical annotation documents a lesion location, so the segment is empty.
4. Each segment is exported as a labelmap NRRD and a binary STL. The STL is built with `vtkDiscreteMarchingCubes` on the exported labelmap, transformed to RAS with the node matrix.
5. A provenance JSON is written beside each segment (effect chain with parameters and library versions, seeds, phase determination, per-slice acquisition numbers, variant names, keep-out margin and note), and `manifest.json` lists all files with SHA-256 hashes, voxel counts, and bounding boxes.

## Keep-out safety margin (VAL-031 clause (b))

- Margin value: 1.0 mm beyond the segmented vessel boundary (in-plane dilation of the vessel core, recorded as `keepout_margin_mm` in the vascular provenance sidecar and measured margin-inclusive by the evaluation).
- Carry-forward note: the keep-out safety margin is carried into the FR-RTA-003 envelope parameters. The envelope integration is Phase 3 work. The margin is documented here and in the provenance sidecar, and the evaluation records `margin_documentation` with each run.
- The clause volume bound is grounded at 7.5 times the 40.48 mL reference (VAL-032 addendum marker, slice-7 re-grounding; measured 7.2384 at 293.024 mL margin-inclusive). The margin adds 78.16 mL over the segmented core (214.865 mL) and the margin-free core is 5.31 times the reference, so the margin is not the bound-breaker.

## Reference export

`export_reference_labels.py` imports the CT and SEG folders, loads the SEG as a segmentation node, and resamples each reference segment onto the acquisition 2 CT grid with `arrayFromSegmentBinaryLabelmap`. The mapping is:

- `reference_liver` from Liver
- `reference_tumor` from Mass
- `reference_vessel` from Portal vein and Abdominal aorta (union, the scored reference)
- `reference_portal_vein` from Portal vein and `reference_aorta` from Abdominal aorta (split labelmaps for the label-convention measurement only)

Each reference sidecar records the SEG SOP instance UID, the SEG file SHA-256, the referenced SOP UIDs, the z-set alignment check, the labelmap SHA-256, and the voxel count.

## Evaluation

`evaluate_g21.py` evaluates the VAL-032 clauses per structure and reports Dice, Jaccard, recall, volumes, FP and FN, per-slice disagreement profiles, the SEG label-convention notes, the parenchyma envelope scores, the stratified vessel metrics, and the grounded markers:

- Alignment check first: origin, spacing, size, and direction must match within 1e-4. A mismatch stops the evaluation.
- Overlap from `SimpleITK.LabelOverlapMeasuresImageFilter`, with a NumPy Dice cross-check.
- Clause verdicts (VAL-032 with the slice-7 addendum): (a) parenchyma Dice at or above 0.90 and recall at or above 0.90 against the liver envelope (the reference liver label with the tumor and vessel carve-outs filled), with the disjoint-label score reported for the audit trail; (b) vascular keep-out recall at or above the grounded 0.47 floor over the reference-resolvable set (reference components with lumen diameter at or above the 3.0 mm modality floor), full-tree recall as information, volume at most the grounded 7.5 times the reference, and the margin documentation check; (c) tumor seeded Dice at or above 0.70 when a documented seed source exists, otherwise not applicable.
- Reference inspection in this script is evaluation-side only. The distance measures are square-root-corrected (the bundled Maurer filter returns squared distances).

### Result (2026-11-05 final run, defaults liver v4, tumor v1, vessel v5)

| Structure | Dice (scored convention) | Jaccard | Recall | Pipeline mL | Reference mL | Clause verdicts |
| --- | --- | --- | --- | --- | --- | --- |
| parenchyma_liver | 0.9077 (liver envelope) | 0.8311 | 0.9505 | 1671.73 | 1468.28 (envelope 1527.7) | Dice PASS, recall PASS |
| tumor_hypoattenuating | 0.0000 | 0.0000 | 0.0000 | 0.00 | 35.75 | NOT APPLICABLE (no documented seed source) |
| vascular_keepout_bone_excluded | 0.1129 (full tree, information) | 0.0598 | 0.4650 | 293.02 | 40.48 | gated recall 0.4762 PASS (floor 3.0 mm, grounded recall floor 0.47), volume 7.2384 times PASS (grounded bound 7.5), margin documented PASS |

Vascular band recalls on the final chain: 0.2684 (under 2 mm), 0.4254 (2 to 3 mm), 0.5854 (3 to 5 mm), 0.8350 (5 to 10 mm), 0.9936 (10 mm and above). The slice-7 variant Pareto and the re-grounding record are in `SNDEV/docs/impl-2026-11-05-task21-slice7-vessels.md` and `docs/val-032-g21-metric-recenter.md`: the fix for the missed resolvable vessels reaches gated recall 0.9614 only at organ-scale volume (31.4 times the reference) and the bounded attempt reads 0.3108 through its source rule, so the grounded recall floor 0.47 is the measured bounded-volume capability and the owner re-centers. The ungated residual is recorded in the risk register (plan Section 7.1) where FR-RTA-003 picks it up.

## Provenance rules

- Every dataset in `data/` has a checksum and source entry in `data/PROVENANCE.md`. New datasets require the same entry before a run.
- Each per-segment pipeline sidecar records: dataset ID, source note, volume UID, volume node name, shape, spacing, excluded acquisitions, per-slice acquisition numbers, the phase determination with its evidence file, the variant names, inputs (CT only), the operator, Slicer version and revision, the effect chain with parameters and library versions, output file names, mesh method, triangle count, voxel count, timestamp (UTC), and `is_g21_reference: false`. The vascular sidecar adds `keepout_margin_mm`, `vessel_core_voxels`, and the margin carry-forward note.
- Each reference sidecar records `is_g21_reference: true`, the source SEG SOP instance UID and file SHA-256, the referenced SOP UIDs, and the labelmap SHA-256.
- Outputs are regenerated by the runners. Old outputs are overwritten by the same names, so keep the run logs as the audit record.

## Known limitations

- The tumor segment is empty because no lesion is detectable by inspection on the available phases and the clinical annotation documents no lesion location. The documented search candidates are recorded in the tumor provenance. Lesion detection is excluded from the gate (VAL-031 clause (c)) and recorded as a limitation.
- The 2 to 4 mm portal branches partial-volume to HU values that overlap the parenchyma range at 0.78 by 0.78 by 5 mm (`SNDEV/logs/probe23b-vesselness-separation-2026-11-05.log`), and the Frangi measures degenerate at this anisotropy (the blob measure reads plain parenchyma as tube-like; the line-term reads the portal lumen below the parenchyma 95th percentile). This is the mechanism behind the vascular clause tension.
- The liver ROI, the aorta corridor, the z range, and the seed points are fixed values chosen from CT inspection of this dataset. They are not anatomical atlases.
- The reference and the pipeline input differ at 15 of 36 z levels, where the SEG references slices from the other acquisition. The two acquisitions are different breath-holds, so organ boundaries shift between adjacent slices of the staged volume.
- The Segment Editor Smoothing and Islands effects crashed `SlicerApp-real` in a no-main-window run (seen 2026-11-05). The morphology steps run through SimpleITK instead.
- No lint or typecheck gate exists for `sim/`. The Python scripts were compiled with `py_compile` but not linted.

## Decisions closed

- Reference dataset for G2.1: TCIA HCC-TACE-Seg, patient HCC_001, with its SEG object as the held-out reference (VAL-030, applied in SRS v1.4.0).
- Contrast phases: acquisition 1 is late arterial and acquisition 2 is portal venous, measured from aorta and liver HU on 2026-11-05 (`SNDEV/logs/probe9b-phase-hu-2026-11-05.json`).
- SEG label conventions: disjoint labels (Liver excludes Mass and vessels) and the full intrahepatic tree convention for "Portal vein" (measured 2026-11-05, evaluation-side).
