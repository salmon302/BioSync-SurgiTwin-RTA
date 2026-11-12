Title: Arterial O2 partial pressure NaN in the Pulse data paths (defect fix)
Date: 2026-11-07T02:00:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: defect found in SNDEV/docs/impl-2026-11-07-task27-slice3-pulse-fmu.md (flag 1)
Summary: Investigates why ArterialOxygenPartialPressure is NaN in every step of the Pulse REL_4_3_2 data-request set, inventories the blood-gas and respiratory requests in the biosync-pulse container, and fixes the FMU and middleware paths or enforces an explicit unavailability policy at the serialization boundaries.

## Task Reference

Defect raised by the slice-3 record (flag 1: arterial oxygen partial pressure is NaN in every step). The middleware FR-MS-006 path (`middleware/engine/pulse.py`, `arterial_o2_partial_pressure_mmhg`) uses the same engine request, so it is affected too. NaN is not valid JSON, and it threatens the FHIR Observation validation path (FR-DAT-007) and the hash-chain digest path (FR-DAT-005). Requirements: FR-MS-006 and FR-MS-007 (`SRS.md` v1.2.0, read only).

## Specification Summary

1. Inventory the Pulse REL_4_3_2 data-request surface for blood gases and respiratory values in the `biosync-pulse` container, on the resting-adult scenario.
2. If a working source exists, route the FMU worker output and the middleware field to it, or to a documented derivation. Check PaO2 in the 80 to 100 mmHg band for a resting adult.
3. If none exists, make the unavailability explicit at every serialization boundary (null with an `unavailable_reason` marker where the schema allows, never a bare NaN), and check the hash-chain digest path handles null.
4. Add a regression check that fails if the field serializes as NaN.

Scope: `sim/fmi/`, `middleware/engine/pulse.py`, `middleware/engine/pulse_bridge.py`, and the test file that covers the data-request surface. Not touched: `middleware/api/`, `middleware/database*`, `vv/`, `SRS.md`, `DEVELOPMENT_PLAN.md`, `sim/sofa/`, `sim/bridge/`, `sim/segmentation/`, `env/`, `sim/SOUP.md`.

## Preflight

* Middleware references (grep, read only): `middleware/engine/pulse.py` line 132 (`SimulationMetrics.arterial_o2_partial_pressure_mmhg`, default 95.0), line 162 (request name in `_PULSE_DATA_REQUESTS`), line 183 (unit map `PressureUnit.mmHg`), line 383 (`_metrics_from_values`), line 613 (the metric dictionary key `ArterialOxygenPartialPressure_mmHg`). `middleware/engine/pulse_bridge.py` line 112 (the metric is passed on). `middleware/Pulse/__init__.py` line 35 (shim, does not change). `middleware/tests/test_pulse_worker.py` lines 329 and 335 assert the field equals 95.0 (the default stub value, not engine data).
* Container: `biosync-pulse:latest` (image ID `sha256:63ee533f26a5...`, REL_4_3_2). Worker container `pulse-fmi-worker` is running on 127.0.0.1:5055 from slice 3.

## Implementation Notes

Status: complete for the fix path (working source found). Commit follows this record.

### Finding (item 1: request-surface inventory in the biosync-pulse container, REL_4_3_2)

Engine: Kitware Pulse `REL_4_3_2`, HumanAdultWholeBody, StandardMale-equivalent resting adult (45 y, 70 kg, 175 cm, male), 100 advances of 0.01 s unless noted. The inventory used `SEDataRequest.create_physiology_request(name)` (28 names accepted, none rejected at creation) and `pull_data()`.

| Request name | Value (resting adult) | Status |
|:--|:--|:--|
| ArterialOxygenPressure (PaO2) | 89.13 mmHg | working, unit mmHg |
| ArterialOxygenPartialPressure (middleware and FMU, before the fix) | NaN | accepted, returns NaN in every step, with and without a unit |
| ArterialOxygenContent | NaN | accepted, NaN |
| PulmonaryArterialOxygenPressure | 39.10 mmHg | working |
| PulmonaryVenousOxygenPressure | 89.22 mmHg | working |
| AlveolarOxygenPressure, AlveolarOxygenPartialPressure | NaN | NaN |
| OxygenSaturation | 0.9743 (fraction) | working |
| OxygenConsumptionRate | 3.90 | working |
| ArterialCarbonDioxidePressure (PaCO2) | 39.40 mmHg | working |
| PulmonaryArterialCarbonDioxidePressure | 44.08 mmHg | working |
| AlveolarCarbonDioxidePressure | NaN | NaN |
| EndTidalCarbonDioxidePressure | 49.08 mmHg | working |
| EndTidalCarbonDioxideFraction | 0.0475 | working |
| AlveolarArterialGradient | 24.62 mmHg | working |
| PulmonaryShuntFraction | NaN | NaN |
| ArterialBloodPH | NaN | NaN |
| RespirationRate, TidalVolume, MeanAirwayPressure | 12.05 per min, 0.495 L, 0.0 cmH2O | working |
| HeartRate, SystolicArterialPressure | 72.00 per min, 114.24 mmHg | working |

The engine's protobuf binding (`pulse/cdm/bind/Physiology_pb2.py`) and the shared library both name the request `ArterialOxygenPressure` (and `PulmonaryArterialOxygenPressure`), with the suffix `Pressure`. The `...PartialPressure` name exists in the request factory, but it is not a physiology property in this build.

Source of the NaN (the question from the owner). The NaN comes from the REL_4_3_2 engine data request for the name `ArterialOxygenPartialPressure`, not from the scenario and not from the unit path:

* Scenario: the same resting-adult scenario returns a finite value for `ArterialOxygenPressure` (89.06 to 89.20 mmHg over 30 s). The scenario is not the cause.
* Unit path: the explicit unit `PressureUnit.mmHg` gives 89.16 for `ArterialOxygenPressure` and NaN for `ArterialOxygenPartialPressure`. The unit map at `middleware/engine/pulse.py` line 183 is not the cause, because removing the unit (the FMU path) gives the same NaN.
* Engine: the name is accepted by the request factory but has no physiology property in the REL_4_3_2 build, so the engine never writes a value for it. The NaN is therefore the engine's answer to a request for a property it does not produce.

So the real fix is the request name, not an engine upgrade. An engine upgrade is not required to obtain PaO2 in this build, and no newer engine was tested.

### Fix path taken (item 2: working source exists)

The request `ArterialOxygenPressure` is routed through every path:

* `middleware/engine/pulse.py`: `_PULSE_DATA_REQUESTS` (request name), `_build_data_requests` unit map (`PressureUnit.mmHg`), `_metrics_from_values` (field read), and the metric dictionary key `ArterialOxygenPressure_mmHg`. `SimulationMetrics.arterial_o2_partial_pressure_mmhg` keeps its name (the bridge and tests read it) and its default changes from the stub 95.0 to `None`-capable `Optional[float]`.
* `middleware/engine/pulse_bridge.py`: the return annotation of `pulse_baseline` accepts `None` for the field.
* `sim/fmi/pulse/worker/pulse_worker.py`: request list, and `pull()` now sends a non-finite value as `None` (MessagePack nil).
* `sim/fmi/pulse/src/pulse_physiology.cpp`: reads the nil as unavailable (NaN in the fmi3 double) and adds the explicit availability output `arterial_o2_available` (value reference 29).
* `sim/fmi/pulse/model/modelDescription.xml`: `arterial_o2_pressure` (value reference 26), `arterial_o2_available` (29).
* `sim/fmi/check_fmu.py`: the PaO2 band check (80 to 100 mmHg) is part of P1, and the P1b comparison uses the new name.

The middleware test file `middleware/tests/test_pulse_worker.py` had asserted the stub default 95.0 on both the nominal and the missing-value paths. Those assertions are updated to the real engine value (the nominal stub value is 89.1, measured on the resting adult) and to `None` for a missing value.

### Measured values after the fix

* FMU P1 (resting adult, 30 s, 3000 DoSteps): PaO2 89.06 to 89.20 mmHg, final 89.197 mmHg; availability 1 at every step; zero out-of-band samples (band 80 to 100). Record `SNDEV/logs/fmi-pulse-check-pao2-fix-2026-11-07.json`, and the final run with P5 at `SNDEV/logs/fmi-pulse-check-pao2-fix-final-2026-11-07.json`.
* Middleware data path (the FR-MS-006 metric read, `_metrics_from_values` on the real engine, inside the container): PaO2 at t = 1, 2, 3 s is 89.126, 89.063, 89.091 mmHg, and the metric equals the raw engine value at each sample.
* Persisted payload with the metric: `{"metrics": {"ArterialOxygenPressure_mmHg": 89.09063094682374}}`, valid JSON, SHA-256 `b5ca34fd66a9a1cec91a060bf8359b687f187e1f9faba7ba696c906ed60268ac`.
* FMU P1b (FMU against direct engine, 200 steps): deviation 0.0. P2 reset: 0 mismatches over 300 steps and 9 outputs (the availability marker included). P4 step cost: mean 2.71 ms, p95 4.26 ms, p99 5.65 ms, zero steps over 10 ms.

### Regression checks

* Worker side, check P5 (`check_fmu.py`, no engine needed): a fake engine returning NaN for PaO2 must produce `None` in the worker reply and zero NaN floats. Result: PASS (`reply_values` ends in null).
* Worker side, live engine: the reply for PaO2 is a finite float (89.126 mmHg), with zero NaN values in the reply (probe run, 100 steps).
* Middleware side, `middleware/tests/test_pulse_worker.py` (30 tests, run with `.venv-qual311`, CPython 3.11): PASS. New tests: `test_nan_pao2_is_explicit_unavailable_not_nan` (a NaN engine value gives `None`, and `finite_or_none` rejects NaN and infinity) and `test_persisted_payload_with_unavailable_pao2_is_valid_json` (the payload encodes with `allow_nan=False`, contains no `NaN`, round-trips with `null`, and a bare NaN raises).
* Persistence boundary: `_append_state` encodes with `allow_nan=False`, so a NaN raises instead of being written as a bare token. The change is one argument in `middleware/engine/pulse.py`.

### Serialization boundaries (item 3 policy, applied where the field reaches a boundary)

* Engine to worker (`pull`): non-finite becomes nil. Applied.
* Worker to FMU (DLL): nil becomes NaN in the fmi3 double, and the explicit availability output carries the marker. Applied. The fmi3 Float64 type has no null, so the marker is the explicit signal.
* Engine to middleware metric (`finite_or_none`): non-finite becomes `None`. Applied.
* Middleware persistence (`_append_state`): `allow_nan=False` rejects any NaN. Applied.
* Hash-chain digest (`middleware/engine/hash_chain.py`): `json.loads(..., parse_constant=_reject_constant)` rejects a bare NaN token, and a JSON `null` renders as `null` (checked in the container: a `null` payload renders as `{"ArterialOxygenPressure_mmHg": null}`, and a bare NaN raises "NaN is not valid jsonb"). No change is needed in `hash_chain.py`, which is outside the bounded scope in any case.
* FHIR Observation (`middleware/fhir_validator.py`): the validator checks Observation resources that callers pass in. No code builds an Observation from the Pulse metrics, so the PaO2 field does not reach the FHIR path today. Recorded as no current boundary. A future Observation builder must map `None` to an absent value with a data-absent reason, not to a number.

### Owner decisions and reported items

1. Keep `arterial_o2_partial_pressure_mmhg` in the FR-MS-006 metric set. The value is now real (89.1 mmHg on the resting adult). The field name keeps "partial pressure", which is not the engine's unit of measure for PaO2 (PaO2 is a partial pressure, so the name is correct). The owner decides whether to rename the field in the metric contract. This record did not rename it.
2. `middleware/Pulse/__init__.py` (the compatibility shim, outside the bounded scope) still lists `ArterialOxygenPartialPressure` in its `_FR364_REQUESTS` (line 35). The shim is the legacy `Pulse` API. It must be updated to `ArterialOxygenPressure` in a follow-up. This record did not edit it, because `middleware/Pulse/` is not in the bounded scope.
3. The OQ-16 and IQ-4 suites under `vv/` do not reference the field, so no update is needed there. Vv is out of scope.
4. The middleware `SimulationMetrics` dataclass default for the field is still 0.0 when the dataclass is built with no arguments. That is a bare-object default, not an engine value. The boundary (`_metrics_from_values`) always sets `None` for an unavailable value. The owner may prefer `None` as the bare default too; not changed here.
5. The worker container reports "unhealthy" from the image HEALTHCHECK (middleware `/health`). Unchanged. Recorded in the slice-3 log.

### Scope and style

Files changed: `middleware/engine/pulse.py`, `middleware/engine/pulse_bridge.py`, `middleware/tests/test_pulse_worker.py` (bounded scope), `sim/fmi/pulse/worker/pulse_worker.py`, `sim/fmi/pulse/src/pulse_physiology.cpp`, `sim/fmi/pulse/model/modelDescription.xml`, `sim/fmi/pulse/README.md`, `sim/fmi/check_fmu.py`, and this log. No `sim/SOUP.md` row is needed, because no new dependency is added.
