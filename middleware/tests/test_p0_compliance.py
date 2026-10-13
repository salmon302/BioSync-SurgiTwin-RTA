# SPDX-License-Identifier: MIT
"""
Telemetry filter compliance tests (no database).

Origin: BioSync-Gateway tests/test_p0_compliance.py (adapted). The Gateway telemetry alarm
evaluation (evaluate_alarm) and the ingest and Bundle persistence API tests are not migrated,
because the telemetry routes are not in this phase. Their absence is recorded in
docs/migration-map.md.

Implements SRS FR-RTA-005 (EMA smoothing of input streams) and FR-DAT-007 (FHIR observation
channel resolution through LOINC codes).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.signal import MultiChannelEMAFilter  # noqa: E402


def test_resolve_channel_from_loinc_code():
    obs = {"code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]}}
    assert MultiChannelEMAFilter.resolve_channel(obs) == "hr"


def test_resolve_channel_falls_back_to_text():
    obs = {"code": {"text": "flow"}}
    assert MultiChannelEMAFilter.resolve_channel(obs) == "flow"


def test_resolve_channel_unknown():
    obs = {"code": {"coding": [{"code": "9999-9"}]}}
    assert MultiChannelEMAFilter.resolve_channel(obs) == "unknown"


def test_ema_filter_applies_with_per_channel_alpha():
    f = MultiChannelEMAFilter()
    obs = {
        "resourceType": "Observation",
        "code": {"coding": [{"code": "8310-5"}]},
        "valueQuantity": {"value": 140.0, "unit": "mmHg"},
    }
    out = f.filter_observation(obs)
    assert out["filtered_data"]["value"] == 140.0
    assert out["filtered_data"]["alpha"] == 0.2  # pressure default

    # Second sample should be smoothed, not equal to raw
    obs2 = {
        "resourceType": "Observation",
        "code": {"coding": [{"code": "8310-5"}]},
        "valueQuantity": {"value": 200.0, "unit": "mmHg"},
    }
    out2 = f.filter_observation(obs2)
    assert out2["filtered_data"]["value"] < 200.0
    assert out2["filtered_data"]["value"] > 140.0
