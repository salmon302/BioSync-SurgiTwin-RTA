# SPDX-License-Identifier: MIT
"""Step-timing harness for the G2.2 reference scene (task 2.2, FR-MS-002).

Runs sim/sofa/src/reference_scene.scn headless through runSofa.exe batch mode
with a fixed step count, then reports per-step animation wall times and the
divergence check from SRS Section 5 (non-finite output, or a monotonically
growing strain-energy series).

Statistics come from the runSofa "Steps Duration Statistics" rows at
--computationTimeSampling 1, so every step contributes one level-0 TOTAL row
whose MEAN is that step's wall time. The divergence check parses the scene's
WriteState dump (positions.out), recomputes the NeoHookean strain energy of
every tetrahedron per sample with the parenchyma Lame constants, and applies
the two clauses recorded in SNDEV/docs/impl-2026-10-15-sofa-scene-slice1.md.

A JSON capture is written to SNDEV/logs/ (gitignored runtime capture).

Usage:
    python sim/sofa/src/run_reference_scene.py --steps 1000 --label g22-1000

runSofa.exe lookup order: --run-sofa, then the SRTA_RUN_SOFA environment
variable, then the pinned install path C:\\Users\\salmo\\SOFA\\v26.06.00.
"""

import argparse
import datetime
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

DEFAULT_RUN_SOFA = r"C:\Users\salmo\SOFA\v26.06.00\collections\bin\runSofa.exe"
FRAME_BUDGET_MS = 16.7
WARMUP_STEPS = 10
SCENE_NAME = "reference_scene.scn"
LOG_DIR = pathlib.Path(__file__).resolve().parents[3] / "SNDEV" / "logs"

# Parenchyma Lame constants (E = 5000 Pa, nu = 0.4), same values the scene
# passes to the parenchyma TetrahedronHyperelasticityFEMForceField.
PARENCHYMA_MU = 1785.714286
PARENCHYMA_LAMBDA = 7142.857143

_GROWTH_FRACTION = 0.01


class HarnessError(RuntimeError):
    """runSofa failed, crashed, or returned fewer steps than requested."""


def find_run_sofa(explicit=None):
    """Return the runSofa.exe path, or None when no candidate exists."""
    env = os.environ.get("SRTA_RUN_SOFA")
    for candidate in (explicit, env, DEFAULT_RUN_SOFA):
        if candidate and pathlib.Path(candidate).is_file():
            return str(pathlib.Path(candidate))
    return None


def _parse_step_times(lines):
    """Level-0 TOTAL rows of each Steps Duration Statistics block."""
    times = []
    expect_header = False
    for line in lines:
        if "Steps Duration Statistics" in line:
            expect_header = True
            continue
        if not expect_header:
            continue
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "LEVEL":  # column header row
            continue
        if tokens[0] == "0" and tokens[-1] == "TOTAL":
            # LEVEL START NUM MIN MAX MEAN DEV TOTAL PERCENT ID
            num = int(float(tokens[2]))
            mean = float(tokens[5])
            if num == 1:  # one step per window at sampling 1
                times.append(mean)
            else:
                times.extend([mean] * num)
        elif tokens[0].isdigit() and len(tokens) < 4:
            expect_header = False  # block ended before a TOTAL row
    return times


def _parse_pcg_iterations(lines):
    """Aggregate the 'PCG iterations' rows of the Values Statistics blocks."""
    total = 0.0
    count = 0
    lo = None
    hi = None
    for line in lines:
        if not line.rstrip().endswith("PCG iterations"):
            continue
        tokens = line.split()
        # NUM MIN MAX MEAN DEV TOTAL ID
        num = int(float(tokens[0]))
        row_min = float(tokens[1])
        row_max = float(tokens[2])
        row_total = float(tokens[5])
        count += num
        total += row_total
        lo = row_min if lo is None else min(lo, row_min)
        hi = row_max if hi is None else max(hi, row_max)
    if not count:
        return None
    return {"count": count, "min": lo, "max": hi, "mean": total / count}


def _read_msh(path):
    """Return ({node_id: (x, y, z)}, [tet node-id tuples]) from Gmsh 2.2 ASCII."""
    positions = {}
    tets = []
    section = None
    remaining = 0
    for raw in path.read_text(encoding="ascii").splitlines():
        line = raw.strip()
        if line.startswith("$"):
            section = line
            remaining = 0
            continue
        if section == "$Nodes":
            if remaining == 0:
                remaining = int(line)
                continue
            nid, x, y, z = line.split()
            positions[int(nid)] = (float(x), float(y), float(z))
            remaining -= 1
        elif section == "$Elements":
            if remaining == 0:
                remaining = int(line)
                continue
            tokens = line.split()
            if tokens[1] == "4":  # 4-node tetrahedron
                a, b, c, d = (int(v) for v in tokens[5:9])
                tets.append((a, b, c, d))
            remaining -= 1
    return positions, tets


def _mat3_inverse(m):
    """Inverse of a 3x3 matrix given as three row tuples; None if singular."""
    a, b, c = m
    det = (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )
    if det == 0.0 or not math.isfinite(det):
        return None
    inv_det = 1.0 / det
    return (
        (
            (b[1] * c[2] - b[2] * c[1]) * inv_det,
            (a[2] * c[1] - a[1] * c[2]) * inv_det,
            (a[1] * b[2] - a[2] * b[1]) * inv_det,
        ),
        (
            (b[2] * c[0] - b[0] * c[2]) * inv_det,
            (a[0] * c[2] - a[2] * c[0]) * inv_det,
            (a[2] * b[0] - a[0] * b[2]) * inv_det,
        ),
        (
            (b[0] * c[1] - b[1] * c[0]) * inv_det,
            (a[1] * c[0] - a[0] * c[1]) * inv_det,
            (a[0] * b[1] - a[1] * b[0]) * inv_det,
        ),
    )


def _tet_geometry(rest_pts, curr_pts):
    """Deformation gradient F and rest volume of one tetrahedron."""
    rest_edges = tuple(
        tuple(rest_pts[j][i] - rest_pts[0][i] for j in (1, 2, 3)) for i in range(3)
    )
    inv_rest = _mat3_inverse(rest_edges)
    if inv_rest is None:
        return None, None
    curr_edges = tuple(
        tuple(curr_pts[j][i] - curr_pts[0][i] for j in (1, 2, 3)) for i in range(3)
    )
    # F = Ds * Dm^-1 (columns transform): F[row][col] = sum_k Ds[row][k] * inv[k][col]
    grad = tuple(
        tuple(sum(curr_edges[r][k] * inv_rest[k][c] for k in range(3)) for c in range(3))
        for r in range(3)
    )
    rest_volume = abs(
        rest_edges[0][0] * (rest_edges[1][1] * rest_edges[2][2] - rest_edges[1][2] * rest_edges[2][1])
        - rest_edges[0][1] * (rest_edges[1][0] * rest_edges[2][2] - rest_edges[1][2] * rest_edges[2][0])
        + rest_edges[0][2] * (rest_edges[1][0] * rest_edges[2][1] - rest_edges[1][1] * rest_edges[2][0])
    ) / 6.0
    return grad, rest_volume


def _neo_hookean_density(grad, mu, lam):
    """Compressible NeoHookean energy density W = mu/2 (I1-3) - mu lnJ + lam/2 (lnJ)^2."""
    f = grad
    i1 = sum(f[r][c] ** 2 for r in range(3) for c in range(3))
    det_j = (
        f[0][0] * (f[1][1] * f[2][2] - f[1][2] * f[2][1])
        - f[0][1] * (f[1][0] * f[2][2] - f[1][2] * f[2][0])
        + f[0][2] * (f[1][0] * f[2][1] - f[1][1] * f[2][0])
    )
    if det_j <= 0.0:
        return math.nan
    log_j = math.log(det_j)
    return 0.5 * mu * (i1 - 3.0) - mu * log_j + 0.5 * lam * log_j * log_j


def _parse_state_dump(path):
    """Yield (time, [floats]) samples from a WriteState positions.out file."""
    samples = []
    current_time = None
    pending = False
    for raw in path.read_text(encoding="ascii").splitlines():
        stripped = raw.strip()
        if stripped.startswith("T="):
            current_time = float(stripped[2:])
            pending = True
            continue
        if pending and stripped.startswith("X="):
            values = [float(v) for v in stripped[2:].split()]
            samples.append((current_time, values))
            pending = False
    return samples


def _strain_energy_series(samples, rest_positions, tets):
    """Per-sample total NeoHookean energy (parenchyma constants, all tets)."""
    prepared = []
    for tet in tets:
        rest_pts = [rest_positions[nid] for nid in tet]
        prepared.append((tet, rest_pts))
    series = []
    finite_outputs = True
    for _, values in samples:
        if any(not math.isfinite(v) for v in values):
            finite_outputs = False
            series.append(math.nan)
            continue
        energy = 0.0
        sample_ok = True
        for tet, rest_pts in prepared:
            curr_pts = [tuple(values[(nid - 1) * 3 + i] for i in range(3)) for nid in tet]
            grad, volume = _tet_geometry(rest_pts, curr_pts)
            density = math.nan if grad is None else _neo_hookean_density(
                grad, PARENCHYMA_MU, PARENCHYMA_LAMBDA
            )
            if not math.isfinite(density):
                sample_ok = False
                break
            energy += density * volume
        if not sample_ok:
            finite_outputs = False
            series.append(math.nan)
        else:
            series.append(energy)
    return series, finite_outputs


def _monotonic_growth(series):
    """True when the second half grows monotonically by more than 1 percent."""
    usable = [v for v in series if math.isfinite(v)]
    if len(usable) != len(series) or len(usable) < 4:
        return False
    half = usable[len(usable) // 2:]
    if any(half[i + 1] <= half[i] for i in range(len(half) - 1)):
        return False
    baseline = abs(half[0])
    if baseline == 0.0:
        return False
    return (half[-1] - half[0]) / baseline > _GROWTH_FRACTION


def _percentile_nearest_rank(values, fraction):
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def _summarize(times):
    return {
        "mean": sum(times) / len(times),
        "p95": _percentile_nearest_rank(times, 0.95),
        "max": max(times),
        "min": min(times),
    }


def _tail(lines, count=25):
    return "\n".join(lines[-count:])


def run_reference_scene(steps=1000, run_sofa=None, label="run", scene_dir=None,
                        log_dir=None):
    """Run the reference scene headless and return the capture report dict.

    Raises HarnessError when runSofa is missing or the run does not produce
    every requested step.
    """
    exe = find_run_sofa(run_sofa)
    if exe is None:
        raise HarnessError(
            "runSofa.exe not found (checked --run-sofa, SRTA_RUN_SOFA, "
            f"{DEFAULT_RUN_SOFA})"
        )
    scene_dir = pathlib.Path(scene_dir) if scene_dir else pathlib.Path(
        __file__).resolve().parent
    log_dir = pathlib.Path(log_dir) if log_dir else LOG_DIR
    scene_path = scene_dir / SCENE_NAME
    if not scene_path.is_file():
        raise HarnessError(f"scene not found: {scene_path}")

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="sofa-g22-") as tmp_name:
        tmp = pathlib.Path(tmp_name)
        shutil.copy2(scene_path, tmp / SCENE_NAME)
        shutil.copytree(scene_dir / "meshes", tmp / "meshes")

        cmd = [
            exe, SCENE_NAME, "-g", "batch",
            "-n", str(steps), "--computationTimeSampling", "1",
        ]
        stdout_path = tmp / "runSofa-stdout.log"
        try:
            with stdout_path.open("w", encoding="utf-8", errors="replace") as log_file:
                proc = subprocess.run(
                    cmd, cwd=tmp, stdout=log_file, stderr=subprocess.STDOUT,
                    timeout=60 + int(steps * 0.5), check=False,
                )
        except subprocess.TimeoutExpired as exc:
            raise HarnessError(f"runSofa timed out after {exc.timeout} s") from exc

        lines = stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()
        times = _parse_step_times(lines)
        if len(times) < steps:
            raise HarnessError(
                f"runSofa produced {len(times)} of {steps} steps "
                f"(exit code {proc.returncode}); log tail:\n{_tail(lines)}"
            )

        state_path = tmp / "positions.out"
        samples = _parse_state_dump(state_path) if state_path.is_file() else []
        rest_positions, tets = _read_msh(scene_dir / "meshes" / "reference_organ.msh")

    errors = [line.strip() for line in lines if "[ERROR]" in line]
    warnings = [line.strip() for line in lines if "[WARNING]" in line]

    times = times[:steps]
    energy_series, finite_outputs = _strain_energy_series(
        samples, rest_positions, tets)
    growth = _monotonic_growth(energy_series)
    divergence_ok = bool(samples) and finite_outputs and not growth

    steady = times[WARMUP_STEPS:] if len(times) > WARMUP_STEPS else times
    all_stats = _summarize(times)
    steady_stats = _summarize(steady)
    report = {
        "schema": "g22-step-timing-v1",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "label": label,
        "scene": SCENE_NAME,
        "scene_dir": str(scene_dir),
        "run_sofa": exe,
        "steps_requested": steps,
        "steps_measured": len(times),
        "frame_budget_ms": FRAME_BUDGET_MS,
        "step_time_ms": all_stats,
        "steady_after_warmup": {"warmup_steps": WARMUP_STEPS, **steady_stats},
        "pcg_iterations": _parse_pcg_iterations(lines),
        "step_time_series_ms": [round(t, 4) for t in times],
        "divergence": {
            "samples": len(samples),
            "finite_outputs": finite_outputs,
            "strain_energy_monotonic_growth": growth,
            "strain_energy_series": [None if not math.isfinite(v) else round(v, 9)
                                     for v in energy_series],
            "ok": divergence_ok,
        },
        "budget_pass": all_stats["max"] <= FRAME_BUDGET_MS,
        "exit_code": proc.returncode,
        "errors": errors,
        "warning_count": len(warnings),
        "warnings": sorted(set(warnings)),
        "wall_time_s": round(time.perf_counter() - started, 3),
    }

    log_dir.mkdir(parents=True, exist_ok=True)
    date = report["timestamp_utc"][:10]
    safe_label = re.sub(r"[^A-Za-z0-9._-]+", "-", label)
    capture_path = log_dir / f"sofa-{date}-{safe_label}.json"
    capture_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["capture"] = str(capture_path)

    print(f"steps: {len(times)}/{steps}")
    print(f"step time ms: mean={all_stats['mean']:.3f} "
          f"p95={all_stats['p95']:.3f} max={all_stats['max']:.3f} "
          f"(budget {FRAME_BUDGET_MS} ms)")
    print(f"steady (after {WARMUP_STEPS} warmup steps): "
          f"mean={steady_stats['mean']:.3f} p95={steady_stats['p95']:.3f} "
          f"max={steady_stats['max']:.3f}")
    print(f"divergence ok: {divergence_ok} "
          f"(finite={finite_outputs}, monotonic_growth={growth}, "
          f"samples={len(samples)})")
    print(f"capture: {capture_path}")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--steps", type=int, default=1000,
                        help="animation steps to run (default 1000)")
    parser.add_argument("--label", default="run",
                        help="capture label used in the SNDEV/logs file name")
    parser.add_argument("--run-sofa", default=None,
                        help="path to runSofa.exe (default: SRTA_RUN_SOFA, "
                             "then the pinned install)")
    parser.add_argument("--scene-dir", default=None,
                        help="directory holding reference_scene.scn and meshes/")
    args = parser.parse_args(argv)
    try:
        run_reference_scene(steps=args.steps, run_sofa=args.run_sofa,
                            label=args.label, scene_dir=args.scene_dir)
    except HarnessError as exc:
        print(f"HarnessError: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())