# SPDX-License-Identifier: MIT
"""Tissue cutting topology for the task 2.3 slice 2 needle scene (SRS FR-MS-003).

Pure numpy. The SofaPython3 build in this repository does not bind the
TetrahedronSetTopologyModifier methods (see sim/sofa/README.md, cutting model),
so a cut is applied here to the organ state, and the SOFA scene is rebuilt from
the edited state in the next runSofa segment.

State dict keys (all numpy arrays):
* pos: (N, 3) current node positions (m)
* vel: (N, 3) node velocities (m/s)
* rest: (N, 3) reference (rest) node positions (m)
* tets: (T, 4) tetrahedra as node indices into pos, rest, vel
* base: (N,) boolean, true for nodes fixed by the base fixation

Release rule (documented in sim/sofa/README.md): the crossed tetrahedra are
removed together with their stored strain energy. The nodes of the neighbor
tetrahedra (sharing a node with a crossed tetrahedron, one ring) have their rest
positions reset to their current positions, so the strain in that neighborhood
is released to zero at the cut instant. The released energy is the
Neo-Hookean energy of the neighborhood before the reset, and it is recorded.
"""

import json

import numpy as np

SAMPLE_EPS = 1e-9


def tet_dets(pos, tets):
    v0 = pos[tets[:, 0]]
    e1 = pos[tets[:, 1]] - v0
    e2 = pos[tets[:, 2]] - v0
    e3 = pos[tets[:, 3]] - v0
    return np.einsum("ij,ij->i", np.cross(e1, e2), e3)


def tets_containing(points, pos, tets):
    """Boolean per tetrahedron: true when any of the points lies inside it (barycentric test)."""
    v0 = pos[tets[:, 0]]
    m = np.stack([pos[tets[:, 1]] - v0, pos[tets[:, 2]] - v0, pos[tets[:, 3]] - v0], axis=2)
    det = np.linalg.det(m)
    ok = np.abs(det) > 1e-30
    inv = np.zeros_like(m)
    inv[ok] = np.linalg.inv(m[ok])
    hit = np.zeros(len(tets), dtype=bool)
    for p in points:
        lam = np.einsum("tij,tj->ti", inv, p[None, :] - v0)
        inside = (lam >= -SAMPLE_EPS).all(axis=1) & (lam.sum(axis=1) <= 1.0 + SAMPLE_EPS) & ok
        hit |= inside
    return hit


def path_samples(p0, p1, count):
    """count points from p0 to p1, both ends included."""
    s = np.linspace(0.0, 1.0, count)
    return p0[None, :] + s[:, None] * (p1 - p0)[None, :]


def neohookean_energy(rest, pos, tets, mu, lam):
    """Per-tetrahedron compressible Neo-Hookean energy (J) with F = Ds Dm^-1."""
    dm = np.stack([rest[tets[:, 1]] - rest[tets[:, 0]], rest[tets[:, 2]] - rest[tets[:, 0]],
                   rest[tets[:, 3]] - rest[tets[:, 0]]], axis=2)
    ds = np.stack([pos[tets[:, 1]] - pos[tets[:, 0]], pos[tets[:, 2]] - pos[tets[:, 0]],
                   pos[tets[:, 3]] - pos[tets[:, 0]]], axis=2)
    dm_det = np.linalg.det(dm)
    f = ds @ np.linalg.inv(dm)
    j = np.linalg.det(f)
    i1 = np.einsum("tij,tij->t", f, f)
    vol = np.abs(dm_det) / 6.0
    log_j = np.log(np.maximum(j, 1e-12))
    w = 0.5 * mu * (i1 - 3.0) - mu * log_j + 0.5 * lam * log_j * log_j
    return w * vol


def faces_of(tets):
    faces = {}
    for t_index, tet in enumerate(tets):
        for drop in range(4):
            face = tuple(sorted(int(tet[k]) for k in range(4) if k != drop))
            faces.setdefault(face, []).append(t_index)
    return faces


def connected_components(tets):
    adj = [[] for _ in range(len(tets))]
    for owners in faces_of(tets).values():
        if len(owners) == 2:
            a, b = owners
            adj[a].append(b)
            adj[b].append(a)
    seen = np.zeros(len(tets), dtype=bool)
    count = 0
    for start in range(len(tets)):
        if seen[start]:
            continue
        count += 1
        stack = [start]
        seen[start] = True
        while stack:
            cur = stack.pop()
            for nxt in adj[cur]:
                if not seen[nxt]:
                    seen[nxt] = True
                    stack.append(nxt)
    return count


def check_integrity(state, orient_sign):
    """Topology and geometry checks after a cut. Returns (ok, dict of counts and failures)."""
    pos, rest, tets, base = state["pos"], state["rest"], state["tets"], state["base"]
    n = len(pos)
    failures = []
    valid_index = bool(tets.size == 0 or (tets.min() >= 0 and tets.max() < n))
    if not valid_index:
        failures.append("tetrahedron references a node outside the node array")
    distinct = bool(np.all([len(set(t)) == 4 for t in tets.tolist()])) if len(tets) else False
    if not distinct:
        failures.append("degenerate tetrahedron (repeated node)")
    referenced = np.zeros(n, dtype=bool)
    if len(tets):
        referenced[tets.reshape(-1)] = True
    orphans = int(np.count_nonzero(~referenced))
    if orphans:
        failures.append(f"{orphans} orphaned node(s) not referenced by any tetrahedron")
    finite = bool(np.isfinite(pos).all() and np.isfinite(rest).all() and np.isfinite(state["vel"]).all())
    if not finite:
        failures.append("non-finite node state")
    cur_det = tet_dets(pos, tets) if len(tets) else np.zeros(0)
    rest_det = tet_dets(rest, tets) if len(tets) else np.zeros(0)
    inverted_cur = int(np.count_nonzero(np.sign(cur_det) != orient_sign))
    inverted_rest = int(np.count_nonzero(np.sign(rest_det) != orient_sign))
    if inverted_cur:
        failures.append(f"{inverted_cur} tetrahedron(s) inverted in the current configuration")
    if inverted_rest:
        failures.append(f"{inverted_rest} tetrahedron(s) inverted in the rest configuration")
    faces = faces_of(tets) if len(tets) else {}
    over = sum(1 for owners in faces.values() if len(owners) > 2)
    if over:
        failures.append(f"{over} face(s) shared by more than two tetrahedra")
    boundary = sum(1 for owners in faces.values() if len(owners) == 1)
    if len(tets) and boundary == 0:
        failures.append("no boundary faces")
    components = connected_components(tets) if len(tets) else 0
    base_ok = bool(base.shape == (n,))
    if not base_ok:
        failures.append("base flag array size mismatch")
    counts = {
        "nodes": int(n),
        "tetrahedra": int(len(tets)),
        "boundary_faces": int(boundary),
        "orphan_nodes": orphans,
        "inverted_current": inverted_cur,
        "inverted_rest": inverted_rest,
        "non_manifold_faces": int(over),
        "connected_components": int(components),
        "min_det_current": float(np.min(np.sign(cur_det) * np.abs(cur_det))) if len(tets) else 0.0,
    }
    if components != 1 and len(tets):
        failures.append(f"tetrahedra form {components} disconnected components")
    return len(failures) == 0, {"counts": counts, "failures": failures}


def compact(state, keep_tets_mask):
    """Drop the tetrahedra not in keep_tets_mask, then renumber nodes and drop orphaned nodes."""
    tets = state["tets"][keep_tets_mask]
    used = np.zeros(len(state["pos"]), dtype=bool)
    used[tets.reshape(-1)] = True
    new_index = -np.ones(len(state["pos"]), dtype=np.int64)
    new_index[used] = np.arange(int(used.sum()))
    return {
        "pos": state["pos"][used],
        "vel": state["vel"][used],
        "rest": state["rest"][used],
        "tets": new_index[tets],
        "base": state["base"][used],
    }, int(np.count_nonzero(~used))


def apply_cut(state, crossed, orient_sign, mu, lam):
    """Remove the crossed tetrahedra, release the neighborhood strain, and check integrity.

    Returns (new_state, record). record holds the removed count, the neighborhood size,
    the released energy (J), the integrity result, and the pre and post counts.
    """
    tets = state["tets"]
    crossed = np.asarray(crossed, dtype=bool)
    if not crossed.any():
        raise ValueError("cut requested with no crossed tetrahedra")
    crossed_nodes = np.zeros(len(state["pos"]), dtype=bool)
    crossed_nodes[tets[crossed].reshape(-1)] = True
    neighbor = (~crossed) & crossed_nodes[tets].any(axis=1)
    neighbor_nodes = np.zeros(len(state["pos"]), dtype=bool)
    neighbor_nodes[tets[neighbor].reshape(-1)] = True
    energy_before = float(neohookean_energy(state["rest"], state["pos"], tets[neighbor], mu, lam).sum())
    removed_energy = float(neohookean_energy(state["rest"], state["pos"], tets[crossed], mu, lam).sum())

    rest = state["rest"].copy()
    rest[neighbor_nodes] = state["pos"][neighbor_nodes]
    staged = {"pos": state["pos"], "vel": state["vel"], "rest": rest, "tets": tets, "base": state["base"]}
    new_state, orphans_removed = compact(staged, ~crossed)
    energy_after = float(neohookean_energy(new_state["rest"], new_state["pos"],
                                           new_state["tets"][neighbor[~crossed]], mu, lam).sum())
    ok, integrity = check_integrity(new_state, orient_sign)
    total_before = float(neohookean_energy(state["rest"], state["pos"], tets[~crossed], mu, lam).sum())
    total_after = float(neohookean_energy(new_state["rest"], new_state["pos"], new_state["tets"], mu, lam).sum())
    record = {
        "total_energy_before_j": total_before,
        "total_energy_after_j": total_after,
        "total_energy_jump_j": total_after - total_before,
        "crossed_tetrahedra": int(crossed.sum()),
        "neighbor_tetrahedra": int(neighbor.sum()),
        "neighbor_nodes_reset": int(neighbor_nodes.sum()),
        "orphan_nodes_removed": orphans_removed,
        "removed_tet_energy_j": removed_energy,
        "neighborhood_energy_before_j": energy_before,
        "neighborhood_energy_after_j": energy_after,
        "released_energy_j": energy_before - energy_after,
        "integrity_ok": ok,
        "integrity": integrity,
        "nodes_before": int(len(state["pos"])),
        "tetrahedra_before": int(len(tets)),
    }
    return new_state, record


def save_state(path, state, extra):
    payload = {
        "pos": state["pos"].tolist(),
        "vel": state["vel"].tolist(),
        "rest": state["rest"].tolist(),
        "tets": state["tets"].tolist(),
        "base": state["base"].astype(int).tolist(),
    }
    payload.update(extra)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle)
        handle.write("\n")


def load_state(path):
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    state = {
        "pos": np.array(raw["pos"], dtype=float),
        "vel": np.array(raw["vel"], dtype=float),
        "rest": np.array(raw["rest"], dtype=float),
        "tets": np.array(raw["tets"], dtype=np.int64),
        "base": np.array(raw["base"], dtype=bool),
    }
    extra = {k: v for k, v in raw.items() if k not in state_keys()}
    return state, extra


def state_keys():
    return ("pos", "vel", "rest", "tets", "base")
