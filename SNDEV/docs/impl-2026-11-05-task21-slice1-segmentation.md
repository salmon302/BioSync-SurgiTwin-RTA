Title: Plan task 2.1 slice 1, DICOM segmentation pipeline on native 3D Slicer
Date: 2026-11-05T15:53:22Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.1 slice 1
Summary: Headless 3D Slicer 5.12.4 pipeline that ingests a DICOM volume and exports labelmaps, meshes, and provenance manifests for three segments.

## Task Reference

Plan task 2.1, slice 1 (about 2 of 5.0 days). Requirement FR-MS-001 in SRS.md. Gate G2.1 is a later slice and is not claimed here.

## Specification Summary

FR-MS-001: the system shall ingest patient-specific volumetric medical imaging (CT/MRI DICOM, including the Kitware TAIR benchmark set) through native Windows 3D Slicer and generate segmented 3D meshes of parenchymal organs (liver/breast), tumors, and vascular keep-out zones.

Slice 1 scope:

1. Acquire a DICOM dataset (TAIR preferred; public smoke sample as fallback), with source, license, and SHA-256 recorded.
2. Headless Slicer 5.12.4 pipeline invoked by one recorded command.
3. Three segments (organ, lesion, vascular keep-out) with a provenance sidecar JSON each.
4. Labelmap and mesh exports plus a manifest JSON under `sim/segmentation/output/<dataset-id>/`.
5. One end-to-end run with stdout and stderr captured to `SNDEV/logs/`.
6. `sim/segmentation/README.md` updated.

Pinned environment (from sim/SOUP.md): 3D Slicer 5.12.4 (revision 34645), installed at `I:\Library\3D Slicer 5.12.4`. The brief suggested `C:\Users\salmo\AppData\Local\NA-MIC\Slicer 5.12.4`, which does not exist on this host. The real path was verified with `Test-Path`, returning True for `I:\Library\3D Slicer 5.12.4\Slicer.exe`.

## Implementation Notes

Path check: `I:\Library\3D Slicer 5.12.4\Slicer.exe` present (2026-11-05). Pre-existing directories `SNDEV/docs` and `SNDEV/logs` present. `sim/segmentation` did not exist before this work and was created.

Dataset search trail (TAIR):

1. Web search for "Kitware TAIR dataset DICOM" returned Arabidopsis TAIR (plant database) results. Not relevant.
2. TAIR resolved to "Testbed for Autonomous Interventions and Robotics", a Kitware-led ARPA-H AIR project (announced 2026-08-06, https://www.kitware.com/kitware-awarded-up-to-17-5-million-arpa-h-contract-to-develop-virtual-testing-platform-for-robot-assisted-stroke-interventions/).
3. Kitware release note 2026-11-04 (https://www.kitware.com/kitware-and-unc-chapel-hill-release-new-imaging-dataset-through-arpa-h-air-program/) and dataset page http://tair.kitware.com/clinical-data.
4. Findings for the TAIR "Multimodal Imaging Dataset for Cerebrovascular Disease":
   - Content: cerebrovascular CTA and MRA (500 studies in the current release), plus X-ray fluoroscopy video (150 datasets, MP4). No liver, breast, or tumor labels.
   - Format: NIfTI for CTA/MRA, not DICOM. FR-MS-001 names DICOM.
   - Size: 70 GB single zip (`s3://multimodal-imaging-for-cerebrovascular-disease/tair-project-data.zip`), public, `--no-sign-request`. The AWS CLI is not installed on this host.
   - License: CC BY 4.0. No credentials required.
   - Page metadata lists "Created" and "Last update" as November 13, 2026, which is later than the current date (2026-11-05). This date is inconsistent and was not resolved.
   - Anatomical models (segmented, centerlined CTA) are announced for December 2026 and are not released yet.
5. Decision: the TAIR set is not used for slice 1. It is not DICOM, it does not carry the organ or tumor content FR-MS-001 needs, and the 70 GB download is outside the slice budget. It remains the candidate for the vascular keep-out work and is the likely source for the G2.1 reference set after the December 2026 annotation release. This should be confirmed with the user.
6. Fallback: Osirix DICOM Image Library (Slicer SampleData cites it for CTA abdomen "Panoramix") requires a Premium membership and forbids redistribution. Rejected.
7. Selected smoke dataset: TCIA HCC-TACE-Seg (DOI 10.7937/TCIA.5FNA-0924), Patient HCC_001. Multiphase contrast CT in DICOM, with liver, tumor, and vessel SEG objects. License CC BY 4.0 (bundled LICENSE file). Citation: Moawad AW, Fuentes D, Morshid A, et al. (2021) Multimodality annotated HCC cases with and without advanced imaging segmentation. The Cancer Imaging Archive. The SEG objects are not used as segmentation input in slice 1 to avoid self-comparison in slice 2.

Download (NBIA REST API, `https://services.cancerimagingarchive.net/nbia-api/services/v1/getImage?SeriesInstanceUID=...`, no authentication, 2026-11-05 UTC session):

| File (under sim/segmentation/data/) | Series | Bytes | SHA-256 |
| --- | --- | --- | --- |
| HCC_001_CT_C-A-P_1.3.6.1.4.1.14519.5.2.1.1706.8374.302065206690360709343725942120.zip | CT "C-A-P", 66 slices, Modality CT | 17780801 | 4B3E47905148EDE21FDE9AD97AD2EE9EF4BB98A2D63EA6D2DB226F82234DD832 |
| HCC_001_SEG_1.2.276.0.7230010.3.1.3.8323329.719.1600928570.399942.zip | SEG, 1 object | 36327 | D1CADD284A15A477C0CACD76E9C9AE239701A7AAC280EC99A0A5B3AD5B220A17 |

Both zips were opened with `System.IO.Compression` and are valid. The CT zip holds 66 DICOM files plus a LICENSE file. The SEG zip holds one DICOM file. The SEG series is the one TCIA documents as referencing CT series `302065...` (the note on HCC_001 in the collection description).

Data layout: the LICENSE files were moved out of the DICOM folders to `sim/segmentation/data/LICENSE-HCC-TACE-Seg-CT.txt` and `LICENSE-HCC-TACE-Seg-SEG.txt`. The first probe showed DCMTK parse errors on the LICENSE file inside the DICOM folder. Dataset record: `sim/segmentation/data/PROVENANCE.md`.

Slicer invocation (path check and run mechanics):

- `Slicer.exe` is a GUI launcher. It returns to the shell before the app exits and writes nothing to a redirected stdout, so `Start-Process -Wait` and `*>` did not capture output.
- Running `SlicerApp-real.exe` directly failed with `STATUS_DLL_NOT_FOUND` (0xC0000135), then fast-failed with 0xC0000409 when `PATH` was adjusted by hand. The supported route is the launcher.
- The working invocation is `cmd /c "Slicer.exe --no-splash --no-main-window --python-script <script> > <log> 2>&1"`. stdout and stderr are both captured, and the shell waits on `SlicerApp-real`.
- Probe scripts: `SNDEV/logs/probe-slicer-2026-11-05.py` (DICOM import) and `SNDEV/logs/probe2-slicer-2026-11-05.py` (mid-slice PNG and Threshold test). Both ran clean. The probe-2 Python exception (`GetOrigin` signature) was fixed in the probe and not in the pipeline.
- Probe 1 wall time was 63 s on cold start.

Probe findings:

- Loaded volumes: `3: C-A-P - acquisitionNumber 2` (36 x 512 x 512, origin z -415.0, spacing 0.78125 x 0.78125 x 5.0 mm) and `3: C-A-P - acquisitionNumber 1` (30 x 512 x 512, origin z -375.0, same spacing). The two acquisitions overlap in z between -375 and -240 mm.
- The acquisition with more slices (acquisition 2) is selected. The choice is deterministic and recorded as excluded in each sidecar. It is not a contrast-phase selection. Phase identity was not checked against DICOM tags in slice 1.
- Probe 2 Threshold 40 to 200 HU on acquisition 2: 1,632,246 voxels before ROI clip.
- Mid-slice (index 18) review: liver on the image left, spleen image right, aorta near pixel (275, 230), vertebral body from about y 250. These coordinates set the ROI boxes in `segment_reference.py`.

Pipeline development (failures and fixes, in order):

1. `Smoothing` Segment Editor effect (MEDIAN, KernelSizeMm) crashed `SlicerApp-real` with exit abnormally and no Python traceback. Replaced with `sitk.BinaryMedian` (SimpleITK 2.5.5 bundled with Slicer).
2. `Islands` effect path replaced with `sitk.ConnectedComponent` and `RelabelComponent` (keep largest).
3. `Margin` effect replaced with `sitk.BinaryDilate`.
4. `slicer.vtkMatrix4x4` does not exist. Fixed to `vtk.vtkMatrix4x4`.
5. `sitk.Version()` returns an object. Fixed to `.VersionString()`.
6. `ExportSegmentsClosedSurfaceRepresentationToFiles` rejected the segment ID argument (needs `vtkStringArray`, and the argument list is not documented in the sources available here). Replaced with `vtkDiscreteMarchingCubes` on the exported labelmap, transformed to RAS, written with `vtkSTLWriter`.
7. `run.ps1` resolved `$Root` one level too shallow and wrote its log to `sim\SNDEV\logs`. That folder was created by the failed run, and it was removed. Fixed to two levels up.
8. `qMRMLSegmentEditorWidget.setMasterVolumeNode` is deprecated in 5.12. Changed to `setSourceVolumeNode`.

Files changed or created in this slice (owned paths only):

- `sim/segmentation/segment_reference.py` (SPDX MIT, pipeline script)
- `sim/segmentation/run.ps1` (SPDX MIT, one-command runner)
- `sim/segmentation/README.md`
- `sim/segmentation/.gitignore` (excludes `data/*` except PROVENANCE and LICENSE, and excludes `output/`)
- `sim/segmentation/data/PROVENANCE.md`
- `sim/segmentation/data/LICENSE-HCC-TACE-Seg-CT.txt`, `sim/segmentation/data/LICENSE-HCC-TACE-Seg-SEG.txt`
- `sim/segmentation/data/HCC_001_CT_C-A-P_<UID>.zip`, its extracted folder, `HCC_001_SEG_<UID>.zip`, and its extracted folder (gitignored)
- `sim/segmentation/output/tcia-hcc-tace-seg-hcc001/` (gitignored, 9 files and manifest)
- `SNDEV/logs/probe-slicer-2026-11-05.py`, `.log`, `probe2-slicer-2026-11-05.py`, `.log`, `probe2-png/` (runtime traces, gitignored by `SNDEV/logs/*`)
- `SNDEV/docs/impl-2026-11-05-task21-slice1-segmentation.md` (this log)

Verification gates (run 2026-11-05):

- End-to-end run: `powershell -ExecutionPolicy Bypass -File sim\segmentation\run.ps1`. Result: PASS. Slicer exit 0. Wall time 8.7 s on warm cache (the 63 s cold probe was the first DICOM index creation). Log: `SNDEV/logs/segment-run-tcia-hcc-tace-seg-hcc001-20261105T161305Z.log`.
- Log contains `SURGITWIN_DONE`, and no `SURGITWIN_FAILED` or traceback.
- Earlier failed run logs (161044Z, 161119Z, 161201Z, 161215Z, 161251Z) are kept in `SNDEV/logs/` as the audit trail of the fixes above.
- Style scan of `sim/segmentation/`: no banned words, no em dashes or en dashes.
- Lint or typecheck: no project Python gate was found in the repo for `sim/`. The script was not linted. This is a gap for the user to decide.

Slicer warnings in the final run log:

- `Unable to enumerate family` for 11 "FONTSPRING DEMO - P22 Mackinac" font families. Benign, a host font issue.
- `qSlicer*Module*::addToolBar: no main window is available`, three lines. Expected under `--no-main-window`.
- `qMRMLSegmentEditorWidget::setMasterVolumeNode is deprecated` (earlier run only, fixed).
- No DCMTK warning in the final run (LICENSE files moved out of the folders).

Manifest summary (`sim/segmentation/output/tcia-hcc-tace-seg-hcc001/manifest.json`, generated 2026-11-05T16:13:11Z, `is_g21_reference` false):

| Segment | Voxels | Bounding box IJK (min to max) | Bounding box RAS mm (min to max) |
| --- | --- | --- | --- |
| parenchyma_liver_smoke | 515885 | (61,88,0) to (229,330,35) | (45.9,-57.8,-415.0) to (177.1,131.3,-240.0) |
| lesion_synthetic | 599 | (134,196,15) to (158,220,18) | (101.4,28.1,-340.0) to (120.1,46.9,-325.0) |
| vascular_keepout_contrast | 183017 | (186,165,0) to (334,252,35) | (-36.1,3.1,-415.0) to (79.5,71.1,-240.0) |

Output files (bytes):

- `parenchyma_liver_smoke_labelmap.nrrd` 168590, `parenchyma_liver_smoke_mesh.stl` 63445284, `parenchyma_liver_smoke_provenance.json` 1934
- `lesion_synthetic_labelmap.nrrd` 9923, `lesion_synthetic_mesh.stl` 131284, `lesion_synthetic_provenance.json` 1559
- `vascular_keepout_contrast_labelmap.nrrd` 46815, `vascular_keepout_contrast_mesh.stl` 10651984, `vascular_keepout_contrast_provenance.json` 1793
- `manifest.json` 3602

Known issues found in the output (recorded, not fixed in slice 1):

- The vascular segment bounding box reaches IJK y 252, which includes the top of the vertebral body. The 150 to 300 HU threshold catches cancellous bone. The vessel segment is a contrast-threshold approximation, not a vessel mask.
- The liver mask volume is about 1.57 L by voxel count (515885 voxels at 3.05 mm^3 per voxel). This is in a plausible range, but it was not checked against a reference.
- The organ ROI box may include other soft-tissue structures at some z levels. Not verified in slice 1.

Decision required from the user (blocker for G2.1, not for slice 1):

- The SRS names TAIR. The released TAIR set is CTA and MRA in NIfTI with no organ or tumor labels. A DICOM liver set with reference labels is needed for the Dice gate. Which dataset should G2.1 use?
- The ingest was run on a TCIA smoke dataset, not TAIR. The SRS requires the reference set for G2.1.

Blockers and gaps (slice 1):

- TAIR not used (see decision above).
- Segment Editor Smoothing and Islands effects crash headless. The workaround is SimpleITK.
- No linter or typecheck gate was found for `sim/`. The Python script was not linted.
- The `.gitignore` in `sim/segmentation/` is a new file in an owned directory. The repo-level `.gitignore` already ignores `SNDEV/logs/*`.
- Nothing was committed, per instruction.
