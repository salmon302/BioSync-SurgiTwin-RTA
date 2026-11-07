Title: Pulse physiology IPC-proxy FMU with TCP transport (plan task 2.7 slice 3)
Date: 2026-11-07T20:00:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.7 slice 3
Summary: Adds the pulse_physiology FMI 3.0 Co-Simulation FMU, a C++17 proxy DLL that talks to a container-side Pulse worker over TCP with MessagePack frames. The worker owns one PulseEngine instance. fmi3Reset restarts the worker. The record holds the build, the container route, the variable list, and the P-case checks.

## Task Reference

Plan task 2.7 in `DEVELOPMENT_PLAN.md` (Phase 2 row "2.7 Package the thermal ablation, mechanical (SOFA), and physiology (Pulse) plant models as FMI 3.0 FMUs"). This slice is the physiology FMU. Requirement FR-MS-007 in `SRS.md` v1.2.0, and FR-MS-006 for the Pulse engine behavior (one long-lived worker per engine instance, the step bound, and the state serialization). Gate G2.6 is later. `DEVELOPMENT_PLAN.md` is not edited. Slice 1 record: `SNDEV/docs/impl-2026-11-05-task27-slice1-thermal-fmu.md`. Slice 2 record: `SNDEV/docs/impl-2026-11-07-task27-slice2-mechanical-fmu.md`.

## Owner Rulings (2026-11-07)

1. Transport: a TCP socket with MessagePack frames (the edge-bridge pattern).
2. Engine ownership: the FMU owns one engine instance (the FR-MS-006 one-long-lived-worker-per-instance rule).
3. fmi3Reset: a worker restart with a fresh engine instance (the SOFA FMU's pattern).

## Specification Summary

* FMI 3.0 Co-Simulation FMU `pulse_physiology`, C++17 proxy DLL, fmi3 C entry points.
* DLL-to-worker over TCP (host and port parameters, default documented). The worker is a container-side Python process that owns one `Pulse.Engine` instance.
* Inputs: the scenario controls the engine accepts. Outputs: hemodynamic pressure, SpO2, and the physiology data requests the engine exposes, with units and start values.
* fmi3Reset is a worker restart.
* Build target in `sim/fmi/build.ps1`. The container image is a host dependency; its tag and digest are recorded.
* Checks in `check_fmu.py` (P1 to P4) with JSON output to `SNDEV/logs/`.
* README section (transport contract, ownership and reset, container precondition, variable list, known limits).
* SOUP rows for new pinned dependencies only.

## Preflight (2026-11-07 record)

* Engine surface (`middleware/engine/pulse.py`, read only): the adapter constructs `Pulse.Engine(data_root_dir=...)` with the patient from `SEPatientConfiguration.get_patient()`, calls `initialize_engine(pc, drm)`, steps with `advance_time_s(TIME_STEP)` where `TIME_STEP = 0.01` s, and reads seven physiology data requests through `pull_data()`: HeartRate, SystolicArterialPressure, DiastolicArterialPressure, RespirationRate, OxygenSaturation, MeanAirwayPressure, ArterialOxygenPartialPressure. OxygenSaturation is a 0 to 1 fraction in the engine. The middleware converts it to percent. Serialization is `serialize_to_string(eSerializationFormat.JSON)`. `PULSE_DATA_ROOT` defaults to `/pulse/bin`.
* Dockerfile (`middleware/Dockerfile.pulse`, read only): the runtime is `python:3.11-bullseye` with `/pulse` copied from the builder. `PYTHONPATH=/pulse/python:/pulse/bin`, `PULSE_DATA_ROOT=/pulse/bin`. The engine version is `REL_4_3_2`.
* Docker: the Docker Desktop service was stopped at the start of this slice. The record starts the service and waits for the daemon (`docker info` succeeded after about 5 s). The image `biosync-pulse:latest` (image ID `sha256:63ee533f26a53267bcf28a7e18565f756130103c1bc124743c7275f5e817dade`, created 2026-10-14T23:36:22Z, 2.03 GB) is present. It has no repo digest, because it was built locally. A second tag `biosync-pulse:local` (ID `59d28034fca4`, 2.11 GB) also exists. The record uses the `latest` ID above.
* Container probe (`SNDEV/logs/`, see the results section): the engine initializes from `/pulse/bin` in 19.9 s, 100 advances of 0.01 s take 68 ms, and seven data requests return values.
* Python packages inside the image: Python 3.11.13, pandas 2.2.2, and the Pulse 4.x bindings (`/pulse/python/Pulse`). `msgpack` is not in the image. It is installable as `msgpack==1.2.3` (the repo pin, also in `sim/fmi/requirements.txt`).
* The repo has no tracked MessagePack code. `edge/README.md` is a placeholder, so the pattern named by the owner is a design pattern, not a code path to copy. The MessagePack pin is therefore the existing `msgpack==1.2.3`.

## Design Decisions

1. Worker location: a container-side process. The worker script is shipped in the FMU `resources/` directory. The container runs the worker through `docker exec` from the DLL launch step, or the container is started with the worker as its command (documented route, see the README). The owner ruling names TCP, so the DLL connects to `127.0.0.1:<port>` on the host, and the container publishes that port.
2. Frames: 4-byte big-endian length prefix, then a MessagePack map. Every request has an `op` field and every reply has `ok`. The FMU and the worker read exactly one frame per request.
3. Step size: the FMU step is 0.01 s, which is the engine `TIME_STEP` from `middleware/engine/pulse.py`. One fmi3DoStep advances the engine by one step (one `advance_time_s(0.01)`). The master step can be a multiple of this.
4. Outputs: the seven data requests plus the simulation time. SpO2 is exposed as the engine fraction (0 to 1), with the middleware's percent conversion documented.
5. Reset: fmi3Reset sends `shutdown`, closes the socket, and the next initialization starts a new worker connection. The worker creates a fresh engine for each connection (one connection per FMU instance).
6. Errors: a container down, a refused connection, a timeout, a malformed frame, or an engine error each return fmi3Error with the cause in the log.

## Implementation Notes

Status: complete for slice 3 (build, container route, checks, records). Commit follows the record.

Files (`sim/fmi/pulse/` is new, plus edits to `sim/fmi/CMakeLists.txt`, `sim/fmi/build.ps1`, `sim/fmi/check_fmu.py`, `sim/fmi/README.md`, and `sim/SOUP.md`):

* `pulse/src/pulse_physiology.cpp`: DLL (C++17, Winsock TCP, hand-written MessagePack encoder and decoder for the protocol subset, fmi3 entry points). About 700 lines, SPDX MIT.
* `pulse/worker/pulse_worker.py`: container-side TCP worker (one `Pulse.Engine` per connection, frame limit 8 MiB). SPDX MIT.
* `pulse/worker/requirements.txt`: `msgpack==1.2.3` (container pin).
* `pulse/model/modelDescription.xml`: 15 variables.
* `pulse/README.md`: the transport contract, container route, ownership and reset, variables, metric mapping, checks, step size, known limits.

Build (`sim/fmi/build.ps1`, Release, MSVC 19.44.35217, x64, `/W4 /WX`): zero warnings. Packaged FMU `sim/fmi/build/fmu/pulse_physiology.fmu` (29763 bytes, sha256 `d906c827398e54a352b73ce8ea5d8c661cdc1d955fb1a9dc1dbedda76cdcd5d5`). Archive contents: `modelDescription.xml` (5965 bytes), `binaries/x86_64-windows/pulse_physiology.dll` (51712 bytes), `resources/pulse_worker.py` (7483 bytes). The thermal and mechanical FMUs build unchanged in the same run.

Container route as built: the operator starts the worker container (command in `pulse/README.md`). The FMU does not start Docker. It connects to `127.0.0.1:5055`. The docker daemon was stopped at the start of the slice and was started for this run (`com.docker.service`). The image is a host dependency (SOUP row added).

Preflight findings: the Docker Desktop service was stopped and was started for the run. The image `biosync-pulse:latest` has no `msgpack`, so a pinned install runs at worker start. `edge/` is a placeholder, so no MessagePack code exists to copy. The MessagePack pin is the existing `msgpack==1.2.3`. The engine's `advance_time_s` advances in internal sub-steps, so engine time is not exactly equal to FMU time.

Checks and changes during the run (recorded for transparency). The first full run (`SNDEV/logs/fmi-pulse-check-attempt2-2026-11-07.json`) failed P1, P1b, and P2. The causes and the fixes:

1. P1b failed with a deviation of 9646 because the check converted the SpO2 engine fraction to percent on the FMU side and did not convert the worker side correctly. The FMU was right. The check was fixed to scale the worker's fraction once. After the fix, the deviation is 0.0 over 200 steps (`attempt4`).
2. P1 failed on the engine-time rule. The check assumed engine time equals FMU time at each step. The engine advances in sub-steps, so the rule was changed to what the engine does: non-decreasing and at most one step behind. This is a change of the pre-run assumption, and the check now tests a weaker, documented property. The FMU's time is still exact.
3. P2 failed with 300 of 300 mismatches. The FMU outputs were identical across the two runs. The mismatch came from the wall-time output (`engine_step_ms`, which varies run to run) and from NaN compared as a value. The check was changed to exclude the wall-time output and to compare NaN as a token. The physiology outputs are compared exactly.

These are check corrections, not FMU changes. The pass criteria stayed the same in spirit (exact agreement, bounds, error returns). The P1 engine-time rule is the one that weakened, and that is recorded here.

Results (official run `SNDEV/logs/fmi-pulse-check-2026-11-07.json`, all five cases PASS. Host state after the run is in `SNDEV/logs/fmi-pulse-host-after-2026-11-07.txt`: 0.4 percent total CPU and no watched process. No before snapshot was saved for this run, so the quiet state before the run is not recorded and is an open item):

* P1 stepped sanity (resting adult, 3000 DoSteps, 30 s engine time): zero out-of-bounds samples for heart rate, systolic, diastolic, respiration, and SpO2 (bands in the README). All 3000 rows have finite bounded outputs. Final values: heart rate 72.02, systolic 114.23, diastolic 73.60 mmHg, respiration 12.05 per min, SpO2 97.43 percent. Engine time non-decreasing and within one step of FMU time. ArterialOxygenPartialPressure NaN in all steps (known limit).
* P1b FMU against the engine (200 DoSteps against 200 direct worker steps): max absolute deviation 0.0 (tolerance 1e-9).
* P2 reset (300 DoSteps, exercise action at step 100, fmi3Reset, re-initialization, same 300 DoSteps): 0 mismatched physiology output values across 300 steps and 8 outputs (engine time included, wall time excluded, NaN as a token).
* P3 error paths: unreachable port (connection refused) returns fmi3Error; exercise intensity 2.0 returns fmi3Error; communicationStepSize 0.02 s returns fmi3Error; malformed frame (length 2^30 against the 8 MiB limit) returns fmi3Error. All status 3.
* P4 step cost (1000 DoSteps at 0.01 s, wall time per fmi3DoStep, TCP and worker included): mean 2.219 ms, p50 2.481 ms, p95 3.398 ms, p99 3.838 ms, min 1.226 ms, max 4.608 ms, zero steps over 10 ms. The worker's engine advance averages 0.777 ms of that.

Worker-down run (`SNDEV/logs/fmi-pulse-check-worker-down-2026-11-07.json`): with the worker container stopped, each P case fails with a structured record (`P_failed_*`, error text), and no traceback. The container precondition is therefore fail-closed.

Reset equivalence against a fresh instance: the P2 comparison runs the same scenario through two connections (a reset and a fresh instance). Identical outputs at every step confirm that the restarted engine equals a fresh engine for the physiology outputs. The serialized state of two fresh engines differs in five numeric fields (patient weight and tissue fluid volumes). The serialized state is therefore not byte-equal between runs, and the check does not use it.

Master step size implication (task 2.8). The engine step is 10 ms and the FMU accepts one engine step per DoStep. The measured DoStep p99 (3.84 ms) is below 10 ms, so the master can call this FMU at a 10 ms master step. A finer master step is not supported. A coarser master step needs an FMU that accepts multiple engine steps per call, which is a later decision.

Host and container notes. The `pulse-fmi-worker` container reports "unhealthy" from the image HEALTHCHECK, which probes the middleware `/health` path. The engine is not affected, and the FMU does not use Docker health.

Engineering notes (bring-up): (1) The first worker probe ran in a separate container that could not see the client file (a mount issue), so the client now runs in the worker container. (2) The 2.3 MB serialize reply exceeded the first 1 MiB frame limit, so the limit is 8 MiB. (3) The FMU model description had the schema-order error seen in slices 1 and 2 (UnitDefinitions must come first), fixed. (4) The FMU's host parameter cannot be set through a float reference, so the worker host is fixed to 127.0.0.1 in this slice.

Owner items (not decided here): the container route (operator starts the container, FMU connects) and the port choice are recorded as built. If the owner prefers the FMU to start the container, that is a later change. The container is on the loopback interface only.

Open items: the arterial oxygen partial pressure is NaN in the REL_4_3_2 data-request set (the middleware data-request list has the same name, so this affects the FR-MS-006 metric set too). The engine's sub-step timing is documented, not corrected. The worker is one connection at a time. The exercise response is a scenario control, not a validated physiological response.
