# SPDX-License-Identifier: MIT
# Metadata: Author Seth Nenninger (Builder_Int34 Agent); Contribution: plan task 2.1 slice 3 (confound fix);
# Log: SNDEV/docs/impl-2026-11-05-task21-slice3-method.md
"""Stage the pipeline input as exactly the SEG-referenced CT instances.

Run by run.ps1 before segment_reference.py, through the Slicer 5.12.4 bundled Python. This is the
only code that opens the SEG object for input selection, and it reads only the SEG header fields
ReferencedSeriesSequence and ReferencedInstanceSequence (SOP instance UIDs). No label pixel data is
read here. It copies the selected CT files into output/<dataset-id>/input/ and writes
input_selection.json with the instance list, acquisition numbers, and checksums.

The SEG references one CT instance per z level for 36 z levels. The CT folder holds two
acquisitions that share 28 z levels. A z-set match alone cannot choose between the two files at
those levels, so the SOP instance UID list decides which file is used.

segment_reference.py reads only output/<dataset-id>/input/ and never reads the SEG or reference/.
"""

import datetime
import glob
import hashlib
import json
import os
import shutil

import pydicom

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_ID = os.environ.get("SURGITWIN_DATASET_ID", "tcia-hcc-tace-seg-hcc001")
SEG_DIR = os.environ.get("SURGITWIN_SEG_DIR", os.path.join(HERE, "data", "HCC_001_SEG_1.2.276.0.7230010.3.1.3.8323329.719.1600928570.399942"))
CT_DIR = os.environ.get("SURGITWIN_CT_DIR", os.path.join(HERE, "data", "HCC_001_CT_C-A-P_1.3.6.1.4.1.14519.5.2.1.1706.8374.302065206690360709343725942120"))
OUT_ROOT = os.environ.get("SURGITWIN_OUTPUT_ROOT", os.path.join(HERE, "output"))


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def main():
    seg_file = sorted(glob.glob(os.path.join(SEG_DIR, "*.dcm")))[0]
    seg = pydicom.dcmread(seg_file, stop_before_pixels=True)
    ref_sops = set()
    for series in seg.ReferencedSeriesSequence:
        for inst in series.ReferencedInstanceSequence:
            ref_sops.add(str(inst.ReferencedSOPInstanceUID))

    ct_files = sorted(glob.glob(os.path.join(CT_DIR, "*.dcm")))
    all_headers = {f: pydicom.dcmread(f, stop_before_pixels=True) for f in ct_files}
    selected = [f for f in ct_files if str(all_headers[f].SOPInstanceUID) in ref_sops]
    not_selected = [f for f in ct_files if f not in selected]
    if len(selected) != len(ref_sops):
        raise RuntimeError("Selected %d CT instances for %d SEG references" % (len(selected), len(ref_sops)))
    if any(str(d.Modality) == "SEG" for d in all_headers.values()):
        raise RuntimeError("SEG object found in CT folder")

    out_dir = os.path.join(OUT_ROOT, DATASET_ID, "input")
    if os.path.isdir(out_dir):
        for old in glob.glob(os.path.join(out_dir, "*.dcm")):
            os.remove(old)
    os.makedirs(out_dir, exist_ok=True)

    records = []
    for f in sorted(selected, key=lambda p: float(all_headers[p].ImagePositionPatient[2])):
        ds = all_headers[f]
        full = pydicom.dcmread(f)
        dst = os.path.join(out_dir, os.path.basename(f))
        shutil.copyfile(f, dst)
        records.append({
            "file": os.path.basename(f),
            "sop_instance_uid": str(ds.SOPInstanceUID),
            "instance_number": int(ds.InstanceNumber),
            "acquisition_number": int(ds.AcquisitionNumber),
            "image_position_z_mm": float(ds.ImagePositionPatient[2]),
            "file_sha256": sha256_file(dst),
            "pixel_data_sha256": sha256_bytes(full.PixelData),
        })

    z_selected = sorted({r["image_position_z_mm"] for r in records})
    acq_selected = {}
    for r in records:
        acq_selected[str(r["acquisition_number"])] = acq_selected.get(str(r["acquisition_number"]), 0) + 1
    acq_not_selected = {}
    for f in not_selected:
        a = str(int(all_headers[f].AcquisitionNumber))
        acq_not_selected[a] = acq_not_selected.get(a, 0) + 1

    doc = {
        "dataset_id": DATASET_ID,
        "generated_utc": utc_now(),
        "selection_rule": "CT instances whose SOPInstanceUID appears in the SEG ReferencedInstanceSequence",
        "seg_file": os.path.basename(seg_file),
        "seg_file_sha256": sha256_file(seg_file),
        "seg_sop_instance_uid": str(seg.SOPInstanceUID),
        "ct_series_uid": str(all_headers[selected[0]].SeriesInstanceUID),
        "ct_files_in_folder": len(ct_files),
        "selected_instances": len(records),
        "selected_unique_z": len(z_selected),
        "selected_z_min_max_mm": [z_selected[0], z_selected[-1]],
        "selected_acquisition_counts": acq_selected,
        "not_selected_instances": len(not_selected),
        "not_selected_acquisition_counts": acq_not_selected,
        "holdout": "Reads SEG header fields only (ReferencedSOPInstanceUID). No label pixel data. "
                   "Never reads reference/. segment_reference.py reads only this folder.",
        "instances": records,
    }
    with open(os.path.join(OUT_ROOT, DATASET_ID, "input_selection.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    print("SELECT_DONE", len(records), "instances", "acq", acq_selected, "not_selected", acq_not_selected, flush=True)


main()
