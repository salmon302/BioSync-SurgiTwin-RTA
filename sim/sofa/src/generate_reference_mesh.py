# SPDX-License-Identifier: MIT
"""Deterministic generator for the G2.2 placeholder reference scene meshes.

Retired by task 2.2 slice 3: the scene now loads the G2.1 meshes from
prepare_g21_meshes.py, and this script refuses to run once
meshes/g21_provenance.json exists. It remains for reproducing the slice-1
placeholder block.

Emits four Gmsh 2.2 ASCII files under sim/sofa/src/meshes/:

* reference_organ.msh: structured tetrahedral block, the parenchymal organ
  volume placeholder until gate G2.1 exports real segmentation meshes.
* reference_organ_tumor.msh: same node list, only the tetrahedra whose
  centroid lies inside the tumor sphere (the stiffer subset).
* reference_organ_parenchyma.msh: same node list, the disjoint complement.
* vessel_keepout_centerline.msh: two-node line elements sampling the vascular
  keep-out centerline (scene geometry only, no material coupling).

Each grid cell is split into six tetrahedra around the cell diagonal, every
tetrahedron is checked for positive volume, and the tumor/parenchyma subsets
are asserted to partition the full tetrahedron list. No random input; the
output is byte-stable for a given script version.

Regenerate with:  python sim/sofa/src/generate_reference_mesh.py
"""

import pathlib

CELLS = (6, 6, 6)
SIZE = (0.04, 0.04, 0.04)  # meters, block centered on [0, SIZE]

# Tumor region: sphere whose interior tets become the stiffer subset.
TUMOR_CENTER = (0.02, 0.02, 0.02)
TUMOR_RADIUS = 0.007  # meters

# Vascular keep-out centerline: straight vessel segment beside the tumor.
CENTERLINE_START = (0.030, 0.0, 0.020)
CENTERLINE_END = (0.030, 0.04, 0.020)
CENTERLINE_POINTS = 9

# Six-tetrahedron split of a cell around the 000-111 diagonal.
CELL_TETS = (
    ((0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1)),
    ((0, 0, 0), (1, 1, 0), (0, 1, 0), (1, 1, 1)),
    ((0, 0, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)),
    ((0, 0, 0), (0, 1, 1), (0, 0, 1), (1, 1, 1)),
    ((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1)),
    ((0, 0, 0), (1, 0, 1), (1, 0, 0), (1, 1, 1)),
)

MESH_DIR = pathlib.Path(__file__).resolve().parent / "meshes"
OUTPUT = MESH_DIR / "reference_organ.msh"
OUTPUT_TUMOR = MESH_DIR / "reference_organ_tumor.msh"
OUTPUT_PARENCHYMA = MESH_DIR / "reference_organ_parenchyma.msh"
OUTPUT_CENTERLINE = MESH_DIR / "vessel_keepout_centerline.msh"


def node_id(i, j, k, nx, ny):
    return 1 + i + j * (nx + 1) + k * (nx + 1) * (ny + 1)


def signed_volume(a, b, c, d):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    wx, wy, wz = d[0] - a[0], d[1] - a[1], d[2] - a[2]
    det = ux * (vy * wz - vz * wy) - uy * (vx * wz - vz * wx) + uz * (vx * wy - vy * wx)
    return det / 6.0


def write_msh(path, positions, elements, elem_type):
    """Write a Gmsh 2.2 ASCII file. elements: list of node-id tuples."""
    lines = ["$MeshFormat", "2.2 0 8", "$EndMeshFormat", "$Nodes", str(len(positions))]
    for nid in sorted(positions):
        x, y, z = positions[nid]
        lines.append(f"{nid} {x:.9f} {y:.9f} {z:.9f}")
    lines += ["$EndNodes", "$Elements", str(len(elements))]
    for eid, elt in enumerate(elements, start=1):
        ids = " ".join(str(n) for n in elt)
        lines.append(f"{eid} {elem_type} 2 1 1 {ids}")
    lines.append("$EndElements")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def build_organ():
    nx, ny, nz = CELLS
    positions = {}
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                nid = node_id(i, j, k, nx, ny)
                positions[nid] = (
                    i * SIZE[0] / nx,
                    j * SIZE[1] / ny,
                    k * SIZE[2] / nz,
                )

    tetrahedra = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                corners = {}
                for (di, dj, dk) in {(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
                                     (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)}:
                    corners[(di, dj, dk)] = node_id(i + di, j + dj, k + dk, nx, ny)
                for cell_tet in CELL_TETS:
                    tet = [corners[c] for c in cell_tet]
                    pts = [positions[n] for n in tet]
                    if signed_volume(*pts) <= 0.0:
                        tet[2], tet[3] = tet[3], tet[2]
                    vol = signed_volume(*[positions[n] for n in tet])
                    if vol <= 0.0:
                        raise SystemExit(f"non-positive tetra volume at cell {i} {j} {k}")
                    tetrahedra.append(tuple(tet))
    return positions, tetrahedra


def split_tumor(positions, tetrahedra):
    tumor, parenchyma = [], []
    for tet in tetrahedra:
        pts = [positions[n] for n in tet]
        cx = sum(p[0] for p in pts) / 4.0
        cy = sum(p[1] for p in pts) / 4.0
        cz = sum(p[2] for p in pts) / 4.0
        dist2 = (cx - TUMOR_CENTER[0]) ** 2 + (cy - TUMOR_CENTER[1]) ** 2 + (
            cz - TUMOR_CENTER[2]) ** 2
        (tumor if dist2 <= TUMOR_RADIUS ** 2 else parenchyma).append(tet)
    if not tumor or not parenchyma:
        raise SystemExit(
            f"degenerate split: tumor={len(tumor)} parenchyma={len(parenchyma)}")
    if len(tumor) + len(parenchyma) != len(tetrahedra):
        raise SystemExit("subsets do not partition the full tetrahedron list")
    return tumor, parenchyma


def build_centerline():
    positions = {}
    for idx in range(CENTERLINE_POINTS):
        t = idx / (CENTERLINE_POINTS - 1)
        positions[idx + 1] = tuple(
            start + t * (end - start)
            for start, end in zip(CENTERLINE_START, CENTERLINE_END)
        )
    edges = [(n, n + 1) for n in range(1, CENTERLINE_POINTS)]
    return positions, edges


def main():
    if (MESH_DIR / "g21_provenance.json").exists():
        raise SystemExit(
            "meshes hold G2.1 output (g21_provenance.json); this placeholder "
            "generator is retired and would overwrite them")
    positions, tetrahedra = build_organ()
    tumor, parenchyma = split_tumor(positions, tetrahedra)
    center_positions, edges = build_centerline()

    write_msh(OUTPUT, positions, tetrahedra, 4)
    write_msh(OUTPUT_TUMOR, positions, tumor, 4)
    write_msh(OUTPUT_PARENCHYMA, positions, parenchyma, 4)
    write_msh(OUTPUT_CENTERLINE, center_positions, edges, 1)

    print(f"wrote {OUTPUT}")
    print(f"nodes={len(positions)} tetrahedra={len(tetrahedra)}")
    print(f"tumor_tetrahedra={len(tumor)} parenchyma_tetrahedra={len(parenchyma)}")
    print(f"centerline_points={len(center_positions)} centerline_edges={len(edges)}")


if __name__ == "__main__":
    main()
