# SPDX-License-Identifier: MIT
"""
LTTB downsampling invariants (no database).

Implements SRS FR-RTA-005 and NFR-PERF-001 telemetry downsampling for visualization. Origin:
BioSync-Gateway engine/lttb.py (copied unchanged). These tests cover output size, endpoint
preservation, and peak retention.
"""

import math

from engine.lttb import lttb


def _series(n):
    return [(float(i), math.sin(i / 10.0)) for i in range(n)]


def test_returns_input_when_threshold_exceeds_length():
    data = _series(50)
    assert lttb(data, 100) == data


def test_output_size_matches_threshold():
    out = lttb(_series(5000), 200)
    assert len(out) == 200


def test_first_and_last_points_are_kept():
    data = _series(1000)
    out = lttb(data, 50)
    assert out[0] == data[0]
    assert out[-1] == data[-1]


def test_retains_isolated_spike():
    data = [(float(i), 0.0) for i in range(1000)]
    data[437] = (437.0, 100.0)
    out = lttb(data, 40)
    assert any(point[1] == 100.0 for point in out)
