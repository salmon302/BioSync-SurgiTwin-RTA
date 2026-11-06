# SPDX-License-Identifier: MIT
# Metadata: Author Seth Nenninger (MiMo-V2.6-Pro Agent); Contribution: plan task 2.1 slices 2, 4, and 5
# (gate G2.1 measurement; slice 5 adds the VAL-031 clause verdicts and the SEG label-convention notes);
# Log: SNDEV/docs/impl-2026-11-05-task21-slice2-dice.md, SNDEV/docs/impl-2026-11-05-task21-slice4-method.md,
# SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md
"""G2.1 evaluation for FR-MS-001 (VAL-031 clauses, VTM row FR-MS-001).

Gate G2.1 (VAL-031, applied 2026-11-05): meshes for parenchyma, tumor, and vascular keep-out zones
exported from the TCIA HCC-TACE-Seg HCC_001 series with segmentation provenance, evaluated against
the expert SEG reference labels held out of pipeline inputs, per structure: (a) parenchyma, Dice at
or above 0.90 and recall at or above 0.90 against the held-out liver reference; (b) vascular keep-out,
recall at or above 0.95, keep-out volume at most 3 times the reference vessel volume, and the
keep-out safety margin documented and carried into the FR-RTA-003 envelope parameters; (c) tumor,
operator-seeded with detection excluded, Dice at or above 0.70 when a documented seed source exists,
otherwise the sub-gate is recorded not applicable. Each run records the SEG label-convention notes
(Portal vein main trunk versus full tree).

Pairs: parenchyma_liver to reference_liver, tumor_hypoattenuating to reference_tumor, and
vascular_keepout_bone_excluded to reference_vessel (Portal vein and Abdominal aorta union).

This script is the only reader of output/<dataset-id>/reference/ besides export_reference_labels.py,
which writes it. The reference inspection in this script (label-convention geometry, disagreement
profiles) is evaluation-side and never enters the scoring chain. Run through run_evaluation.ps1 with
the Slicer bundled SimpleITK 2.5.5. Writes output/<dataset-id>/evaluation.json and prints a summary
table. The process exits 0 when the evaluation completes, whatever the verdicts. A FAIL verdict is a
measurement, not a script error.
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
    ref_dist = sitk.SignedMaurerDistanceMap(r_bin, insideIsPositive=True, useImageSpacing=True)
    pred_dist = sitk.SignedMaurerDistanceMap(p_bin, insideIsPositive=True, useImageSpacing=True)
    ref_d = sitk.GetArrayViewFromImage(ref_dist)
    pred_d = sitk.GetArrayViewFromImage(pred_dist)
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
    dist = sitk.SignedMaurerDistanceMap(sitk.Cast(img > 0, sitk.sitkUInt8), insideIsPositive=True, useImageSpacing=True)
    dist_arr = sitk.GetArrayViewFromImage(dist)
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
    overlays = export_disagreement_overlays(utc_now().replace(":", "").replace("-", ""))
    doc = {
        "dataset_id": DATASET_ID,
        "generated_utc": utc_now(),
        "gate": "G2.1 (VAL-031 per-structure clauses, VTM row FR-MS-001)",
        "gate_clauses": CLAUSE,
        "simpleitk_version": sitk.Version().VersionString(),
        "seg_label_convention_notes": conventions,
        "clause_verdicts": clauses,
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
    print("PORTAL_VEIN_CONVENTION", conventions["portal_vein_convention"],
          "components", conventions["reference_portal_vein"]["components_26"],
          "volume_ml", conventions["reference_portal_vein"]["volume_ml"],
          "max_lumen_radius_mm", conventions["reference_portal_vein"]["max_lumen_radius_mm"], flush=True)
    for name, a in attribution.items():
        print("LABEL_COVERAGE", name, "recall", a["recall"], "missed_voxels", a["missed_voxels"], flush=True)
    print("LABEL_OVERLAPS", json.dumps(conventions["label_overlaps"], sort_keys=True), flush=True)
    print("DISAGREEMENT_OVERLAYS", overlays["folder"], flush=True)
    for name in ("parenchyma", "vascular_keepout", "tumor"):
        print("CLAUSE", name, json.dumps(clauses[name], sort_keys=True), flush=True)
    print("EVALUATION_DONE", os.path.join(OUT_DIR, "evaluation.json"))


if __name__ == "__main__":
    main()
