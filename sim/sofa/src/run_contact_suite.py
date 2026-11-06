# SPDX-License-Identifier: MIT
"""Scripted smoke contact suite for the task 2.3 slice 1 needle scene (SRS FR-MS-003).

Runs contact_scene.py through runSofa with the SofaPython3 plugin, once per
trial, and checks each approach:

* contact is detected on at least one step,
* no tunneling: no step has the tool tip inside the organ with zero contact
  points (geometric post-run check on the per-step inside flag),
* wrench sanity: every contact step has a finite, non-zero tool wrench,
* the bridge capture follows the sim/bridge/README.md replay schema,
* culling reduces the collision candidates (static counts from scene_build.json).

This is a smoke suite, not the G2.3 gate suite (1000 trials, dissection and
cutting are slice 2).

Runtime: the SofaPython3 plugin is built for CPython 3.12. The interpreter is
the pinned conda-forge CPython 3.12.16 in the repository's pixi default
environment (env/ros2-jazzy/pixi.lock). It is used read-only through PATH and
PYTHONPATH, and no file under env/ is changed.

Usage:
    python sim/sofa/src/run_contact_suite.py
"""

import argparse
import csv
import datetime
import json
import math
import os
import pathlib
import subprocess
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCENE = HERE / "contact_scene.py"
MESH = HERE / "meshes" / "reference_organ.msh"
LOG_DIR = REPO / "SNDEV" / "logs"
SOFA_ROOT = pathlib.Path(os.environ.get("SRTA_SOFA_ROOT", r"C:\Users\salmo\SOFA\v26.06.00"))
RUN_SOFA = SOFA_ROOT / "collections" / "bin" / "runSofa.exe"
PIXI_ENV = pathlib.Path(os.environ.get(
    "SRTA_SOFAPY_ENV", str(REPO / "env" / "ros2-jazzy" / ".pixi" / "envs" / "default")))
DT = 0.001
RATE_HZ = 1000
HOLD_STEPS = 500
DEPTH_MM = 8.0
CLEARANCE_MM = 30.0
SPEEDS_MM_S = [10, 20, 40, 60, 80, 100, 120, 150, 180, 200]
ANGLES_DEG = [0.0, 15.0, 30.0]
BRIDGE_HEADER = [
    "tick", "time_s", "pos_x", "pos_y", "pos_z",
    "quat_x", "quat_y", "quat_z", "quat_w",
    "force_x", "force_y", "force_z", "torque_x", "torque_y", "torque_z",
    "mode_0",
]


def base_config():
    return {
        "mesh_path": str(MESH),
        "dt": DT,
        "gravity": 0.0,
        "total_mass_kg": 1.64,
        "pcg_iterations": 25,
        "clearance_mm": CLEARANCE_MM,
        "depth_mm": DEPTH_MM,
        "contact_stiffness": 100.0,
        "contact_damping": 0.5,
        "contact_m": 0.0005,
        "puncture_k_perp": 100.0,
        "puncture_anisotropy": 2.0,
        "fiber_dir": [1.0, 0.0, 0.0],
        "puncture_nodes": 4,
        "shaft_radius_m": 0.0005,
        "cone_half_deg": 15.0,
        "shaft_length_m": 0.04,
        "tool_segments": 8,
        "corridor_mm": 12.0,
        "ring_k": 3,
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


def trial_plan():
    plan = []
    for k, speed in enumerate(SPEEDS_MM_S):
        angle = ANGLES_DEG[k % len(ANGLES_DEG)]
        travel_mm = CLEARANCE_MM + DEPTH_MM
        approach_steps = int(math.ceil(travel_mm / 1000.0 / (speed / 1000.0) / DT))
        plan.append({
            "id": f"T{k + 1:02d}",
            "speed_mm_s": speed,
            "angle_deg": angle,
            "total_steps": approach_steps + HOLD_STEPS,
            "approach_steps": approach_steps,
        })
    return plan


def run_trial(run_dir, trial):
    out_dir = run_dir / trial["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = base_config()
    cfg.update({
        "speed_mm_s": trial["speed_mm_s"],
        "angle_deg": trial["angle_deg"],
        "total_steps": trial["total_steps"],
        "out_dir": str(out_dir),
    })
    cfg_path = out_dir / "config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{PIXI_ENV};{PIXI_ENV / 'Library' / 'bin'};" + env.get("PATH", "")
    env["PYTHONPATH"] = f"{SOFA_ROOT / 'plugins' / 'SofaPython3' / 'lib' / 'python3' / 'site-packages'};" \
                        f"{SOFA_ROOT / 'collections' / 'bin'}"
    env["SRTA_CONTACT_CONFIG"] = str(cfg_path)
    started = time.perf_counter()
    stdout_path = out_dir / "runSofa.log"
    with stdout_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.run(
            [str(RUN_SOFA), "-l", "SofaPython3", str(SCENE), "-g", "batch", "-n", str(trial["total_steps"])],
            cwd=str(out_dir), env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    wall = time.perf_counter() - started
    log_lines = stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()
    errors = [line for line in log_lines if "[ERROR]" in line and "readBasicIniFile" not in line]
    return {
        "exit_code": proc.returncode,
        "wall_s": round(wall, 3),
        "run_errors": errors,
        "out_dir": str(out_dir),
    }


def check_trial(trial, out_dir):
    bridge_path = out_dir / "bridge_capture.csv"
    diag_path = out_dir / "diagnostics.csv"
    build = json.loads((out_dir / "scene_build.json").read_text(encoding="utf-8"))
    with bridge_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        bridge_rows = list(reader)
    with diag_path.open("r", encoding="utf-8", newline="") as handle:
        diag = list(csv.DictReader(handle))

    schema_ok = header == BRIDGE_HEADER
    ticks = [int(r[0]) for r in bridge_rows]
    schema_ok = schema_ok and ticks == list(range(len(bridge_rows)))
    schema_ok = schema_ok and len(bridge_rows) == trial["total_steps"]
    time_ok = all(abs(float(r[1]) - int(r[0]) / RATE_HZ) <= 1e-6 for r in bridge_rows)
    quat = np.array([[float(v) for v in r[5:9]] for r in bridge_rows])
    quat_ok = bool(np.all(np.abs(np.linalg.norm(quat, axis=1) - 1.0) <= 1e-6))
    values = np.array([[float(v) for v in r[1:16]] for r in bridge_rows])
    finite_ok = bool(np.all(np.isfinite(values)))

    contact_steps = [i for i, row in enumerate(diag) if int(row["contact_points"]) > 0]
    tunneling = [i for i, row in enumerate(diag) if int(row["inside"]) == 1 and int(row["contact_points"]) == 0]
    wrench = np.array([[float(v) for v in r[9:12]] + [float(v) for v in r[12:15]] for r in bridge_rows])
    force_norm = np.linalg.norm(wrench[:, :3], axis=1)
    contact_force_ok = bool(contact_steps) and all(
        np.isfinite(wrench[i]).all() and force_norm[i] > 0.0 for i in contact_steps)
    first_contact = contact_steps[0] if contact_steps else None
    peak_contact = max((float(diag[i]["contact_force_n"]) for i in contact_steps), default=0.0)
    peak_puncture = max(float(row["puncture_force_n"]) for row in diag)
    max_depth = max(float(row["depth_m"]) for row in diag)
    inside_steps = sum(int(row["inside"]) for row in diag)
    swept_steps = sum(1 for row in diag if int(row["swept_hits"]) > 0)

    passed = bool(contact_steps) and not tunneling and contact_force_ok and schema_ok and time_ok and quat_ok \
        and finite_ok and build["surface_triangles_culled"] < build["surface_triangles_full"]
    return {
        "trial": trial["id"],
        "speed_mm_s": trial["speed_mm_s"],
        "angle_deg": trial["angle_deg"],
        "total_steps": trial["total_steps"],
        "approach_steps": trial["approach_steps"],
        "contact_detected": bool(contact_steps),
        "first_contact_step": first_contact,
        "first_contact_time_s": None if first_contact is None else round(first_contact * DT, 6),
        "contact_steps": len(contact_steps),
        "tunneling_steps": len(tunneling),
        "inside_steps": inside_steps,
        "swept_hit_steps": swept_steps,
        "wrench_nonzero_on_contact": contact_force_ok,
        "peak_contact_force_n": round(peak_contact, 6),
        "peak_puncture_force_n": round(peak_puncture, 6),
        "max_depth_m": round(max_depth, 6),
        "schema_ok": schema_ok,
        "time_ok": time_ok,
        "quat_norm_ok": quat_ok,
        "finite_ok": finite_ok,
        "candidates_full": build["candidate_pairs_full"],
        "candidates_culled": build["candidate_pairs_culled"],
        "passed": passed,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", default=None, help="run label (default: UTC timestamp)")
    args = parser.parse_args(argv)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = args.label or stamp
    run_dir = LOG_DIR / f"task23-smoke-{label}"
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot = quiet_host_snapshot()
    results = []
    for trial in trial_plan():
        info = run_trial(run_dir, trial)
        check = check_trial(trial, pathlib.Path(info["out_dir"]))
        check.update({"exit_code": info["exit_code"], "wall_s": info["wall_s"],
                      "run_errors": info["run_errors"]})
        if info["exit_code"] != 0 or info["run_errors"]:
            check["passed"] = False
        capture = LOG_DIR / f"contact-smoke-{label}-{trial['id']}-bridge.csv"
        capture.write_bytes((pathlib.Path(info["out_dir"]) / "bridge_capture.csv").read_bytes())
        check["bridge_capture"] = str(capture.relative_to(REPO)).replace("\\", "/")
        results.append(check)
        print(f"{trial['id']} speed={trial['speed_mm_s']} angle={trial['angle_deg']} "
              f"contact_steps={check['contact_steps']} tunneling={check['tunneling_steps']} "
              f"passed={check['passed']}")
    summary = {
        "schema": "task23-smoke-v1",
        "label": label,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dt_s": DT,
        "rate_hz": RATE_HZ,
        "hold_steps": HOLD_STEPS,
        "depth_mm": DEPTH_MM,
        "clearance_mm": CLEARANCE_MM,
        "quiet_host_before": snapshot,
        "trials": results,
        "trials_total": len(results),
        "trials_passed": sum(1 for r in results if r["passed"]),
        "tunneling_steps_total": sum(r["tunneling_steps"] for r in results),
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
