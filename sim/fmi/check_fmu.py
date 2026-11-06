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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fmu", default=str(DEFAULT_FMU))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

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
        cases = [
            case_conservation(unzip_dir, md),
            case_cooling(unzip_dir, md),
            case_ablation(unzip_dir, md),
            case_error_paths(unzip_dir, md),
            case_reset(unzip_dir, md),
        ]

    report = {
        "title": "thermal_pennes FMI 3.0 import checks (plan task 2.7 slice 1)",
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
        "solver_step_s": STEP,
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
