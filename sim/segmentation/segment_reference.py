# SPDX-License-Identifier: MIT
# Metadata: Author Seth Nenninger (Builder_Int34 Agent); Contribution: plan task 2.1 slices 1 and 2;
# Log: SNDEV/docs/impl-2026-11-05-task21-slice1-segmentation.md, SNDEV/docs/impl-2026-11-05-task21-slice2-dice.md
"""Headless 3D Slicer segmentation pipeline (FR-MS-001, plan task 2.1).

Run through sim/segmentation/run.ps1. Inputs come from environment variables
set by run.ps1: SURGITWIN_DICOM_DIR, SURGITWIN_SERIES_UID, SURGITWIN_DATASET_ID,
SURGITWIN_OUTPUT_ROOT, SURGITWIN_SCRIPT, SURGITWIN_SOURCE_NOTE.

Holdout: the input folder must contain CT only. The script refuses any DICOM object with
Modality SEG, and it never opens the output/<dataset-id>/reference/ folder. The expert SEG
reference labels are read only by export_reference_labels.py (writes reference/) and
evaluate_g21.py (reads reference/).

Segments are the output of a scripted chain on CT inputs. The tumor segment is a
hypoattenuating-region attempt, not a validated lesion detector.
"""

import datetime
import glob
import hashlib
import json
import os

import numpy as np
import pydicom
import SimpleITK as sitk
import slicer
import vtk
from DICOMLib import DICOMUtils

ORGAN = "parenchyma_liver"
TUMOR = "tumor_hypoattenuating"
VESSEL = "vascular_keepout_bone_excluded"

# ROI boxes as fractions of the volume (x = columns, y = rows); z is unrestricted.
# Chosen from the mid-axial slice (pixel coordinates 512 x 512): liver x 60-230, y 90-330;
# aorta and IVC x 190-330, y 170-250, above the vertebral body.
ORGAN_ROI = {"x": (0.12, 0.45), "y": (0.17, 0.65)}
VESSEL_ROI = {"x": (0.37, 0.65), "y": (0.33, 0.49)}

ORGAN_THRESHOLD = (40, 200)
VESSEL_THRESHOLD = (150, 300)
SMOOTH_KERNEL_MM = 3
VESSEL_MARGIN_MM = 2
TUMOR_INTERIOR_MM = 10
TUMOR_SMOOTH_SIGMA_MM = 1.0
TUMOR_DELTA_HU = 30
BONE_HU = 250
BONE_MARGIN_MM = 3


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_ct_only_input(dicom_dir):
    for f in glob.glob(os.path.join(dicom_dir, "*.dcm")):
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        if str(getattr(ds, "Modality", "")) == "SEG":
            raise RuntimeError("Holdout violation: SEG object in pipeline input " + f)


def roi_mask(shape_zyx, roi):
    z, y, x = shape_zyx
    m = np.zeros(shape_zyx, dtype=np.uint8)
    x0, x1 = int(roi["x"][0] * x), int(roi["x"][1] * x)
    y0, y1 = int(roi["y"][0] * y), int(roi["y"][1] * y)
    m[:, y0:y1, x0:x1] = 1
    return m


def ijk_bbox_ras(volume, mask_zyx):
    if not mask_zyx.any():
        return None
    zs, ys, xs = np.nonzero(mask_zyx)
    lo = [int(xs.min()), int(ys.min()), int(zs.min())]
    hi = [int(xs.max()), int(ys.max()), int(zs.max())]
    m = vtk.vtkMatrix4x4()
    volume.GetIJKToRASMatrix(m)
    corners = []
    for cx in (lo[0], hi[0]):
        for cy in (lo[1], hi[1]):
            for cz in (lo[2], hi[2]):
                p = m.MultiplyPoint([cx, cy, cz, 1.0])
                corners.append(p[:3])
    arr = np.array(corners)
    return {
        "ijk_min": lo,
        "ijk_max": hi,
        "ras_min_mm": [round(float(v), 3) for v in arr.min(axis=0)],
        "ras_max_mm": [round(float(v), 3) for v in arr.max(axis=0)],
    }


def apply_effect(widget, node, seg_id, effect_name, params):
    print("STAGE effect", effect_name, flush=True)
    widget.setActiveEffectByName(effect_name)
    eff = widget.activeEffect()
    for k, v in params.items():
        eff.setParameter(k, str(v))
    eff.self().onApply()
    print("STAGE done", effect_name, flush=True)
    return {"effect": effect_name, "parameters": params}


def voxel_radius(mm, spacing_xyz):
    return [max(0, int(round(mm / s))) for s in spacing_xyz]


def sitk_median(array_zyx, mm, spacing_xyz):
    img = sitk.GetImageFromArray(array_zyx.astype(np.uint8))
    out = sitk.BinaryMedian(img, voxel_radius(mm, spacing_xyz))
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_keep_largest(array_zyx):
    img = sitk.GetImageFromArray(array_zyx.astype(np.uint8))
    cc = sitk.RelabelComponent(sitk.ConnectedComponent(img), sortByObjectSize=True)
    return sitk.GetArrayFromImage(cc == 1).astype(np.uint8)


def sitk_dilate(array_zyx, mm, spacing_xyz):
    img = sitk.GetImageFromArray(array_zyx.astype(np.uint8))
    out = sitk.BinaryDilate(img, voxel_radius(mm, spacing_xyz))
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_erode(array_zyx, mm, spacing_xyz):
    img = sitk.GetImageFromArray(array_zyx.astype(np.uint8))
    out = sitk.BinaryErode(img, voxel_radius(mm, spacing_xyz))
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_fill_holes(array_zyx):
    img = sitk.GetImageFromArray(array_zyx.astype(np.uint8))
    out = sitk.BinaryFillhole(img)
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_open_1vox(array_zyx):
    img = sitk.GetImageFromArray(array_zyx.astype(np.uint8))
    out = sitk.BinaryMorphologicalOpening(img, [1, 1, 1])
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_smooth_hu(hu_zyx, sigma_mm, spacing_xyz):
    img = sitk.GetImageFromArray(hu_zyx.astype(np.float32))
    img.SetSpacing(spacing_xyz)
    out = sitk.SmoothingRecursiveGaussian(img, sigma_mm)
    return sitk.GetArrayFromImage(out)


def write_array_to_segment(array_zyx, seg_node, seg_id, volume):
    slicer.util.updateSegmentBinaryLabelmapFromArray(array_zyx.astype(np.uint8), seg_node, seg_id, volume)


def export_labelmap(seg_node, seg_id, volume, path):
    arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, seg_id, volume).astype(np.uint8)
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "tmp_" + seg_id)
    node.CopyOrientation(volume)
    node.SetOrigin(volume.GetOrigin())
    node.SetSpacing(volume.GetSpacing())
    slicer.util.updateVolumeFromArray(node, arr)
    node.CopyOrientation(volume)
    slicer.util.saveNode(node, path)
    return arr, node


def export_mesh(label_node, path):
    mc = vtk.vtkDiscreteMarchingCubes()
    mc.SetInputData(label_node.GetImageData())
    mc.SetValue(0, 1)
    mc.Update()
    m = vtk.vtkMatrix4x4()
    label_node.GetIJKToRASMatrix(m)
    tf = vtk.vtkTransform()
    tf.SetMatrix(m)
    tpd = vtk.vtkTransformPolyDataFilter()
    tpd.SetInputConnection(mc.GetOutputPort())
    tpd.SetTransform(tf)
    tpd.Update()
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(path)
    writer.SetFileTypeToBinary()
    writer.SetInputConnection(tpd.GetOutputPort())
    writer.Write()
    return int(tpd.GetOutput().GetNumberOfCells())


def main():
    dicom_dir = os.environ["SURGITWIN_DICOM_DIR"]
    series_uid = os.environ["SURGITWIN_SERIES_UID"]
    dataset_id = os.environ["SURGITWIN_DATASET_ID"]
    out_root = os.environ["SURGITWIN_OUTPUT_ROOT"]
    script_path = os.environ["SURGITWIN_SCRIPT"]
    source_note = os.environ.get("SURGITWIN_SOURCE_NOTE", "")

    assert_ct_only_input(dicom_dir)

    out_dir = os.path.join(out_root, dataset_id)
    os.makedirs(out_dir, exist_ok=True)
    operator = {
        "script": os.path.basename(script_path),
        "script_sha256": sha256_file(script_path),
        "slicer_version": slicer.app.applicationVersion,
        "slicer_revision": slicer.app.repositoryRevision,
    }
    sitk_version = sitk.Version().VersionString()

    with DICOMUtils.TemporaryDICOMDatabase() as db:
        DICOMUtils.importDicom(dicom_dir, db)
        loaded_ids = DICOMUtils.loadPatientByUID(db.patients()[0])
    volumes = [slicer.mrmlScene.GetNodeByID(i) for i in loaded_ids]
    volumes = [v for v in volumes if v is not None and v.IsA("vtkMRMLScalarVolumeNode")]
    if not volumes:
        raise RuntimeError("No scalar volume loaded from " + dicom_dir)
    candidates = sorted(volumes, key=lambda v: -slicer.util.arrayFromVolume(v).shape[0])
    vol = candidates[0]
    excluded = [{"name": v.GetName(), "reason": "fewer slices than selected acquisition"} for v in candidates[1:]]
    arr = slicer.util.arrayFromVolume(vol)
    hu = arr.astype(np.float32)
    shape = arr.shape
    spacing = vol.GetSpacing()

    seg_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "SurgiTwin_" + dataset_id)
    seg_node.CreateDefaultDisplayNodes()
    seg_node.SetReferenceImageGeometryParameterFromVolumeNode(vol)
    editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    widget = slicer.qMRMLSegmentEditorWidget()
    widget.setMRMLScene(slicer.mrmlScene)
    widget.setMRMLSegmentEditorNode(editor_node)
    widget.setSegmentationNode(seg_node)
    widget.setSourceVolumeNode(vol)

    segs = {}
    for name in (ORGAN, TUMOR, VESSEL):
        seg_id = seg_node.GetSegmentation().AddEmptySegment("")
        seg_node.GetSegmentation().GetSegment(seg_id).SetName(name)
        segs[name] = seg_id

    chains = {name: [] for name in segs}

    # Parenchyma: threshold, ROI clip, median smoothing, keep largest island.
    organ_id = segs[ORGAN]
    editor_node.SetSelectedSegmentID(organ_id)
    chains[ORGAN].append(apply_effect(widget, seg_node, organ_id, "Threshold",
                                      {"MinimumThreshold": ORGAN_THRESHOLD[0], "MaximumThreshold": ORGAN_THRESHOLD[1]}))
    organ_roi = roi_mask(shape, ORGAN_ROI)
    clipped = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, organ_id, vol) * organ_roi
    write_array_to_segment(clipped, seg_node, organ_id, vol)
    chains[ORGAN].append({"effect": "ROI_clip_numpy", "parameters": {"x_fraction": ORGAN_ROI["x"], "y_fraction": ORGAN_ROI["y"]}})
    organ_arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, organ_id, vol)
    organ_arr = sitk_median(organ_arr, SMOOTH_KERNEL_MM, spacing)
    chains[ORGAN].append({"effect": "sitk.BinaryMedian", "parameters": {"kernel_mm": SMOOTH_KERNEL_MM,
                          "radius_voxels_xyz": voxel_radius(SMOOTH_KERNEL_MM, spacing)}, "library": "SimpleITK " + sitk_version})
    organ_arr = sitk_keep_largest(organ_arr)
    chains[ORGAN].append({"effect": "sitk.ConnectedComponent+RelabelComponent keep largest", "parameters": {}, "library": "SimpleITK " + sitk_version})
    write_array_to_segment(organ_arr, seg_node, organ_id, vol)

    # Tumor attempt: hypoattenuating region inside the eroded parenchyma mask, relative to background liver.
    tumor_id = segs[TUMOR]
    liver_median = float(np.median(hu[organ_arr > 0]))
    interior = sitk_erode(organ_arr, TUMOR_INTERIOR_MM, spacing)
    smooth = sitk_smooth_hu(hu, TUMOR_SMOOTH_SIGMA_MM, spacing)
    cand = ((smooth <= liver_median - TUMOR_DELTA_HU) & (interior > 0)).astype(np.uint8)
    cand = sitk_open_1vox(cand)
    tumor_arr = sitk_keep_largest(cand)
    write_array_to_segment(tumor_arr, seg_node, tumor_id, vol)
    chains[TUMOR].append({
        "effect": "sitk.BinaryErode of parenchyma mask",
        "parameters": {"radius_mm": TUMOR_INTERIOR_MM, "radius_voxels_xyz": voxel_radius(TUMOR_INTERIOR_MM, spacing)},
        "library": "SimpleITK " + sitk_version,
    })
    chains[TUMOR].append({
        "effect": "numpy background median and threshold on Gaussian-smoothed HU",
        "parameters": {"background_median_HU_parenchyma": round(liver_median, 2), "delta_HU": TUMOR_DELTA_HU,
                       "upper_bound_HU": round(liver_median - TUMOR_DELTA_HU, 2), "gaussian_sigma_mm": TUMOR_SMOOTH_SIGMA_MM},
        "library": "SimpleITK " + sitk_version,
    })
    chains[TUMOR].append({"effect": "sitk.BinaryMorphologicalOpening", "parameters": {"radius_voxels": 1}, "library": "SimpleITK " + sitk_version})
    chains[TUMOR].append({"effect": "sitk.ConnectedComponent+RelabelComponent keep largest", "parameters": {}, "library": "SimpleITK " + sitk_version})

    # Vessel: threshold, ROI clip, vertebral and cortical bone exclusion, margin.
    vessel_id = segs[VESSEL]
    editor_node.SetSelectedSegmentID(vessel_id)
    chains[VESSEL].append(apply_effect(widget, seg_node, vessel_id, "Threshold",
                                       {"MinimumThreshold": VESSEL_THRESHOLD[0], "MaximumThreshold": VESSEL_THRESHOLD[1]}))
    vessel_roi = roi_mask(shape, VESSEL_ROI)
    vclip = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, vessel_id, vol) * vessel_roi
    chains[VESSEL].append({"effect": "ROI_clip_numpy", "parameters": {"x_fraction": VESSEL_ROI["x"], "y_fraction": VESSEL_ROI["y"]}})
    bone_core = sitk_keep_largest((hu >= BONE_HU).astype(np.uint8))
    bone_filled = sitk_fill_holes(bone_core)
    bone_excl = sitk_dilate(bone_filled, BONE_MARGIN_MM, spacing)
    chains[VESSEL].append({
        "effect": "bone exclusion: HU >= BONE_HU, keep largest component, fill holes, dilate",
        "parameters": {"bone_HU": BONE_HU, "dilate_mm": BONE_MARGIN_MM, "bone_core_voxels": int(bone_core.sum()),
                       "exclusion_voxels": int(bone_excl.sum())},
        "library": "SimpleITK " + sitk_version,
    })
    vclip = vclip * (1 - bone_excl)
    write_array_to_segment(vclip, seg_node, vessel_id, vol)
    vdil = sitk_dilate(slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, vessel_id, vol), VESSEL_MARGIN_MM, spacing)
    vdil = vdil * (1 - bone_excl)
    write_array_to_segment(vdil, seg_node, vessel_id, vol)
    chains[VESSEL].append({"effect": "sitk.BinaryDilate", "parameters": {"margin_mm": VESSEL_MARGIN_MM,
                           "radius_voxels_xyz": voxel_radius(VESSEL_MARGIN_MM, spacing)}, "library": "SimpleITK " + sitk_version})
    chains[VESSEL].append({"effect": "subtract bone exclusion after dilation", "parameters": {}, "library": "SimpleITK " + sitk_version})

    files = []
    segment_records = []
    prov_common = {
        "dataset_id": dataset_id,
        "source_note": source_note,
        "volume_uid": series_uid,
        "volume_node_name": vol.GetName(),
        "volume_shape_zyx": list(shape),
        "volume_spacing_mm": [round(float(s), 5) for s in vol.GetSpacing()],
        "excluded_acquisitions": excluded,
        "inputs": "CT only (SEG refused by assert_ct_only_input)",
        "operator": operator,
    }
    stamp = utc_now()
    for name, seg_id in segs.items():
        base = os.path.join(out_dir, name)
        label_path = base + "_labelmap.nrrd"
        mesh_path = base + "_mesh.stl"
        arr_seg, label_node = export_labelmap(seg_node, seg_id, vol, label_path)
        mesh_cells = export_mesh(label_node, mesh_path)
        slicer.mrmlScene.RemoveNode(label_node)
        voxels = int(arr_seg.sum())
        bbox = ijk_bbox_ras(vol, arr_seg)
        prov = dict(prov_common)
        prov.update({
            "segment_name": name,
            "timestamp_utc": stamp,
            "effect_chain": chains[name],
            "outputs": [os.path.basename(label_path), os.path.basename(mesh_path)],
            "mesh_method": "vtkDiscreteMarchingCubes on exported labelmap, transformed to RAS",
            "mesh_triangles": mesh_cells,
            "voxel_count": voxels,
            "is_g21_reference": False,
        })
        with open(base + "_provenance.json", "w", encoding="utf-8") as f:
            json.dump(prov, f, indent=2)
        for p in (label_path, mesh_path, base + "_provenance.json"):
            files.append({"file": os.path.basename(p), "bytes": os.path.getsize(p) if os.path.exists(p) else 0,
                          "sha256": sha256_file(p) if os.path.exists(p) else None})
        segment_records.append({"segment": name, "voxel_count": voxels, "bounding_box": bbox})

    manifest = {
        "dataset_id": dataset_id,
        "generated_utc": stamp,
        "is_g21_reference": False,
        "source_note": source_note,
        "volume_uid": series_uid,
        "volume_node_name": vol.GetName(),
        "operator": operator,
        "segments": segment_records,
        "files": files,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("SURGITWIN_DONE manifest=" + os.path.join(out_dir, "manifest.json"))


try:
    main()
except Exception as exc:
    import traceback
    traceback.print_exc()
    print("SURGITWIN_FAILED " + str(exc))
    slicer.app.exit(1)
else:
    slicer.app.exit(0)
