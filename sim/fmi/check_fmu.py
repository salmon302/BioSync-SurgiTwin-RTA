# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: FMI 3.0 import checks for thermal_pennes (plan task 2.7 slice 1)
# Date: 2026-11-05T19:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.7 slice 1
# Summary: Unzips, validates, instantiates, and steps the thermal_pennes Co-Simulation FMU with FMPy 0.3.32 and checks two analytic sanity cases and the lesion-dose behavior; writes a JSON result to SNDEV/logs/.
#
# Usage: python sim\fmi\check_fmu.py [--fmu PATH] [--out PATH]
# Requires fmpy==0.3.32 (sim/fmi/requirements.txt). Exit status 0 when every check passes.

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from ctypes import byref, c_double
from datetime import datetime, timezone
from pathlib import Path

import fmpy
from fmpy import extract, read_model_description
from fmpy.fmi1 import FMICallException
from fmpy.fmi3 import FMU3Slave, fmi3Boolean, fmi3Float64, fmi3OK, fmi3ValueReference

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_FMU = HERE / "build" / "fmu" / "thermal_pennes.fmu"
DEFAULT_OUT = REPO / "SNDEV" / "logs" / "fmi-thermal-pennes-check-2026-11-05.json"

STEP = 0.1
T_A = 310.15
T_CASE_A = 323.15
P_ON_S = 30.0
T_STOP_A = 60.0
T_STOP_B = 120.0
TRACE_EVERY_S = 5.0

TOL_CONSERVATION_K = 1.0e-9
TOL_ANALYTIC_K = 0.01
TOL_DISCRETE_K = 1.0e-9
TOL_STABILIZE_REL = 1.0e-3
TOL_BOUND_K = 1.0e-9
TOL_ENERGY_J = 1.0e-6

DEFAULT_PARAMS = {
    "rho": 1078.8,
    "c": 3540.2,
    "k": 0.519,
    "w_b": 16.24,
    "c_b": 3617.0,
    "T_a": T_A,
    "Q_met": 10712.9,
    "dx": 1.0e-3,
    "r_app": 3.0e-3,
    "T_init": T_A,
}
OUTPUTS = ["T_max", "T_mean", "V60", "V_lesion"]


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Fmu:
    def __init__(self, unzip_dir, md):
        self.md = md
        self.vr = {variable.name: variable.valueReference for variable in md.modelVariables}
        self.slave = FMU3Slave(
            guid=md.instantiationToken,
            unzipDirectory=str(unzip_dir),
            modelIdentifier=md.coSimulation.modelIdentifier,
            instanceName="thermal_pennes_check",
        )

    def check(self, status, what):
        if status != fmi3OK:
            raise RuntimeError(f"{what} returned FMI status {status}")

    def set_values(self, names, values):
        refs = (fmi3ValueReference * len(names))(*[self.vr[n] for n in names])
        vals = (fmi3Float64 * len(names))(*values)
        status = self.slave.fmi3SetFloat64(self.slave.component, refs, len(names), vals, len(names))
        self.check(status, f"fmi3SetFloat64 {names}")

    def get_values(self, names):
        refs = (fmi3ValueReference * len(names))(*[self.vr[n] for n in names])
        vals = (fmi3Float64 * len(names))()
        status = self.slave.fmi3GetFloat64(self.slave.component, refs, len(names), vals, len(names))
        self.check(status, f"fmi3GetFloat64 {names}")
        return list(vals)

    def do_step(self, t, h):
        event = fmi3Boolean()
        terminate = fmi3Boolean()
        early = fmi3Boolean()
        last = c_double()
        status = self.slave.fmi3DoStep(
            self.slave.component,
            c_double(t),
            c_double(h),
            fmi3Boolean(True),
            byref(event),
            byref(terminate),
            byref(early),
            byref(last),
        )
        self.check(status, f"fmi3DoStep at t={t}")
        if terminate.value:
            raise RuntimeError("FMU requested termination")
        return last.value


def simulate(unzip_dir, md, params, stop_time, power_of_time):
    fmu = Fmu(unzip_dir, md)
    slave = fmu.slave
    slave.instantiate(visible=False, loggingOn=False)
    slave.enterInitializationMode(startTime=0.0, stopTime=stop_time)
    names = list(params.keys())
    fmu.set_values(names, [params[n] for n in names])
    fmu.set_values(["P_abl", "h_bc", "T_env"], [power_of_time(0.0), 0.0, T_A])
    slave.exitInitializationMode()

    n_steps = int(round(stop_time / STEP))
    times = [0.0]
    series = {name: [] for name in OUTPUTS}
    values = fmu.get_values(OUTPUTS)
    for name, value in zip(OUTPUTS, values):
        series[name].append(value)

    for n in range(n_steps):
        t = n * STEP
        fmu.set_values(["P_abl"], [power_of_time(t)])
        last = fmu.do_step(t, STEP)
        t_next = (n + 1) * STEP
        if abs(last - t_next) > 1.0e-9:
            raise RuntimeError(f"lastSuccessfulTime {last} does not match {t_next}")
        times.append(t_next)
        for name, value in zip(OUTPUTS, fmu.get_values(OUTPUTS)):
            series[name].append(value)

    slave.terminate()
    slave.freeInstance()
    return times, series


def trace_rows(times, series):
    stride = max(1, int(round(TRACE_EVERY_S / STEP)))
    rows = []
    for index in range(0, len(times), stride):
        rows.append(
            {
                "t_s": round(times[index], 6),
                "T_max_K": series["T_max"][index],
                "T_mean_K": series["T_mean"][index],
                "V60_mm3": series["V60"][index],
                "V_lesion_mm3": series["V_lesion"][index],
            }
        )
    return rows


def case_conservation(unzip_dir, md):
    params = dict(DEFAULT_PARAMS, w_b=0.0, Q_met=0.0, T_init=T_CASE_A)
    times, series = simulate(unzip_dir, md, params, T_STOP_A, lambda t: 0.0)
    max_dev = max(
        max(abs(v - T_CASE_A) for v in series["T_mean"]),
        max(abs(v - T_CASE_A) for v in series["T_max"]),
    )
    passed = max_dev <= TOL_CONSERVATION_K
    return {
        "name": "A1_no_perfusion_no_source_conservation",
        "description": "w_b=0, Q_met=0, P_abl=0, h_bc=0, uniform start at 50 C; the uniform field must stay constant",
        "stop_time_s": T_STOP_A,
        "steps": len(times) - 1,
        "tolerance_K": TOL_CONSERVATION_K,
        "max_abs_deviation_K": max_dev,
        "pass": passed,
        "trace": trace_rows(times, series),
    }


def case_cooling(unzip_dir, md):
    params = dict(DEFAULT_PARAMS, Q_met=0.0, T_init=T_CASE_A)
    times, series = simulate(unzip_dir, md, params, T_STOP_A, lambda t: 0.0)
    rate = DEFAULT_PARAMS["w_b"] * DEFAULT_PARAMS["c_b"] / (DEFAULT_PARAMS["rho"] * DEFAULT_PARAMS["c"])
    step_factor = 1.0 - rate * STEP
    analytic_err = 0.0
    discrete_err = 0.0
    for index, t in enumerate(times):
        analytic = T_A + (T_CASE_A - T_A) * math.exp(-rate * t)
        discrete = T_A + (T_CASE_A - T_A) * step_factor ** index
        observed = series["T_mean"][index]
        analytic_err = max(analytic_err, abs(observed - analytic))
        discrete_err = max(discrete_err, abs(observed - discrete))
    monotone = all(series["T_mean"][i + 1] <= series["T_mean"][i] for i in range(len(times) - 1))
    uniform_dev = max(abs(a - b) for a, b in zip(series["T_max"], series["T_mean"]))
    passed = analytic_err <= TOL_ANALYTIC_K and discrete_err <= TOL_DISCRETE_K and monotone and uniform_dev <= TOL_BOUND_K
    return {
        "name": "A2_perfusion_cooling_analytic",
        "description": "Q_met=0, P_abl=0, h_bc=0, uniform start at 50 C, perfusion only: T(t)=T_a+(T0-T_a)exp(-w_b c_b t/(rho c))",
        "stop_time_s": T_STOP_A,
        "steps": len(times) - 1,
        "decay_rate_per_s": rate,
        "tolerance_analytic_K": TOL_ANALYTIC_K,
        "max_abs_error_vs_analytic_K": analytic_err,
        "tolerance_discrete_K": TOL_DISCRETE_K,
        "max_abs_error_vs_discrete_closed_form_K": discrete_err,
        "monotone_nonincreasing_T_mean": monotone,
        "max_T_max_minus_T_mean_K": uniform_dev,
        "pass": passed,
        "trace": trace_rows(times, series),
    }


def case_ablation(unzip_dir, md):
    params = dict(DEFAULT_PARAMS)
    power = 5.0

    def power_of_time(t):
        return power if t < P_ON_S else 0.0

    times, series = simulate(unzip_dir, md, params, T_STOP_B, power_of_time)
    lesion = series["V_lesion"]
    tmax = series["T_max"]
    tmean = series["T_mean"]
    index_on = int(round(P_ON_S / STEP))
    index_end = len(times) - 1
    index_tail = int(round((T_STOP_B - 20.0) / STEP))

    lesion_monotone = all(lesion[i + 1] >= lesion[i] for i in range(len(times) - 1))
    rises_on = lesion[0] == 0.0 and lesion[index_on] > 0.0
    tail_growth = lesion[index_end] - lesion[index_tail]
    stabilized = lesion[index_end] > 0.0 and tail_growth <= TOL_STABILIZE_REL * lesion[index_end]
    mean_bounded = all(v >= T_A - TOL_BOUND_K for v in tmean)
    tmax_nonincreasing_after_off = all(tmax[i + 1] <= tmax[i] + TOL_BOUND_K for i in range(index_on, len(times) - 1))

    volume = 16 * 16 * 16 * DEFAULT_PARAMS["dx"] ** 3
    heat_capacity = DEFAULT_PARAMS["rho"] * DEFAULT_PARAMS["c"] * volume
    perfusion_coeff = DEFAULT_PARAMS["w_b"] * DEFAULT_PARAMS["c_b"] * volume
    residual_max = 0.0
    for k in range(len(times) - 1):
        stored_change = heat_capacity * (tmean[k + 1] - tmean[k])
        source = (
            power_of_time(times[k])
            - perfusion_coeff * (tmean[k] - T_A)
            + DEFAULT_PARAMS["Q_met"] * volume
        ) * STEP
        residual_max = max(residual_max, abs(stored_change - source))
    energy_ok = residual_max <= TOL_ENERGY_J

    passed = (
        lesion_monotone and rises_on and stabilized and mean_bounded and tmax_nonincreasing_after_off and energy_ok
    )
    return {
        "name": "B1_ablation_lesion_dose_rises_then_stabilizes",
        "description": "P_abl=5 W for 0 to 30 s, then 0 to 120 s; h_bc=0; default tissue parameters",
        "stop_time_s": T_STOP_B,
        "steps": len(times) - 1,
        "power_on_s": P_ON_S,
        "power_W": power,
        "tolerance_stabilize_relative": TOL_STABILIZE_REL,
        "V_lesion_at_power_off_mm3": lesion[index_on],
        "V_lesion_at_end_mm3": lesion[index_end],
        "V_lesion_growth_last_20s_mm3": tail_growth,
        "T_max_at_power_off_K": tmax[index_on],
        "T_max_peak_K": max(tmax),
        "T_mean_min_K": min(tmean),
        "energy_balance_tolerance_J": TOL_ENERGY_J,
        "energy_balance_max_residual_J": residual_max,
        "checks": {
            "V_lesion_monotone": lesion_monotone,
            "V_lesion_rises_during_power_on": rises_on,
            "V_lesion_stabilized_after_power_off": stabilized,
            "T_mean_at_or_above_T_a": mean_bounded,
            "T_max_nonincreasing_after_power_off": tmax_nonincreasing_after_off,
            "discrete_energy_balance": energy_ok,
        },
        "pass": passed,
        "trace": trace_rows(times, series),
    }


def case_reset(unzip_dir, md):
    fmu = Fmu(unzip_dir, md)
    slave = fmu.slave
    slave.instantiate(visible=False, loggingOn=False)
    slave.enterInitializationMode(startTime=0.0, stopTime=T_STOP_A)
    fmu.set_values(["P_abl", "h_bc", "T_env"], [5.0, 0.0, T_A])
    slave.exitInitializationMode()

    def run(n_steps):
        rows = []
        for n in range(n_steps):
            fmu.set_values(["P_abl"], [5.0])
            fmu.do_step(n * STEP, STEP)
            rows.append(fmu.get_values(OUTPUTS))
        return rows

    first = run(200)
    slave.fmi3Reset(slave.component)
    # w_b is changed before reset. After fmi3Reset the instantiation default must be back, so the second run
    # without setting w_b must reproduce the first run exactly.
    fmu.set_values(["w_b"], [0.0])
    slave.fmi3Reset(slave.component)
    slave.enterInitializationMode(startTime=0.0, stopTime=T_STOP_A)
    fmu.set_values(["P_abl", "h_bc", "T_env"], [5.0, 0.0, T_A])
    slave.exitInitializationMode()
    second = run(200)
    slave.terminate()
    slave.freeInstance()

    max_dev = max(abs(a - b) for row_a, row_b in zip(first, second) for a, b in zip(row_a, row_b))
    passed = max_dev == 0.0
    return {
        "name": "R1_reset_restores_instantiation_defaults",
        "description": "run 200 steps at default parameters, set w_b=0, fmi3Reset, re-initialize without setting parameters, run 200 steps; the second run must equal the first",
        "steps_per_run": 200,
        "tolerance": 0.0,
        "max_abs_deviation_between_runs": max_dev,
        "pass": passed,
    }


def case_error_paths(unzip_dir, md):
    fmu = Fmu(unzip_dir, md)
    slave = fmu.slave
    slave.instantiate(visible=False, loggingOn=False)
    slave.enterInitializationMode(startTime=0.0, stopTime=T_STOP_A)
    slave.exitInitializationMode()

    fmu.set_values(["h_bc"], [1.0e6])
    unstable_status = None
    try:
        fmu.do_step(0.0, STEP)
    except FMICallException as error:
        unstable_status = str(error)

    fmu.set_values(["h_bc"], [0.0])
    wrong_step_status = None
    try:
        fmu.do_step(0.0, 0.05)
    except FMICallException as error:
        wrong_step_status = str(error)

    slave.terminate()
    slave.freeInstance()
    passed = unstable_status is not None and wrong_step_status is not None
    return {
        "name": "N1_error_paths_return_fmi3_error",
        "description": "h_bc=1e6 W/(m2.K) violates the stability bound; communicationStepSize=0.05 s differs from the 0.1 s solver step",
        "unstable_boundary_status": unstable_status,
        "wrong_step_size_status": wrong_step_status,
        "pass": passed,
    }


# ---------------------------------------------------------------------------
# Mechanical FMU (mechanical_sofa, task 2.7 slice 2). Selected with --model mechanical.
# The worker runs in a runSofa.exe process; these cases use the same worker scene in standalone
# script mode and the pinned reference scene for the organ setup check.
# ---------------------------------------------------------------------------

MECH_FMU = HERE / "build" / "fmu" / "mechanical_sofa.fmu"
MECH_STEP = 0.001
MECH_WORKER = HERE / "mechanical" / "worker" / "mechanical_worker.py"
MECH_MESH = HERE.parent / "sofa" / "src" / "meshes" / "reference_organ.msh"
REF_SCENE_DIR = HERE.parent / "sofa" / "src"
MECH_OUTPUTS = ["force_x", "force_y", "force_z", "torque_x", "torque_y", "torque_z",
                "max_disp", "mean_disp", "tip_node_disp", "step_count"]
MECH_TIP = (0.10, 0.195, 0.10)
MECH_STIFFNESS = 2000.0
MECH_STEP_COST_STEPS = 1000
MECH_BUDGET_MS = 16.7
MECH_REF_MEAN_MS = 11.0
MECH_MEAN_LIMIT_MS = MECH_REF_MEAN_MS * 1.2
MECH_TOL_REF_M = 1.0e-6
MECH_TOL_STANDALONE_N = 1.0e-6
MECH_TOL_RESET = 1.0e-9


def mech_sofa_runtime():
    sofa_root = Path(os.environ.get("SRTA_SOFA_ROOT", r"C:\Users\salmo\SOFA\v26.06.00"))
    pixi = Path(os.environ.get("SRTA_SOFAPY_ENV", str(REPO / "env" / "ros2-jazzy" / ".pixi" / "envs" / "default")))
    env = dict(os.environ)
    env["PATH"] = f"{pixi};{pixi / 'Library' / 'bin'};" + env.get("PATH", "")
    env["PYTHONPATH"] = (f"{sofa_root / 'plugins' / 'SofaPython3' / 'lib' / 'python3' / 'site-packages'};"
                         f"{sofa_root / 'collections' / 'bin'}")
    return env, sofa_root / "collections" / "bin" / "runSofa.exe"


def mech_scratch_dir(prefix):
    scratch = Path(r"C:\Users\salmo\AppData\Local\Temp\opencode")
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(scratch) if scratch.is_dir() else None))


def run_worker_script(commands, dump_steps, stiffness):
    """Standalone worker run (script transport). Returns (replies, {step: positions})."""
    tmp = mech_scratch_dir("mech-standalone-")
    cfg = {
        "mesh_path": str(MECH_MESH),
        "transport": "script",
        "commands": list(commands) + ["QUIT"],
        "tool_stiffness_n_per_m": stiffness,
        "initial_tip_m": list(MECH_TIP),
        "dump_steps": list(dump_steps),
        "dump_dir": str(tmp),
        "results_path": str(tmp / "results.json"),
    }
    cfg_path = tmp / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    env, runsofa = mech_sofa_runtime()
    env["SRTA_MECH_CONFIG"] = str(cfg_path)
    subprocess.run([str(runsofa), str(MECH_WORKER), "-l", "SofaPython3", "-g", "batch",
                    "-n", str(len(commands) + 10)],
                   cwd=str(tmp), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=300 + int(len(commands) * 0.5), check=False)
    results_path = tmp / "results.json"
    if not results_path.is_file():
        raise RuntimeError(f"standalone worker produced no results ({tmp})")
    replies = json.loads(results_path.read_text(encoding="utf-8"))
    dumps = {}
    for step in dump_steps:
        path = tmp / f"positions_step{step:06d}.json"
        if path.is_file():
            dumps[step] = json.loads(path.read_text(encoding="utf-8"))["positions"]
    return replies, dumps


def reference_frames(steps):
    """Frames of the pinned reference_scene.scn run (positions.out), keyed by time (rounded to 1e-9)."""
    tmp = mech_scratch_dir("mech-reference-")
    shutil.copy2(REF_SCENE_DIR / "reference_scene.scn", tmp / "reference_scene.scn")
    shutil.copytree(REF_SCENE_DIR / "meshes", tmp / "meshes")
    env, runsofa = mech_sofa_runtime()
    subprocess.run([str(runsofa), "reference_scene.scn", "-g", "batch", "-n", str(steps),
                    "--computationTimeSampling", "1"],
                   cwd=str(tmp), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=300, check=False)
    text = (tmp / "positions.out").read_text(encoding="ascii")
    frames = {}
    for match in re.finditer(r"T=\s*([0-9.eE+-]+)\s*\r?\n\s*X=\s*([^\r\n]+)", text):
        values = [float(v) for v in match.group(2).split()]
        frames[round(float(match.group(1)), 9)] = [values[i:i + 3] for i in range(0, len(values), 3)]
    return frames


def mech_instance(unzip_dir, md, stiffness):
    fmu = Fmu(unzip_dir, md)
    slave = fmu.slave
    slave.instantiate(visible=False, loggingOn=False)
    slave.enterInitializationMode(startTime=0.0, stopTime=1.0)
    fmu.set_values(["tool_stiffness"], [stiffness])
    slave.exitInitializationMode()
    return fmu


def mech_set_tip(fmu, tip):
    fmu.set_values(["tip_x", "tip_y", "tip_z"], list(tip))


def mech_outputs(fmu):
    return dict(zip(MECH_OUTPUTS, fmu.get_values(MECH_OUTPUTS)))


def mech_case_organ_setup(unzip_dir, md):
    steps = 40
    # The reference writer lags the step count by about 10 steps (frames T = 0.04 needs -n 52), see the log.
    frames = reference_frames(52)
    t_end = round(steps * MECH_STEP, 9)
    ref0 = frames[0.0]
    ref_end = frames[t_end]
    ref_flat = [c for node in ref_end for c in node]
    ref_max_disp = max(math.dist(a, b) for a, b in zip(ref_end, ref0))

    replies, dumps = run_worker_script(["STEP 0.1 0.195 0.1 0 0 0 1"] * steps, [steps], 0.0)
    worker_flat = [c for node in dumps[steps] for c in node]
    worker_dev = max(abs(a - b) for a, b in zip(worker_flat, ref_flat)) if len(worker_flat) == len(ref_flat) else float("inf")

    fmu = mech_instance(unzip_dir, md, 0.0)
    for n in range(steps):
        mech_set_tip(fmu, MECH_TIP)
        fmu.do_step(n * MECH_STEP, MECH_STEP)
    fmu_out = mech_outputs(fmu)
    fmu.slave.terminate()
    fmu.slave.freeInstance()
    fmu_dev = abs(fmu_out["max_disp"] - ref_max_disp)
    passed = worker_dev <= MECH_TOL_REF_M and fmu_dev <= MECH_TOL_REF_M
    return {
        "name": "M1_organ_setup_matches_reference_scene",
        "description": "tool stiffness 0 (gravity only), 40 steps; worker positions and FMU max displacement against the pinned reference_scene.scn run at T = 0.04 s",
        "steps": steps,
        "reference_time_s": t_end,
        "tolerance_m": MECH_TOL_REF_M,
        "max_abs_position_deviation_worker_vs_reference_m": worker_dev,
        "reference_max_displacement_m": ref_max_disp,
        "fmu_max_displacement_m": fmu_out["max_disp"],
        "abs_deviation_fmu_max_disp_vs_reference_m": fmu_dev,
        "pass": passed,
    }


def mech_case_static_load(unzip_dir, md):
    steps = 500
    commands = [f"STEP {MECH_TIP[0]:.17g} {MECH_TIP[1]:.17g} {MECH_TIP[2]:.17g} 0 0 0 1"] * steps
    replies, _ = run_worker_script(commands, [], MECH_STIFFNESS)
    standalone = [[float(v) for v in r.split()[1:4]] for r in replies]

    fmu = mech_instance(unzip_dir, md, MECH_STIFFNESS)
    fmu_forces = []
    for n in range(steps):
        mech_set_tip(fmu, MECH_TIP)
        fmu.do_step(n * MECH_STEP, MECH_STEP)
        out = mech_outputs(fmu)
        fmu_forces.append([out["force_x"], out["force_y"], out["force_z"]])
    fmu.slave.terminate()
    fmu.slave.freeInstance()

    dev = max(abs(a - b) for fa, sa in zip(fmu_forces, standalone) for a, b in zip(fa, sa))
    last = fmu_forces[-100:]
    drift = max(max(abs(v[i] - last[0][i]) for v in last) for i in range(3))
    force_norm = math.sqrt(sum(v * v for v in fmu_forces[-1]))
    passed = dev <= MECH_TOL_STANDALONE_N and len(standalone) == steps
    return {
        "name": "M2_static_load_matches_standalone_scene",
        "description": "tip fixed at (0.10, 0.195, 0.10) m, tool stiffness 2000 N/m, 500 steps; FMU wrench against the standalone worker scene (same commands)",
        "steps": steps,
        "tolerance_N": MECH_TOL_STANDALONE_N,
        "max_abs_force_deviation_fmu_vs_standalone_N": dev,
        "final_force_N": fmu_forces[-1],
        "final_force_norm_N": force_norm,
        "last_100_steps_force_drift_N": drift,
        "drift_is_pass_criterion": False,
        "pass": passed,
    }


def mech_case_step_cost(unzip_dir, md):
    fmu = mech_instance(unzip_dir, md, MECH_STIFFNESS)
    times = []
    for n in range(MECH_STEP_COST_STEPS):
        mech_set_tip(fmu, MECH_TIP)
        started = time.perf_counter()
        fmu.do_step(n * MECH_STEP, MECH_STEP)
        times.append((time.perf_counter() - started) * 1000.0)
    fmu.slave.terminate()
    fmu.slave.freeInstance()
    ordered = sorted(times)
    mean = sum(times) / len(times)
    p95 = ordered[max(1, math.ceil(0.95 * len(ordered))) - 1]
    p99 = ordered[max(1, math.ceil(0.99 * len(ordered))) - 1]
    passed = mean <= MECH_MEAN_LIMIT_MS and p95 <= MECH_BUDGET_MS
    return {
        "name": "M3_step_cost_against_budget",
        "description": "wall time of fmi3DoStep (pipe round trip included), 1000 steps of the coupled scene",
        "steps": MECH_STEP_COST_STEPS,
        "reference_mean_ms": MECH_REF_MEAN_MS,
        "mean_limit_ms": MECH_MEAN_LIMIT_MS,
        "budget_ms": MECH_BUDGET_MS,
        "mean_ms": mean,
        "p95_ms": p95,
        "p99_ms": p99,
        "max_ms": ordered[-1],
        "min_ms": ordered[0],
        "steps_over_budget": sum(1 for t in times if t > MECH_BUDGET_MS),
        "pass": passed,
        "step_time_series_ms": [round(t, 4) for t in times],
    }


def mech_case_reset(unzip_dir, md):
    fmu = mech_instance(unzip_dir, md, MECH_STIFFNESS)
    first = []
    for n in range(200):
        mech_set_tip(fmu, MECH_TIP)
        fmu.do_step(n * MECH_STEP, MECH_STEP)
        first.append(list(mech_outputs(fmu).values()))
    fmu.slave.reset()
    slave = fmu.slave
    slave.enterInitializationMode(startTime=0.0, stopTime=1.0)
    slave.exitInitializationMode()
    second = []
    for n in range(200):
        mech_set_tip(fmu, MECH_TIP)
        fmu.do_step(n * MECH_STEP, MECH_STEP)
        second.append(list(mech_outputs(fmu).values()))
    slave.terminate()
    slave.freeInstance()
    dev = max(abs(a - b) for ra, rb in zip(first, second) for a, b in zip(ra, rb))
    return {
        "name": "M4_reset_restarts_worker_and_reproduces_run",
        "description": "200 steps, fmi3Reset (worker restart), re-initialization with the default stiffness, 200 steps",
        "steps_per_run": 200,
        "tolerance": MECH_TOL_RESET,
        "max_abs_deviation_between_runs": dev,
        "pass": dev <= MECH_TOL_RESET,
    }


def mech_case_error_paths(unzip_dir, md):
    results = {}
    fmu = mech_instance(unzip_dir, md, MECH_STIFFNESS)
    try:
        fmu.slave.fmi3DoStep(fmu.slave.component, fmi3Float64(0.0), fmi3Float64(0.002),
                             fmi3Boolean(True), byref(fmi3Boolean()), byref(fmi3Boolean()),
                             byref(fmi3Boolean()), byref(fmi3Float64()))
        results["wrong_step_size"] = "no error"
    except FMICallException as error:
        results["wrong_step_size"] = str(error)
    fmu.slave.terminate()
    fmu.slave.freeInstance()

    fmu = mech_instance(unzip_dir, md, MECH_STIFFNESS)
    fmu.set_values(["tip_x"], [float("nan")])
    try:
        fmu.do_step(0.0, MECH_STEP)
        results["non_finite_tip"] = "no error"
    except FMICallException as error:
        results["non_finite_tip"] = str(error)
    fmu.slave.terminate()
    fmu.slave.freeInstance()
    passed = all("failed with status 3" in v for v in results.values())
    return {
        "name": "M5_error_paths_return_fmi3_error",
        "description": "communicationStepSize 0.002 s, and a NaN tool-tip input",
        "results": results,
        "pass": passed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("thermal", "mechanical"), default="thermal")
    parser.add_argument("--fmu", default=None)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    if args.fmu is None:
        args.fmu = str(MECH_FMU if args.model == "mechanical" else DEFAULT_FMU)

    fmu_path = Path(args.fmu).resolve()
    if not fmu_path.is_file():
        raise SystemExit(f"FMU not found: {fmu_path} (run sim/fmi/build.ps1 first)")

    started = time.time()
    md = read_model_description(str(fmu_path), validate=True)
    if md.fmiVersion != "3.0":
        raise SystemExit(f"fmiVersion is {md.fmiVersion}, expected 3.0")
    if md.coSimulation is None:
        raise SystemExit("FMU has no CoSimulation element")

    scratch = Path(r"C:\Users\salmo\AppData\Local\Temp\opencode")
    with tempfile.TemporaryDirectory(
        prefix="fmi-thermal-", dir=str(scratch) if scratch.is_dir() else None, ignore_cleanup_errors=True
    ) as tmp:
        unzip_dir = Path(tmp) / "unzipped"
        extract(str(fmu_path), str(unzip_dir))
        if args.model == "mechanical":
            cases = [
                mech_case_organ_setup(unzip_dir, md),
                mech_case_static_load(unzip_dir, md),
                mech_case_step_cost(unzip_dir, md),
                mech_case_reset(unzip_dir, md),
                mech_case_error_paths(unzip_dir, md),
            ]
        else:
            cases = [
                case_conservation(unzip_dir, md),
                case_cooling(unzip_dir, md),
                case_ablation(unzip_dir, md),
                case_error_paths(unzip_dir, md),
                case_reset(unzip_dir, md),
            ]

    title = ("mechanical_sofa FMI 3.0 import checks (plan task 2.7 slice 2)" if args.model == "mechanical"
             else "thermal_pennes FMI 3.0 import checks (plan task 2.7 slice 1)")
    report = {
        "title": title,
        "date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fmpy_version": fmpy.__version__,
        "python_version": sys.version.split()[0],
        "fmu": {
            "path": str(fmu_path.relative_to(REPO)) if fmu_path.is_relative_to(REPO) else fmu_path.name,
            "bytes": fmu_path.stat().st_size,
            "sha256": sha256_of(fmu_path),
            "fmiVersion": md.fmiVersion,
            "modelIdentifier": md.coSimulation.modelIdentifier,
            "fixedInternalStepSize_s": md.coSimulation.fixedInternalStepSize,
            "variables": len(md.modelVariables),
        },
        "solver_step_s": MECH_STEP if args.model == "mechanical" else STEP,
        "wall_time_s": round(time.time() - started, 3),
        "cases": cases,
        "pass": all(case["pass"] for case in cases),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for case in cases:
        print(f"{case['name']}: {'PASS' if case['pass'] else 'FAIL'}")
    print(f"overall: {'PASS' if report['pass'] else 'FAIL'}; wrote {out_path}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
