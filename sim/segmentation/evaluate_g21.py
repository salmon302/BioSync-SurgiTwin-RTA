# SPDX-License-Identifier: MIT
# Metadata: Author Seth Nenninger (Builder_Int34 Agent); Contribution: plan task 2.1 slice 2 (gate G2.1 measurement);
# Log: SNDEV/docs/impl-2026-11-05-task21-slice2-dice.md
"""G2.1 Dice evaluation for FR-MS-001 (SRS.md v1.4.0, VAL-030).

Gate G2.1 (proposed metric, not changed by this script): meshes for parenchyma, tumor, and
vascular keep-out zones exported from the TCIA HCC-TACE-Seg HCC_001 series with segmentation
provenance, overlap with the expert SEG reference labels held out of pipeline inputs at a Dice
score of 0.90 or higher (proposed).

Pairs: parenchyma_liver to reference_liver, tumor_hypoattenuating to reference_tumor, and
vascular_keepout_bone_excluded to reference_vessel (Portal vein and Abdominal aorta union).

This script is the only reader of output/<dataset-id>/reference/ besides export_reference_labels.py,
which writes it. Run through run_evaluation.ps1 with the Slicer bundled SimpleITK 2.5.5. Writes
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
GATE_DICE = 0.90
PAIRS = [
    ("parenchyma_liver", "reference_liver"),
    ("tumor_hypoattenuating", "reference_tumor"),
    ("vascular_keepout_bone_excluded", "reference_vessel"),
]
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output", DATASET_ID)
REF_DIR = os.path.join(OUT_DIR, "reference")


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
    recall = float(np.logical_and(p_arr, r_arr).sum() / r_arr.sum()) if r_arr.sum() else 1.0
    if abs(dice_np - dice_sitk) > 1e-6:
        raise RuntimeError("Dice mismatch SimpleITK vs numpy for " + pipe_name)

    voxel_mm3 = float(np.prod(pred.GetSpacing()))
    pred_vox = int(p_arr.sum())
    ref_vox = int(r_arr.sum())
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
        "dice": round(dice_sitk, 6),
        "dice_numpy_check": round(dice_np, 6),
        "jaccard": round(jaccard_sitk, 6),
        "recall": round(recall, 6),
        "gate_threshold": GATE_DICE,
        "verdict": "PASS" if dice_sitk >= GATE_DICE else "FAIL",
    }


def main():
    results = [evaluate_pair(p, r) for p, r in PAIRS]
    doc = {
        "dataset_id": DATASET_ID,
        "generated_utc": utc_now(),
        "gate": "G2.1 (SRS v1.4.0 FR-MS-001, proposed metric)",
        "gate_threshold_dice": GATE_DICE,
        "simpleitk_version": sitk.Version().VersionString(),
        "results": results,
    }
    with open(os.path.join(OUT_DIR, "evaluation.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    header = "{:<32} {:>8} {:>8} {:>8} {:>10} {:>10} {:>10} {:>10} {:>8}".format(
        "segment", "dice", "jaccard", "recall", "pred_mL", "ref_mL", "pred_vox", "ref_vox", "verdict")
    print(header)
    for r in results:
        print("{:<32} {:>8.4f} {:>8.4f} {:>8.4f} {:>10.2f} {:>10.2f} {:>10d} {:>10d} {:>8}".format(
            r["pipeline_segment"], r["dice"], r["jaccard"], r["recall"], r["pipeline_volume_ml"], r["reference_volume_ml"],
            r["pipeline_voxels"], r["reference_voxels"], r["verdict"]))
    print("EVALUATION_DONE", os.path.join(OUT_DIR, "evaluation.json"))


if __name__ == "__main__":
    main()
