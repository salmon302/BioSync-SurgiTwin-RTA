# SPDX-License-Identifier: MIT
"""Task 2.3 slice 1 tool-tissue contact scene (SRS FR-MS-003), SOFA Python scene.

Loaded by runSofa with `-l SofaPython3` (see sim/sofa/src/run_contact_suite.py).

The organ is the 20 mm budget-fit reference mesh (meshes/reference_organ.msh)
with the slice-1 parenchyma material, the EulerImplicitSolver + PCG chain (25
iterations), and the base fixation nodes (the y = 0 plane). The rigid needle is
a kinematic SOFA MechanicalObject (Rigid3d) with a triangulated surface, driven
along a scripted trajectory by the controller.

Contact is computed in the scene controller (ContactController), not by the SOFA
collision pipeline. The SOFA pipeline (CCDTightInclusionIntersection,
RuleBasedContactManager, TriangleCollisionModel) was configured in this build
and produced no contact response for the needle (see the slice log). The
controller implements the contact algorithm documented in
sim/sofa/README.md: corridor-culled candidates, a swept segment-triangle test
for each tool sample point, a penalty normal force with normal damping, and the
reaction distributed to organ nodes through a ConstantForceField with a fixed
index set.

Outputs written to <out_dir>:

* bridge_capture.csv: one row per tick in the sim/bridge/README.md replay
  capture schema (tick, time_s, pos, quat, force, torque, mode_0).
* diagnostics.csv: per-tick contact, puncture, depth, and inside-organ values.
* scene_build.json: culling counts and geometry values.

Gravity is a config key (the suite uses 0). The reference base fixation does
not hold the organ under gravity: with gravity on, the organ sinks through its
own fixed face (see the slice log), so the contact scene keeps the organ in its
undeformed shape.
"""

import json
import math
import os

import numpy as np
import Sofa

PLUGINS = [
    "Sofa.Component.AnimationLoop",
    "Sofa.Component.Constraint.Projective",
    "Sofa.Component.IO.Mesh",
    "Sofa.Component.LinearSolver.Iterative",
    "Sofa.Component.Mapping.Linear",
    "Sofa.Component.Mapping.NonLinear",
    "Sofa.Component.Mass",
    "Sofa.Component.MechanicalLoad",
    "Sofa.Component.ODESolver.Backward",
    "Sofa.Component.SolidMechanics.FEM.HyperElastic",
    "Sofa.Component.SolidMechanics.Spring",
    "Sofa.Component.StateContainer",
    "Sofa.Component.Topology.Container.Dynamic",
    "Sofa.Component.Visual",
]

BRIDGE_HEADER = [
    "tick", "time_s", "pos_x", "pos_y", "pos_z",
    "quat_x", "quat_y", "quat_z", "quat_w",
    "force_x", "force_y", "force_z", "torque_x", "torque_y", "torque_z",
    "mode_0",
]
DIAG_HEADER = [
    "tick", "time_s", "contact_points", "contact_force_n", "puncture_force_n", "depth_m",
    "inside", "tip_x", "tip_y", "tip_z", "mesh_tip_x", "mesh_tip_y", "mesh_tip_z",
    "organ_top_y", "swept_hits",
]


def load_config():
    with open(os.environ["SRTA_CONTACT_CONFIG"], "r", encoding="utf-8") as handle:
        return json.load(handle)


def boundary_triangles(tets, positions):
    """Boundary faces of the tet mesh, oriented outward (0-based node indices)."""
    faces = {}
    for tet in tets:
        for drop in range(4):
            face = tuple(sorted(tet[k] for k in range(4) if k != drop))
            faces.setdefault(face, []).append(tet[drop])
    tris = []
    for face, opposites in faces.items():
        if len(opposites) != 1:
            continue
        a, b, c = face
        opp = opposites[0]
        n = np.cross(positions[b] - positions[a], positions[c] - positions[a])
        if np.dot(n, positions[opp] - positions[a]) > 0.0:
            b, c = c, b
        tris.append((a, b, c))
    return np.array(tris, dtype=np.int64)


def vertex_adjacency(tris, count):
    adj = [set() for _ in range(count)]
    for a, b, c in tris:
        adj[a].update((b, c))
        adj[b].update((a, c))
        adj[c].update((a, b))
    return adj


def corridor_vertices(positions, start, end, radius, ring_k, adj):
    """Vertices within radius of the tool corridor segment, grown by ring_k adjacency rings."""
    seg = end - start
    length2 = float(np.dot(seg, seg))
    t = np.clip(((positions - start) @ seg) / length2, 0.0, 1.0)
    closest = start + t[:, None] * seg
    dist = np.linalg.norm(positions - closest, axis=1)
    keep = set(np.nonzero(dist <= radius)[0].tolist())
    frontier = set(keep)
    for _ in range(ring_k):
        nxt = set()
        for v in frontier:
            nxt.update(adj[v])
        nxt -= keep
        keep |= nxt
        frontier = nxt
    return keep


def rotation_quat(z_axis, target):
    """Unit quaternion (x, y, z, w) rotating unit vector z_axis onto unit vector target."""
    z_axis = z_axis / np.linalg.norm(z_axis)
    target = target / np.linalg.norm(target)
    dot = float(np.clip(np.dot(z_axis, target), -1.0, 1.0))
    if dot < -1.0 + 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0])
    axis = np.cross(z_axis, target)
    s = math.sqrt((1.0 + dot) * 2.0)
    q = np.array([axis[0] / s, axis[1] / s, axis[2] / s, s / 2.0])
    return q / np.linalg.norm(q)


def quat_rotate(q, v):
    x, y, z, w = q
    qv = np.array([x, y, z])
    t = 2.0 * np.cross(qv, v)
    return v + w * t + np.cross(qv, t)


def tool_geometry(shaft_radius, cone_half_deg, shaft_length, segments):
    """Tool surface in the tool frame: tip at the origin, shaft along +z."""
    cone_len = shaft_radius / math.tan(math.radians(cone_half_deg))
    pts = [np.zeros(3)]
    ring_cone, ring_shaft_base, ring_shaft_end = [], [], []
    for z, ring in ((cone_len, ring_cone), (cone_len, ring_shaft_base), (shaft_length, ring_shaft_end)):
        for k in range(segments):
            a = 2.0 * math.pi * k / segments
            pts.append(np.array([shaft_radius * math.cos(a), shaft_radius * math.sin(a), z]))
            ring.append(len(pts) - 1)
    tris = []
    for k in range(segments):
        k1 = (k + 1) % segments
        tris.append((0, ring_cone[k], ring_cone[k1]))
    for k in range(segments):
        k1 = (k + 1) % segments
        a0, a1 = ring_shaft_base[k], ring_shaft_base[k1]
        b0, b1 = ring_shaft_end[k], ring_shaft_end[k1]
        tris.append((a0, b0, b1))
        tris.append((a0, b1, a1))
    return np.array(pts), np.array(tris, dtype=np.int64), cone_len


def ray_parity(point, tris_pos, direction):
    v0 = tris_pos[:, 0]
    e1 = tris_pos[:, 1] - v0
    e2 = tris_pos[:, 2] - v0
    pvec = np.cross(direction, e2)
    det = np.einsum("ij,ij->i", e1, pvec)
    ok = np.abs(det) > 1e-14
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    tvec = point - v0
    u = np.einsum("ij,ij->i", tvec, pvec) * inv
    qvec = np.cross(tvec, e1)
    v = (qvec @ direction) * inv
    t = np.einsum("ij,ij->i", e2, qvec) * inv
    hit = ok & (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0) & (t > 1e-9)
    return int(np.count_nonzero(hit)) % 2 == 1


RAY_DIRECTIONS = [
    np.array([0.4123, 0.7418, 0.5298]) / np.linalg.norm([0.4123, 0.7418, 0.5298]),
    np.array([-0.6271, 0.2197, 0.7476]) / np.linalg.norm([-0.6271, 0.2197, 0.7476]),
    np.array([0.1834, -0.8123, 0.5553]) / np.linalg.norm([0.1834, -0.8123, 0.5553]),
]


def ray_inside(point, tris_pos):
    """Majority vote of ray-parity tests in three generic directions."""
    votes = sum(1 for direction in RAY_DIRECTIONS if ray_parity(point, tris_pos, direction))
    return votes >= 2


def segment_triangle_hits(p0, p1, tri_a, tri_b, tri_c):
    """Boolean per triangle: segment p0 to p1 crosses the triangle (Moeller-Trumbore, t in [0, 1])."""
    d = p1 - p0
    e1 = tri_b - tri_a
    e2 = tri_c - tri_a
    pvec = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, pvec)
    ok = np.abs(det) > 1e-14
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    tvec = p0 - tri_a
    u = np.einsum("ij,ij->i", tvec, pvec) * inv
    qvec = np.cross(tvec, e1)
    v = (qvec @ d) * inv
    t = np.einsum("ij,ij->i", e2, qvec) * inv
    return ok & (u >= 0.0) & (v >= 0.0) & (u + v <= 1.0) & (t >= 0.0) & (t <= 1.0)


def project_barycentric(points, tri_a, tri_b, tri_c, normals):
    """Signed distance to each triangle plane, projection barycentrics, inside flag (points x tris)."""
    diff = points[:, None, :] - tri_a[None, :, :]
    sd = np.einsum("ptk,tk->pt", diff, normals)
    proj = points[:, None, :] - sd[:, :, None] * normals[None, :, :]
    v0 = tri_b - tri_a
    v1 = tri_c - tri_a
    v2 = proj - tri_a[None, :, :]
    d00 = np.einsum("tk,tk->t", v0, v0)
    d01 = np.einsum("tk,tk->t", v0, v1)
    d11 = np.einsum("tk,tk->t", v1, v1)
    d20 = np.einsum("ptk,tk->pt", v2, v0)
    d21 = np.einsum("ptk,tk->pt", v2, v1)
    denom = d00 * d11 - d01 * d01
    denom = np.where(np.abs(denom) < 1e-18, 1e-18, denom)
    bv = (d11[None, :] * d20 - d01[None, :] * d21) / denom[None, :]
    bw = (d00[None, :] * d21 - d01[None, :] * d20) / denom[None, :]
    bu = 1.0 - bv - bw
    inside = (bu >= -1e-9) & (bv >= -1e-9) & (bw >= -1e-9)
    return sd, np.stack([bu, bv, bw], axis=-1), inside


class ContactController(Sofa.Core.Controller):
    def __init__(self, cfg, state, needle_rigid, needle_mesh, force_field, surface_tris, contact_tris,
                 contact_index_map, puncture_index_map, tool_local, start_tip, end_travel, d,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cfg = cfg
        self.state = state
        self.needle = needle_rigid
        self.needle_mesh = needle_mesh
        self.cff = force_field
        self.surface = surface_tris
        self.surface_full = surface_tris
        self.contact_tris = contact_tris
        self.cmap = contact_index_map
        self.pmap = puncture_index_map
        self.tool_local = tool_local
        self.dt = float(cfg["dt"])
        self.speed = float(cfg["speed_mm_s"]) * 1e-3
        self.start_tip = start_tip
        self.end_travel = end_travel
        self.d = d
        self.k = float(cfg["contact_stiffness"])
        self.c = float(cfg["contact_damping"])
        self.margin = float(cfg["contact_m"])
        self.puncture_k = float(cfg["puncture_k_perp"])
        self.anisotropy = float(cfg["puncture_anisotropy"])
        self.fiber = np.array(cfg["fiber_dir"], dtype=float)
        self.fiber = self.fiber / np.linalg.norm(self.fiber)
        self.app_nodes = int(cfg["puncture_nodes"])
        self.total_steps = int(cfg["total_steps"])
        self.out_dir = cfg["out_dir"]
        self.tick = 0
        self.last_inside = False
        self.entry = None
        self.depth = 0.0
        self.last_puncture = 0.0
        self.current_tip = np.array(start_tip, dtype=float)
        self.prev_pts = None
        self.contact_force = np.zeros(3)
        self.contact_torque = np.zeros(3)
        self.contact_points = 0
        self.swept_hits = 0
        self.rows = []
        self.diag = []
        self.q = rotation_quat(np.array([0.0, 0.0, 1.0]), -self.d)

    def tool_pose(self, tick):
        tau = tick * self.dt
        travel = min(self.speed * tau, self.end_travel)
        tip = self.start_tip + travel * self.d
        return tip, self.q, tau

    def onAnimateBeginEvent(self, event):
        tip, q, _ = self.tool_pose(self.tick)
        self.needle.position.value = [[tip[0], tip[1], tip[2], q[0], q[1], q[2], q[3]]]
        pts = tip[None, :] + np.array([quat_rotate(q, p) for p in self.tool_local])
        pos = np.array(self.state.position.value, dtype=float)
        self.compute_contact(pos, pts, tip)
        self.apply_puncture(tip, pos)
        forces = np.zeros((len(self.cmap["nodes"]), 3))
        self.add_contact_reaction(forces)
        pforces = self.puncture_reaction()
        for node, f in pforces.items():
            forces[self.cmap["index_of"][node]] += f
        self.cff.forces.value = forces.tolist()
        self.prev_pts = pts

    def compute_contact(self, pos, pts, tip):
        tris = pos[self.contact_tris]
        tri_a, tri_b, tri_c = tris[:, 0], tris[:, 1], tris[:, 2]
        normals = np.cross(tri_b - tri_a, tri_c - tri_a)
        norm = np.linalg.norm(normals, axis=1)
        normals = normals / np.maximum(norm, 1e-18)[:, None]
        sd, bary, inside_proj = project_barycentric(pts, tri_a, tri_b, tri_c, normals)
        active = inside_proj & (sd < self.margin)
        self.contact_points = 0
        self.swept_hits = 0
        self.contact_force = np.zeros(3)
        self.contact_torque = np.zeros(3)
        self.contact_records = []
        velocity = (pts - self.prev_pts) / self.dt if self.prev_pts is not None else np.zeros_like(pts)
        for i in range(pts.shape[0]):
            cand = active[i].copy()
            if self.prev_pts is not None:
                hits = segment_triangle_hits(self.prev_pts[i], pts[i], tri_a, tri_b, tri_c)
                if hits.any():
                    self.swept_hits += int(hits.sum())
                    cand = cand | hits
            if not cand.any():
                if not ray_inside(pts[i], pos[self.surface_full]):
                    continue
                cand = np.ones(len(normals), dtype=bool)
            idx = np.nonzero(cand)[0]
            t = idx[np.argmin(np.abs(sd[i, idx]))]
            n = normals[t]
            pen = self.margin - sd[i, t]
            if pen <= 0.0:
                pen = max(pen, 0.0)
            vn = float(np.dot(velocity[i], n))
            f_mag = self.k * pen - self.c * vn
            if f_mag <= 0.0:
                continue
            f = f_mag * n
            self.contact_force += f
            self.contact_torque += np.cross(pts[i] - tip, f)
            self.contact_points += 1
            self.contact_records.append((int(t), bary[i, t].tolist(), (-f).tolist()))

    def add_contact_reaction(self, forces):
        index_of = self.cmap["index_of"]
        for t, weights, f_neg in self.contact_records:
            tri = self.contact_tris[t]
            for node, w in zip(tri, weights):
                forces[index_of[int(node)]] += np.array(f_neg) * w

    def apply_puncture(self, tip, pos):
        if not self.last_inside or self.entry is None:
            self.last_puncture = 0.0
            return
        cosf = float(np.dot(self.d, self.fiber))
        sin2 = 1.0 - cosf * cosf
        k_eff = self.puncture_k * (sin2 + self.anisotropy * cosf * cosf)
        self.depth = max(float(np.dot(tip - self.entry, self.d)), 0.0)
        self.last_puncture = k_eff * self.depth

    def puncture_reaction(self):
        out = {}
        if self.last_puncture <= 0.0:
            return out
        share = self.d * self.last_puncture / self.app_nodes
        for node in self.pmap:
            out[node] = share
        return out

    def onAnimateEndEvent(self, event):
        tip, q, tau = self.tool_pose(self.tick)
        self.current_tip = tip
        pos = np.array(self.state.position.value, dtype=float)
        mesh_tip = np.array(self.needle_mesh.position.value, dtype=float)[0]
        inside = ray_inside(tip, pos[self.surface])
        if inside and not self.last_inside:
            self.entry = tip.copy()
        if not inside:
            self.entry = None
            self.depth = 0.0
        self.last_inside = inside

        f_tool = self.contact_force - self.last_puncture * self.d
        torque_tool = self.contact_torque
        self.rows.append([
            self.tick, f"{tau:.6f}",
            f"{tip[0]:.9f}", f"{tip[1]:.9f}", f"{tip[2]:.9f}",
            f"{q[0]:.9f}", f"{q[1]:.9f}", f"{q[2]:.9f}", f"{q[3]:.9f}",
            f"{f_tool[0]:.9f}", f"{f_tool[1]:.9f}", f"{f_tool[2]:.9f}",
            f"{torque_tool[0]:.9f}", f"{torque_tool[1]:.9f}", f"{torque_tool[2]:.9f}",
            "0.0",
        ])
        self.diag.append([
            self.tick, f"{tau:.6f}", self.contact_points,
            f"{float(np.linalg.norm(self.contact_force)):.9f}", f"{self.last_puncture:.9f}",
            f"{self.depth:.9f}", int(inside),
            f"{tip[0]:.9f}", f"{tip[1]:.9f}", f"{tip[2]:.9f}",
            f"{mesh_tip[0]:.9f}", f"{mesh_tip[1]:.9f}", f"{mesh_tip[2]:.9f}",
            f"{float(pos[:, 1].max()):.9f}", self.swept_hits,
        ])
        self.tick += 1
        if self.tick >= self.total_steps:
            self.flush()

    def flush(self):
        os.makedirs(self.out_dir, exist_ok=True)
        with open(os.path.join(self.out_dir, "bridge_capture.csv"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(",".join(BRIDGE_HEADER) + "\n")
            for row in self.rows:
                handle.write(",".join(str(v) for v in row) + "\n")
        with open(os.path.join(self.out_dir, "diagnostics.csv"), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(",".join(DIAG_HEADER) + "\n")
            for row in self.diag:
                handle.write(",".join(str(v) for v in row) + "\n")


def createScene(root):
    cfg = load_config()
    gravity = float(cfg.get("gravity", 0.0))
    root.gravity = [0.0, -gravity, 0.0]
    root.dt = float(cfg["dt"])
    root.addObject("RequiredPlugin", pluginName=PLUGINS)
    root.addObject("VisualStyle", displayFlags="showBehaviorModels showForceFields")
    root.addObject("DefaultAnimationLoop", name="animationLoop")

    organ = root.addChild("organ")
    loader = organ.addObject("MeshGmshLoader", name="organLoader", filename=cfg["mesh_path"])
    organ.addObject("TetrahedronSetTopologyContainer", name="organTopology", src="@organLoader")
    organ.addObject("TetrahedronSetGeometryAlgorithms", template="Vec3d", name="organGeometry")
    state = organ.addObject("MechanicalObject", name="organState", src="@organLoader")
    organ.addObject("MeshMatrixMass", name="organMass", totalMass=cfg["total_mass_kg"])
    organ.addObject("EulerImplicitSolver", name="implicitSolver", rayleighMass=0.1, rayleighStiffness=0.1)
    organ.addObject("PCGLinearSolver", name="linearSolver", iterations=int(cfg.get("pcg_iterations", 25)),
                    tolerance=1e-9)
    positions = np.array(loader.position.value, dtype=float)
    base_idx = np.nonzero(positions[:, 1] <= 1e-9)[0].tolist()
    organ.addObject("FixedProjectiveConstraint", name="baseFixed", indices=base_idx)
    parenchyma = organ.addChild("parenchyma")
    parenchyma.addObject("TetrahedronHyperelasticityFEMForceField", name="parenchymaMaterial",
                         materialName="NeoHookean", ParameterSet="1785.714286 7142.857143")

    tets = np.array(loader.tetrahedra.value, dtype=np.int64)
    all_tris = boundary_triangles(tets, positions)
    adj = vertex_adjacency(all_tris, len(positions))
    top_y = float(positions[:, 1].max())
    top_nodes = np.nonzero(positions[:, 1] >= top_y - 1e-6)[0]
    top_point = positions[top_nodes].mean(axis=0)
    puncture_nodes = np.argsort(np.linalg.norm(positions - top_point, axis=1))[: int(cfg["puncture_nodes"])].tolist()

    tool_local, tool_tris, cone_len = tool_geometry(
        float(cfg["shaft_radius_m"]), float(cfg["cone_half_deg"]),
        float(cfg["shaft_length_m"]), int(cfg["tool_segments"]))

    d = np.array([math.sin(math.radians(cfg["angle_deg"])), -math.cos(math.radians(cfg["angle_deg"])), 0.0])
    clearance = float(cfg["clearance_mm"]) * 1e-3
    depth_target = float(cfg["depth_mm"]) * 1e-3
    start_tip = top_point - clearance * d
    end_tip = top_point + depth_target * d
    end_travel = clearance + depth_target
    corridor = corridor_vertices(positions, start_tip, end_tip,
                                 float(cfg["corridor_mm"]) * 1e-3, int(cfg["ring_k"]), adj)
    culled_tris = all_tris[np.array([all(v in corridor for v in tri) for tri in all_tris], dtype=bool)]
    contact_nodes = sorted(set(int(v) for tri in culled_tris for v in tri))
    union_nodes = sorted(set(contact_nodes) | set(puncture_nodes))
    index_of = {node: k for k, node in enumerate(union_nodes)}
    cff = organ.addObject("ConstantForceField", name="contactAndPunctureReaction",
                          indices=union_nodes, forces=[[0.0, 0.0, 0.0]] * len(union_nodes))

    tool = root.addChild("tool")
    needle_rigid = tool.addObject("MechanicalObject", name="needleRigid", template="Rigid3d",
                                  position=[[start_tip[0], start_tip[1], start_tip[2], 0, 0, 0, 1]])
    tool_child = tool.addChild("needleSurface")
    needle_mesh = tool_child.addObject("MechanicalObject", name="needlePoints", template="Vec3d",
                                       position=tool_local.tolist())
    tool_child.addObject("RigidMapping", name="needleRigidMapping", template="Rigid3d,Vec3d",
                         input="@../needleRigid", output="@needlePoints", index=0)

    scene_build = {
        "surface_triangles_full": int(len(all_tris)),
        "surface_triangles_culled": int(len(culled_tris)),
        "corridor_vertices": int(len(corridor)),
        "contact_nodes": int(len(contact_nodes)),
        "puncture_nodes": int(len(puncture_nodes)),
        "vertices": int(len(positions)),
        "tets": int(len(tets)),
        "base_fixed_nodes": int(len(base_idx)),
        "tool_triangles": int(len(tool_tris)),
        "tool_points": int(len(tool_local)),
        "cone_length_m": cone_len,
        "organ_top_y_m": top_y,
        "top_point_m": top_point.tolist(),
        "start_tip_m": start_tip.tolist(),
        "end_tip_m": end_tip.tolist(),
        "candidate_pairs_full": int(len(all_tris) * len(tool_tris)),
        "candidate_pairs_culled": int(len(culled_tris) * len(tool_tris)),
        "gravity_m_s2": gravity,
    }
    os.makedirs(cfg["out_dir"], exist_ok=True)
    with open(os.path.join(cfg["out_dir"], "scene_build.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(scene_build, handle, indent=2)
        handle.write("\n")

    controller = ContactController(
        cfg, state, needle_rigid, needle_mesh, cff, all_tris, culled_tris,
        {"nodes": union_nodes, "index_of": index_of},
        puncture_nodes, tool_local, start_tip, end_travel, d,
        name="contactController")
    root.addObject(controller)
    return root
