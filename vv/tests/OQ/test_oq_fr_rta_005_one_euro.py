# SPDX-License-Identifier: MIT
"""
OQ: One Euro adaptive filter and EMA behaviour for teleoperation input (SRS FR-RTA-005)

Acceptance:
  * A constant input is returned unchanged.
  * On a noisy constant signal, the filter reduces the spread of the output compared with the raw input.
  * With beta > 0, a fast intentional ramp is tracked with less lag than with beta = 0.
  * The One Euro output converges to a step within the 5 percent band.
  * Invalid parameters are rejected.

Scope: the scalar filter only. MANO constraints and per-axis RTA integration are new development
(docs/migration-map.md).
"""

import random
import statistics

import pytest

from engine.one_euro import OneEuroFilter

pytestmark = pytest.mark.oq


def test_constant_input_is_unchanged():
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0, frequency=100.0)
    outputs = [f.filter_value(5.0) for _ in range(200)]
    assert all(abs(v - 5.0) < 1e-9 for v in outputs)


def test_jitter_is_suppressed_on_noisy_constant():
    rng = random.Random(20261013)
    raw = [10.0 + rng.gauss(0.0, 0.5) for _ in range(2000)]
    f = OneEuroFilter(min_cutoff=0.5, beta=0.0, frequency=100.0)
    filtered = [f.filter_value(x) for x in raw]
    assert statistics.pstdev(filtered[200:]) < statistics.pstdev(raw[200:]) * 0.5


def test_beta_reduces_lag_on_fast_ramp():
    ramp = [float(i) for i in range(400)]  # 1 unit per sample

    def lag(beta):
        f = OneEuroFilter(min_cutoff=0.1, beta=beta, frequency=100.0)
        out = [f.filter_value(x) for x in ramp]
        return ramp[-1] - out[-1]

    assert lag(beta=5.0) < lag(beta=0.0)


def test_step_converges_within_five_percent():
    f = OneEuroFilter(min_cutoff=2.0, beta=0.0, frequency=100.0)
    f.filter_value(0.0)
    out = [f.filter_value(100.0) for _ in range(500)]
    assert abs(out[-1] - 100.0) <= 5.0


def test_timestamps_derive_frequency():
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0, frequency=1.0)
    f.filter_value(0.0, t=0.0)
    out = f.filter_value(10.0, t=0.01)
    assert 0.0 < out < 10.0


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        OneEuroFilter(min_cutoff=0.0)
    with pytest.raises(ValueError):
        OneEuroFilter(beta=-1.0)
    with pytest.raises(ValueError):
        OneEuroFilter(frequency=0.0)
