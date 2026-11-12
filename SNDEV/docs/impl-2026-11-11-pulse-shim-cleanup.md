Title: Pulse shim request name and unavailable-value default (O2 fix follow-on)
Date: 2026-11-11T00:00:00Z
Author: Seth Nenninger (Builder_Int29 Agent)
Contribution Type: Implementation
Ticket/Context: arterial O2 fix follow-on cleanup
Summary: Routes the legacy Pulse compatibility shim to the working ArterialOxygenPressure request and makes the SimulationMetrics PaO2 default None (unavailable) instead of the 0.0 bare value.

## Task Reference

Follow-on items 1 to 5 from SNDEV/docs/impl-2026-11-07-pulse-pao2-nan-fix.md, Owner decisions 2 and 4 (the coordinator ruling of 2026-11-11). The O2 fix record is SNDEV/docs/impl-2026-11-07-pulse-pao2-nan-fix.md, commit 6cf0b4a.

## Specification Summary

1. `middleware/Pulse/__init__.py` line 35: the compatibility shim requests `ArterialOxygenPartialPressure`, which the REL_4_3_2 engine accepts but never writes. Route it to `ArterialOxygenPressure`.
2. `middleware/engine/pulse.py`, `SimulationMetrics.arterial_o2_partial_pressure_mmhg`: the bare default is 0.0 (a fake value). Change the default to `None` so an unpopulated metric reads as unavailable.
3. `middleware/tests/test_pulse_worker.py` stale 95.0 default assertions: update to the fixed behavior.
4. Run the middleware test suite and record the result.
5. Commit the changed files and this log with a path-scoped commit.

## Implementation Notes

### Preflight

* `middleware/tests/test_pulse_worker.py` (item 3): no 95.0 assertion remains in the working tree. Line 331 asserts the engine nominal value (pytest.approx 89.1), and line 338 asserts `is None` for the missing-value path. Both were updated in commit 6cf0b4a, so no edit is made to this file.
* `SimulationMetrics.arterial_o2_partial_pressure_mmhg` is already typed `Optional[float]`, so no typing change is needed beyond the default.

### Files changed

* `middleware/Pulse/__init__.py` line 35: `"ArterialOxygenPartialPressure",` becomes `"ArterialOxygenPressure",`.
* `middleware/engine/pulse.py` line 136: `arterial_o2_partial_pressure_mmhg: Optional[float] = 0.0` becomes `arterial_o2_partial_pressure_mmhg: Optional[float] = None`.

### Consumers checked

* `middleware/engine/pulse.py` `_metrics_from_values` (lines 384 and 400) passes `None` explicitly for unavailable values. No construction site relied on the 0.0 default.
* `middleware/engine/pulse_bridge.py` line 112 passes the field through, and its return annotation already accepts `None` (O2 fix).
* `middleware/engine/pulse.py` `SerializedState` builder (`_m`, lines 617 to 630): the default there is a separate 0.0 parameter for the no-history path. It is outside the bounded scope (the SimulationMetrics default only), so it is not changed. Recorded as an open item below.

### Open items

* `pulse.py` `_m(name, default=0.0)` (line 617) returns 0.0 for `ArterialOxygenPressure_mmHg` when no metrics exist yet. This is the same fake-value pattern. It needs an owner ruling on scope before a change.
