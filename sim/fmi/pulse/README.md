# Pulse Physiology FMU (pulse_physiology)

Status: slice 3 of plan task 2.7 (SRS FR-MS-006 engine rules behind FR-MS-007). The FMU is an FMI 3.0 Co-Simulation FMU. Its DoStep advances one engine step of 0.01 s, and the engine runs in the `biosync-pulse` container. It passes the physiology checks in `sim/fmi/check_fmu.py --model pulse` (P1 to P4). Gate G2.6 is not measured here. The FR-MS-006 non-blocking requirement applies to the middleware telemetry path and is not claimed by this FMU.

## Files

* `pulse/src/pulse_physiology.cpp`: the FMI 3.0 entry points (C++17). The DLL uses Winsock TCP and a small MessagePack encoder and decoder for the protocol subset. It does not link Pulse.
* `pulse/worker/pulse_worker.py`: the container-side worker. It listens on TCP, owns one `Pulse.Engine` per connection, and serves the frames.
* `pulse/worker/requirements.txt`: the container-side pin (`msgpack==1.2.3`).
* `pulse/model/modelDescription.xml`: the FMI 3.0 variable list (15 variables).
* The build (`sim/fmi/build.ps1`) packages the DLL, the model description, and `resources/pulse_worker.py` into `sim/fmi/build/fmu/pulse_physiology.fmu`.

## Container Route and Precondition

The Pulse engine is compiled into the image `biosync-pulse`. The image is built from `middleware/Dockerfile.pulse` (engine tag `REL_4_3_2`) and is a host dependency of this FMU. It is not in the FMU archive.

* Image: `biosync-pulse:latest`, image ID `sha256:63ee533f26a53267bcf28a7e18565f756130103c1bc124743c7275f5e817dade`, created 2026-10-14T23:36:22Z, 2025137735 bytes. The image was built locally, so it has no registry repo digest. The image is also tagged `biosync-pulse:local` (ID `59d28034fca4`).
* Engine: Kitware Pulse `REL_4_3_2`, Python 3.11.13 in the image, `PULSE_DATA_ROOT=/pulse/bin`.

Route, as built and checked. The DLL does not start the container. The container is a precondition that the operator starts, and the FMU connects to it.

1. Start the worker in the image. The worker script is mounted from the repository and the port is published on the loopback interface:

```
docker run -d --name pulse-fmi-worker -p 127.0.0.1:5055:5055 ^
  -v "<repo>\sim\fmi\pulse\worker\pulse_worker.py:/tmp/pulse_worker.py:ro" ^
  -v "<repo>\sim\fmi\pulse\worker\requirements.txt:/tmp/requirements.txt:ro" ^
  --entrypoint sh biosync-pulse:latest ^
  -c "pip install -q --no-cache-dir -r /tmp/requirements.txt && python /tmp/pulse_worker.py 5055"
```

2. The FMU connects to `127.0.0.1:5055` (the `tcp_port` parameter). The worker logs `pulse_worker listening on 0.0.0.0:5055` when it is ready. The engine loads in about 20 s on the first connection, so a client waits for the `init` reply.

The worker in the image also serves the middleware `Pulse` shim on `PYTHONPATH`. The worker does not import the middleware application.

Known container detail: the image's HEALTHCHECK probes `http://localhost:8000/health` (the middleware API). The worker does not serve that path, so `docker ps` shows the worker container as "unhealthy". The engine is not affected. The FMU does not use Docker health.

## Transport Contract (Frames)

One TCP connection is one FMU instance. The worker serves one connection at a time (listen backlog 4).

* Frame: a 4-byte unsigned big-endian length, then one MessagePack map. The maximum payload is 8 MiB (the serialized engine state is about 2.3 MB).
* Each request has `op`. Each reply has `ok` (boolean). A failure reply has `error` (string).

| Request `op` | Fields | Reply |
|:---|:---|:---|
| `init` | `patient` (map: `patient_id`, `age` in years, `weight_kg`, `height_cm`, `sex`) | `{ok: true}` after `initialize_engine` |
| `step` | `n` (integer, 1 to 1000) | `{ok: true, engine_ms}` after n engine steps of 0.01 s |
| `action` | `kind` (`exercise_intensity`), `value` (float, 0 to 1 is checked by the FMU) | `{ok: true}` |
| `pull` | none | `{ok: true, time_s, values: [7 floats]}`, values in the order of the data requests below |
| `serialize` | none | `{ok: true, state_json}` (a JSON string of the engine state) |
| `shutdown` | none | `{ok: true}`, then the worker releases the engine and closes the connection |

Data requests, in `values` order: HeartRate, SystolicArterialPressure, DiastolicArterialPressure, RespirationRate, OxygenSaturation, MeanAirwayPressure, ArterialOxygenPartialPressure.

Any reply with `ok: false`, a malformed length (zero or above 8 MiB), a malformed map, a closed connection, or a receive timeout (120 s) makes the FMU return fmi3Error and log the cause.

## Lifecycle, Ownership, and Reset (as ruled 2026-11-07)

* Engine ownership: the worker owns exactly one `Pulse.Engine` per connection. The engine is created on `init`, is never pickled or shared across connections, and is released on `shutdown` or on connection close. This is the FR-MS-006 one-long-lived-worker-per-instance rule. The engine stays in the worker across all steps of one FMU instance.
* Transport: TCP with MessagePack frames (edge-bridge pattern), as ruled.
* fmi3ExitInitializationMode connects and sends `init`.
* fmi3DoStep sends `action` (only when the `exercise_intensity` input changed), then `step` with n = 1, then `pull`. One DoStep is one engine step.
* fmi3Reset sends `shutdown` and closes the connection. The next initialization opens a new connection, and the worker creates a fresh engine. This is the SOFA FMU's exact pattern (a worker restart, no replayed command).
* fmi3Terminate sends `shutdown` and closes the connection.

The reset equivalence is checked by case P2 (below). Two engine runs of the same scenario through two connections produce identical physiology outputs at every step.

## Variables

| Name | Causality | Unit | Start | Meaning |
|:---|:---|:---|:---|:---|
| time | independent | s | 0 | FMU time |
| tcp_port | parameter (fixed) | 1 | 5055 | worker TCP port on 127.0.0.1 |
| patient_age | parameter (fixed) | a | 45 | patient age |
| patient_weight | parameter (fixed) | kg | 70 | patient weight |
| patient_height | parameter (fixed) | cm | 175 | patient height |
| exercise_intensity | input | 1 | 0 | exercise action intensity, 0 to 1 (engine `SEExercise`), applied when it changes |
| heart_rate | output | 1/min | calculated | HeartRate |
| systolic_pressure | output | mmHg | calculated | SystolicArterialPressure |
| diastolic_pressure | output | mmHg | calculated | DiastolicArterialPressure |
| respiration_rate | output | 1/min | calculated | RespirationRate |
| spo2 | output | % | calculated | OxygenSaturation converted from the engine fraction to percent |
| mean_airway_pressure | output | cmH2O | calculated | MeanAirwayPressure (0 in the default scenario) |
| arterial_o2_partial_pressure | output | mmHg | calculated | ArterialOxygenPartialPressure (NaN in this data-request set, see known limits) |
| engine_time | output | s | calculated | engine time reported by `pull_data` |
| engine_step_ms | output | ms | calculated | worker wall time of the last engine advance (engine only, excludes transport) |

The FMU step is 0.01 s (`fixedInternalStepSize`). A DoStep with another size returns fmi3Error.

## Mapping to the FR-MS-006 Metric Set

The FR-MS-006 middleware metric set (`middleware/engine/pulse.py`, `SimulationMetrics`) is reproduced by the FMU outputs: heart_rate, blood_pressure_systolic, blood_pressure_diastolic, respiratory_rate, spo2 (percent), and mean_airway_pressure_cm_h2o. arterial_o2_partial_pressure_mmhg maps to arterial_o2_partial_pressure, which is NaN in this engine build. The middleware fields temperature, cardiac_output, stroke_volume, and systemic_vascular_resistance are not data requests in the middleware and are not outputs of this FMU. The PK/PD state of the engine is not exposed as a variable in this slice. The engine state is available through the `serialize` operation of the worker, and is not a co-simulation output.

## Checks (`check_fmu.py --model pulse`)

Results are in `SNDEV/logs/fmi-pulse-check-2026-11-07.json`. Numbers are in the implementation record `SNDEV/docs/impl-2026-11-07-task27-slice3-pulse-fmu.md`.

* P1 stepped physiology sanity: a resting adult (45 y, 70 kg, 175 cm, male), 3000 DoSteps (30 s of engine time), no actions. Every bounded output stays inside its band (heart rate 30 to 200 1/min, systolic 60 to 200 mmHg, diastolic 30 to 130 mmHg, respiration 4 to 60 1/min, SpO2 70 to 100 percent). Engine time is non-decreasing and at most one step (0.01 s) behind the FMU time.
* P1b FMU against the engine: 200 DoSteps through the FMU against 200 direct worker steps of the same scenario, tolerance 1e-9 on the physiology outputs.
* P2 reset: 300 DoSteps with an exercise action at step 100, `fmi3Reset`, re-initialization, the same 300 DoSteps. The physiology outputs are compared at every step (exact equality, NaN as a token). `engine_step_ms` (wall time) is excluded.
* P3 error paths: no listener on the port, an exercise input of 2.0, a communicationStepSize of 0.02 s, and a malformed frame from a fake worker. Each returns fmi3Error.
* P4 step cost: wall time of fmi3DoStep over 1000 DoSteps.

## Step Cost and Master Step Size

P4 measured the DoStep wall time over 1000 steps (see the implementation record for the full distribution). The engine advance is about 0.8 ms of the step. The rest is the TCP round trip and the Python frame handling in the worker. The supported co-simulation step is therefore 10 ms (the engine step). The DoStep cost is well below 10 ms at p99, so the master can call the FMU at every 10 ms of the master timeline. A master step below 10 ms is not supported by this FMU, because the engine step is 10 ms. The master step cannot be finer than the engine step, and a coarser master step (for example 50 or 100 ms) runs the engine for several steps per call. That is a later decision for task 2.8, and this FMU accepts only one engine step per DoStep.

## Known Limits

* The FMU path is synchronous and blocking (each DoStep waits for the worker reply). This is acceptable for co-simulation, where the master calls each participant in turn. The FR-MS-006 non-blocking requirement applies to the middleware telemetry path, and it is not claimed for this FMU.
* ArterialOxygenPartialPressure is NaN in every step of the REL_4_3_2 data-request set used by `middleware/engine/pulse.py`. The FMU reports the NaN and does not invent a value.
* The Pulse engine advances in internal sub-steps. The engine time reported by `pull_data` lags the FMU time by at most one step (0.01 s) and is not exactly equal to it at every step.
* The default scenario (no actions) keeps heart rate near 72 1/min and pressures near 114/74 mmHg. Exercise lowers the pressures sharply in three seconds of engine time (the exercise action is a scenario control, not a validated response). The P1 bounds apply to the default scenario only.
* The worker serves one connection at a time. A second FMU instance must use a second worker (a second port and container). This is the one-engine-per-instance rule.
* The worker container is reached on 127.0.0.1 only. A remote worker needs its own network and security review (NFR-SEC) before use.
* `serialize` returns about 2.3 MB. The FMU does not use it. It is kept for the OQ-16 style state check and for persistence.
* The engine's serialized state differs in five numeric fields (patient weight and tissue fluid volumes) between two fresh engines of the same scenario. The physiology outputs are identical. The reset check uses the outputs, not the serialized state.

## Build and Check

```
powershell -ExecutionPolicy Bypass -File sim\fmi\build.ps1
(start the worker container as in "Container Route and Precondition")
python sim\fmi\check_fmu.py --model pulse
```

The Pulse checks need the worker on 127.0.0.1:5055. With the worker stopped, every case writes a structured FAIL record (no traceback), which is the P3 fail-closed behavior seen at the top level.

## Pulse Engine Surface Used

From `middleware/engine/pulse.py` (read only, not edited): `Pulse.Engine(data_root_dir=...)`, `SEPatientConfiguration().get_patient()`, `initialize_engine(config, drm)`, `advance_time_s(0.01)`, `pull_data()`, `process_action(SEExercise)`, and `serialize_to_string(eSerializationFormat.JSON)`. The data requests are built with `SEDataRequest.create_physiology_request(name)`.
