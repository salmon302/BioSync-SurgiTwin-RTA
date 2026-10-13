# SPDX-License-Identifier: MIT
"""
OQ: Pulse worker fails closed without the native bindings, and the synthetic opt-in is explicit (SRS FR-MS-006, SRS C1)

Acceptance (runs without the native engine):
  * PulseWorker.initialize() returns False and sets state ERROR when the pulse bindings cannot be imported.
  * pulse_bridge.real_pulse_available() returns False when BIOSSYNC_SYNTHETIC=1.

The full engine round trip (initialization, stepping, serialization) is covered by the IQ-4 and
OQ-16 suites, which run only where the bindings are present.

Limitation: SimulationManager.step_simulation is synchronous. The ProcessPoolExecutor delegation of
FR-MS-006 is not active (docs/migration-map.md, open item).
"""

import importlib.util

import pytest

from engine.pulse import PatientConfig, PulseWorker, SimulationState

pytestmark = pytest.mark.oq


def _pulse_bindings_present():
    return importlib.util.find_spec("pulse") is not None


@pytest.mark.skipif(_pulse_bindings_present(), reason="native Pulse bindings present; fail-closed path not exercised")
def test_initialize_fails_closed_without_bindings():
    worker = PulseWorker(PatientConfig(patient_id="oq-fail-closed", age=40, weight_kg=70.0, height_cm=175.0, sex="male"))
    assert worker.initialize() is False
    assert worker.state == SimulationState.ERROR


def test_synthetic_opt_in_disables_real_engine(monkeypatch):
    import engine.pulse_bridge as bridge

    monkeypatch.setattr(bridge, "SYNTHETIC_ONLY", True)
    assert bridge.real_pulse_available() is False


def test_pulse_baseline_is_none_without_engine(monkeypatch):
    import engine.pulse_bridge as bridge

    monkeypatch.setattr(bridge, "SYNTHETIC_ONLY", True)
    assert bridge.pulse_baseline("oq-baseline") is None
