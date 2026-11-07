# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: SofaPython3 worker scene for the mechanical FMU (plan task 2.7 slice 2)
# Date: 2026-11-07T09:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.7 slice 2
# Summary: Runs the SOFA reference organ (parameters of sim/sofa/src/reference_scene.scn) under runSofa with SofaPython3, applies a tip-to-node penalty coupling, and advances one solver step per command read from a named pipe (FMU) or from a scripted command list (standalone reference run).
"""SOFA worker scene for the mechanical FMU (SRS FR-MS-002/FR-MS-007, plan task 2.7 slice 2).

Loaded by runSofa with `-l SofaPython3`. The environment variable SRTA_MECH_CONFIG names a JSON file:

  mesh_path                absolute path of reference_organ.msh (the pinned 20 mm budget-fit mesh)
  transport                "pipe" (FMU) or "script" (standalone reference run)
  pipe_path                named pipe path, for transport "pipe"
  commands                 list of command lines, for transport "script"
  results_path            script mode: JSON list of the replies, written at QUIT
  tool_stiffness_n_per_m   penalty stiffness of the tip-to-node coupling (default 2000)
  initial_tip_m            tip position before the first command (used only for the echo default)
  dump_steps               step counts after which positions are written to dump_dir
  dump_dir                 directory for position dumps

Protocol (one line per message, ASCII). Every STEP command produces exactly one reply after its solver step.
  command  "STEP tx ty tz qx qy qz qw"   apply the tip pose and advance one solver step (dt 0.001 s)
  command  "QUIT"                        end the worker
  reply    "OK fx fy fz tx ty tz max_disp_m mean_disp_m tip_node_disp_m steps"   after each step
  reply    "ERR message"                 on a malformed command; the worker then exits with status 3.
A reset is a worker restart (the FMU starts a new worker), because a SOFA step cannot be skipped.

Organ parameters follow sim/sofa/src/reference_scene.scn: gravity -9.81 along y, dt 0.001, mass
1.640000 kg, EulerImplicitSolver (rayleighMass 0.1, rayleighStiffness 0.1), PCG with 25 iterations and
tolerance 1e-9, base fixation box (-0.0005, -0.0005, -0.0005) to (0.2005, 0.0005, 0.1805), and the
parenchyma NeoHookean ParameterSet 1785.714286 7142.857143.

Tool coupling: the force on the organ node is k (tip - x_node). The force on the tool is k (x_node - tip),
and the torque is zero (point coupling). Cut events are not handled here (see the FMU README).

The controller keeps its Python state in one plain object (_Runtime). Assigning ad hoc attributes to a
SOFA object from Python crashed the SofaPython3 binding in the probe, so the controller does not do it.
"""

import json
import os

import numpy as np
import Sofa

PLUGINS = [
    "Sofa.Component.AnimationLoop",
    "Sofa.Component.Constraint.Projective",
    "Sofa.Component.Engine.Select",
    "Sofa.Component.IO.Mesh",
    "Sofa.Component.LinearSolver.Iterative",
    "Sofa.Component.Mass",
    "Sofa.Component.MechanicalLoad",
    "Sofa.Component.ODESolver.Backward",
    "Sofa.Component.Playback",
    "Sofa.Component.SolidMechanics.FEM.HyperElastic",
    "Sofa.Component.StateContainer",
    "Sofa.Component.Topology.Container.Dynamic",
    "Sofa.Component.Visual",
]

DT = 0.001
GRAVITY = -9.81
TOTAL_MASS_KG = 1.640000
PARENCHYMA_PARAMETERS = "1785.714286 7142.857143"
BASE_BOX_MIN = np.array([-0.0005, -0.0005, -0.0005])
BASE_BOX_MAX = np.array([0.2005, 0.0005, 0.1805])
DEFAULT_TOOL_STIFFNESS = 2000.0


def load_config():
    with open(os.environ["SRTA_MECH_CONFIG"], "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def base_indices(positions):
    inside = np.all((positions >= BASE_BOX_MIN - 1e-12) & (positions <= BASE_BOX_MAX + 1e-12), axis=1)
    return np.nonzero(inside)[0].tolist()


def coupling_node(positions):
    top_y = positions[:, 1].max()
    top = np.nonzero(positions[:, 1] >= top_y - 1e-6)[0]
    center = positions[top][:, [0, 2]].mean(axis=0)
    distance = np.linalg.norm(positions[top][:, [0, 2]] - center, axis=1)
    return int(top[int(np.argmin(distance))])


class _Runtime:
    """Plain Python state of the controller."""

    def __init__(self, cfg, state, cff, initial_positions, node):
        self.cfg = cfg
        self.state = state
        self.cff = cff
        self.initial_positions = initial_positions
        self.node = node
        self.k = float(cfg.get("tool_stiffness_n_per_m", DEFAULT_TOOL_STIFFNESS))
        self.tip = np.array(cfg["initial_tip_m"], dtype=float)
        self.steps = 0
        self.stepping = False
        self.replies = []
        self.dump_steps = sorted(int(s) for s in cfg.get("dump_steps", []))
        self.pipe = None
        self.script = []
        self.script_index = 0
        if cfg["transport"] == "pipe":
            self.pipe = open(cfg["pipe_path"], "r+b")
        else:
            self.script = list(cfg.get("commands", []))


class MechanicalController(Sofa.Core.Controller):
    """Advances one solver step per command. Python state lives in self.rt (see _Runtime)."""

    def __init__(self, *args, **kwargs):
        rt = _Runtime(kwargs.pop("cfg"), kwargs.pop("state"), kwargs.pop("cff"),
                      kwargs.pop("initial_positions"), kwargs.pop("node"))
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "rt", rt)

    def _read_command(self, rt):
        if rt.pipe is not None:
            line = rt.pipe.readline()
            if not line:
                return "QUIT"
            return line.decode("ascii").strip()
        if rt.script_index >= len(rt.script):
            return "QUIT"
        command = rt.script[rt.script_index]
        rt.script_index += 1
        return command

    def _reply(self, rt, text):
        if rt.pipe is not None:
            rt.pipe.write((text + "\n").encode("ascii"))
            rt.pipe.flush()
        else:
            rt.replies.append(text)

    def _fail(self, rt, text):
        self._reply(rt, "ERR " + text)
        if rt.pipe is not None:
            rt.pipe.close()
        os._exit(3)

    def onAnimateBeginEvent(self, event):
        rt = self.rt
        command = self._read_command(rt)
        parts = command.split()
        if not parts:
            self._fail(rt, "empty command")
        if parts[0] == "QUIT":
            if rt.pipe is not None:
                rt.pipe.close()
            else:
                with open(rt.cfg["results_path"], "w", encoding="utf-8") as handle:
                    json.dump(rt.replies, handle)
            os._exit(0)
        if parts[0] != "STEP" or len(parts) != 8:
            self._fail(rt, "malformed command: " + command[:120])
        try:
            values = np.array([float(v) for v in parts[1:]], dtype=float)
        except ValueError:
            self._fail(rt, "non-numeric STEP value")
        if not np.all(np.isfinite(values)):
            self._fail(rt, "non-finite STEP value")
        rt.tip = values[0:3]
        positions = np.array(rt.state.position.value, dtype=float)
        rt.cff.forces.value = [(rt.k * (rt.tip - positions[rt.node])).tolist()]
        rt.stepping = True

    def onAnimateEndEvent(self, event):
        rt = self.rt
        if not rt.stepping:
            return
        rt.stepping = False
        rt.steps += 1
        positions = np.array(rt.state.position.value, dtype=float)
        disp = positions - rt.initial_positions
        norms = np.linalg.norm(disp, axis=1)
        force_on_tool = rt.k * (positions[rt.node] - rt.tip)
        self._reply(rt, "OK {:.12e} {:.12e} {:.12e} 0 0 0 {:.12e} {:.12e} {:.12e} {}".format(
            force_on_tool[0], force_on_tool[1], force_on_tool[2],
            float(norms.max()), float(norms.mean()), float(norms[rt.node]), rt.steps))
        if rt.steps in rt.dump_steps:
            path = os.path.join(rt.cfg["dump_dir"], f"positions_step{rt.steps:06d}.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"steps": rt.steps, "positions": positions.tolist()}, handle)


def createScene(root):
    cfg = load_config()
    root.gravity = [0.0, GRAVITY, 0.0]
    root.dt = DT
    root.addObject("RequiredPlugin", pluginName=PLUGINS)
    root.addObject("DefaultAnimationLoop", name="animationLoop")

    organ = root.addChild("ReferenceOrgan")
    loader = organ.addObject("MeshGmshLoader", name="organLoader", filename=cfg["mesh_path"])
    positions = np.array(loader.position.value, dtype=float)
    tets = np.array(loader.tetrahedra.value, dtype=np.int64)
    organ.addObject("TetrahedronSetTopologyContainer", name="organTopology",
                    position=positions.tolist(), tetrahedra=tets.tolist())
    organ.addObject("TetrahedronSetGeometryAlgorithms", template="Vec3d", name="organGeometry")
    state = organ.addObject("MechanicalObject", name="organState", template="Vec3d",
                            position=positions.tolist(), velocity=np.zeros_like(positions).tolist(),
                            rest_position=positions.tolist())
    organ.addObject("MeshMatrixMass", name="organMass", totalMass=TOTAL_MASS_KG)
    organ.addObject("EulerImplicitSolver", name="implicitSolver", rayleighMass=0.1, rayleighStiffness=0.1)
    organ.addObject("PCGLinearSolver", name="linearSolver", iterations=25, tolerance=1e-9)
    organ.addObject("FixedProjectiveConstraint", name="baseFixed", indices=base_indices(positions))
    parenchyma = organ.addChild("Parenchyma")
    parenchyma.addObject("TetrahedronHyperelasticityFEMForceField", name="parenchymaMaterial",
                         materialName="NeoHookean", ParameterSet=PARENCHYMA_PARAMETERS)

    node = coupling_node(positions)
    cff = organ.addObject("ConstantForceField", name="toolCoupling", indices=[node],
                          forces=[[0.0, 0.0, 0.0]])

    controller = MechanicalController(
        name="mechanicalController", cfg=cfg, state=state, cff=cff,
        initial_positions=positions.copy(), node=node)
    root.addObject(controller)
    return root
