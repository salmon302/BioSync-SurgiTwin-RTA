# SPDX-License-Identifier: MIT
# Metadata: Author Seth Nenninger (MiMo-V2.6-Pro Agent); Contribution: plan task 2.1 slices 2, 4, 5, and 6
# (gate G2.1 measurement; slice 5 adds the VAL-031 clause verdicts and the SEG label-convention notes;
# slice 6 adds the VAL-032 envelope convention, the stratified vessel metrics, and the grounded markers);
# Log: SNDEV/docs/impl-2026-11-05-task21-slice2-dice.md, SNDEV/docs/impl-2026-11-05-task21-slice4-method.md,
# SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md, SNDEV/docs/impl-2026-11-05-val032-recenter.md
"""G2.1 evaluation for FR-MS-001 (VAL-032 re-centered clauses, VTM row FR-MS-001).

Gate G2.1 (VAL-032, from the owner decisions of 2026-11-05): meshes for parenchyma, tumor, and
vascular keep-out zones exported from the TCIA HCC-TACE-Seg HCC_001 series with segmentation
provenance, evaluated against the expert SEG reference labels held out of pipeline inputs, per
structure: (a) parenchyma, Dice at or above 0.90 and recall at or above 0.90 against the liver
envelope (the reference liver label with the tumor and vessel carve-outs filled; the envelope
convention is documented in each evaluation record); (b) vascular keep-out, recall at or above 0.95
over the reference-resolvable vessel set (reference components with lumen diameter at or above the
grounded floor), full-tree recall reported as information, keep-out volume at most the grounded
multiple of the reference vessel volume with the 1.0 mm safety margin documented and carried into
the FR-RTA-003 envelope parameters, and the unresolved thin-branch residual risk recorded in the
risk file; (c) tumor, unchanged from VAL-031 (operator-placed seed, Dice at or above 0.70 when
applicable, detection excluded; on HCC_001 the sub-gate is not applicable). Each evaluation record
carries the label-convention notes and the dataset note (clinical Tr_Size 0.8 cm inconsistent with
the 35.75 mL labeled mass). The VAL-031 clause verdicts are retained alongside for the audit trail.

Pairs: parenchyma_liver to reference_liver, tumor_hypoattenuating to reference_tumor, and
vascular_keepout_bone_excluded to reference_vessel (Portal vein and Abdominal aorta union).

This script is the only reader of output/<dataset-id>/reference/ besides export_reference_labels.py,
which writes it. The reference inspection in this script (label-convention geometry, coverage
attribution, disagreement profiles, stratified metrics) is evaluation-side and never enters the
scoring chain. Run through run_evaluation.ps1 with the Slicer bundled SimpleITK 2.5.5. Writes
output/<dataset-id>/evaluation.json and prints a summary table. The process exits 0 when the
evaluation completes, whatever the verdicts. A FAIL verdict is a measurement, not a script error.
"""

import datetime
import hashlib
import json
import os

import numpy as np
import SimpleITK as sitk

DATASET_ID = "tcia-hcc-tace-seg-hcc001"
PAIRS = [
    ("parenchyma_liver", "reference_liver"),
    ("tumor_hypoattenuating", "reference_tumor"),
    ("vascular_keepout_bone_excluded", "reference_vessel"),
]
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output", DATASET_ID)
REF_DIR = os.path.join(OUT_DIR, "reference")

# VAL-031 clause thresholds (docs/val-031-g21-metric-proposal.md Section 3). The 3 times vessel
# volume bound and the 0.70 tumor floor carry adjustable markers in the clause.
CLAUSE = {
    "parenchyma_min_dice": 0.90,
    "parenchyma_min_recall": 0.90,
    "vascular_min_recall": 0.95,
    "vascular_max_volume_multiple": 3.0,
    "tumor_min_dice_seeded": 0.70,
}

# VAL-032 addendum (owner ruling 2026-11-05, "Slice 7, modality floor"): the diameter floor is fixed
# at 3.0 mm in partial-volume physics at 0.78 x 0.78 x 5 mm. The recall floor is the gated recall at
# that floor achieved by the measured keep-out (rounded down to two decimals) and the volume
# multiplier is the measured margin-inclusive multiple (rounded up to the next 0.5). The owner
# re-centers; this script reports the measured values.
MODALITY_FLOOR_MM = 3.0
KEEP_OUT_MARGIN_NOTE = ("keep-out safety margin is documented in sim/segmentation/README.md and in the "
                        "vascular provenance sidecar and is carried into the FR-RTA-003 envelope "
                        "parameters (envelope integration is Phase 3 work)")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def alignment(pred, ref):
    fields = {
        "origin": (pred.GetOrigin(), ref.GetOrigin()),
        "spacing": (pred.GetSpacing(), ref.GetSpacing()),
        "size": (pred.GetSize(), ref.GetSize()),
        "direction": (pred.GetDirection(), ref.GetDirection()),
    }
    report = {}
    ok = True
    for key, (a, b) in fields.items():
        same = bool(np.allclose(np.array(a, dtype=float), np.array(b, dtype=float), atol=1e-4))
        report[key] = {"pipeline": [round(float(v), 5) for v in a], "reference": [round(float(v), 5) for v in b], "match": same}
        ok = ok and same
    report["all_match"] = ok
    return report, ok


def dice_numpy(a, b):
    inter = np.logical_and(a, b).sum()
    denom = a.sum() + b.sum()
    return float(2.0 * inter / denom) if denom else 1.0


def evaluate_pair(pipe_name, ref_name):
    pred_path = os.path.join(OUT_DIR, pipe_name + "_labelmap.nrrd")
    ref_path = os.path.join(REF_DIR, ref_name + "_labelmap.nrrd")
    ref_sidecar_path = os.path.join(REF_DIR, ref_name + "_provenance.json")
    with open(ref_sidecar_path, encoding="utf-8") as f:
        ref_sidecar = json.load(f)
    pred = sitk.ReadImage(pred_path)
    ref = sitk.ReadImage(ref_path)
    align, aligned = alignment(pred, ref)
    if not aligned:
        raise RuntimeError("Grid mismatch for " + pipe_name + ": " + json.dumps(align))

    p_bin = sitk.Cast(pred > 0, sitk.sitkUInt8)
    r_bin = sitk.Cast(ref > 0, sitk.sitkUInt8)
    overlap = sitk.LabelOverlapMeasuresImageFilter()
    overlap.Execute(p_bin, r_bin)
    dice_sitk = float(overlap.GetDiceCoefficient(1))
    jaccard_sitk = float(overlap.GetJaccardCoefficient(1))

    p_arr = sitk.GetArrayViewFromImage(p_bin).astype(bool)
    r_arr = sitk.GetArrayViewFromImage(r_bin).astype(bool)
    dice_np = dice_numpy(p_arr, r_arr)
    jaccard_np = float(np.logical_and(p_arr, r_arr).sum() / np.logical_or(p_arr, r_arr).sum())
    inter = int(np.logical_and(p_arr, r_arr).sum())
    recall = float(inter / r_arr.sum()) if r_arr.sum() else 1.0
    if abs(dice_np - dice_sitk) > 1e-6:
        raise RuntimeError("Dice mismatch SimpleITK vs numpy for " + pipe_name)

    voxel_mm3 = float(np.prod(pred.GetSpacing()))
    pred_vox = int(p_arr.sum())
    ref_vox = int(r_arr.sum())
    fp_vox = pred_vox - inter
    fn_vox = ref_vox - inter
    # Disagreement character: distance of FP voxels to the reference surface and of FN voxels to
    # the pipeline surface (evaluation-side geometry, no CT involved).
    ref_dist = signed_distance(r_bin)
    pred_dist = signed_distance(p_bin)
    ref_d = ref_dist
    pred_d = pred_dist
    fp_mask = p_arr & ~r_arr
    fn_mask = r_arr & ~p_arr
    buckets = [(0.0, 1.0), (1.0, 2.0), (2.0, 4.0), (4.0, 8.0), (8.0, float("inf"))]

    def dist_hist(mask, dist_arr):
        vals = -dist_arr[mask] if mask.any() else np.zeros(0)
        return {"%g-%g_mm" % (lo, hi) if hi != float("inf") else "%g+mm" % lo:
                int(np.logical_and(vals >= lo, vals < hi).sum()) for lo, hi in buckets}

    disagreement = {
        "fp_distance_to_reference": dist_hist(fp_mask, ref_d),
        "fn_distance_to_pipeline": dist_hist(fn_mask, pred_d),
    }
    per_slice = {
        "pipeline_voxels": [int(c) for c in p_arr.sum(axis=(1, 2))],
        "reference_voxels": [int(c) for c in r_arr.sum(axis=(1, 2))],
        "intersection_voxels": [int(c) for c in np.logical_and(p_arr, r_arr).sum(axis=(1, 2))],
        "fp_voxels": [int(c) for c in (p_arr & ~r_arr).sum(axis=(1, 2))],
        "fn_voxels": [int(c) for c in (r_arr & ~p_arr).sum(axis=(1, 2))],
    }
    labelmap_check = sha256_file(ref_path) == ref_sidecar["labelmap_sha256"]
    return {
        "pipeline_segment": pipe_name,
        "reference": ref_name,
        "pipeline_file": os.path.basename(pred_path),
        "pipeline_sha256": sha256_file(pred_path),
        "reference_file": os.path.basename(ref_path),
        "reference_sha256_matches_sidecar": labelmap_check,
        "reference_sop_instance_uid": ref_sidecar["seg_sop_instance_uid"],
        "reference_seg_label_source": ref_sidecar["seg_label_source"],
        "grid_alignment": align,
        "voxel_mm3": round(voxel_mm3, 6),
        "pipeline_voxels": pred_vox,
        "reference_voxels": ref_vox,
        "pipeline_volume_ml": round(pred_vox * voxel_mm3 / 1000.0, 3),
        "reference_volume_ml": round(ref_vox * voxel_mm3 / 1000.0, 3),
        "intersection_voxels": inter,
        "fp_voxels": fp_vox,
        "fn_voxels": fn_vox,
        "fp_volume_ml": round(fp_vox * voxel_mm3 / 1000.0, 3),
        "fn_volume_ml": round(fn_vox * voxel_mm3 / 1000.0, 3),
        "dice": round(dice_sitk, 6),
        "dice_numpy_check": round(dice_np, 6),
        "jaccard": round(jaccard_sitk, 6),
        "recall": round(recall, 6),
        "disagreement": disagreement,
        "per_slice": per_slice,
    }


def label_geometry(name, ref_name):
    """Reference-label geometry for the SEG label-convention note (evaluation-side reference inspection)."""
    path = os.path.join(REF_DIR, ref_name + "_labelmap.nrrd")
    img = sitk.ReadImage(path)
    arr = sitk.GetArrayViewFromImage(img) > 0
    voxel_mm3 = float(np.prod(img.GetSpacing()))
    filt = sitk.ConnectedComponentImageFilter()
    filt.SetFullyConnected(True)
    cc_img = filt.Execute(sitk.Cast(img > 0, sitk.sitkUInt8))
    stats = sitk.LabelShapeStatisticsImageFilter()
    stats.Execute(cc_img)
    comps = []
    for lbl in stats.GetLabels():
        comps.append({"voxels": int(round(stats.GetPhysicalSize(lbl) / voxel_mm3)),
                      "volume_ml": round(stats.GetPhysicalSize(lbl) / 1000.0, 3)})
    comps.sort(key=lambda c: -c["voxels"])
    dist_arr = signed_distance(sitk.Cast(img > 0, sitk.sitkUInt8))
    max_radius_mm = float(dist_arr[arr].max()) if arr.any() else 0.0
    nz = np.nonzero(arr.sum(axis=(1, 2)))[0]
    ys, xs = np.nonzero(arr.sum(axis=0))
    out = {
        "label": ref_name,
        "voxels": int(arr.sum()),
        "volume_ml": round(float(arr.sum()) * voxel_mm3 / 1000.0, 3),
        "components_26": len(comps),
        "largest_components_ml": [c["volume_ml"] for c in comps[:5]],
        "slice_range_with_label": [int(nz.min()), int(nz.max())] if len(nz) else [],
        "bbox_x_pixel": [int(xs.min()), int(xs.max())] if len(xs) else [],
        "bbox_y_pixel": [int(ys.min()), int(ys.max())] if len(ys) else [],
        "per_slice_voxels": [int(c) for c in arr.sum(axis=(1, 2))],
        "max_lumen_radius_mm": round(max_radius_mm, 2),
    }
    return out


def convention_notes():
    """SEG label-convention notes: Portal vein main trunk versus full tree (VAL-031 run record)."""
    vessel = label_geometry("reference_vessel", "reference_vessel")
    portal = label_geometry("reference_portal_vein", "reference_portal_vein")
    aorta = label_geometry("reference_aorta", "reference_aorta")
    liver = label_geometry("reference_liver", "reference_liver")
    tumor = label_geometry("reference_tumor", "reference_tumor")

    def load_arr(name):
        img = sitk.ReadImage(os.path.join(REF_DIR, name + "_labelmap.nrrd"))
        b = sitk.Cast(img > 0, sitk.sitkUInt8)
        return sitk.GetArrayViewFromImage(b) > 0

    liver_arr = load_arr("reference_liver")
    tumor_arr = load_arr("reference_tumor")
    vessel_arr = load_arr("reference_vessel")
    portal_arr = load_arr("reference_portal_vein")
    aorta_arr = load_arr("reference_aorta")
    overlaps = {
        "tumor_inside_liver_share": round(float(np.logical_and(liver_arr, tumor_arr).sum()) / float(tumor_arr.sum()), 4) if tumor_arr.sum() else None,
        "vessel_inside_liver_share": round(float(np.logical_and(liver_arr, vessel_arr).sum()) / float(vessel_arr.sum()), 4) if vessel_arr.sum() else None,
        "portal_inside_liver_share": round(float(np.logical_and(liver_arr, portal_arr).sum()) / float(portal_arr.sum()), 4) if portal_arr.sum() else None,
        "aorta_inside_liver_share": round(float(np.logical_and(liver_arr, aorta_arr).sum()) / float(aorta_arr.sum()), 4) if aorta_arr.sum() else None,
    }
    branch_share = None
    if portal["voxels"] and portal["largest_components_ml"] and portal["volume_ml"]:
        branch_share = round(1.0 - portal["largest_components_ml"][0] / portal["volume_ml"], 4)
    if portal["components_26"] <= 2 and portal["max_lumen_radius_mm"] >= 5.0 and branch_share is not None and branch_share < 0.35:
        portal_call = "main trunk with limited branches"
    elif portal["components_26"] >= 3 or (branch_share is not None and branch_share >= 0.35):
        portal_call = "full intrahepatic tree (trunk plus branches)"
    else:
        portal_call = "indeterminate from geometry alone"
    notes = {
        "purpose": "VAL-031 requires the SEG label-convention notes (Portal vein main trunk versus full tree) with each run",
        "reference_vessel": vessel,
        "reference_portal_vein": portal,
        "reference_aorta": aorta,
        "reference_liver": liver,
        "reference_tumor": tumor,
        "label_overlaps": overlaps,
        "portal_branch_volume_share": branch_share,
        "portal_vein_convention": portal_call,
        "dataset_note": ("HCC_001 clinical annotation (HCC-TACE-Seg_clinical_data-V2.xlsx) records Tr_Size 0.8 cm, "
                         "which is inconsistent with the 35.75 mL labeled mass (about 4 cm across), and documents "
                         "no lesion location; the tumor sub-gate is not applicable and the search trail is in "
                         "SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md"),
        "note": ("The scored reference_vessel is the union of the SEG labels Portal vein and Abdominal aorta. "
                 "The split labelmaps reference_portal_vein and reference_aorta are exported by "
                 "export_reference_labels.py for this measurement only. The measurement is evaluation-side "
                 "and never enters the scoring chain."),
    }
    return notes


def vessel_attribution(pipe_name="vascular_keepout_bone_excluded"):
    """Attribute the vascular coverage and misses to the split SEG labels (evaluation-side geometry)."""
    pred = sitk.ReadImage(os.path.join(OUT_DIR, pipe_name + "_labelmap.nrrd"))
    p_img = sitk.Cast(pred > 0, sitk.sitkUInt8)
    p = sitk.GetArrayViewFromImage(p_img).astype(bool)
    out = {}
    for name in ("reference_aorta", "reference_portal_vein"):
        img = sitk.ReadImage(os.path.join(REF_DIR, name + "_labelmap.nrrd"))
        r_img = sitk.Cast(img > 0, sitk.sitkUInt8)
        r = sitk.GetArrayViewFromImage(r_img) > 0
        covered = int(np.logical_and(p, r).sum())
        total = int(r.sum())
        out[name] = {
            "reference_voxels": total,
            "covered_voxels": covered,
            "missed_voxels": total - covered,
            "recall": round(covered / total, 6) if total else 1.0,
            "missed_per_slice": [int(c) for c in (r & ~p).sum(axis=(1, 2))],
        }
    return out


def signed_distance(mask_img):
    """True signed distance from SignedMaurerDistanceMap.

    This SimpleITK 2.5.5 build returns SQUARED distances from the Maurer filter (verified on a
    synthetic disk: 98.9 reported for a 10.9 mm radius, and 162 reported for a 14 voxel radius).
    The true distance is the square root of the magnitude, with the filter's sign kept
    (positive inside when insideIsPositive=True).
    """
    d = sitk.SignedMaurerDistanceMap(mask_img, insideIsPositive=True, useImageSpacing=True)
    a = sitk.GetArrayViewFromImage(d)
    return np.sign(a) * np.sqrt(np.abs(a))


def load_ref_arr(name):
    img = sitk.ReadImage(os.path.join(REF_DIR, name + "_labelmap.nrrd"))
    b = sitk.Cast(img > 0, sitk.sitkUInt8)
    return sitk.GetArrayViewFromImage(b) > 0


def parenchyma_envelope(pipe_name="parenchyma_liver"):
    """Parenchyma scored against the liver envelope (VAL-032 convention) and the disjoint label.

    The envelope is the reference liver label with the tumor and vessel carve-outs filled: the SEG
    labels are disjoint, so the Mass and vessel label regions are added back into the liver
    reference for scoring. Both scores are reported for the audit trail.
    """
    pred = sitk.ReadImage(os.path.join(OUT_DIR, pipe_name + "_labelmap.nrrd"))
    p_img = sitk.Cast(pred > 0, sitk.sitkUInt8)
    p = sitk.GetArrayViewFromImage(p_img) > 0
    liver = load_ref_arr("reference_liver")
    tumor = load_ref_arr("reference_tumor")
    vessel = load_ref_arr("reference_vessel")
    portal = load_ref_arr("reference_portal_vein")
    envelope = liver | tumor | vessel
    organ_envelope = liver | tumor | portal

    def score(ref):
        inter = int(np.logical_and(p, ref).sum())
        a = int(p.sum())
        b = int(ref.sum())
        return {
            "dice": round(float(2.0 * inter / (a + b)), 6) if (a + b) else 1.0,
            "jaccard": round(float(inter / (a + b - inter)), 6) if (a + b - inter) else 1.0,
            "recall": round(float(inter / b), 6) if b else 1.0,
            "reference_voxels": b,
            "intersection_voxels": inter,
            "fp_voxels": a - inter,
            "fn_voxels": b - inter,
        }

    return {
        "convention": ("liver envelope: the reference liver label with the Mass and vessel carve-outs filled "
                       "(the SEG labels are disjoint, overlap 0.0); the envelope convention is documented in "
                       "each evaluation record"),
        "envelope_definition": ("reference_liver OR reference_tumor OR reference_portal_vein (the organ "
                                "envelope; the Abdominal aorta label is extra-hepatic and is not a carve-out "
                                "of the liver label)"),
        "envelope": score(organ_envelope),
        "envelope_including_aorta_label_for_audit": score(envelope),
        "envelope_including_aorta_definition": "reference_liver OR reference_tumor OR reference_vessel",
        "disjoint_label": score(liver),
    }


DIAMETER_BANDS_MM = [(0.0, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 10.0), (10.0, float("inf"))]


def stratified_vessel(pipe_name="vascular_keepout_bone_excluded", ref_name="reference_vessel"):
    """Stratified vessel metrics: recall per reference component and per lumen-diameter band, and the
    margin-inclusive keep-out volume attributable per band (evaluation-side geometry).

    Lumen diameter is measured as twice the in-sphere radius (the SignedMaurerDistanceMap distance to
    the label boundary, useImageSpacing, the same measure as the 5.49 mm max lumen radius finding).
    """
    pred = sitk.ReadImage(os.path.join(OUT_DIR, pipe_name + "_labelmap.nrrd"))
    p_img = sitk.Cast(pred > 0, sitk.sitkUInt8)
    p = sitk.GetArrayViewFromImage(p_img) > 0
    ref_img = sitk.ReadImage(os.path.join(REF_DIR, ref_name + "_labelmap.nrrd"))
    r_img = sitk.Cast(ref_img > 0, sitk.sitkUInt8)
    r = sitk.GetArrayViewFromImage(r_img) > 0
    voxel_mm3 = float(np.prod(ref_img.GetSpacing()))

    # In-plane lumen diameter: the vessel cross-section is an in-plane measure and the in-plane
    # spacing is isotropic (0.78125 mm). The 3D Maurer distance is unreliable at the 5 mm z spacing
    # (it reported 50 mm in-radius on a 22 mm aorta), so the diameter is the per-slice 2D in-radius.
    d2d = np.zeros(r.shape, dtype=np.float32)
    for k in range(r.shape[0]):
        if not r[k].any():
            continue
        sl_img = sitk.Cast(sitk.GetImageFromArray(r[k].astype(np.uint8)), sitk.sitkUInt8)
        sl_img.SetSpacing(ref_img.GetSpacing()[:2])
        d2d[k] = signed_distance(sl_img)
    diameter = np.where(r, 2.0 * d2d, 0.0)

    bands = []
    band_masks = []
    for lo, hi in DIAMETER_BANDS_MM:
        m = r & (diameter >= lo) & (diameter < hi)
        band_masks.append(m)
        total = int(m.sum())
        covered = int(np.logical_and(p, m).sum())
        bands.append({
            "diameter_mm": ("%g-%g" % (lo, hi)) if hi != float("inf") else "%g+" % lo,
            "reference_voxels": total,
            "reference_volume_ml": round(total * voxel_mm3 / 1000.0, 3),
            "covered_voxels": covered,
            "recall": round(float(covered) / total, 6) if total else None,
        })

    filt = sitk.ConnectedComponentImageFilter()
    filt.SetFullyConnected(True)
    cc_img = filt.Execute(r_img)
    cc = sitk.GetArrayViewFromImage(cc_img)
    comps = []
    for lbl in range(1, int(cc.max()) + 1):
        m = cc == lbl
        total = int(m.sum())
        if not total:
            continue
        covered = int(np.logical_and(p, m).sum())
        czs, cys, cxs = np.nonzero(m)
        comps.append({
            "component": lbl,
            "voxels": total,
            "volume_ml": round(total * voxel_mm3 / 1000.0, 3),
            "max_lumen_diameter_mm": round(float(diameter[m].max()), 2),
            "median_lumen_diameter_mm": round(float(np.median(diameter[m])), 2),
            "bbox_x_pixel": [int(cxs.min()), int(cxs.max())],
            "bbox_y_pixel": [int(cys.min()), int(cys.max())],
            "bbox_slice": [int(czs.min()), int(czs.max())],
            "covered_voxels": covered,
            "recall": round(float(covered) / total, 6),
        })
    comps.sort(key=lambda c: -c["voxels"])

    # Keep-out volume attributable per band: every keep-out voxel is attributed to the nearest band
    # reference voxels (zero distance for the band's own reference voxels).
    pred_vox = int(p.sum())
    owner = np.zeros(p.shape, dtype=np.uint8)
    best = np.full(p.shape, np.inf, dtype=np.float32)
    for bi, m in enumerate(band_masks):
        if not m.any():
            continue
        m_img = sitk.Cast(sitk.GetImageFromArray(m.astype(np.uint8)), sitk.sitkUInt8)
        m_img.SetSpacing(ref_img.GetSpacing())
        bda = signed_distance(m_img)
        dist_to_band = np.where(m, 0.0, -bda).astype(np.float32)
        closer = p & (dist_to_band < best)
        best[closer] = dist_to_band[closer]
        owner[closer] = bi + 1
    attributed = []
    for bi, band in enumerate(bands):
        vox = int(np.logical_and(p, owner == bi + 1).sum())
        attributed.append({"diameter_mm": band["diameter_mm"],
                           "keepout_voxels_attributed": vox,
                           "keepout_ml_attributed": round(vox * voxel_mm3 / 1000.0, 3)})
    unattributed = int(np.logical_and(p, owner == 0).sum())

    return {
        "measure": ("lumen diameter is the per-slice in-plane in-sphere diameter (SignedMaurerDistanceMap "
                    "per slice, in-plane spacing 0.78125 mm); components qualify by max in-plane lumen "
                    "diameter; keep-out voxels are attributed to the nearest band"),
        "voxel_mm3": round(voxel_mm3, 6),
        "bands": bands,
        "components": comps,
        "keepout_attribution_by_band": attributed,
        "keepout_voxels_unattributed": unattributed,
        "keepout_total_voxels": pred_vox,
    }


def grounded_values(strat, vessel_result, groundable=(2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0, 11.0, 12.0, 15.0, 20.0)):
    """Ground the VAL-032 addendum markers at the 3.0 mm modality floor (owner ruling 2026-11-05).

    The diameter floor is fixed at 3.0 mm in partial-volume physics at the acquisition spacing and is
    not anchored to the chain failure pattern. The recall floor is the gated recall at that floor
    achieved by the measured keep-out, rounded down to a clean two-decimal value. The volume
    multiplier is the measured margin-inclusive keep-out volume over the reference vessel volume,
    rounded up to a clean value (the next 0.5). The shortfall from 0.95 is reported plainly; the
    owner re-centers.
    """
    import math
    comp_rows = strat["components"]
    rows = []
    for floor in groundable:
        gated = [c for c in comp_rows if c["max_lumen_diameter_mm"] >= floor]
        total = sum(c["voxels"] for c in gated)
        covered = sum(c["covered_voxels"] for c in gated)
        recall = round(float(covered) / total, 6) if total else None
        rows.append({"floor_mm": floor, "gated_components": len(gated),
                     "gated_reference_voxels": total,
                     "gated_reference_volume_ml": round(total * strat["voxel_mm3"] / 1000.0, 3),
                     "gated_recall": recall})
    gated = [c for c in comp_rows if c["max_lumen_diameter_mm"] >= MODALITY_FLOOR_MM]
    total = sum(c["voxels"] for c in gated)
    covered = sum(c["covered_voxels"] for c in gated)
    achieved = round(float(covered) / total, 6) if total else None
    recall_floor = math.floor(achieved * 100.0) / 100.0 if achieved is not None else None
    measured_multiple = vessel_result["pipeline_volume_ml"] / vessel_result["reference_volume_ml"]
    grounded_multiple = math.ceil(measured_multiple * 2.0) / 2.0
    shortfall = round(0.95 - achieved, 4) if achieved is not None else None
    if achieved is not None and achieved >= 0.95:
        plain = ("gated recall %s at the 3.0 mm floor exceeds the 0.95 aspiration by %s; the measured "
                 "value is proposed as the recall floor and the owner re-centers"
                 % (achieved, round(achieved - 0.95, 4)))
    else:
        plain = ("gated recall %s at the 3.0 mm floor is %s short of the 0.95 aspiration; the measured "
                 "value is proposed as the recall floor and the owner re-centers" % (achieved, shortfall))
    return {
        "diameter_floor_candidates": rows,
        "modality_floor_mm": MODALITY_FLOOR_MM,
        "grounded_diameter_floor_mm": MODALITY_FLOOR_MM,
        "floor_rule": ("3.0 mm modality floor (owner ruling 2026-11-05): at and above 3.0 mm a lumen "
                       "cross-section spans at least four in-plane pixels at 0.78125 mm, so the "
                       "reference is resolvable at this acquisition; components qualify by max "
                       "in-plane lumen diameter"),
        "gated_components": len(gated),
        "gated_reference_voxels": total,
        "gated_reference_volume_ml": round(total * strat["voxel_mm3"] / 1000.0, 3),
        "gated_recall_achieved": achieved,
        "grounded_recall_floor": recall_floor,
        "recall_floor_rule": "gated recall at the 3.0 mm modality floor, rounded down to two decimals (margin note in the proposal)",
        "shortfall_from_0p95": shortfall,
        "plain_statement": plain,
        "measured_keepout_volume_ml": vessel_result["pipeline_volume_ml"],
        "reference_vessel_volume_ml": vessel_result["reference_volume_ml"],
        "measured_volume_multiple": round(measured_multiple, 4),
        "grounded_volume_multiple": grounded_multiple,
        "multiple_rule": "measured margin-inclusive keep-out volume over the reference vessel volume, rounded up to the next 0.5 (margin note in the proposal)",
    }


def pipeline_margin(pipe_name):
    """Keep-out margin and core size recorded by the pipeline sidecar (pipeline output, not reference)."""
    prov_path = os.path.join(OUT_DIR, pipe_name + "_provenance.json")
    if not os.path.exists(prov_path):
        return {"margin_mm": None, "core_voxels": None, "core_volume_ml": None}
    with open(prov_path, encoding="utf-8") as f:
        prov = json.load(f)
    out = {"margin_mm": prov.get("keepout_margin_mm"), "core_voxels": prov.get("vessel_core_voxels")}
    if out["core_voxels"] is not None:
        sp = prov.get("volume_spacing_mm", [0.78125, 0.78125, 5.0])
        out["core_volume_ml"] = round(out["core_voxels"] * float(np.prod(sp)) / 1000.0, 3)
    else:
        out["core_volume_ml"] = None
    return out


def clause_verdicts(results):
    by_name = {r["pipeline_segment"]: r for r in results}
    liver = by_name["parenchyma_liver"]
    tumor = by_name["tumor_hypoattenuating"]
    vessel = by_name["vascular_keepout_bone_excluded"]
    margin = pipeline_margin("vascular_keepout_bone_excluded")
    volume_bound_ml = round(CLAUSE["vascular_max_volume_multiple"] * vessel["reference_volume_ml"], 3)

    parenchyma = {
        "dice": liver["dice"], "dice_floor": CLAUSE["parenchyma_min_dice"],
        "recall": liver["recall"], "recall_floor": CLAUSE["parenchyma_min_recall"],
        "verdict": "PASS" if (liver["dice"] >= CLAUSE["parenchyma_min_dice"] and liver["recall"] >= CLAUSE["parenchyma_min_recall"]) else "FAIL",
    }
    vascular = {
        "recall": vessel["recall"], "recall_floor": CLAUSE["vascular_min_recall"],
        "recall_verdict": "PASS" if vessel["recall"] >= CLAUSE["vascular_min_recall"] else "FAIL",
        "keepout_volume_ml": vessel["pipeline_volume_ml"],
        "keepout_volume_bound_ml": volume_bound_ml,
        "keepout_volume_multiple": round(vessel["pipeline_volume_ml"] / vessel["reference_volume_ml"], 4),
        "volume_verdict": "PASS" if vessel["pipeline_volume_ml"] <= volume_bound_ml else "FAIL",
        "keepout_margin_mm": margin["margin_mm"],
        "keepout_core_volume_ml": margin["core_volume_ml"],
        "margin_documentation": KEEP_OUT_MARGIN_NOTE,
        "margin_documented_verdict": "PASS" if margin["margin_mm"] is not None else "FAIL",
        "verdict": "PASS" if (vessel["recall"] >= CLAUSE["vascular_min_recall"] and vessel["pipeline_volume_ml"] <= volume_bound_ml) else "FAIL",
    }
    if tumor["pipeline_voxels"] > 0:
        tumor_clause = {
            "applicable": True,
            "basis": "operator-seeded chain produced a lesion mask; detection excluded from the gate",
            "dice": tumor["dice"], "dice_floor": CLAUSE["tumor_min_dice_seeded"],
            "verdict": "PASS" if tumor["dice"] >= CLAUSE["tumor_min_dice_seeded"] else "FAIL",
        }
    else:
        tumor_clause = {
            "applicable": False,
            "basis": ("no documented operator-seed source (image inspection found no lesion on the named "
                      "phases and the dataset clinical annotation documents no lesion location); "
                      "lesion detection is excluded from this gate and recorded as a limitation"),
            "verdict": "NOT APPLICABLE",
        }
    return {"parenchyma": parenchyma, "vascular_keepout": vascular, "tumor": tumor_clause}


def export_disagreement_overlays(stamp):
    """Render FP and FN overlays against the CT (evaluation-side geometric inspection artifact).

    Reads the staged CT from output/<dataset-id>/input/ and the labelmaps from output/ and
    reference/. The PNGs are evaluation output for the record; they never enter the scoring chain.
    """
    import glob as _glob
    ct_dir = os.path.join(OUT_DIR, "input")
    entries = []
    for f in _glob.glob(os.path.join(ct_dir, "*.dcm")):
        import pydicom
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        entries.append((float(ds.ImagePositionPatient[2]), f))
    entries.sort()
    reader = sitk.ImageSeriesReader()
    reader.SetFileNames([f for _, f in entries])
    hu = sitk.GetArrayFromImage(reader.Execute()).astype(np.float32)
    png_dir = os.path.join(HERE, "..", "..", "SNDEV", "logs", "g21-disagreement-" + stamp)
    os.makedirs(png_dir, exist_ok=True)
    written = []
    for pipe_name, ref_name in PAIRS[:1] + PAIRS[2:]:
        pred = sitk.ReadImage(os.path.join(OUT_DIR, pipe_name + "_labelmap.nrrd"))
        ref = sitk.ReadImage(os.path.join(REF_DIR, ref_name + "_labelmap.nrrd"))
        p_img = sitk.Cast(pred > 0, sitk.sitkUInt8)
        r_img = sitk.Cast(ref > 0, sitk.sitkUInt8)
        p = sitk.GetArrayViewFromImage(p_img) > 0
        r = sitk.GetArrayViewFromImage(r_img) > 0
        for k in (4, 12, 17, 20, 24, 27, 30, 33):
            base = sitk.Cast(sitk.IntensityWindowing(sitk.GetImageFromArray(hu[k]), -150.0, 350.0, 0.0, 255.0), sitk.sitkUInt8)
            rgb = np.stack([sitk.GetArrayFromImage(base)] * 3, axis=-1).astype(np.float32)
            fp = p[k] & ~r[k]
            fn = r[k] & ~p[k]
            rgb[fn] = np.array([0.0, 200.0, 255.0]) * 0.75 + rgb[fn] * 0.25
            rgb[fp] = np.array([255.0, 220.0, 0.0]) * 0.75 + rgb[fp] * 0.25
            for mask, col in ((p[k], (255, 60, 60)), (r[k], (60, 255, 120))):
                edge = mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
                for c in range(3):
                    rgb[:, :, c][edge] = col[c]
            path = os.path.join(png_dir, "%s_vs_%s_k%02d.png" % (pipe_name, ref_name, k))
            sitk.WriteImage(sitk.GetImageFromArray(np.clip(rgb, 0, 255).astype(np.uint8), isVector=True), path)
            written.append(os.path.basename(path))
    return {"folder": png_dir, "files": written}


def main():
    results = [evaluate_pair(p, r) for p, r in PAIRS]
    conventions = convention_notes()
    attribution = vessel_attribution()
    conventions["vascular_coverage_by_label"] = attribution
    clauses = clause_verdicts(results)
    envelope = parenchyma_envelope()
    strat = stratified_vessel()
    vessel_result = next(r for r in results if r["pipeline_segment"] == "vascular_keepout_bone_excluded")
    grounding = grounded_values(strat, vessel_result)
    recentered = {
        "clause_source": ("VAL-032 re-centered clauses with the addendum modality floor (owner decisions of "
                          "2026-11-05); parenchyma against the liver envelope, vascular recall over the "
                          "reference-resolvable set at the 3.0 mm modality floor with the recall floor and "
                          "volume multiplier grounded from this run, tumor unchanged from VAL-031"),
        "parenchyma": {
            "convention": "liver envelope (carve-outs filled)",
            "dice": envelope["envelope"]["dice"], "dice_floor": CLAUSE["parenchyma_min_dice"],
            "recall": envelope["envelope"]["recall"], "recall_floor": CLAUSE["parenchyma_min_recall"],
            "disjoint_label_dice_for_audit": envelope["disjoint_label"]["dice"],
            "disjoint_label_recall_for_audit": envelope["disjoint_label"]["recall"],
            "verdict": "PASS" if (envelope["envelope"]["dice"] >= CLAUSE["parenchyma_min_dice"]
                                  and envelope["envelope"]["recall"] >= CLAUSE["parenchyma_min_recall"]) else "FAIL",
        },
        "vascular_keepout": {
            "gated_diameter_floor_mm": grounding["grounded_diameter_floor_mm"],
            "gated_recall_achieved": grounding["gated_recall_achieved"],
            "grounded_recall_floor": grounding["grounded_recall_floor"],
            "recall_floor_rule": grounding["recall_floor_rule"],
            "shortfall_from_0p95": grounding["shortfall_from_0p95"],
            "plain_statement": grounding["plain_statement"],
            "full_tree_recall_for_information": vessel_result["recall"],
            "keepout_volume_ml": vessel_result["pipeline_volume_ml"],
            "keepout_volume_multiple": grounding["measured_volume_multiple"],
            "grounded_volume_multiple": grounding["grounded_volume_multiple"],
            "keepout_margin_mm": pipeline_margin("vascular_keepout_bone_excluded")["margin_mm"],
            "margin_documentation": KEEP_OUT_MARGIN_NOTE,
            "thin_branch_residual": ("unresolved thin-branch residual risk recorded in the risk file "
                                     "(DEVELOPMENT_PLAN.md Section 7.1) where FR-RTA-003 picks it up"),
            "verdict": "PASS" if (grounding["gated_recall_achieved"] is not None
                                  and grounding["grounded_recall_floor"] is not None
                                  and grounding["gated_recall_achieved"] >= grounding["grounded_recall_floor"]
                                  and vessel_result["pipeline_volume_ml"] / vessel_result["reference_volume_ml"]
                                  <= grounding["grounded_volume_multiple"]) else "FAIL",
        },
        "tumor": clauses["tumor"],
    }
    overlays = export_disagreement_overlays(utc_now().replace(":", "").replace("-", ""))
    doc = {
        "dataset_id": DATASET_ID,
        "generated_utc": utc_now(),
        "gate": "G2.1 (VAL-032 re-centered clauses; VAL-031 record retained)",
        "gate_clauses": CLAUSE,
        "simpleitk_version": sitk.Version().VersionString(),
        "seg_label_convention_notes": conventions,
        "parenchyma_envelope_scores": envelope,
        "vascular_stratified": strat,
        "grounded_values": grounding,
        "clause_verdicts_val031": clauses,
        "clause_verdicts": recentered,
        "disagreement_overlays": overlays,
        "results": results,
    }
    with open(os.path.join(OUT_DIR, "evaluation.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    header = "{:<32} {:>8} {:>8} {:>8} {:>10} {:>10} {:>10} {:>10}".format(
        "segment", "dice", "jaccard", "recall", "pred_mL", "ref_mL", "fp_mL", "fn_mL")
    print(header)
    for r in results:
        print("{:<32} {:>8.4f} {:>8.4f} {:>8.4f} {:>10.2f} {:>10.2f} {:>10.2f} {:>10.2f}".format(
            r["pipeline_segment"], r["dice"], r["jaccard"], r["recall"], r["pipeline_volume_ml"],
            r["reference_volume_ml"], r["fp_volume_ml"], r["fn_volume_ml"]))
    for r in results:
        print("DISAGREEMENT", r["pipeline_segment"],
              "fp", json.dumps(r["disagreement"]["fp_distance_to_reference"], sort_keys=True),
              "fn", json.dumps(r["disagreement"]["fn_distance_to_pipeline"], sort_keys=True), flush=True)
    print("PARENCHYMA_ENVELOPE", json.dumps(envelope["envelope"], sort_keys=True), flush=True)
    print("PARENCHYMA_ENVELOPE_WITH_AORTA", json.dumps(envelope["envelope_including_aorta_label_for_audit"], sort_keys=True), flush=True)
    print("PARENCHYMA_DISJOINT", json.dumps(envelope["disjoint_label"], sort_keys=True), flush=True)
    for band in strat["bands"]:
        print("VESSEL_BAND", band["diameter_mm"], "ref_vox", band["reference_voxels"],
              "recall", band["recall"], flush=True)
    for row in grounding["diameter_floor_candidates"]:
        print("GATED_FLOOR", row["floor_mm"], "components", row["gated_components"],
              "gated_ref_vox", row["gated_reference_voxels"], "gated_recall", row["gated_recall"], flush=True)
    print("GROUNDED_FLOOR_MM", grounding["grounded_diameter_floor_mm"],
          "GATED_RECALL_ACHIEVED", grounding["gated_recall_achieved"],
          "GROUNDED_RECALL_FLOOR", grounding["grounded_recall_floor"],
          "GROUNDED_VOLUME_MULTIPLE", grounding["grounded_volume_multiple"],
          "MEASURED_MULTIPLE", grounding["measured_volume_multiple"], flush=True)
    print("PLAIN_STATEMENT", grounding["plain_statement"], flush=True)
    print("PORTAL_VEIN_CONVENTION", conventions["portal_vein_convention"],
          "components", conventions["reference_portal_vein"]["components_26"],
          "volume_ml", conventions["reference_portal_vein"]["volume_ml"],
          "max_lumen_radius_mm", conventions["reference_portal_vein"]["max_lumen_radius_mm"], flush=True)
    for name, a in attribution.items():
        print("LABEL_COVERAGE", name, "recall", a["recall"], "missed_voxels", a["missed_voxels"], flush=True)
    print("LABEL_OVERLAPS", json.dumps(conventions["label_overlaps"], sort_keys=True), flush=True)
    print("DISAGREEMENT_OVERLAYS", overlays["folder"], flush=True)
    for name in ("parenchyma", "vascular_keepout", "tumor"):
        print("CLAUSE", name, json.dumps(recentered[name], sort_keys=True), flush=True)
    print("EVALUATION_DONE", os.path.join(OUT_DIR, "evaluation.json"))


if __name__ == "__main__":
    main()
