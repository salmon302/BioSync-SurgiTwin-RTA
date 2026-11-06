# SPDX-License-Identifier: MIT
# Metadata: Author Seth Nenninger (MiMo-V2.6-Pro Agent); Contribution: plan task 2.1 slices 1 to 4;
# Log: SNDEV/docs/impl-2026-11-05-task21-slice1-segmentation.md, SNDEV/docs/impl-2026-11-05-task21-slice2-dice.md,
# SNDEV/docs/impl-2026-11-05-task21-slice3-method.md, SNDEV/docs/impl-2026-11-05-task21-slice4-method.md
"""Headless 3D Slicer segmentation pipeline (FR-MS-001, plan task 2.1).

Run through sim/segmentation/run.ps1. Inputs come from environment variables
set by run.ps1: SURGITWIN_DICOM_DIR, SURGITWIN_SERIES_UID, SURGITWIN_DATASET_ID,
SURGITWIN_OUTPUT_ROOT, SURGITWIN_SCRIPT, SURGITWIN_SOURCE_NOTE.

Holdout: the input folder must contain CT only. The script refuses any DICOM object with
Modality SEG, and it never opens the output/<dataset-id>/reference/ folder. The expert SEG
reference labels are read only by export_reference_labels.py (writes reference/) and
evaluate_g21.py (reads reference/).

Segments are the output of a scripted chain on CT inputs. Each structure has selectable method
variants: SURGITWIN_LIVER_VARIANT, SURGITWIN_TUMOR_VARIANT, SURGITWIN_VESSEL_VARIANT (v0, v1, v2;
default is the final chain recorded in the slice-4 log). Variant v0 is the slice-2 chain. The
tumor segment is a documented detection attempt, not a validated lesion detector: for HCC_001 no
lesion is confirmed by CT inspection and the segment is empty (see the slice-4 log).
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
# aorta and IVC x 190-330, y 170-250, above the vertebral body. (Variant v0 only.)
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

# Slice-4 constants. HU measurements from CT inspection (SNDEV/logs/probe9b-phase-hu-2026-11-05.json):
# acquisition 1 is late arterial (liver 54 to 74 HU, aorta 225 HU, portal vein 113 HU),
# acquisition 2 is portal venous (liver 94 to 139 HU, aorta 163 HU, portal vein 189 HU).
LIVER_BOUNDS = {1: (50.0, 95.0), 2: (80.0, 150.0)}
BRIGHT_BOUNDS_V1 = {1: (85.0, 285.0), 2: (140.0, 285.0)}
BRIGHT_BOUNDS_V2 = {1: (100.0, 285.0), 2: (150.0, 285.0)}
BRIGHT_BOUNDS_V3 = {1: (85.0, 285.0), 2: (125.0, 285.0)}
BRIGHT_BOUNDS_V4 = {1: (78.0, 285.0), 2: (125.0, 285.0)}
BRIGHT_BOUNDS_V5 = {1: (85.0, 285.0), 2: (145.0, 285.0)}
VESSEL_SIGMAS_MM = (1.5, 3.0, 6.0)
VESSEL_SIGMAS_V3_MM = (0.75, 1.5, 3.0, 6.0)
VESSEL_SIGMAS_V4_MM = (1.2, 2.0, 3.0, 6.0)
VESSEL_BETA = 0.5
VESSEL_C = 6.0
VESSEL_S_FLOOR = 4.0
VESSEL_S_FLOOR_V4 = 5.0
VESSEL_T = {"v1": 0.5, "v2": 0.6, "v3": 0.35, "v4": 0.5, "v5": 0.6}
LIVER_OPEN_MM = {"v1": 3.0, "v2": 2.0, "v3": 2.0}
LIVER_CLOSE_MM = 3.0
LIVER_ROI = {"x": (30, 350), "y": (50, 350)}
LIVER_Z_MM = {"v1": (-390.0, -238.0), "v2": (-390.0, -238.0), "v3": (-416.0, -238.0)}
LIVER_DILATE_FOR_VESSEL_MM = 8.0
AORTA_BOX = {"x": (235, 335), "y": (170, 300)}
# Slice-5 corridors (seed-subtree selection). The aorta corridor (x 250 to 305, y 195 to 285) follows
# the visible aorta axis and cuts the renal, mesenteric, and lumbar branches at 2 to 3 cm from it
# (evaluation-side geometry: the SEG aorta label bbox is x 261 to 297, y 222 to 275). The portal
# subtree is confined to the liver zone, which cuts the SMV below the liver.
AORTA_CORRIDOR = {"x": (250, 305), "y": (195, 285)}
PORTAL_ZONE_DILATE_MM = 8.0
# Kidney ROIs (CT inspection, probe14b and probe11 overlays): the renal arteries connect the aorta
# tree to the kidney vasculature, so the kidneys are excluded from the vessel candidate (v2).
KIDNEY_BOXES = ({"x": (115, 245), "y": (255, 380)}, {"x": (325, 445), "y": (240, 355)})
VESSEL_DILATE_MM = {"v1": 2.0, "v2": 1.0, "v3": 1.0, "v4": 1.0, "v5": 1.0}
VESSEL_CORE_ERODE_MM = 1.5
KEEP_OUT_MARGIN_MM = 1.0
VESSEL_PROTECT_MM = 3.0
SMALL_HOLE_MAX_VOXELS = 100
TUMOR_DELTA_HU_V1 = 15.0
TUMOR_MIN_ML = 2.0
TUMOR_MAX_ML = 150.0
TUMOR_INTERIOR_MM_V1 = 8.0
SPINE_FILL_MIN_VOXELS = 20000

# Seeds from CT inspection of the staged input (slice index k, row y, column x; z = -415 + 5*k mm).
# Liver seeds are verified parenchyma points (probe9b and probe16 renders); vessel seeds are the
# aorta lumen (round prevertebral structure, calcified wall visible on acquisition 2) and the main
# portal vein (rounded contrast-filled structure at the porta, 189 HU on acquisition 2).
LIVER_SEEDS_V1 = [(19, 195, 135), (23, 195, 135), (13, 195, 135)]
LIVER_SEEDS_V2 = LIVER_SEEDS_V1 + [(25, 195, 135), (19, 115, 240), (23, 115, 240)]
AORTA_SEEDS = [(19, 224, 271), (23, 232, 272)]
PORTAL_SEEDS = [(23, 215, 228), (19, 215, 228)]

# Tumor focus confirmation from CT inspection. A focus enters the tumor segment only when it is
# confirmed on CT by the recorded inspection. For HCC_001 no focus is confirmed on either
# acquisition (see SNDEV/docs/impl-2026-11-05-task21-slice4-method.md), so the segment is empty.
TUMOR_CONFIRMED_FOCUS = None

LIVER_VARIANT = os.environ.get("SURGITWIN_LIVER_VARIANT", "v3")
TUMOR_VARIANT = os.environ.get("SURGITWIN_TUMOR_VARIANT", "v1")
VESSEL_VARIANT = os.environ.get("SURGITWIN_VESSEL_VARIANT", "v5")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_ct_only_input(dicom_dir):
    entries = []
    for f in glob.glob(os.path.join(dicom_dir, "*.dcm")):
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        if str(getattr(ds, "Modality", "")) == "SEG":
            raise RuntimeError("Holdout violation: SEG object in pipeline input " + f)
        entries.append((float(ds.ImagePositionPatient[2]), int(ds.AcquisitionNumber)))
    entries.sort()
    return entries


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


def sitk_img(array_zyx, spacing_xyz, dtype=np.uint8):
    img = sitk.GetImageFromArray(array_zyx.astype(dtype))
    img.SetSpacing(spacing_xyz)
    return img


def sitk_arr(img):
    return sitk.GetArrayFromImage(img).astype(np.float32)


def sitk_median(array_zyx, mm, spacing_xyz):
    img = sitk_img(array_zyx, spacing_xyz)
    out = sitk.BinaryMedian(img, voxel_radius(mm, spacing_xyz))
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_keep_largest(array_zyx):
    img = sitk_img(array_zyx, spacing_xyz=(1.0, 1.0, 1.0))
    cc = sitk.RelabelComponent(sitk.ConnectedComponent(img), sortByObjectSize=True)
    return sitk.GetArrayFromImage(cc == 1).astype(np.uint8)


def sitk_dilate(array_zyx, mm, spacing_xyz):
    img = sitk_img(array_zyx, spacing_xyz)
    out = sitk.BinaryDilate(img, voxel_radius(mm, spacing_xyz))
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_erode(array_zyx, mm, spacing_xyz):
    img = sitk_img(array_zyx, spacing_xyz)
    out = sitk.BinaryErode(img, voxel_radius(mm, spacing_xyz))
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_open(array_zyx, mm, spacing_xyz):
    img = sitk_img(array_zyx, spacing_xyz)
    out = sitk.BinaryMorphologicalOpening(img, voxel_radius(mm, spacing_xyz))
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_close(array_zyx, mm, spacing_xyz):
    img = sitk_img(array_zyx, spacing_xyz)
    out = sitk.BinaryMorphologicalClosing(img, voxel_radius(mm, spacing_xyz))
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_fill_holes(array_zyx):
    img = sitk_img(array_zyx, spacing_xyz=(1.0, 1.0, 1.0))
    out = sitk.BinaryFillhole(img)
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_fill_small_holes(array_zyx, max_voxels):
    """Fill only enclosed holes of at most max_voxels voxels (big holes stay open)."""
    filled = sitk_fill_holes(array_zyx)
    holes = ((filled > 0) & (array_zyx == 0)).astype(np.uint8)
    if not holes.any():
        return array_zyx.astype(np.uint8)
    cc = sitk.GetArrayFromImage(sitk.ConnectedComponent(sitk_img(holes, (1.0, 1.0, 1.0))))
    counts = np.bincount(cc.ravel())
    small = np.zeros(cc.shape, dtype=np.uint8)
    for lbl in range(1, len(counts)):
        if counts[lbl] <= max_voxels:
            small[cc == lbl] = 1
    return ((array_zyx > 0) | (small > 0)).astype(np.uint8)


def sitk_open_1vox(array_zyx):
    img = sitk_img(array_zyx, spacing_xyz=(1.0, 1.0, 1.0))
    out = sitk.BinaryMorphologicalOpening(img, [1, 1, 1])
    return sitk.GetArrayFromImage(out).astype(np.uint8)


def sitk_smooth_hu(hu_zyx, sigma_mm, spacing_xyz):
    img = sitk_img(hu_zyx, spacing_xyz, dtype=np.float32)
    out = sitk.SmoothingRecursiveGaussian(img, sigma_mm)
    return sitk.GetArrayFromImage(out)


def keep_seed_components(cand_zyx, seeds, spacing_xyz):
    """Keep connected components that overlap the seed patches (15 x 15 in-plane) by 5 or more voxels."""
    shape = cand_zyx.shape
    seed_mask = np.zeros(shape, dtype=bool)
    for k, y, x in seeds:
        seed_mask[k, y - 7:y + 8, x - 7:x + 8] = True
    filt = sitk.ConnectedComponentImageFilter()
    filt.SetFullyConnected(True)
    cc = filt.Execute(sitk_img(cand_zyx, spacing_xyz))
    arr = sitk.GetArrayFromImage(cc)
    kept = {}
    for lbl in np.unique(arr[seed_mask & (arr > 0)]):
        c = int(((arr == lbl) & seed_mask).sum())
        if c >= 5:
            kept[int(lbl)] = c
    out = np.isin(arr, list(kept)) if kept else np.zeros(shape, dtype=np.uint8)
    return out.astype(np.uint8), kept


def hessian_components(hu_zyx, sigma_mm, spacing_xyz):
    """Physical-unit Hessian of the Gaussian-smoothed volume (HU/mm^2), 6 unique components."""
    img = sitk_img(hu_zyx, spacing_xyz, dtype=np.float32)
    comps = {}
    for a, b, key in ((0, 0, "xx"), (1, 1, "yy"), (2, 2, "zz"), (0, 1, "xy"), (0, 2, "xz"), (1, 2, "yz")):
        cur = img
        for axis in (0, 1, 2):
            rg = sitk.RecursiveGaussianImageFilter()
            rg.SetSigma(sigma_mm)
            rg.SetDirection(axis)
            if axis == a and axis == b:
                rg.SetOrder(sitk.RecursiveGaussianImageFilter.SecondOrder)
            elif axis == a or axis == b:
                rg.SetOrder(sitk.RecursiveGaussianImageFilter.FirstOrder)
            else:
                rg.SetOrder(sitk.RecursiveGaussianImageFilter.ZeroOrder)
            cur = rg.Execute(cur)
        comps[key] = sitk_arr(cur) / (spacing_xyz[a] * spacing_xyz[b])
    return comps


def vesselness_scale(hu_zyx, sigma_mm, spacing_xyz, s_floor=VESSEL_S_FLOOR):
    """Frangi bright-tube vesselness at one scale on scale-normalized eigenvalues (HU)."""
    c = hessian_components(hu_zyx, sigma_mm, spacing_xyz)
    n = c["xx"].size
    h = np.empty((n, 3, 3), dtype=np.float32)
    s2 = sigma_mm * sigma_mm
    h[:, 0, 0] = c["xx"].ravel() * s2
    h[:, 1, 1] = c["yy"].ravel() * s2
    h[:, 2, 2] = c["zz"].ravel() * s2
    h[:, 0, 1] = h[:, 1, 0] = c["xy"].ravel() * s2
    h[:, 0, 2] = h[:, 2, 0] = c["xz"].ravel() * s2
    h[:, 1, 2] = h[:, 2, 1] = c["yz"].ravel() * s2
    lam = np.linalg.eigvalsh(h)
    del h
    order = np.argsort(np.abs(lam), axis=1)
    l1 = np.take_along_axis(lam, order[:, :1], axis=1).ravel()
    l2 = np.take_along_axis(lam, order[:, 1:2], axis=1).ravel()
    l3 = np.take_along_axis(lam, order[:, 2:3], axis=1).ravel()
    del lam, order
    s_norm = np.sqrt(l1 * l1 + l2 * l2 + l3 * l3)
    with np.errstate(divide="ignore", invalid="ignore"):
        rb = np.abs(l1) / np.sqrt(np.abs(l2 * l3))
        v = np.exp(-(rb * rb) / (2.0 * VESSEL_BETA * VESSEL_BETA)) * (
            1.0 - np.exp(-(s_norm * s_norm) / (2.0 * VESSEL_C * VESSEL_C)))
    v = np.where((l2 < 0.0) & (l3 < 0.0) & (s_norm >= s_floor), v, 0.0)
    return v.reshape(c["xx"].shape)


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


def chain_vessel_v0(widget, seg_node, vessel_id, vol, hu, shape, spacing, bone_excl_v0):
    chains = []
    editor_node = widget.mrmlSegmentEditorNode()
    editor_node.SetSelectedSegmentID(vessel_id)
    chains.append(apply_effect(widget, seg_node, vessel_id, "Threshold",
                               {"MinimumThreshold": VESSEL_THRESHOLD[0], "MaximumThreshold": VESSEL_THRESHOLD[1]}))
    vessel_roi = roi_mask(shape, VESSEL_ROI)
    vclip = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, vessel_id, vol) * vessel_roi
    chains.append({"effect": "ROI_clip_numpy", "parameters": {"x_fraction": VESSEL_ROI["x"], "y_fraction": VESSEL_ROI["y"]}})
    vclip = vclip * (1 - bone_excl_v0)
    write_array_to_segment(vclip, seg_node, vessel_id, vol)
    vdil = sitk_dilate(slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, vessel_id, vol), VESSEL_MARGIN_MM, spacing)
    vdil = vdil * (1 - bone_excl_v0)
    write_array_to_segment(vdil, seg_node, vessel_id, vol)
    chains.append({"effect": "sitk.BinaryDilate", "parameters": {"margin_mm": VESSEL_MARGIN_MM,
                   "radius_voxels_xyz": voxel_radius(VESSEL_MARGIN_MM, spacing)}, "library": "SimpleITK " + sitk.Version().VersionString()})
    chains.append({"effect": "subtract bone exclusion after dilation", "parameters": {}})
    return chains


def chain_vessel_v1(hu, sm, acq_by_slice, spacing, liver, variant):
    """Seeded vessel growth: phase-aware brightness, multi-scale Frangi vesselness, seed components.

    Variant v3 applies seed-subtree selection: the aorta subtree is confined to the aorta corridor
    (the renal, mesenteric, and lumbar branches leave it within 2 to 3 cm of the axis) and the portal
    subtree to the liver zone (the SMV leaves it below the liver). Variant v3 also uses the smaller
    vesselness scales for 2 to 4 mm branches and a lower vesselness threshold.
    """
    sitk_version = sitk.Version().VersionString()
    chains = []
    bounds = {"v1": BRIGHT_BOUNDS_V1, "v2": BRIGHT_BOUNDS_V2, "v3": BRIGHT_BOUNDS_V3, "v4": BRIGHT_BOUNDS_V4,
              "v5": BRIGHT_BOUNDS_V5}[variant]
    bright = np.zeros(hu.shape, dtype=np.uint8)
    for k in range(hu.shape[0]):
        lo, hi = bounds[int(acq_by_slice[k])]
        bright[k] = ((sm[k] >= lo) & (sm[k] <= hi)).astype(np.uint8)
    chains.append({"effect": "phase-aware brightness on HU smoothed with sigma 1 mm",
                   "parameters": {"bounds_by_acquisition": {str(a): list(b) for a, b in bounds.items()},
                                  "phase_note": "acquisition 1 late arterial, acquisition 2 portal venous (probe9b HU measurements)"},
                   "library": "SimpleITK " + sitk_version})
    sigmas = {"v3": VESSEL_SIGMAS_V3_MM, "v4": VESSEL_SIGMAS_V4_MM}.get(variant, VESSEL_SIGMAS_MM)
    s_floor = VESSEL_S_FLOOR_V4 if variant in ("v4", "v5") else VESSEL_S_FLOOR
    vness = np.zeros(hu.shape, dtype=np.float32)
    for sigma in sigmas:
        vness = np.maximum(vness, vesselness_scale(hu, sigma, spacing, s_floor))
    chains.append({"effect": "multi-scale Frangi bright-tube vesselness (max over scales), seed-connected components",
                   "parameters": {"sigmas_mm": list(sigmas), "beta": VESSEL_BETA, "c_hu": VESSEL_C,
                                  "s_floor_hu": s_floor, "threshold": VESSEL_T[variant],
                                  "aorta_seeds": AORTA_SEEDS, "portal_seeds": PORTAL_SEEDS},
                   "library": "SimpleITK " + sitk_version + " + numpy " + np.__version__})
    if variant in ("v3", "v4", "v5"):
        aorta_zone = np.zeros(hu.shape, dtype=bool)
        aorta_zone[:, AORTA_CORRIDOR["y"][0]:AORTA_CORRIDOR["y"][1], AORTA_CORRIDOR["x"][0]:AORTA_CORRIDOR["x"][1]] = True
        portal_zone = (sitk_dilate(liver, PORTAL_ZONE_DILATE_MM, spacing) > 0)
        vregion = aorta_zone | portal_zone
    else:
        vregion = np.zeros(hu.shape, dtype=np.uint8)
        vregion[:, AORTA_BOX["y"][0]:AORTA_BOX["y"][1], AORTA_BOX["x"][0]:AORTA_BOX["x"][1]] = 1
        liver_zone = sitk_dilate(liver, LIVER_DILATE_FOR_VESSEL_MM, spacing)
        vregion = ((vregion | liver_zone) > 0)
        aorta_zone = vregion
        portal_zone = vregion
    if variant == "v2":
        spine = np.zeros(hu.shape, dtype=np.uint8)
        cc_img = sitk.ConnectedComponent(sitk_img((hu >= BONE_HU).astype(np.uint8), spacing))
        cc = sitk.GetArrayFromImage(cc_img)
        stats = sitk.LabelShapeStatisticsImageFilter()
        stats.Execute(cc_img)
        big = [int(l) for l in stats.GetLabels() if stats.GetPhysicalSize(l) / float(np.prod(spacing)) >= SPINE_FILL_MIN_VOXELS]
        for lbl in big:
            spine = np.maximum(spine, sitk_fill_holes((cc == lbl).astype(np.uint8)))
        spine_excl = sitk_dilate(spine, BONE_MARGIN_MM, spacing)
    else:
        spine_excl = np.zeros(hu.shape, dtype=np.uint8)
    vcand = ((bright > 0) & (vness >= VESSEL_T[variant]) & vregion & (spine_excl == 0)).astype(np.uint8)
    if variant == "v2":
        kidney = np.zeros(hu.shape, dtype=np.uint8)
        for box in KIDNEY_BOXES:
            kidney[:, box["y"][0]:box["y"][1], box["x"][0]:box["x"][1]] = 1
        vcand = (vcand * (1 - kidney)).astype(np.uint8)
    if variant in ("v3", "v4", "v5"):
        aorta_core, aorta_kept = keep_seed_components((vcand & aorta_zone).astype(np.uint8), AORTA_SEEDS, spacing)
        portal_core, portal_kept = keep_seed_components((vcand & portal_zone).astype(np.uint8), PORTAL_SEEDS, spacing)
        vessel_core = np.maximum(aorta_core, portal_core).astype(np.uint8)
        if variant in ("v4", "v5"):
            # z-continuity closing: bridges the under-opacified acquisition 1 slices along the
            # vessel paths (all portal-tree misses in the slice-5 measurement were on acquisition 1).
            closed = sitk.BinaryMorphologicalClosing(sitk_img(vessel_core, spacing), [1, 1, 2])
            vessel_core = sitk.GetArrayFromImage(closed).astype(np.uint8)
        kept = {"aorta_subtree": aorta_kept, "portal_subtree": portal_kept}
    else:
        vessel_core, kept = keep_seed_components(vcand, AORTA_SEEDS + PORTAL_SEEDS, spacing)
    chains.append({"effect": ("seed-subtree selection: aorta subtree in the aorta corridor, portal subtree in the liver zone"
                              if variant in ("v3", "v4", "v5") else "seed-connected components"),
                   "parameters": {"aorta_box": AORTA_BOX, "aorta_corridor": AORTA_CORRIDOR if variant in ("v3", "v4", "v5") else None,
                                  "liver_dilate_mm": LIVER_DILATE_FOR_VESSEL_MM,
                                  "portal_zone_dilate_mm": PORTAL_ZONE_DILATE_MM if variant in ("v3", "v4", "v5") else None,
                                  "z_continuity_closing_voxels": [1, 1, 2] if variant in ("v4", "v5") else None,
                                  "spine_fill_min_voxels": SPINE_FILL_MIN_VOXELS if variant == "v2" else None,
                                  "kidney_boxes": list(KIDNEY_BOXES) if variant == "v2" else None,
                                  "seed_component_patch_voxels": kept},
                   "library": "SimpleITK " + sitk_version})
    bone_all = sitk_fill_holes((hu >= BONE_HU).astype(np.uint8))
    bone_excl = sitk_dilate(bone_all, BONE_MARGIN_MM, spacing)
    protect = sitk_dilate(vessel_core, VESSEL_PROTECT_MM, spacing)
    bone_excl_v = ((bone_excl * (1 - protect)) > 0).astype(np.uint8)
    vessel = sitk_dilate(vessel_core, VESSEL_DILATE_MM[variant], spacing)
    vessel = (vessel * (1 - bone_excl_v)).astype(np.uint8)
    chains.append({"effect": "bone exclusion: HU at or above 250, holes filled, dilated 3 mm, minus vessel core protected zone; keep-out margin dilation",
                   "parameters": {"bone_HU": BONE_HU, "dilate_mm": BONE_MARGIN_MM, "protect_mm": VESSEL_PROTECT_MM,
                                  "keepout_margin_mm": VESSEL_DILATE_MM[variant],
                                  "seed_component_patch_voxels": kept},
                   "library": "SimpleITK " + sitk_version})
    return vessel, vessel_core, chains


def chain_liver_v0(widget, seg_node, organ_id, vol, shape, spacing):
    chains = []
    editor_node = widget.mrmlSegmentEditorNode()
    editor_node.SetSelectedSegmentID(organ_id)
    chains.append(apply_effect(widget, seg_node, organ_id, "Threshold",
                               {"MinimumThreshold": ORGAN_THRESHOLD[0], "MaximumThreshold": ORGAN_THRESHOLD[1]}))
    organ_roi = roi_mask(shape, ORGAN_ROI)
    clipped = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, organ_id, vol) * organ_roi
    write_array_to_segment(clipped, seg_node, organ_id, vol)
    chains.append({"effect": "ROI_clip_numpy", "parameters": {"x_fraction": ORGAN_ROI["x"], "y_fraction": ORGAN_ROI["y"]}})
    organ_arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, organ_id, vol)
    organ_arr = sitk_median(organ_arr, SMOOTH_KERNEL_MM, spacing)
    chains.append({"effect": "sitk.BinaryMedian", "parameters": {"kernel_mm": SMOOTH_KERNEL_MM,
                   "radius_voxels_xyz": voxel_radius(SMOOTH_KERNEL_MM, spacing)}, "library": "SimpleITK " + sitk.Version().VersionString()})
    organ_arr = sitk_keep_largest(organ_arr)
    chains.append({"effect": "sitk.ConnectedComponent+RelabelComponent keep largest", "parameters": {}})
    write_array_to_segment(organ_arr, seg_node, organ_id, vol)
    return chains


def chain_liver_v1(hu, sm, acq_by_slice, spacing, z_mm_by_slice, variant):
    """Seeded liver growth: phase-aware bounds in the liver ROI and z range, thin-bridge opening,
    seed components, closing, hole handling, keep largest. The organ-minus-vessel step runs after
    the vessel chain (see organ_minus_vessel).

    Variant v3 follows the measured SEG label convention (the Liver label excludes the Mass and the
    vessel labels, evaluation-side overlap 0.0): the global hole fill is replaced by a small-hole
    fill (lung-base pockets, the gallbladder, and the porta region are not filled), the bone
    exclusion is spine-centered (the rib dilation cost dome and lateral liver in v2), and the z range
    covers the full staged extent (the v2 cut cost the inferior liver tip).
    """
    sitk_version = sitk.Version().VersionString()
    chains = []
    seeds = LIVER_SEEDS_V1 if variant == "v1" else LIVER_SEEDS_V2
    open_mm = LIVER_OPEN_MM[variant]
    cand = np.zeros(hu.shape, dtype=np.uint8)
    roi = np.zeros(hu.shape, dtype=np.uint8)
    roi[:, LIVER_ROI["y"][0]:LIVER_ROI["y"][1], LIVER_ROI["x"][0]:LIVER_ROI["x"][1]] = 1
    for k in range(hu.shape[0]):
        if not (LIVER_Z_MM[variant][0] <= z_mm_by_slice[k] <= LIVER_Z_MM[variant][1]):
            continue
        lo, hi = LIVER_BOUNDS[int(acq_by_slice[k])]
        cand[k] = ((sm[k] >= lo) & (sm[k] <= hi)).astype(np.uint8)
    if variant == "v3":
        spine_core = sitk_keep_largest((hu >= BONE_HU).astype(np.uint8))
        bone_excl = sitk_dilate(sitk_fill_holes(spine_core), 2.0, spacing)
    else:
        bone_all = sitk_fill_holes((hu >= BONE_HU).astype(np.uint8))
        bone_excl = sitk_dilate(bone_all, BONE_MARGIN_MM, spacing)
    cand = ((cand & roi) * (1 - bone_excl)).astype(np.uint8)
    chains.append({"effect": "phase-aware HU bounds on smoothed HU (sigma 1 mm), liver ROI and z range, bone exclusion",
                   "parameters": {"bounds_by_acquisition": {str(a): list(b) for a, b in LIVER_BOUNDS.items()},
                                  "roi_pixels": LIVER_ROI, "z_range_mm": list(LIVER_Z_MM[variant]),
                                  "bone_exclusion": "spine-centered (keep largest calcified component, fill, dilate 2 mm)" if variant == "v3" else "all calcified components filled, dilated 3 mm",
                                  "phase_note": "acquisition 1 late arterial, acquisition 2 portal venous (probe9b HU measurements)"},
                   "library": "SimpleITK " + sitk_version})
    opened = sitk_open(cand, open_mm, spacing)
    grown, kept = keep_seed_components(opened, seeds, spacing)
    chains.append({"effect": "thin-bridge opening, then seed-connected components (15 x 15 seed patches)",
                   "parameters": {"open_mm": open_mm, "seeds": seeds, "seed_component_patch_voxels": kept},
                   "library": "SimpleITK " + sitk_version})
    liver = sitk_close(grown, LIVER_CLOSE_MM, spacing)
    if variant == "v3":
        liver = sitk_fill_small_holes(liver, SMALL_HOLE_MAX_VOXELS)
        liver = sitk_keep_largest(liver)
        chains.append({"effect": "sitk.BinaryMorphologicalClosing, small-hole fill (at most 100 voxels), keep largest",
                       "parameters": {"close_mm": LIVER_CLOSE_MM, "small_hole_max_voxels": SMALL_HOLE_MAX_VOXELS},
                       "library": "SimpleITK " + sitk_version})
    else:
        liver = sitk_fill_holes(liver)
        liver = sitk_keep_largest(liver)
        chains.append({"effect": "sitk.BinaryMorphologicalClosing, BinaryFillhole, keep largest",
                       "parameters": {"close_mm": LIVER_CLOSE_MM}, "library": "SimpleITK " + sitk_version})
    return liver, chains


def organ_minus_vessel(liver, vessel_core, variant, spacing, chains):
    """Organ-minus-vessel separation (the vascular keep-out zone leaves the parenchyma segment).

    The SEG Liver label excludes the Mass and the vessel labels (evaluation-side overlap 0.0 in the
    slice-5 convention notes), so the parenchyma subtracts the segmented vessel tree. Variant v3
    subtracts the vessel core as segmented (the labeled tree is carved out of the liver label) and
    keeps the vessel holes open. Variant v2 subtracts the vessel core eroded 1.5 mm (lumen centers
    only) and v1 the vessel core dilated 3 mm.
    """
    sitk_version = sitk.Version().VersionString()
    if variant == "v1":
        vs = sitk_dilate(vessel_core, VESSEL_DILATE_MM["v1"] + 1.0, spacing)
        out = (liver * (1 - vs)).astype(np.uint8)
        out = sitk_fill_holes(out)
        note = "subtract vessel core dilated 3 mm, fill holes"
    elif variant == "v2":
        vs = sitk_erode(vessel_core, VESSEL_CORE_ERODE_MM, spacing)
        out = (liver * (1 - vs)).astype(np.uint8)
        out = sitk_fill_holes(out)
        note = "subtract vessel core eroded 1.5 mm, fill holes"
    else:
        out = (liver * (1 - vessel_core)).astype(np.uint8)
        out = sitk_fill_small_holes(out, SMALL_HOLE_MAX_VOXELS)
        note = "subtract vessel core as segmented, small-hole fill (vessel holes stay open per the disjoint-label convention)"
    chains.append({"effect": "organ-minus-vessel separation: " + note,
                   "parameters": {"variant": variant}, "library": "SimpleITK " + sitk_version})
    return out


def chain_tumor_v0(widget, seg_node, tumor_id, vol, hu, spacing, organ_arr):
    chains = []
    liver_median = float(np.median(hu[organ_arr > 0])) if organ_arr.any() else 0.0
    interior = sitk_erode(organ_arr, TUMOR_INTERIOR_MM, spacing)
    smooth = sitk_smooth_hu(hu, TUMOR_SMOOTH_SIGMA_MM, spacing)
    cand = ((smooth <= liver_median - TUMOR_DELTA_HU) & (interior > 0)).astype(np.uint8)
    cand = sitk_open_1vox(cand)
    tumor_arr = sitk_keep_largest(cand)
    write_array_to_segment(tumor_arr, seg_node, tumor_id, vol)
    chains.append({
        "effect": "sitk.BinaryErode of parenchyma mask",
        "parameters": {"radius_mm": TUMOR_INTERIOR_MM, "radius_voxels_xyz": voxel_radius(TUMOR_INTERIOR_MM, spacing)},
        "library": "SimpleITK " + sitk.Version().VersionString(),
    })
    chains.append({
        "effect": "numpy background median and threshold on Gaussian-smoothed HU",
        "parameters": {"background_median_HU_parenchyma": round(liver_median, 2), "delta_HU": TUMOR_DELTA_HU,
                       "upper_bound_HU": round(liver_median - TUMOR_DELTA_HU, 2), "gaussian_sigma_mm": TUMOR_SMOOTH_SIGMA_MM},
        "library": "SimpleITK " + sitk.Version().VersionString(),
    })
    chains.append({"effect": "sitk.BinaryMorphologicalOpening", "parameters": {"radius_voxels": 1}})
    chains.append({"effect": "sitk.ConnectedComponent+RelabelComponent keep largest", "parameters": {}})
    return chains


def chain_tumor_v1(hu, sm, acq_by_slice, spacing, organ_arr):
    """Documented lesion-detection attempt: compact phase-specific focus search inside the liver.

    Hyper (acquisition 1, late arterial) and hypo (acquisition 2, portal venous) foci relative to
    a 10 mm background are listed as candidates. A focus enters the segment only when confirmed by
    CT inspection (TUMOR_CONFIRMED_FOCUS). For HCC_001 no focus is confirmed and the segment is empty.
    """
    sitk_version = sitk.Version().VersionString()
    interior = sitk_erode(organ_arr, TUMOR_INTERIOR_MM_V1, spacing)
    bg = sitk_smooth_hu(hu, 10.0, spacing)
    focus = np.zeros(hu.shape, dtype=np.uint8)
    for k in range(hu.shape[0]):
        if int(acq_by_slice[k]) == 1:
            focus[k] = (sm[k] > bg[k] + TUMOR_DELTA_HU_V1)
        else:
            focus[k] = (sm[k] < bg[k] - TUMOR_DELTA_HU_V1)
    focus = (focus & (interior > 0)).astype(np.uint8)
    cc_img = sitk.ConnectedComponent(sitk_img(focus, spacing))
    cc = sitk.GetArrayFromImage(cc_img)
    stats = sitk.LabelShapeStatisticsImageFilter()
    stats.Execute(cc_img)
    comps = []
    for lbl in stats.GetLabels():
        ml = stats.GetPhysicalSize(lbl) / 1000.0
        if TUMOR_MIN_ML <= ml <= TUMOR_MAX_ML:
            m = (cc == lbl)
            czs, cys, cxs = np.nonzero(m)
            comps.append({"label": int(lbl), "volume_ml": round(float(ml), 2),
                          "centroid_slice_index": int(round(czs.mean())), "centroid_y": int(round(cys.mean())),
                          "centroid_x": int(round(cxs.mean()))})
    comps.sort(key=lambda r: -r["volume_ml"])
    if TUMOR_CONFIRMED_FOCUS is None:
        tumor_arr = np.zeros(hu.shape, dtype=np.uint8)
    else:
        tumor_arr = (cc == TUMOR_CONFIRMED_FOCUS).astype(np.uint8)
    chains = [{
        "effect": "compact phase-specific focus search (hyper on late arterial slices, hypo on portal venous slices) inside liver eroded 8 mm; candidates recorded; focus enters the segment only when confirmed by CT inspection",
        "parameters": {"delta_HU": TUMOR_DELTA_HU_V1, "background_gaussian_mm": 10.0, "interior_mm": TUMOR_INTERIOR_MM_V1,
                       "component_ml_range": [TUMOR_MIN_ML, TUMOR_MAX_ML], "candidates": comps[:10],
                       "confirmed_focus_label": TUMOR_CONFIRMED_FOCUS},
        "library": "SimpleITK " + sitk_version,
    }]
    return tumor_arr, chains


def main():
    dicom_dir = os.environ["SURGITWIN_DICOM_DIR"]
    series_uid = os.environ["SURGITWIN_SERIES_UID"]
    dataset_id = os.environ["SURGITWIN_DATASET_ID"]
    out_root = os.environ["SURGITWIN_OUTPUT_ROOT"]
    script_path = os.environ["SURGITWIN_SCRIPT"]
    source_note = os.environ.get("SURGITWIN_SOURCE_NOTE", "")

    ct_entries = assert_ct_only_input(dicom_dir)

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

    if len(ct_entries) != shape[0]:
        raise RuntimeError("Staged instance count %d does not match volume slices %d" % (len(ct_entries), shape[0]))
    acq_by_slice = [a for _, a in ct_entries]
    z_mm_by_slice = [z for z, _ in ct_entries]
    m_ijk = vtk.vtkMatrix4x4()
    vol.GetIJKToRASMatrix(m_ijk)
    z_first = float(m_ijk.MultiplyPoint([0, 0, 0, 1.0])[2])
    z_last = float(m_ijk.MultiplyPoint([0, 0, shape[0] - 1, 1.0])[2])
    if z_first > z_last:
        raise RuntimeError("Volume slice order does not ascend in z; slice-index phase mapping is invalid")
    if abs(z_first - z_mm_by_slice[0]) > 1.0 or abs(z_last - z_mm_by_slice[-1]) > 1.0:
        raise RuntimeError("Volume z extent does not match the staged instance z positions")

    chains = {ORGAN: [], TUMOR: [], VESSEL: []}
    variants = {"liver": LIVER_VARIANT, "tumor": TUMOR_VARIANT, "vessel": VESSEL_VARIANT}

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

    organ_id, tumor_id, vessel_id = segs[ORGAN], segs[TUMOR], segs[VESSEL]

    # Bone exclusion for the v0 chains (keep largest component, fill, dilate).
    bone_core_v0 = sitk_keep_largest((hu >= BONE_HU).astype(np.uint8))
    bone_excl_v0 = sitk_dilate(sitk_fill_holes(bone_core_v0), BONE_MARGIN_MM, spacing)

    sm = sitk_smooth_hu(hu, 1.0, spacing)

    # Liver growth runs first (the vessel candidate region uses the liver zone); the
    # organ-minus-vessel step runs after the vessel chain.
    if LIVER_VARIANT == "v0":
        chains[ORGAN] = chain_liver_v0(widget, seg_node, organ_id, vol, shape, spacing)
        liver_pre = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, organ_id, vol)
    else:
        liver_pre, chains[ORGAN] = chain_liver_v1(hu, sm, acq_by_slice, spacing, z_mm_by_slice, LIVER_VARIANT)

    if VESSEL_VARIANT == "v0":
        chains[VESSEL] = chain_vessel_v0(widget, seg_node, vessel_id, vol, hu, shape, spacing, bone_excl_v0)
        vessel_arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, vessel_id, vol)
        vessel_core = vessel_arr
    else:
        vessel_arr, vessel_core, chains[VESSEL] = chain_vessel_v1(hu, sm, acq_by_slice, spacing, liver_pre, VESSEL_VARIANT)
        write_array_to_segment(vessel_arr, seg_node, vessel_id, vol)

    if LIVER_VARIANT == "v0":
        organ_arr = liver_pre
    else:
        organ_arr = organ_minus_vessel(liver_pre, vessel_core, LIVER_VARIANT, spacing, chains[ORGAN])
        write_array_to_segment(organ_arr, seg_node, organ_id, vol)

    if TUMOR_VARIANT == "v0":
        chains[TUMOR] = chain_tumor_v0(widget, seg_node, tumor_id, vol, hu, spacing, organ_arr)
    else:
        tumor_arr, chains[TUMOR] = chain_tumor_v1(hu, sm, acq_by_slice, spacing, organ_arr)
        write_array_to_segment(tumor_arr, seg_node, tumor_id, vol)

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
        "acquisition_by_slice": acq_by_slice,
        "phase_determination": {"acquisition_1": "late arterial", "acquisition_2": "portal venous",
                                "evidence": "SNDEV/logs/probe9b-phase-hu-2026-11-05.json (aorta and liver HU, both acquisitions)"},
        "variants": variants,
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
        if name == VESSEL:
            prov["keepout_margin_mm"] = VESSEL_DILATE_MM[VESSEL_VARIANT] if VESSEL_VARIANT in VESSEL_DILATE_MM else VESSEL_MARGIN_MM
            prov["vessel_core_voxels"] = int(vessel_core.sum())
            prov["keepout_margin_note"] = ("keep-out safety margin of %s mm beyond the segmented vessel boundary, "
                                           "carried into the FR-RTA-003 envelope parameters (envelope integration "
                                           "is Phase 3 work)" % prov["keepout_margin_mm"])
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
        "variants": variants,
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
