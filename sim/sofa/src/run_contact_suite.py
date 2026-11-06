# SPDX-License-Identifier: MIT
"""Parameterized contact and cutting suite for the task 2.3 needle scene (SRS FR-MS-003).

Runs contact_scene.py through runSofa with the SofaPython3 plugin. A trial is a
chain of segments: a segment ends at a cut (runSofa exit code 10), the driver
applies the cut to the organ state (sim/sofa/src/cut_topology.py), and the next
segment resumes from the edited state at the next tick.

Per-trial checks:

* contact_detected: at least one contact step.
* zero_tunneling: no step has the tip inside the organ with zero contact points.
* zero_missed_contacts: no tool point has a full-boundary swept hit without a
  contact record at that tick.
* finite_wrench: every value in the bridge capture is finite, and the wrench is
  finite and non-zero on every contact step.
* topology_integrity: every cut passes cut_topology.check_integrity (no inverted,
  orphaned, non-manifold, or disconnected elements), the driver's crossed set
  matches the scene's crossed set, and the mesh stays valid through the trial.
* capture_schema: the exact header, consecutive ticks from 0 across all segments,
  row count equal to the trial steps, time_s on the 1 kHz grid, unit quaternions,
  and finite values.
* wrench_continuity: a capture row exists for every tick through every cut, and
  the wrench is finite on both sides of each cut.
* culling_reduction: the culled triangle set is smaller than the full boundary in
  every segment.

Pilot (this slice): 100 trials, the grid of 10 speeds, 5 entry angles, and 2
entry points. This validates the harness and the checks. The 1000-trial gate
run (G2.3) is a separate package.

Runtime: the SofaPython3 plugin is built for CPython 3.12. The scene runs under
the pinned conda-forge CPython 3.12.16 in the repository's pixi default
environment (env/ros2-jazzy/pixi.lock) through PATH and PYTHONPATH. No file under
env/ is changed.

Usage (from the repository root):
    python sim/sofa/src/run_contact_suite.py --label <label> [--limit N] [--workers N]
"""

import argparse
import csv
import datetime
import json
import math
import os
import pathlib
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
PIXI_ENV = pathlib.Path(os.environ.get(
    "SRTA_SOFAPY_ENV", str(REPO / "env" / "ros2-jazzy" / ".pixi" / "envs" / "default")))
# numpy linalg loads its delay-loaded DLLs from PATH at call time, so the pixi
# library directory is put first before any linalg call in this process.
os.environ["PATH"] = f"{PIXI_ENV};{PIXI_ENV / 'Library' / 'bin'};" + os.environ.get("PATH", "")

import numpy as np  # noqa: E402

sys.path.insert(0, str(HERE))
import cut_topology  # noqa: E402

SCENE = HERE / "contact_scene.py"
MESH = HERE / "meshes" / "reference_organ.msh"
LOG_DIR = REPO / "SNDEV" / "logs"
SOFA_ROOT = pathlib.Path(os.environ.get("SRTA_SOFA_ROOT", r"C:\Users\salmo\SOFA\v26.06.00"))
RUN_SOFA = SOFA_ROOT / "collections" / "bin" / "runSofa.exe"
CUT_EXIT_CODE = 10
CUT_SAMPLES = 9
DT = 0.001
RATE_HZ = 1000
HOLD_STEPS = 500
DEPTH_MM = 8.0
CLEARANCE_MM = 30.0
SPEEDS_MM_S = [10, 20, 40, 60, 80, 100, 120, 150, 180, 200]
ANGLES_DEG = [0.0, 10.0, 15.0, 20.0, 30.0]
ENTRY_OFFSETS_MM = [(0.0, 0.0, 0.0), (0.0, 0.0, 3.0)]
MAX_SEGMENTS = 200
BRIDGE_HEADER = [
    "tick", "time_s", "pos_x", "pos_y", "pos_z",
    "quat_x", "quat_y", "quat_z", "quat_w",
    "force_x", "force_y", "force_z", "torque_x", "torque_y", "torque_z",
    "mode_0",
]
DIAG_HEADER = [
    "tick", "time_s", "contact_points", "contact_force_n", "puncture_force_n", "depth_m",
    "inside", "tip_x", "tip_y", "tip_z", "mesh_tip_x", "mesh_tip_y", "mesh_tip_z",
    "organ_top_y", "swept_hits", "full_swept_points", "missed_points", "crossed_tets", "cut_requested",
]
CHECKS = [
    "contact_detected", "zero_tunneling", "zero_missed_contacts", "finite_wrench",
    "topology_integrity", "capture_schema", "wrench_continuity", "culling_reduction", "exit_clean",
]

# Calibrated and placeholder constants. Sources and status are in sim/sofa/README.md.
CALIBRATION = {
    "puncture_k_perp": 430.0,
    "puncture_anisotropy": 2.0,
    "contact_stiffness": 100.0,
    "contact_damping": 0.5,
    "contact_m": 0.0005,
    "fracture_toughness_j_m2": 164.0,
    "cut_width_m": 0.001,
    "cut_min_depth_mm": 1.0,
    "release_rings": 1,
    "mu_pa": 1785.714286,
    "lambda_pa": 7142.857143,
}
CALIBRATION["cut_force_n"] = CALIBRATION["fracture_toughness_j_m2"] * CALIBRATION["cut_width_m"]


def base_config():
    return {
        "mesh_path": str(MESH),
        "dt": DT,
        "gravity": 0.0,
        "total_mass_kg": 1.64,
        "pcg_iterations": 25,
        "clearance_mm": CLEARANCE_MM,
        "depth_mm": DEPTH_MM,
        "contact_stiffness": CALIBRATION["contact_stiffness"],
        "contact_damping": CALIBRATION["contact_damping"],
        "contact_m": CALIBRATION["contact_m"],
        "puncture_k_perp": CALIBRATION["puncture_k_perp"],
        "puncture_anisotropy": CALIBRATION["puncture_anisotropy"],
        "fiber_dir": [1.0, 0.0, 0.0],
        "puncture_nodes": 4,
        "shaft_radius_m": 0.0005,
        "cone_half_deg": 15.0,
        "shaft_length_m": 0.04,
        "tool_segments": 8,
        "corridor_mm": 12.0,
        "ring_k": 3,
        "cut_enabled": True,
        "cut_min_depth_mm": CALIBRATION["cut_min_depth_mm"],
        "cut_force_n": CALIBRATION["cut_force_n"],
    }


def quiet_host_snapshot():
    script = (
        "$p = Get-Process -Name Warhammer,Roblox,runSofa,colcon,Slicer -ErrorAction SilentlyContinue | "
        "ForEach-Object { $_.Name }; "
        "$c = (Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples 3)"
        ".CounterSamples | ForEach-Object { [math]::Round($_.CookedValue,1) }; "
        "[pscustomobject]@{ busy_processes = @($p); cpu_percent_samples = @($c) } | ConvertTo-Json -Compress"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, check=False)
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"error": result.stderr.strip()[:200]}


def trial_plan(limit=None):
    plan = []
    travel_mm = CLEARANCE_MM + DEPTH_MM
    k = 0
    for speed in SPEEDS_MM_S:
        for angle in ANGLES_DEG:
            for entry in ENTRY_OFFSETS_MM:
                k += 1
                approach_steps = int(math.ceil(travel_mm / 1000.0 / (speed / 1000.0) / DT))
                plan.append({
                    "id": f"T{k:03d}",
                    "speed_mm_s": speed,
                    "angle_deg": angle,
                    "entry_offset_mm": list(entry),
                    "total_steps": approach_steps + HOLD_STEPS,
                    "approach_steps": approach_steps,
                })
    return plan[:limit] if limit else plan


def sofa_env():
    env = dict(os.environ)
    env["PATH"] = f"{PIXI_ENV};{PIXI_ENV / 'Library' / 'bin'};" + env.get("PATH", "")
    env["PYTHONPATH"] = f"{SOFA_ROOT / 'plugins' / 'SofaPython3' / 'lib' / 'python3' / 'site-packages'};" \
                        f"{SOFA_ROOT / 'collections' / 'bin'}"
    return env


def run_segment(out_dir, cfg, segment, total_steps, start_tick):
    cfg_path = out_dir / f"config_seg{segment:02d}.json"
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    env = sofa_env()
    env["SRTA_CONTACT_CONFIG"] = str(cfg_path)
    stdout_path = out_dir / f"runSofa_seg{segment:02d}.log"
    started = time.perf_counter()
    with stdout_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(
            [str(RUN_SOFA), "-l", "SofaPython3", str(SCENE), "-g", "batch", "-n",
             str(total_steps - start_tick)],
            cwd=str(out_dir), env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    wall = time.perf_counter() - started
    lines = stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()
    errors = [line for line in lines if "[ERROR]" in line and "readBasicIniFile" not in line]
    return proc.returncode, wall, errors


def run_trial(run_dir, trial):
    out_dir = run_dir / trial["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "trial": trial["id"],
        "speed_mm_s": trial["speed_mm_s"],
        "angle_deg": trial["angle_deg"],
        "entry_offset_mm": trial["entry_offset_mm"],
        "total_steps": trial["total_steps"],
        "segments": [],
        "cuts": [],
        "run_errors": [],
        "exit_codes": [],
        "wall_s": 0.0,
        "integrity_failures": [],
    }
    start_tick = 0
    resume = None
    checkpoint_in = None
    segment = 0
    while True:
        cfg = base_config()
        cfg.update({
            "speed_mm_s": trial["speed_mm_s"],
            "angle_deg": trial["angle_deg"],
            "entry_offset_m": [v * 1e-3 for v in trial["entry_offset_mm"]],
            "total_steps": trial["total_steps"],
            "out_dir": str(out_dir),
            "resume": resume,
            "checkpoint_in": checkpoint_in,
        })
        rc, wall, errors = run_segment(out_dir, cfg, segment, trial["total_steps"], start_tick)
        result["exit_codes"].append(rc)
        result["wall_s"] += wall
        result["run_errors"].extend(errors)
        build_path = out_dir / f"scene_build_seg{segment:02d}.json"
        if build_path.exists():
            result["segments"].append(json.loads(build_path.read_text(encoding="utf-8")))
        if rc == 0:
            break
        if rc != CUT_EXIT_CODE or segment >= MAX_SEGMENTS:
            break
        cut_result = apply_checkpoint_cut(out_dir, segment)
        result["cuts"].append(cut_result["record"])
        if not cut_result["ok"]:
            result["integrity_failures"].append({"segment": segment, "failures": cut_result["record"]})
            break
        resume = cut_result["extra"]
        start_tick = int(resume["tick_next"])
        checkpoint_in = cut_result["path"]
        segment += 1
    result["concatenated"] = concatenate(out_dir)
    return result


def apply_checkpoint_cut(out_dir, segment):
    state, extra = cut_topology.load_state(str(out_dir / "checkpoint.json"))
    scene_crossed = np.zeros(len(state["tets"]), dtype=bool)
    scene_crossed[np.array(extra["crossed"], dtype=np.int64)] = True
    path = cut_topology.path_samples(np.array(extra["cut_path_start"], dtype=float),
                                     np.array(extra["cut_path_end"], dtype=float), CUT_SAMPLES)
    driver_crossed = cut_topology.tets_containing(path, state["pos"], state["tets"])
    crossed_match = bool(np.array_equal(driver_crossed, scene_crossed))
    cut_state, record = cut_topology.apply_cut(
        state, scene_crossed, extra["orient_sign"],
        CALIBRATION["mu_pa"], CALIBRATION["lambda_pa"])
    record.update({
        "segment": segment,
        "cut_tick": int(extra["cut_tick"]),
        "depth_m": extra["cut_depth_m"],
        "force_n": extra["cut_force_n"],
        "crossed_match": crossed_match,
    })
    if not crossed_match:
        record["integrity_ok"] = False
        record["integrity"]["failures"].append("scene and driver crossed sets differ")
    new_path = out_dir / f"checkpoint_in_seg{segment + 1:02d}.json"
    cut_topology.save_state(str(new_path), cut_state, extra)
    return {"ok": bool(record["integrity_ok"]), "record": record, "extra": extra, "path": str(new_path)}


def concatenate(out_dir):
    segs = sorted(out_dir.glob("bridge_capture_seg*.csv"))
    diag_segs = sorted(out_dir.glob("diagnostics_seg*.csv"))
    bridge_lines = []
    for path in segs:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not bridge_lines:
            bridge_lines.append(lines[0])
        bridge_lines.extend(lines[1:])
    diag_lines = []
    for path in diag_segs:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not diag_lines:
            diag_lines.append(lines[0])
        diag_lines.extend(lines[1:])
    (out_dir / "bridge_capture.csv").write_text("\n".join(bridge_lines) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "diagnostics.csv").write_text("\n".join(diag_lines) + "\n", encoding="utf-8", newline="\n")
    return {"segments": len(segs), "bridge_rows": len(bridge_lines) - 1, "diag_rows": len(diag_lines) - 1}


def check_trial(trial, result, out_dir):
    with (out_dir / "bridge_capture.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        bridge_rows = list(reader)
    with (out_dir / "diagnostics.csv").open("r", encoding="utf-8", newline="") as handle:
        diag = list(csv.DictReader(handle))

    failures = {}
    values = np.array([[float(v) for v in r[1:16]] for r in bridge_rows])
    ticks = [int(r[0]) for r in bridge_rows]
    quat = np.array([[float(v) for v in r[5:9]] for r in bridge_rows])
    finite_all = bool(np.all(np.isfinite(values)))
    schema_ok = header == BRIDGE_HEADER and ticks == list(range(len(bridge_rows))) \
        and len(bridge_rows) == trial["total_steps"]
    time_ok = all(abs(float(r[1]) - int(r[0]) / RATE_HZ) <= 1e-6 for r in bridge_rows)
    quat_ok = bool(np.all(np.abs(np.linalg.norm(quat, axis=1) - 1.0) <= 1e-6))
    schema_ok = schema_ok and time_ok and quat_ok and finite_all

    contact_steps = [i for i, row in enumerate(diag) if int(row["contact_points"]) > 0]
    tunneling = [i for i, row in enumerate(diag) if int(row["inside"]) == 1 and int(row["contact_points"]) == 0]
    missed = [i for i, row in enumerate(diag) if int(row["missed_points"]) > 0]
    wrench = np.array([[float(v) for v in r[9:12]] + [float(v) for v in r[12:15]] for r in bridge_rows])
    force_norm = np.linalg.norm(wrench[:, :3], axis=1)
    wrench_contact_ok = bool(contact_steps) and all(
        np.isfinite(wrench[i]).all() and force_norm[i] > 0.0 for i in contact_steps)
    finite_wrench = bool(np.isfinite(wrench).all()) and wrench_contact_ok

    cut_ticks = [c["cut_tick"] for c in result["cuts"]]
    cut_integrity_ok = all(c["integrity_ok"] for c in result["cuts"]) and not result["integrity_failures"]
    crossed_ok = all(c["crossed_tetrahedra"] > 0 for c in result["cuts"])
    continuity_ok = all(
        (t + 1) < len(bridge_rows) and np.isfinite(wrench[t]).all() and np.isfinite(wrench[t + 1]).all()
        for t in cut_ticks)
    step_changes = [float(np.linalg.norm(wrench[t + 1, :3] - wrench[t, :3])) for t in cut_ticks
                    if t + 1 < len(bridge_rows)]
    culling_ok = bool(result["segments"]) and all(
        s["surface_triangles_culled"] < s["surface_triangles_full"] for s in result["segments"])
    exit_ok = bool(result["exit_codes"]) and result["exit_codes"][-1] == 0 and not result["run_errors"]

    failures["contact_detected"] = not contact_steps
    failures["zero_tunneling"] = len(tunneling)
    failures["zero_missed_contacts"] = sum(int(row["missed_points"]) for row in diag)
    failures["finite_wrench"] = not finite_wrench
    failures["topology_integrity"] = not cut_integrity_ok
    failures["capture_schema"] = not schema_ok
    failures["wrench_continuity"] = not continuity_ok
    failures["culling_reduction"] = not culling_ok
    failures["exit_clean"] = not exit_ok

    checks = {
        "contact_detected": not failures["contact_detected"],
        "zero_tunneling": failures["zero_tunneling"] == 0,
        "zero_missed_contacts": failures["zero_missed_contacts"] == 0,
        "finite_wrench": not failures["finite_wrench"],
        "topology_integrity": not failures["topology_integrity"],
        "capture_schema": not failures["capture_schema"],
        "wrench_continuity": not failures["wrench_continuity"],
        "culling_reduction": not failures["culling_reduction"],
        "exit_clean": not failures["exit_clean"],
    }
    first_contact = contact_steps[0] if contact_steps else None
    evidence = {
        "tunneling_steps": [int(i) for i in tunneling[:5]],
        "missed_steps": [{"tick": int(diag[i]["tick"]), "missed_points": int(diag[i]["missed_points"])}
                         for i in missed[:5]],
        "cut_ticks": cut_ticks,
        "integrity_failures": result["integrity_failures"][:3],
        "step_change_at_cut_n": [round(x, 6) for x in step_changes],
    }
    summary = {
        "trial": trial["id"],
        "speed_mm_s": trial["speed_mm_s"],
        "angle_deg": trial["angle_deg"],
        "entry_offset_mm": trial["entry_offset_mm"],
        "total_steps": trial["total_steps"],
        "approach_steps": trial["approach_steps"],
        "segments": len(result["segments"]),
        "cuts": len(result["cuts"]),
        "crossed_tetrahedra_total": int(sum(c["crossed_tetrahedra"] for c in result["cuts"])),
        "released_energy_j_total": float(sum(c["released_energy_j"] for c in result["cuts"])),
        "first_contact_step": first_contact,
        "contact_steps": len(contact_steps),
        "tunneling_steps": len(tunneling),
        "missed_points_total": failures["zero_missed_contacts"],
        "inside_steps": sum(int(row["inside"]) for row in diag),
        "peak_contact_force_n": round(max((float(diag[i]["contact_force_n"]) for i in contact_steps),
                                          default=0.0), 6),
        "peak_puncture_force_n": round(max(float(r["puncture_force_n"]) for r in diag), 6),
        "wall_s": round(result["wall_s"], 3),
        "exit_codes": result["exit_codes"],
        "checks": checks,
        "evidence": evidence,
        "passed": all(checks.values()),
    }
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default=None, help="run label (default: UTC timestamp)")
    parser.add_argument("--limit", type=int, default=None, help="run only the first N trials of the grid")
    parser.add_argument("--workers", type=int, default=3, help="trials run in parallel")
    args = parser.parse_args(argv)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = args.label or stamp
    run_dir = LOG_DIR / f"task23-cut-{label}"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot = quiet_host_snapshot()
    plan = trial_plan(args.limit)

    def work(trial):
        raw = run_trial(run_dir, trial)
        summary = check_trial(trial, raw, run_dir / trial["id"])
        summary["run_errors"] = raw["run_errors"][:5]
        print(f"{trial['id']} speed={trial['speed_mm_s']} angle={trial['angle_deg']} "
              f"entry={trial['entry_offset_mm'][2]} cuts={summary['cuts']} "
              f"tunneling={summary['tunneling_steps']} missed={summary['missed_points_total']} "
              f"passed={summary['passed']}", flush=True)
        return summary

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(work, plan))

    check_counts = {}
    for name in CHECKS:
        check_counts[name] = {"pass": sum(1 for r in results if r["checks"][name]),
                              "fail": sum(1 for r in results if not r["checks"][name])}
    summary = {
        "schema": "task23-cut-pilot-v1",
        "label": label,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dt_s": DT,
        "rate_hz": RATE_HZ,
        "hold_steps": HOLD_STEPS,
        "depth_mm": DEPTH_MM,
        "clearance_mm": CLEARANCE_MM,
        "speeds_mm_s": SPEEDS_MM_S,
        "angles_deg": ANGLES_DEG,
        "entry_offsets_mm": ENTRY_OFFSETS_MM,
        "calibration": CALIBRATION,
        "quiet_host_before": snapshot,
        "trials_total": len(results),
        "trials_passed": sum(1 for r in results if r["passed"]),
        "check_counts": check_counts,
        "cuts_total": sum(r["cuts"] for r in results),
        "tunneling_steps_total": sum(r["tunneling_steps"] for r in results),
        "missed_points_total": sum(r["missed_points_total"] for r in results),
        "trials": results,
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
