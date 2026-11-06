# SPDX-License-Identifier: MIT
# Author: Seth Nenninger (Builder_Int34 Agent). Plan task 2.1 slice 2. Log: SNDEV/docs/impl-2026-11-05-task21-slice2-dice.md
"""Export held-out G2.1 reference labelmaps from the TCIA HCC-TACE-Seg HCC_001 SEG object.

Run by run_reference.ps1 through Slicer 5.12.4. This script is the only code that reads the SEG
object. The output folder reference/ is read only by evaluate_g21.py. segment_reference.py must not
read reference/ or the SEG folder (it checks its own input folder and refuses SEG objects).

Segment mapping (SEG segment label to reference name): Liver to reference_liver,
Mass to reference_tumor, Portal vein and Abdominal aorta (union) to reference_vessel.
The two vessel labels are also exported separately as reference_portal_vein and
reference_aorta so that evaluate_g21.py can measure the SEG label convention (VAL-031
requires the convention note with each run). The scored pair stays reference_vessel.
"""

import datetime
import glob
import hashlib
import json
import os

import pydicom
import slicer
from DICOMLib import DICOMUtils

SEG_LABEL_MAP = {
    "reference_liver": ["Liver"],
    "reference_tumor": ["Mass"],
    "reference_vessel": ["Portal vein", "Abdominal aorta"],
    "reference_portal_vein": ["Portal vein"],
    "reference_aorta": ["Abdominal aorta"],
}


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    root = os.environ["SURGITWIN_REF_ROOT"]
    ct_dir = os.environ["SURGITWIN_CT_DIR"]
    seg_dir = os.environ["SURGITWIN_SEG_DIR"]
    out_dir = os.environ["SURGITWIN_REF_OUT"]
    dataset_id = os.environ["SURGITWIN_DATASET_ID"]
    script_path = os.path.join(root, "export_reference_labels.py")
    os.makedirs(out_dir, exist_ok=True)

    seg_file = sorted(glob.glob(os.path.join(seg_dir, "*.dcm")))[0]
    seg_ds = pydicom.dcmread(seg_file)
    ref_sops = {}
    for series in seg_ds.ReferencedSeriesSequence:
        for inst in series.ReferencedInstanceSequence:
            ref_sops[str(inst.ReferencedSOPInstanceUID)] = None
    ct_by_sop = {}
    ct_acq2 = []
    for f in glob.glob(os.path.join(ct_dir, "*.dcm")):
        ds = pydicom.dcmread(f, stop_before_pixels=True)
        ct_by_sop[str(ds.SOPInstanceUID)] = ds
        if int(ds.AcquisitionNumber) == 2:
            ct_acq2.append(f)
    ref_z = []
    ref_acq_tags = []
    for sop in ref_sops:
        ds = ct_by_sop[sop]
        ref_z.append(float(ds.ImagePositionPatient[2]))
        ref_acq_tags.append(int(ds.AcquisitionNumber))
    acq2_z = [float(pydicom.dcmread(f, stop_before_pixels=True).ImagePositionPatient[2]) for f in ct_acq2]
    alignment_sop = {
        "seg_referenced_instances": len(ref_sops),
        "seg_referenced_unique_z": len(set(ref_z)),
        "ct_acquisition2_unique_z": len(set(acq2_z)),
        "identical_z_sets": sorted(set(ref_z)) == sorted(set(acq2_z)),
        "referenced_instances_tagged_acquisition1": sum(1 for t in ref_acq_tags if t == 1),
        "referenced_instances_tagged_acquisition2": sum(1 for t in ref_acq_tags if t == 2),
    }
    if not alignment_sop["identical_z_sets"]:
        raise RuntimeError("SEG referenced z set differs from CT acquisition 2 z set: " + str(alignment_sop))

    with DICOMUtils.TemporaryDICOMDatabase() as db:
        DICOMUtils.importDicom(ct_dir, db)
        DICOMUtils.importDicom(seg_dir, db)
        loaded = DICOMUtils.loadPatientByUID(db.patients()[0])
    nodes = [slicer.mrmlScene.GetNodeByID(i) for i in loaded]
    segs = [n for n in nodes if n is not None and n.IsA("vtkMRMLSegmentationNode")]
    vols = [n for n in nodes if n is not None and n.IsA("vtkMRMLScalarVolumeNode")]
    if not segs:
        raise RuntimeError("SEG object did not load as a segmentation node")
    seg_node = segs[0]
    vol = sorted(vols, key=lambda v: -slicer.util.arrayFromVolume(v).shape[0])[0]
    print("REF_VOLUME", vol.GetName(), "shape", slicer.util.arrayFromVolume(vol).shape, flush=True)

    seg = seg_node.GetSegmentation()
    name_to_id = {}
    for i in range(seg.GetNumberOfSegments()):
        sid = seg.GetNthSegmentID(i)
        name_to_id[seg.GetSegment(sid).GetName()] = sid
    print("SEG_SEGMENTS", sorted(name_to_id.keys()), flush=True)

    stamp = utc_now()
    operator = {
        "script": os.path.basename(script_path),
        "slicer_version": slicer.app.applicationVersion,
        "slicer_revision": slicer.app.repositoryRevision,
    }
    ct_series_uid = str(pydicom.dcmread(ct_acq2[0], stop_before_pixels=True).SeriesInstanceUID)
    records = []
    for ref_name, labels in SEG_LABEL_MAP.items():
        arr = None
        for label in labels:
            part = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, name_to_id[label], vol).astype("uint8")
            arr = part if arr is None else (arr | part)
        arr = arr.astype("uint8")
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "ref_" + ref_name)
        node.CopyOrientation(vol)
        node.SetOrigin(vol.GetOrigin())
        node.SetSpacing(vol.GetSpacing())
        slicer.util.updateVolumeFromArray(node, arr)
        node.CopyOrientation(vol)
        label_path = os.path.join(out_dir, ref_name + "_labelmap.nrrd")
        slicer.util.saveNode(node, label_path)
        slicer.mrmlScene.RemoveNode(node)
        voxels = int(arr.sum())
        sidecar = {
            "segment_name": ref_name,
            "is_g21_reference": True,
            "dataset_id": dataset_id,
            "source": "TCIA HCC-TACE-Seg HCC_001 SEG object, expert labels, CC BY 4.0",
            "seg_label_source": labels,
            "seg_file": os.path.basename(seg_file),
            "seg_file_sha256": sha256_file(seg_file),
            "seg_sop_instance_uid": str(seg_ds.SOPInstanceUID),
            "seg_series_uid": str(seg_ds.SeriesInstanceUID),
            "ct_series_uid": ct_series_uid,
            "ct_referenced_sop_instances": len(ref_sops),
            "ct_referenced_sop_uids": sorted(ref_sops.keys()),
            "alignment_check": alignment_sop,
            "resampling": "slicer.util.arrayFromSegmentBinaryLabelmap onto CT acquisition 2 grid",
            "volume_shape_zyx": list(arr.shape),
            "volume_spacing_mm": [round(float(s), 5) for s in vol.GetSpacing()],
            "volume_origin_ras_mm": [round(float(o), 5) for o in vol.GetOrigin()],
            "outputs": [os.path.basename(label_path)],
            "labelmap_sha256": sha256_file(label_path),
            "voxel_count": voxels,
            "generated_utc": stamp,
            "operator": operator,
            "holdout": "read only by evaluate_g21.py; never an input to segment_reference.py",
        }
        with open(os.path.join(out_dir, ref_name + "_provenance.json"), "w", encoding="utf-8") as f:
            json.dump(sidecar, f, indent=2)
        records.append({"reference": ref_name, "labelmap": os.path.basename(label_path), "voxel_count": voxels})
        print("REF_WRITTEN", ref_name, voxels, flush=True)

    manifest = {
        "dataset_id": dataset_id,
        "generated_utc": stamp,
        "is_g21_reference": True,
        "alignment_check_sop": alignment_sop,
        "references": records,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print("SURGITWIN_REF_DONE", os.path.join(out_dir, "manifest.json"), flush=True)


try:
    main()
except Exception as exc:
    import traceback
    traceback.print_exc()
    print("SURGITWIN_REF_FAILED " + str(exc), flush=True)
    slicer.app.exit(1)
else:
    slicer.app.exit(0)
