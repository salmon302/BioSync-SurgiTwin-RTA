# sim/segmentation

Segmentation pipeline for FR-MS-001 (SRS.md v1.4.0): DICOM volume ingest, segment export on the native Windows 3D Slicer install (SOUP pin in sim/SOUP.md), and the G2.1 Dice evaluation against held-out expert labels.

Status: plan task 2.1, slice 2. The pipeline runs end to end on the TCIA HCC-TACE-Seg HCC_001 series. The G2.1 evaluation runs on the same series. The 2026-11-05 run gives Dice below 0.90 for all three segments (see Evaluation). Gate G2.1 is not claimed.

## Pinned environment

- 3D Slicer 5.12.4, revision 34645, installed at `I:\Library\3D Slicer 5.12.4` (the path in sim/SOUP.md; the path `C:\Users\salmo\AppData\Local\NA-MIC\Slicer 5.12.4` does not exist on this host)
- Slicer bundles SimpleITK 2.5.5 and VTK, used through Slicer's Python. No additional packages are installed. Both are recorded in the output sidecars. The evaluation uses the same bundled SimpleITK through `bin\PythonSlicer.exe`.

## Scripts

| Script | Role | Reads | Writes |
| --- | --- | --- | --- |
| `run.ps1` | Runs `segment_reference.py` on the CT folder | `data/` CT folder only | `output/<dataset-id>/` segments, sidecars, manifest |
| `segment_reference.py` | Pipeline (Slicer) | CT only | segments |
| `run_reference.ps1` | Runs `export_reference_labels.py` | CT and SEG folders | `output/<dataset-id>/reference/` |
| `export_reference_labels.py` | Exports held-out labelmaps from the SEG object | CT and SEG | `reference/` |
| `run_evaluation.ps1` | Runs `evaluate_g21.py` with Slicer's Python | `output/` segments and `reference/` | `output/<dataset-id>/evaluation.json` |
| `evaluate_g21.py` | Dice, Jaccard, volumes, alignment check | segments and `reference/` | `evaluation.json`, summary table |

## One-command runs

From the repository root:

    powershell -ExecutionPolicy Bypass -File sim\segmentation\run.ps1
    powershell -ExecutionPolicy Bypass -File sim\segmentation\run_reference.ps1
    powershell -ExecutionPolicy Bypass -File sim\segmentation\run_evaluation.ps1

Run order: the pipeline first, then the reference export, then the evaluation. The reference export only needs to run once per dataset. Each runner captures stdout and stderr to `SNDEV\logs\`. `run.ps1` exits non-zero unless the log contains `SURGITWIN_DONE`.

## Holdout of the reference labels

The expert SEG labels are the G2.1 reference. They are kept out of pipeline inputs as follows:

- `select_seg_input.py` (slice 3a) opens the SEG object only to read the `ReferencedSOPInstanceUID` list and the series and study identifiers needed for selection. It writes `output/<dataset-id>/input/` (the SEG-referenced CT files) and `output/<dataset-id>/input_selection.json` (selection provenance). No SEG pixel data, label data, or geometry enters the pipeline or any output other than that provenance file.
- `segment_reference.py` reads only the staged `input/` folder. Before import, it reads every DICOM header in that folder and aborts if any object has Modality SEG. It never opens the SEG object, `input_selection.json`, or `output/<dataset-id>/reference/`.
- `export_reference_labels.py` is the only code that reads SEG label content. It writes `reference/`.
- `evaluate_g21.py` is the only code that reads `reference/`, apart from the export.
- Ruling of 2026-11-05 (document owner): the `select_seg_input.py` SEG read is approved under the constraint above. Any change that lets the pipeline consume SEG content or `reference/` at run time requires a new ruling.
- The reference sidecars carry `is_g21_reference: true` and the holdout statement. The pipeline sidecars and manifest carry `is_g21_reference: false`.

Tuning of thresholds, seeds, and ROI boxes used CT inputs only (CT montage and CT HU statistics). The reference labels were not used to choose a parameter, and no parameter was changed after its Dice reading.

## Dataset

TCIA HCC-TACE-Seg, patient HCC_001. Details, checksums, and licenses are in `data/PROVENANCE.md`.

- CT series `1.3.6.1.4.1.14519.5.2.1.1706.8374.302065206690360709343725942120`, "C-A-P". Two acquisitions share this series UID: acquisition 2 (36 slices, z -415 to -240 mm) and acquisition 1 (30 slices, z -375 to -230 mm). The pipeline input is the 36 SEG-referenced instances (21 acquisition 2 and 15 acquisition 1), selected by `select_seg_input.py`. Before slice 3a, the pipeline used all acquisition 2 files.
- SEG series `1.2.276.0.7230010.3.1.3.8323329.719.1600928570.399942`, one object, SOP instance `1.2.276.0.7230010.3.1.4.8323329.719.1600928570.399943`, with four segments: Liver, Mass, Portal vein, and Abdominal aorta.
- The SEG references 36 CT instances. Their z positions equal the acquisition 2 z set exactly, with the same origin, orientation, and 0.78125 mm pixel spacing. 21 of the referenced instances carry AcquisitionNumber 2 and 15 carry AcquisitionNumber 1, because the two acquisitions overlap in z. At those 15 levels the reference was drawn on different pixel data from the pipeline input. This is a limit on the Dice reading and is recorded in `reference/*_provenance.json`.
- The CT has no contrast phase tags. The phase is inferred from the image as portal venous.

## Pipeline

1. `DICOMUtils.importDicom` imports the CT folder into a temporary Slicer database. `loadPatientByUID` loads the series. The script picks the acquisition with the most slices and records the others as excluded.
2. A segmentation node is created with the selected volume as reference geometry.
3. Three segments are created:
   - `parenchyma_liver`: Segment Editor Threshold, 40 to 200 HU, numpy ROI clip to a liver box, SimpleITK median smoothing (3 mm kernel), and keep-largest-island.
   - `tumor_hypoattenuating`: scripted attempt on the CT. The interior of the parenchyma mask (erosion 10 mm) is thresholded on Gaussian-smoothed HU (sigma 1 mm) at the background liver median minus 30 HU, then opened (1 voxel) and reduced to the largest component. The background median is recorded in the sidecar.
   - `vascular_keepout_bone_excluded`: Segment Editor Threshold, 150 to 300 HU, numpy ROI clip to the aorta and IVC box, bone exclusion (HU at or above 250, largest component, hole fill, 3 mm dilation), SimpleITK dilation by 2 mm, and subtraction of the bone exclusion again.
4. Each segment is exported as a labelmap NRRD and a binary STL. The STL is built with `vtkDiscreteMarchingCubes` on the exported labelmap, transformed to RAS with the node matrix.
5. A provenance JSON is written beside each segment, and `manifest.json` lists all files with SHA-256 hashes, voxel counts, and bounding boxes.

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
- Volumes in mL and voxel counts for both sides.
- Verdict per segment: PASS at Dice 0.90 or higher, otherwise FAIL. The threshold is the proposed G2.1 value in SRS v1.4.0 and is not changed by the script.

Output: `output/<dataset-id>/evaluation.json` and a summary table on stdout.

### Result (2026-11-05 run)

| Segment | Reference | Dice | Jaccard | Pipeline mL | Reference mL | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| parenchyma_liver | reference_liver | 0.6745 | 0.5088 | 1574.36 | 1468.28 | FAIL |
| tumor_hypoattenuating | reference_tumor | 0.0000 | 0.0000 | 0.18 | 35.75 | FAIL |
| vascular_keepout_bone_excluded | reference_vessel | 0.0449 | 0.0230 | 524.53 | 40.48 | FAIL |

The grid alignment check passed for all three pairs. The full run, timings, and warnings are in `SNDEV/docs/impl-2026-11-05-task21-slice2-dice.md`.

## Provenance rules

- Every dataset in `data/` has a checksum and source entry in `data/PROVENANCE.md`. New datasets require the same entry before a run.
- Each per-segment pipeline sidecar records: dataset ID, source note, volume UID (series instance UID), volume node name, shape, spacing, excluded acquisitions, inputs (CT only), the operator (script name and SHA-256), Slicer version and revision, the effect chain with parameters and library versions, output file names, mesh method, triangle count, voxel count, timestamp (UTC), and `is_g21_reference: false`.
- Each reference sidecar records `is_g21_reference: true`, the source SEG SOP instance UID and file SHA-256, the referenced SOP UIDs, and the labelmap SHA-256.
- Outputs are regenerated by the runners. Old outputs are overwritten by the same names, so keep the run logs as the audit record.

## Known limitations

- The organ, vessel, and bone ROI boxes are fixed boxes chosen from one mid-axial slice. They are not anatomical atlases.
- The vessel window (150 to 300 HU) also catches enhancing non-vascular tissue in this portal venous CT. The bone exclusion removed 191254 exclusion voxels but the vessel mask stayed at 171879 voxels. The vessel segment is not a vessel mask.
- The tumor attempt found 59 voxels against a 35.75 mL reference. The method does not reach the lesion at this threshold.
- The reference and the pipeline input differ at 15 of 36 z levels, where the SEG references slices from the other acquisition (see Dataset).
- The Segment Editor Smoothing and Islands effects crashed `SlicerApp-real` in a no-main-window run (seen 2026-11-05). The morphology steps run through SimpleITK instead. The Segment Editor Threshold effect runs normally.
- The organ mesh is about 63 MB of binary STL at 0.78 by 0.78 by 5 mm voxels.
- No lint or typecheck gate exists for `sim/`. The Python scripts were not linted.

## Decisions closed

- Reference dataset for G2.1: TCIA HCC-TACE-Seg, patient HCC_001, with its SEG object as the held-out reference. This follows VAL-030, applied in SRS v1.4.0 (commits 51608bc and d14c481). The Kitware TAIR set was not used. It is cerebrovascular CTA and MRA in NIfTI and has no organ or tumor labels (see the slice 1 log).

## Slice 3 target

If the G2.1 gate keeps its 0.90 threshold, slice 3 targets the three failing segments:

- Parenchyma: boundary and extra-structure check on the CT, with a separation method for organ and vessel that does not use the reference.
- Tumor: a method that reaches the lesion on the portal venous CT, with the lesion located from CT inspection.
- Vascular: a method that separates contrast-enhanced vessels from enhancing parenchyma and bone, for example a tubular filter in a vessel-only ROI or a segment-based selection, in place of the HU window.
