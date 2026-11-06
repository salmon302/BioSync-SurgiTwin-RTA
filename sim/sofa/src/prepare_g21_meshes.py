# SPDX-License-Identifier: MIT
"""G2.1 mesh preparation for the G2.2 reference scene (task 2.2 slice 3).

Converts the G2.1 labelmaps under sim/segmentation/output/tcia-hcc-tace-seg-hcc001/
into the Gmsh 2.2 files that reference_scene.scn loads from sim/sofa/src/meshes/:

* reference_organ.msh: every tetrahedron of the liver envelope (the scene organ).
* reference_organ_parenchyma.msh: the parenchyma subset (organ minus tumor).
* reference_organ_tumor.msh: the tumor subset (empty on HCC_001).
* vessel_keepout_points.msh: keep-out boundary points for the VasculatureKeepOut node.
* keepout_distance_nodes.json: signed distance from each scene node to the keep-out.
* g21_provenance.json: source checksums, tool versions, decimation parameters,
  tet and triangle counts, and output checksums.

Decimation (the remesh level is the design parameter, --cell-mm):

1. The liver labelmap is sampled on an isotropic grid of cells of --cell-mm
   (default 16 mm, 2490 tets, the low end of the 2000 to 8000 tet range).
   A cell is occupied when at least half of its 4 x 4 x 4 sub-samples fall
   inside the labelmap (nearest-voxel lookup).
2. Cell-level holes are filled and only the largest face-connected component
   of occupied cells is kept.
3. Each occupied cell is split into six tetrahedra around the 000-111 diagonal
   (the split of generate_reference_mesh.py), which is face-conforming.
4. Vertices used by no tetrahedron are dropped and node ids are renumbered 1..N.

The vascular keep-out is not carried as tets. At the timing-reference cell size
the vessels (0.78 by 0.78 by 5 mm sampling) are smaller than a cell, so a tet
subset would drop them. The keep-out is carried as a signed distance field
evaluated at every scene node (negative inside the keep-out; the 1.0 mm safety
margin is already in the labelmap) and as boundary points on a 5 mm lattice.

Scene frame: RAS millimetres are rotated so that scene y is superior, scene z is
posterior, and scene x is patient right, then shifted so the inferior-most node
is at y = 0 and the minimum corners of x and z are at 0. Units are metres. The
rotation is proper (determinant +1), so tetrahedron orientation is preserved.

Usage:
    python sim/sofa/src/prepare_g21_meshes.py
    python sim/sofa/src/prepare_g21_meshes.py --cell-mm 10.0 --out-dir SNDEV/logs/scan
"""

import argparse
import datetime
import gzip
import hashlib
import json
import pathlib
import platform
import re
import sys

import numpy as np

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SEG_DIR = REPO_ROOT / "sim" / "segmentation" / "output" / "tcia-hcc-tace-seg-hcc001"
MESH_DIR = pathlib.Path(__file__).resolve().parent / "meshes"
SOURCE_STEMS = {
    "liver": "parenchyma_liver",
    "keepout": "vascular_keepout_bone_excluded",
    "tumor": "tumor_hypoattenuating",
}
DEFAULT_CELL_MM = 16.0
TARGET_TET_RANGE = (2000, 8000)
SUBSAMPLES = 4
OCCUPANCY_FRACTION = 0.5
KEEPOUT_LATTICE_MM = 5.0
DISTANCE_CHUNK = 64
DENSITY_KG_M3 = 1000.0
SCENE_UNIT_M = 1e-3
BASE_PLANE_TOLERANCE_M = 0.5e-3
SIGN_LPS_TO_RAS = np.array([-1.0, -1.0, 1.0])

# Six-tetrahedron split of a cell around the 000-111 diagonal, corners as (di, dj, dk).
CELL_TETS = (
    ((0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1)),
    ((0, 0, 0), (1, 1, 0), (0, 1, 0), (1, 1, 1)),
    ((0, 0, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)),
    ((0, 0, 0), (0, 1, 1), (0, 0, 1), (1, 1, 1)),
    ((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1)),
    ((0, 0, 0), (1, 0, 1), (1, 0, 0), (1, 1, 1)),
)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Volume:
    """Binary labelmap indexed [k, j, i] (z, y, x), with LPS geometry from the NRRD header."""

    def __init__(self, mask, spacing, origin_lps, label_values):
        self.mask = mask
        self.spacing = spacing
        self.origin = origin_lps
        self.label_values = label_values
        self.shape_xyz = (mask.shape[2], mask.shape[1], mask.shape[0])

    def voxel_count(self):
        return int(self.mask.sum())


def read_nrrd(path):
    raw = path.read_bytes()
    split = raw.index(b"\n\n")
    fields = {}
    for line in raw[:split].decode("ascii").splitlines()[1:]:
        if not line or line.startswith("#") or ":=" in line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    if fields["type"] != "unsigned char" or fields["dimension"] != "3":
        raise SystemExit(f"{path.name}: expected 3D unsigned char NRRD")
    if fields["space"] != "left-posterior-superior":
        raise SystemExit(f"{path.name}: expected LPS space, got {fields['space']}")
    body = raw[split + 2:]
    if fields["encoding"] == "gzip":
        body = gzip.decompress(body)
    elif fields["encoding"] != "raw":
        raise SystemExit(f"{path.name}: unsupported encoding {fields['encoding']}")
    sizes = [int(v) for v in fields["sizes"].split()]
    data = np.frombuffer(body, dtype=np.uint8)
    if data.size != sizes[0] * sizes[1] * sizes[2]:
        raise SystemExit(f"{path.name}: payload size does not match sizes")
    directions = [
        tuple(float(v) for v in d.split(","))
        for d in re.findall(r"\(([^)]*)\)", fields["space directions"])
    ]
    off_diagonal = [directions[a][b] for a in range(3) for b in range(3) if a != b]
    if any(value != 0.0 for value in off_diagonal):
        raise SystemExit(f"{path.name}: non-axis-aligned space directions")
    spacing = np.array([directions[a][a] for a in range(3)])
    origin = np.array([float(v) for v in fields["space origin"].strip("()").split(",")])
    mask = data.reshape(sizes[2], sizes[1], sizes[0])
    return Volume(mask > 0, spacing, origin, [int(v) for v in np.unique(data)])


def index_to_ras(vol, idx_xyz):
    lps = vol.origin + np.asarray(idx_xyz, dtype=float) * vol.spacing
    return lps * SIGN_LPS_TO_RAS


def ras_to_index(vol, ras_xyz):
    lps = np.asarray(ras_xyz, dtype=float) * SIGN_LPS_TO_RAS
    return (lps - vol.origin) / vol.spacing


def sample_grid(vol, xs, ys, zs):
    """Nearest-voxel labelmap values on the outer product of RAS coordinates (mm), [k, j, i]."""
    axes = []
    for axis, coords in enumerate((xs, ys, zs)):
        lps = SIGN_LPS_TO_RAS[axis] * coords
        idx = np.floor((lps - vol.origin[axis]) / vol.spacing[axis] + 0.5).astype(np.int64)
        axes.append(idx)
    valid = [(a >= 0) & (a < n) for a, n in zip(axes, vol.shape_xyz)]
    clipped = [np.clip(a, 0, n - 1) for a, n in zip(axes, vol.shape_xyz)]
    values = vol.mask[np.ix_(clipped[2], clipped[1], clipped[0])]
    inside = valid[2][:, None, None] & valid[1][None, :, None] & valid[0][None, None, :]
    return values & inside


def sample_points(vol, ras_points):
    """Nearest-voxel labelmap values at RAS points (mm), shape (n,) boolean."""
    idx = np.floor(ras_to_index(vol, ras_points) + 0.5).astype(np.int64)
    valid = np.all((idx >= 0) & (idx < np.array(vol.shape_xyz)), axis=1)
    clipped = np.clip(idx, 0, np.array(vol.shape_xyz) - 1)
    values = vol.mask[clipped[:, 2], clipped[:, 1], clipped[:, 0]]
    return values & valid


def cell_fractions(vol, lo, cell_mm, cells_xyz):
    """Fraction of sub-samples inside the labelmap per grid cell, [k, j, i]."""
    sub = SUBSAMPLES
    axes = []
    for axis in range(3):
        offsets = (np.arange(cells_xyz[axis] * sub) + 0.5) / sub * cell_mm
        axes.append(lo[axis] + offsets)
    inside = sample_grid(vol, axes[0], axes[1], axes[2])
    nz, ny, nx = cells_xyz[2], cells_xyz[1], cells_xyz[0]
    return inside.reshape(nz, sub, ny, sub, nx, sub).mean(axis=(1, 3, 5))


def label_components(mask):
    """Face-connected components of a boolean [k, j, i] array. Returns labels and sizes."""
    labels = np.zeros(mask.shape, dtype=np.int64)
    sizes = [0]
    for seed in map(tuple, np.argwhere(mask)):
        if labels[seed]:
            continue
        label = len(sizes)
        sizes.append(0)
        labels[seed] = label
        stack = [seed]
        while stack:
            point = stack.pop()
            sizes[label] += 1
            for axis in range(3):
                for step in (-1, 1):
                    nxt = list(point)
                    nxt[axis] += step
                    if 0 <= nxt[axis] < mask.shape[axis]:
                        nxt = tuple(nxt)
                        if mask[nxt] and not labels[nxt]:
                            labels[nxt] = label
                            stack.append(nxt)
    return labels, sizes


def fill_cell_holes(occ):
    padded = np.pad(occ, 1, constant_values=False)
    labels, _ = label_components(~padded)
    exterior = labels[0, 0, 0]
    holes = (~padded) & (labels != exterior)
    return (padded | holes)[1:-1, 1:-1, 1:-1], int(holes.sum())


def keep_largest(occ):
    labels, sizes = label_components(occ)
    if len(sizes) <= 1:
        return occ, 0
    best = int(np.argmax(sizes[1:])) + 1
    dropped = int(sum(sizes[1:]) - sizes[best])
    return labels == best, dropped


def build_scene_mesh(liver, cell_mm, tumor):
    """Return the decimated grid and tetrahedra in RAS-grid vertex form."""
    idx = np.argwhere(liver.mask)
    lo_idx = idx.min(axis=0)[::-1].astype(float)
    hi_idx = idx.max(axis=0)[::-1].astype(float)
    corner_a = index_to_ras(liver, lo_idx - 0.5)
    corner_b = index_to_ras(liver, hi_idx + 0.5)
    lo = np.minimum(corner_a, corner_b)
    hi = np.maximum(corner_a, corner_b)
    cells_xyz = tuple(int(np.ceil((hi[a] - lo[a]) / cell_mm - 1e-9)) for a in range(3))

    fraction = cell_fractions(liver, lo, cell_mm, cells_xyz)
    occ = fraction >= OCCUPANCY_FRACTION
    occ_before_fill = int(occ.sum())
    occ, holes_filled = fill_cell_holes(occ)
    occ, lcc_dropped = keep_largest(occ)

    tumor_fraction = cell_fractions(tumor, lo, cell_mm, cells_xyz)
    tumor_cells = occ & (tumor_fraction >= OCCUPANCY_FRACTION)
    parenchyma_cells = occ & ~tumor_cells

    used = np.zeros((cells_xyz[2] + 1, cells_xyz[1] + 1, cells_xyz[0] + 1), dtype=bool)
    for dk in (0, 1):
        for dj in (0, 1):
            for di in (0, 1):
                used[dk:dk + cells_xyz[2], dj:dj + cells_xyz[1], di:di + cells_xyz[0]] |= occ
    ids = np.zeros(used.shape, dtype=np.int64)
    ids[used] = np.arange(1, int(used.sum()) + 1)

    k_grid, j_grid, i_grid = np.nonzero(used)
    ras_nodes = np.stack([
        lo[0] + i_grid * cell_mm,
        lo[1] + j_grid * cell_mm,
        lo[2] + k_grid * cell_mm,
    ], axis=1)

    return {
        "lo": lo,
        "hi": hi,
        "cells_xyz": cells_xyz,
        "occ": occ,
        "occ_before_fill": occ_before_fill,
        "holes_filled": holes_filled,
        "lcc_dropped": lcc_dropped,
        "tumor_cells": tumor_cells,
        "parenchyma_cells": parenchyma_cells,
        "ids": ids,
        "ras_nodes_grid_order": ras_nodes,
    }


def tets_for_cells(ids, cell_mask):
    cells = np.argwhere(cell_mask)
    if cells.size == 0:
        return np.zeros((0, 4), dtype=np.int64)
    k, j, i = cells[:, 0], cells[:, 1], cells[:, 2]
    blocks = []
    for pattern in CELL_TETS:
        block = np.stack(
            [ids[k + dk, j + dj, i + di] for (di, dj, dk) in pattern], axis=1)
        blocks.append(block)
    tets = np.stack(blocks, axis=1).reshape(-1, 4)
    return tets


def signed_volumes(points, tets):
    corners = points[tets - 1]
    a = corners[:, 0]
    u = corners[:, 1] - a
    v = corners[:, 2] - a
    w = corners[:, 3] - a
    return np.einsum("ij,ij->i", u, np.cross(v, w)) / 6.0


def orient_positive(points, tets):
    vols = signed_volumes(points, tets)
    negative = vols < 0.0
    swapped = tets.copy()
    swapped[negative, 2], swapped[negative, 3] = tets[negative, 3], tets[negative, 2]
    vols = np.abs(vols)
    if np.any(vols <= 0.0):
        raise SystemExit("degenerate tetrahedron in decimated mesh")
    return swapped, vols


def surface_triangle_count(tets):
    faces = np.concatenate([
        tets[:, [0, 1, 2]], tets[:, [0, 1, 3]], tets[:, [0, 2, 3]], tets[:, [1, 2, 3]],
    ])
    faces = np.sort(faces, axis=1)
    _, counts = np.unique(faces, axis=0, return_counts=True)
    return int(np.sum(counts == 1))


def write_msh(path, positions, elements, elem_type):
    """Write Gmsh 2.2 ASCII. positions: {node_id: (x, y, z)}; elements: list of node-id tuples."""
    lines = ["$MeshFormat", "2.2 0 8", "$EndMeshFormat", "$Nodes", str(len(positions))]
    for nid in sorted(positions):
        x, y, z = positions[nid]
        lines.append(f"{nid} {x:.9f} {y:.9f} {z:.9f}")
    lines += ["$EndNodes", "$Elements", str(len(elements))]
    for eid, elt in enumerate(elements, start=1):
        lines.append(f"{eid} {elem_type} 2 1 1 " + " ".join(str(n) for n in elt))
    lines.append("$EndElements")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def keepout_boundary_ras(keep):
    padded = np.pad(keep.mask, 1, constant_values=False)
    core = padded[1:-1, 1:-1, 1:-1]
    interior = (core
                & padded[:-2, 1:-1, 1:-1] & padded[2:, 1:-1, 1:-1]
                & padded[1:-1, :-2, 1:-1] & padded[1:-1, 2:, 1:-1]
                & padded[1:-1, 1:-1, :-2] & padded[1:-1, 1:-1, 2:])
    boundary = keep.mask & ~interior
    kk, jj, ii = np.nonzero(boundary)
    idx = np.stack([ii, jj, kk], axis=1)
    return index_to_ras(keep, idx), int(boundary.sum())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cell-mm", type=float, default=DEFAULT_CELL_MM,
                        help="grid cell size of the decimated liver envelope in mm "
                             f"(default {DEFAULT_CELL_MM})")
    parser.add_argument("--out-dir", default=None,
                        help="output directory (default sim/sofa/src/meshes)")
    args = parser.parse_args(argv)
    out_dir = pathlib.Path(args.out_dir) if args.out_dir else MESH_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_mm = args.cell_mm

    sources = {}
    for role, stem in SOURCE_STEMS.items():
        labelmap = SEG_DIR / f"{stem}_labelmap.nrrd"
        stl = SEG_DIR / f"{stem}_mesh.stl"
        sidecar = json.loads((SEG_DIR / f"{stem}_provenance.json").read_text(encoding="utf-8"))
        sources[role] = {
            "segment": stem,
            "labelmap": labelmap.name,
            "labelmap_sha256": sha256_file(labelmap),
            "labelmap_bytes": labelmap.stat().st_size,
            "stl": stl.name,
            "stl_sha256": sha256_file(stl),
            "stl_bytes": stl.stat().st_size,
            "stl_triangles": sidecar["mesh_triangles"],
            "voxel_count_sidecar": sidecar["voxel_count"],
            "is_g21_reference": sidecar.get("is_g21_reference"),
        }

    liver = read_nrrd(SEG_DIR / f"{SOURCE_STEMS['liver']}_labelmap.nrrd")
    keep = read_nrrd(SEG_DIR / f"{SOURCE_STEMS['keepout']}_labelmap.nrrd")
    tumor = read_nrrd(SEG_DIR / f"{SOURCE_STEMS['tumor']}_labelmap.nrrd")
    if liver.voxel_count() != sources["liver"]["voxel_count_sidecar"]:
        raise SystemExit("liver labelmap voxel count does not match its provenance")

    grid = build_scene_mesh(liver, cell_mm, tumor)
    ids = grid["ids"]
    ras_nodes = grid["ras_nodes_grid_order"]
    xmin = ras_nodes[:, 0].min()
    ymax = ras_nodes[:, 1].max()
    zmin = ras_nodes[:, 2].min()
    scene_nodes = np.stack([
        (ras_nodes[:, 0] - xmin) * SCENE_UNIT_M,
        (ras_nodes[:, 2] - zmin) * SCENE_UNIT_M,
        (ymax - ras_nodes[:, 1]) * SCENE_UNIT_M,
    ], axis=1)

    organ_tets = tets_for_cells(ids, grid["occ"])
    parenchyma_tets = tets_for_cells(ids, grid["parenchyma_cells"])
    tumor_tets = tets_for_cells(ids, grid["tumor_cells"])
    organ_tets, organ_vols = orient_positive(scene_nodes, organ_tets)
    parenchyma_tets, _ = orient_positive(scene_nodes, parenchyma_tets)
    tumor_tets, _ = orient_positive(scene_nodes, tumor_tets)
    total_volume_m3 = float(organ_vols.sum())
    total_mass_kg = DENSITY_KG_M3 * total_volume_m3

    node_count = scene_nodes.shape[0]
    positions = {nid + 1: tuple(scene_nodes[nid]) for nid in range(node_count)}

    boundary_ras, keepout_voxels_boundary = keepout_boundary_ras(keep)
    boundary_scene = np.stack([
        (boundary_ras[:, 0] - xmin) * SCENE_UNIT_M,
        (boundary_ras[:, 2] - zmin) * SCENE_UNIT_M,
        (ymax - boundary_ras[:, 1]) * SCENE_UNIT_M,
    ], axis=1)
    lattice = np.unique(
        np.round(boundary_scene / (KEEPOUT_LATTICE_MM * SCENE_UNIT_M)).astype(np.int64), axis=0)
    keep_points = lattice * (KEEPOUT_LATTICE_MM * SCENE_UNIT_M)

    distances = np.empty(node_count)
    for start in range(0, node_count, DISTANCE_CHUNK):
        block = scene_nodes[start:start + DISTANCE_CHUNK]
        d2 = np.sum((block[:, None, :] - boundary_scene[None, :, :]) ** 2, axis=2)
        distances[start:start + DISTANCE_CHUNK] = np.sqrt(d2.min(axis=1))
    inside = sample_points(keep, ras_nodes)
    distances = np.where(inside, -distances, distances)

    base_ymax = scene_nodes[:, 1].min() + BASE_PLANE_TOLERANCE_M
    base_mask = scene_nodes[:, 1] <= base_ymax
    base_box = (
        scene_nodes[:, 0].min() - 0.5e-3,
        scene_nodes[:, 1].min() - 0.5e-3,
        scene_nodes[:, 2].min() - 0.5e-3,
        scene_nodes[:, 0].max() + 0.5e-3,
        base_ymax,
        scene_nodes[:, 2].max() + 0.5e-3,
    )

    write_msh(out_dir / "reference_organ.msh", positions, [tuple(t) for t in organ_tets], 4)
    write_msh(out_dir / "reference_organ_parenchyma.msh", positions,
              [tuple(t) for t in parenchyma_tets], 4)
    write_msh(out_dir / "reference_organ_tumor.msh", positions,
              [tuple(t) for t in tumor_tets], 4)
    write_msh(out_dir / "vessel_keepout_points.msh",
              {n + 1: tuple(p) for n, p in enumerate(keep_points)},
              [(n + 1,) for n in range(len(keep_points))], 15)
    distance_payload = {
        "schema": "g21-keepout-distance-v1",
        "units": "m",
        "sign": "negative inside the keep-out (margin included), positive outside",
        "precision_note": "distance to the centres of keep-out boundary voxels, "
                          "so the value is quantized to the 5 mm slice grid in z",
        "nodes": {str(n + 1): round(float(distances[n]), 9) for n in range(node_count)},
    }
    (out_dir / "keepout_distance_nodes.json").write_text(
        json.dumps(distance_payload, indent=2) + "\n", encoding="utf-8")

    outputs = [
        "reference_organ.msh", "reference_organ_parenchyma.msh",
        "reference_organ_tumor.msh", "vessel_keepout_points.msh",
        "keepout_distance_nodes.json",
    ]
    output_records = []
    for name in outputs:
        path = out_dir / name
        output_records.append({
            "file": name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    provenance = {
        "schema": "g21-scene-mesh-v1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "is_g21_reference": False,
        "source_note": "TCIA HCC-TACE-Seg HCC_001 CT, CC BY 4.0; smoke dataset, not G2.1 reference data",
        "sources": sources,
        "tools": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "script": str(pathlib.Path(__file__).resolve().relative_to(REPO_ROOT)).replace("\\", "/"),
        },
        "decimation": {
            "cell_mm": cell_mm,
            "target_tet_range": list(TARGET_TET_RANGE),
            "within_target_range": TARGET_TET_RANGE[0] <= int(organ_tets.shape[0]) <= TARGET_TET_RANGE[1],
            "subsamples_per_axis": SUBSAMPLES,
            "occupancy_fraction": OCCUPANCY_FRACTION,
            "grid_cells_xyz": list(grid["cells_xyz"]),
            "occupied_cells_before_fill": grid["occ_before_fill"],
            "holes_filled_cells": grid["holes_filled"],
            "largest_component_dropped_cells": grid["lcc_dropped"],
            "occupied_cells": int(grid["occ"].sum()),
            "tet_split": "six tetrahedra per cell around the 000-111 diagonal",
        },
        "keepout": {
            "representation": "signed distance field at every scene node plus boundary points",
            "margin_mm": 1.0,
            "margin_note": "the 1.0 mm margin is in the vascular_keepout labelmap (sidecar keepout_margin_mm)",
            "boundary_voxels": keepout_voxels_boundary,
            "lattice_mm": KEEPOUT_LATTICE_MM,
            "lattice_points": int(len(keep_points)),
            "nodes_inside": int(inside.sum()),
            "distance_min_m": round(float(distances.min()), 9),
            "distance_max_m": round(float(distances.max()), 9),
        },
        "counts": {
            "nodes": int(node_count),
            "tetrahedra_organ": int(organ_tets.shape[0]),
            "tetrahedra_parenchyma": int(parenchyma_tets.shape[0]),
            "tetrahedra_tumor": int(tumor_tets.shape[0]),
            "surface_triangles_organ": surface_triangle_count(organ_tets),
            "tet_volume_min_m3": float(organ_vols.min()),
            "tet_volume_max_m3": float(organ_vols.max()),
            "base_nodes": int(base_mask.sum()),
        },
        "scene": {
            "frame": "x = RAS x - min, y = RAS z - min (superior), z = max RAS y - RAS y (posterior), metres",
            "total_volume_m3": total_volume_m3,
            "density_kg_m3": DENSITY_KG_M3,
            "total_mass_kg": total_mass_kg,
            "base_fixation_box_m": [round(float(v), 9) for v in base_box],
        },
        "outputs": output_records,
    }
    (out_dir / "g21_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    print(f"cell_mm={cell_mm} grid_cells={grid['cells_xyz']} occupied={int(grid['occ'].sum())}")
    print(f"nodes={node_count} tets_organ={organ_tets.shape[0]} "
          f"tets_parenchyma={parenchyma_tets.shape[0]} tets_tumor={tumor_tets.shape[0]}")
    print(f"surface_triangles={provenance['counts']['surface_triangles_organ']} "
          f"total_mass_kg={total_mass_kg:.6f} base_nodes={int(base_mask.sum())}")
    print(f"keepout nodes_inside={int(inside.sum())} lattice_points={len(keep_points)}")
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
