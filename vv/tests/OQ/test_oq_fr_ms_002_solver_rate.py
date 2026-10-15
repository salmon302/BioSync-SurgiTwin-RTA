# SPDX-License-Identifier: MIT
"""
OQ: SOFA reference-scene solver step rate against the 16.7 ms frame budget (SRS FR-MS-002, NFR-PERF-003)

Acceptance (runs where runSofa.exe is installed):
  * The harness completes the requested steps on the pinned G2.2 reference scene.
  * The reported maximum animation-step wall time is within the 16.7 ms frame budget of 60 FPS.
  * Mean, p95, and the divergence verdict are reported alongside the assertion and written to
    the JSON capture under SNDEV/logs/.

Scope: gate G2.2 slice 1 measures step time on sim/sofa/src/reference_scene.scn (THE pinned
reference scene; changing it re-opens the gate). The 30-minute divergence load case is slice 2.
The test skips with a clear reason when runSofa.exe is not found, following the repo precedent
of skipping when the native dependency is absent (vv/tests/IQ/test_iq4_pulse_engine_init.py).
"""

import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_HARNESS_DIR = _REPO_ROOT / "sim" / "sofa" / "src"
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

import run_reference_scene as harness  # noqa: E402

_RUN_SOFA = harness.find_run_sofa()
_STEPS = 1000

pytestmark = [
    pytest.mark.oq,
    pytest.mark.skipif(
        _RUN_SOFA is None,
        reason=(
            "runSofa.exe not found; install the pinned SOFA v26.06.00 at "
            f"{harness.DEFAULT_RUN_SOFA} or set SRTA_RUN_SOFA"
        ),
    ),
]


def test_max_step_time_within_frame_budget(capsys):
    report = harness.run_reference_scene(
        steps=_STEPS, run_sofa=_RUN_SOFA, label="oq-fr-ms-002-solver-rate"
    )
    stats = report["step_time_ms"]
    budget = report["frame_budget_ms"]
    summary = (
        f"max={stats['max']:.3f} ms, p95={stats['p95']:.3f} ms, "
        f"mean={stats['mean']:.3f} ms over {report['steps_measured']} steps "
        f"(budget {budget} ms); divergence_ok={report['divergence']['ok']}; "
        f"capture: {report['capture']}"
    )
    with capsys.disabled():
        print(f"FR-MS-002 solver rate: {summary}")
    assert report["steps_measured"] == _STEPS, (
        f"harness measured {report['steps_measured']} of {_STEPS} steps; {summary}"
    )
    assert stats["max"] <= budget, f"step time exceeds the frame budget: {summary}"