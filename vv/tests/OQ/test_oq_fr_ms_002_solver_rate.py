# SPDX-License-Identifier: MIT
"""
OQ: SOFA reference-scene solver step rate against the 16.7 ms frame budget (SRS FR-MS-002, NFR-PERF-003)

Acceptance is the VAL-029 criterion (docs/srs-v1.3-change-proposal.md), not the maximum reading:
  * p95 of the animation-step wall time is at or below the 16.7 ms budget of 60 FPS.
  * Over-budget fraction (steps above 16.7 ms) is at or below 0.1 percent in the load case.
  * No divergence: finite output and no monotonically growing strain-energy norm.
  * The maximum step time, mean, over-budget count, and over-budget fraction are reported
    alongside every assertion and written to the JSON capture under SNDEV/logs/.

Modes:
  * Short (default, _STEPS steps): asserts p95 and divergence. The 0.1 percent cap is not
    asserted, because that cap is defined over the 30-minute load case.
  * Long (SRTA_G22_LONG=1, 160000 steps): asserts all three clauses of the criterion.

Scope: gate G2.2 measures step time on sim/sofa/src/reference_scene.scn (THE pinned reference
scene; changing it re-opens the gate). The test skips with a clear reason when runSofa.exe is
not found, following the repo precedent of skipping when the native dependency is absent
(vv/tests/IQ/test_iq4_pulse_engine_init.py).
"""

import os
import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_HARNESS_DIR = _REPO_ROOT / "sim" / "sofa" / "src"
if str(_HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(_HARNESS_DIR))

import run_reference_scene as harness  # noqa: E402

_RUN_SOFA = harness.find_run_sofa()
_LONG = os.environ.get("SRTA_G22_LONG") == "1"
# Short mode uses 2000 steps. The settling transient reaches the energy plateau near step 530,
# so a 1000-step window puts settling in the second half that the growth flag evaluates.
# At 2000 steps the second half (steps 1000 to 2000) lies on the plateau.
_STEPS = 160000 if _LONG else 2000
_LABEL = "oq-fr-ms-002-solver-rate-long" if _LONG else "oq-fr-ms-002-solver-rate"
_OVER_BUDGET_FRACTION_LIMIT = 0.001

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


def test_step_time_meets_vv_criterion(capsys):
    report = harness.run_reference_scene(
        steps=_STEPS, run_sofa=_RUN_SOFA, label=_LABEL
    )
    stats = report["step_time_ms"]
    budget = report["frame_budget_ms"]
    series = report["step_time_series_ms"]
    over_budget = sum(1 for t in series if t > budget)
    over_fraction = over_budget / len(series) if series else float("nan")
    mode = "long" if _LONG else "short"
    summary = (
        f"mode={mode}, max={stats['max']:.3f} ms, p95={stats['p95']:.3f} ms, "
        f"mean={stats['mean']:.3f} ms over {report['steps_measured']} steps "
        f"(budget {budget} ms); over_budget={over_budget} "
        f"({over_fraction * 100:.3f} percent); divergence_ok={report['divergence']['ok']}; "
        f"capture: {report['capture']}"
    )
    with capsys.disabled():
        print(f"FR-MS-002 solver rate: {summary}")
    assert report["steps_measured"] == _STEPS, (
        f"harness measured {report['steps_measured']} of {_STEPS} steps; {summary}"
    )
    assert stats["p95"] <= budget, f"p95 step time exceeds the frame budget: {summary}"
    # The 0.1 percent outlier cap is defined over the 30-minute load case. A short window
    # of 2000 steps resolves that fraction at 2 steps, so the cap is asserted in long mode only.
    if _LONG:
        assert over_fraction <= _OVER_BUDGET_FRACTION_LIMIT, (
            f"over-budget fraction exceeds 0.1 percent: {summary}"
        )
    assert report["divergence"]["ok"], f"solver divergence detected: {summary}"
