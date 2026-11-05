# sim/segmentation

Segmentation pipeline for FR-MS-001 (SRS.md v1.4.0): DICOM volume ingest, segment export on the native Windows 3D Slicer install (SOUP pin in sim/SOUP.md), and the G2.1 Dice evaluation against held-out expert labels.

Status: plan task 2.1, slice 4. The pipeline runs end to end on the TCIA HCC-TACE-Seg HCC_001 series with the slice-4 method variants (vessel tubularness, seeded liver growth, documented tumor search). The G2.1 evaluation runs on the same series. The 2026-11-05 final run gives Dice below 0.90 for all three segments (see Evaluation). Gate G2.1 is not claimed.

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
| `evaluate_g21.py` | Dice, Jaccard, recall, volumes, alignment check | segments and `reference/` | `evaluation.json`, summary table |

## One-command runs

From the repository root:

    powershell -ExecutionPolicy Bypass -File sim\segmentation\run.ps1
    powershell -ExecutionPolicy Bypass -File sim\segmentation\run_reference.ps1
    powershell -ExecutionPolicy Bypass -File sim\segmentation\run_evaluation.ps1

Run order: the pipeline first, then the reference export, then the evaluation. The reference export only needs to run once per dataset. Each runner captures stdout and stderr to `SNDEV\logs\`. `run.ps1` exits non-zero unless the log contains `SURGITWIN_DONE`.

Method variants are selected per structure with environment variables `SURGITWIN_LIVER_VARIANT`, `SURGITWIN_TUMOR_VARIANT`, `SURGITWIN_VESSEL_VARIANT` (values v0, v1, v2; the default is the final chain: liver v2, tumor v1, vessel v2). Variant v0 is the slice-2 chain and needs the Segment Editor Threshold effect; v1 and v2 are numpy and SimpleITK chains.

## Holdout of the reference labels

The expert SEG labels are the G2.1 reference. They are kept out of pipeline inputs as follows:

- `select_seg_input.py` (slice 3a) opens the SEG object only to read the `ReferencedSOPInstanceUID` list and the series and study identifiers needed for selection. It writes `output/<dataset-id>/input/` (the SEG-referenced CT files) and `output/<dataset-id>/input_selection.json` (selection provenance). No SEG pixel data, label data, or geometry enters the pipeline or any output other than that provenance file.
- `segment_reference.py` reads only the staged `input/` folder. Before import, it reads every DICOM header in that folder and aborts if any object has Modality SEG. It never opens the SEG object, `input_selection.json`, or `output/<dataset-id>/reference/`. The per-slice `AcquisitionNumber` values from those same CT headers drive the phase-aware HU bounds; this is CT input inspection and is recorded in the sidecars.
- `export_reference_labels.py` is the only code that reads SEG label content. It writes `reference/`.
- `evaluate_g21.py` is the only code that reads `reference/`, apart from the export.
- Ruling of 2026-11-05 (document owner): the `select_seg_input.py` SEG read is approved under the constraint above. Any change that lets the pipeline consume SEG content or `reference/` at run time requires a new ruling.
- The reference sidecars carry `is_g21_reference: true` and the holdout statement. The pipeline sidecars and manifest carry `is_g21_reference: false`.

Tuning of thresholds, seeds, and ROI boxes used CT inputs only (CT montages, zoomed crops, and CT HU statistics, recorded in `SNDEV/logs/` probes and `SNDEV/docs/impl-2026-11-05-task21-slice4-method.md`). The reference labels were not used to place a seed. Each method variant was scored once through `evaluate_g21.py` and the numbers are recorded in the slice-4 log; the final scoring chain is the reported pipeline.

## Dataset

TCIA HCC-TACE-Seg, patient HCC_001. Details, checksums, and licenses are in `data/PROVENANCE.md`.

- CT series `1.3.6.1.4.1.14519.5.2.1.1706.8374.302065206690360709343725942120`, "C-A-P". Two acquisitions share this series UID: acquisition 2 (36 slices, z -415 to -240 mm) and acquisition 1 (30 slices, z -375 to -230 mm). The pipeline input is the 36 SEG-referenced instances (21 acquisition 2 and 15 acquisition 1), selected by `select_seg_input.py`.
- SEG series `1.2.276.0.7230010.3.1.3.8323329.719.1600928570.399942`, one object, SOP instance `1.2.276.0.7230010.3.1.4.8323329.719.1600928570.399943`, with four segments: Liver, Mass, Portal vein, and Abdominal aorta.
- The SEG references 36 CT instances, one per z level. 21 of the referenced instances carry AcquisitionNumber 2 and 15 carry AcquisitionNumber 1, because the two acquisitions overlap in z. At 15 levels the reference was drawn on different pixel data from the pipeline input. This is a limit on the Dice reading and is recorded in `reference/*_provenance.json`.
- The CT has no contrast phase tags. Measured HU (7x7 pixel ROIs, `SNDEV/logs/probe9b-phase-hu-2026-11-05.json`): acquisition 1 aorta 225 HU against liver 54 to 74 HU (late arterial), acquisition 2 aorta 163 HU against liver 94 to 139 HU (portal venous). Acquisition 1 shows corticomedullary kidneys and acquisition 2 nephrographic kidneys.

## Pipeline

1. `DICOMUtils.importDicom` imports the staged CT folder into a temporary Slicer database. `loadPatientByUID` loads the series. The script picks the acquisition with the most slices and records the others as excluded. Staged instance count, z order, and the per-slice acquisition numbers are verified against the loaded volume.
2. A segmentation node is created with the selected volume as reference geometry.
3. Three segments are produced (final chains; variant chains in `SNDEV/docs/impl-2026-11-05-task21-slice4-method.md`):
   - `vascular_keepout_bone_excluded` (vessel v2): phase-aware brightness on HU smoothed with sigma 1 mm (acquisition 1: 100 to 285 HU, acquisition 2: 150 to 285 HU), multi-scale Frangi bright-tube vesselness (sigma 1.5, 3, 6 mm; SimpleITK RecursiveGaussian derivatives and numpy eigenvalues), candidate region of the liver zone dilated 8 mm union the aorta box, vertebral and kidney exclusions, seed-connected components from aorta and portal-vein seed patches (CT inspection), bone exclusion (HU at or above 250, holes filled, dilated 3 mm, minus the protected vessel core), and a 1 mm margin.
   - `parenchyma_liver` (liver v2): phase-aware HU bounds (acquisition 1: 50 to 95, acquisition 2: 80 to 150) on smoothed HU in the liver ROI and z range, bone exclusion, thin-bridge opening 2 mm, seed-connected components from CT-inspected parenchyma seed patches, closing 3 mm, hole fill, keep largest, organ-minus-vessel separation (vessel core eroded 1.5 mm), hole fill.
   - `tumor_hypoattenuating` (tumor v1): documented detection attempt. Compact hyper foci on late arterial slices and hypo foci on portal venous slices (15 HU against a 10 mm background) inside the liver eroded 8 mm, 2 to 150 mL components. A focus enters the segment only when confirmed by CT inspection. For HCC_001 no focus is confirmed and the segment is empty (see the slice-4 log).
4. Each segment is exported as a labelmap NRRD and a binary STL. The STL is built with `vtkDiscreteMarchingCubes` on the exported labelmap, transformed to RAS with the node matrix.
5. A provenance JSON is written beside each segment (effect chain with parameters and library versions, seeds, phase determination, per-slice acquisition numbers, variant names), and `manifest.json` lists all files with SHA-256 hashes, voxel counts, and bounding boxes.

Outputs go to `sim/segmentation/output/<dataset-id>/`.

## Reference export

`export_reference_labels.py` imports the CT and SEG folders, loads the SEG as a segmentation node, and resamples each reference segment onto the acquisition 2 CT grid with `arrayFromSegmentBinaryLabelmap`. The mapping is:

- `reference_liver` from Liver
- `reference_tumor` from Mass
- `reference_vessel` from Portal vein and Abdominal aorta (union)

Each reference sidecar records the SEG SOP instance UID, the SEG file SHA-256, the referenced SOP UIDs, the z-set alignment check, the labelmap SHA-256, and the voxel count.

## Evaluation

`evaluate_g21.py` compares each pipeline segment to its reference labelmap:

- Alignment check first: origin, spacing, size, and direction must match within 1e-4. A mismatch stops the evaluation.
- Dice and Jaccard from `SimpleITK.LabelOverlapMeasuresImageFilter`, with a NumPy Dice cross-check.
- Recall (reference-voxel coverage), volumes in mL, and voxel counts for both sides.
- Verdict per segment: PASS at Dice 0.90 or higher, otherwise FAIL. The threshold is the proposed G2.1 value in SRS v1.4.0 and is not changed by the script.

Output: `output/<dataset-id>/evaluation.json` and a summary table on stdout.

### Result (2026-11-05 final run)

| Segment | Reference | Dice | Jaccard | Recall | Pipeline mL | Reference mL | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| parenchyma_liver | reference_liver | 0.8915 | 0.8042 | 0.9290 | 1591.81 | 1468.28 | FAIL |
| tumor_hypoattenuating | reference_tumor | 0.0000 | 0.0000 | 0.0000 | 0.00 | 35.75 | FAIL |
| vascular_keepout_bone_excluded | reference_vessel | 0.2063 | 0.1150 | 0.5676 | 182.25 | 40.48 | FAIL |

The grid alignment check passed for all three pairs. Variant rows and run logs are in `SNDEV/docs/impl-2026-11-05-task21-slice4-method.md`.

## Provenance rules

- Every dataset in `data/` has a checksum and source entry in `data/PROVENANCE.md`. New datasets require the same entry before a run.
- Each per-segment pipeline sidecar records: dataset ID, source note, volume UID (series instance UID), volume node name, shape, spacing, excluded acquisitions, per-slice acquisition numbers, the phase determination with its evidence file, the variant names, inputs (CT only), the operator (script name and SHA-256), Slicer version and revision, the effect chain with parameters and library versions, output file names, mesh method, triangle count, voxel count, timestamp (UTC), and `is_g21_reference: false`.
- Each reference sidecar records `is_g21_reference: true`, the source SEG SOP instance UID and file SHA-256, the referenced SOP UIDs, and the labelmap SHA-256.
- Outputs are regenerated by the runners. Old outputs are overwritten by the same names, so keep the run logs as the audit record.

## Known limitations

- The liver ROI, the aorta box, the kidney ROIs, the z range, and the seed points are fixed values chosen from CT inspection of this dataset. They are not anatomical atlases.
- The tumor segment is empty because no lesion is detectable by inspection on the available phases. The documented search candidates are recorded in the tumor provenance. The V0 tumor chain produced a 1.72 mL background-median artifact and is kept only as a scored variant.
- The vessel segment still carries perivascular partial-volume rinds, mesenteric branches of the portal tree, and intercostal and lumbar artery branches. The reference vessel (40.48 mL) is much smaller than any seed-connected tree the CT supports at 0.78 by 0.78 by 5 mm.
- The reference and the pipeline input differ at 15 of 36 z levels, where the SEG references slices from the other acquisition (see Dataset). The two acquisitions are different breath-holds, so organ boundaries shift between adjacent slices of the staged volume.
- The Segment Editor Smoothing and Islands effects crashed `SlicerApp-real` in a no-main-window run (seen 2026-11-05). The morphology steps run through SimpleITK instead. The Segment Editor Threshold effect runs normally and is used only by the v0 variants.
- The organ mesh is tens of MB of binary STL at 0.78 by 0.78 by 5 mm voxels.
- No lint or typecheck gate exists for `sim/`. The Python scripts were compiled with `py_compile` but not linted.

## Decisions closed

- Reference dataset for G2.1: TCIA HCC-TACE-Seg, patient HCC_001, with its SEG object as the held-out reference. This follows VAL-030, applied in SRS v1.4.0 (commits 51608bc and d14c481). The Kitware TAIR set was not used. It is cerebrovascular CTA and MRA in NIfTI and has no organ or tumor labels (see the slice 1 log).
- Contrast phases: acquisition 1 is late arterial and acquisition 2 is portal venous, measured from aorta and liver HU on 2026-11-05 (`SNDEV/logs/probe9b-phase-hu-2026-11-05.json`).

## Slice 5 needs

- Parenchyma: sub-voxel boundary refinement, agreement on porta and gallbladder-bed convention, and a single-phase or registered dual-phase input. Cutting about 30 mL of false positives without losing intersection reaches 0.90.
- Tumor: an acquisition where the lesion is visible (for example the delayed phase), or a documented dataset note that locates the mass under a holdout ruling.
- Vascular: the convention of the SEG Portal vein segment (main trunk versus full tree), a smaller vesselness scale range for 2 to 4 mm branches, and seed-subtree selection to drop mesenteric and lumbar branches.
