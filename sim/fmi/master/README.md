# FMI 3.0 Co-Simulation Master (SRS FR-MS-007)

Status: slice 1 of plan task 2.8. The master core runs one participant (`thermal_pennes.fmu`, from `sim/fmi/`). It publishes the master clock and the participant state over Fast DDS and has a single-node skew and jitter harness. The three-node run, the G2.6 gate, and the multi-participant schedule are later slices.

## Files

* `CMakeLists.txt`, `package.xml`: ament_cmake package `srtra_fmi_master` (C++17).
* `include/srtra_fmi_master/participant.hpp`: participant interface used by the scheduler (FMU adapter and test fake).
* `include/srtra_fmi_master/scheduler.hpp`, `src/scheduler.cpp`: the scheduler (schedule table, exchange, latched errors, reset).
* `include/srtra_fmi_master/fmu_participant.hpp`, `src/fmu_participant.cpp`: FMI 3.0 Co-Simulation adapter (loads the FMU DLL, the only file that includes the FMI headers).
* `include/srtra_fmi_master/tick_waiter.hpp`: high-resolution waitable timer pacing (bridge node pattern).
* `src/master_node.cpp`: the `fmi_master_node` executable (ROS 2 publisher).
* `msg/MasterClock.msg`, `msg/ParticipantState.msg`: topic types.
* `tests/test_scheduler.cpp`: Catch2 v3.9.1 unit tests against a fake FMU stub.
* `build.ps1`: colcon build (MSVC, Release or RelWithDebInfo) and CTest run.
* `tools/measure_master.py`: rclpy harness (pixi CPython 3.12). Records per-message arrival and source stamps, writes the record and the sidecar, and computes skew and jitter.
* `tools/run_measure.ps1`: extracts the FMU, starts the harness, runs `fmi_master_node`, records host state before and after.

## Build and Run

Build the FMU first (`sim\fmi\build.ps1`), then:

```
powershell -NoProfile -ExecutionPolicy Bypass -File sim\fmi\master\build.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File sim\fmi\master\tools\run_measure.ps1 -Duration 600
```

`build.ps1` accepts `-Config Release` (default) or `-Config RelWithDebInfo`, and `-SkipTests`. The package builds from `env/ros2-jazzy` (ROS 2 Jazzy, CPython 3.12.16, `rmw_fastrtps_cpp`). The build base is `sim\fmi\master\build\b`, and the outputs are gitignored.

The CMake configure prints a warning about `CMAKE_OBJECT_PATH_MAX` for the generated ROS type support code (one object directory is 162 characters long, because of the repository path length). The build still succeeds.

`fmi_master_node` parameters (`--ros-args -p name:=value`): `fmu_dir` (unzipped FMU), `instantiation_token` (the `instantiationToken` of the model description), `model_identifier` (default `thermal_pennes`), `participant_name` (default `thermal_pennes`), `duration_s`, `base_step_ms` (default 10), `fmu_step_ms` (default 100), and `timer_mode` (`high_resolution` or `sleep`).

## Scheduler Semantics

* Timeline: integer nanoseconds. The base step `H` is the master tick (10 ms). Ticks are `0, H, 2H, ...`, and `advance_to(t)` must be called with consecutive ticks. Any other tick returns `kTimeError`.
* Schedule table: each participant has a communication step `P` (the `h` of `fmi3DoStep`) and an offset `O`. Its step points are `O + kP`. `P` and `O` must be multiples of `H`, and `P` must equal the FMU fixed step. The constructor rejects any other configuration with `std::invalid_argument`.
* Exchange at a tick `t`: for each participant with a step point at `t`, in participant index order:
  1. set the master-side stimuli for this participant at `t`;
  2. set every wired input from the producer output cache (the value the producer published at its most recent step point);
  3. call `fmi3DoStep(t, P)` through `do_step`;
  4. read the participant outputs into the cache.
* Zero-order hold: a consumer reads the producer's last published output. A producer that steps later in the same tick is seen at its previous step point. The ordering rule is part of the deterministic result.
* Failure: any failed `set_real`, `do_step`, or `get_real` latches. Every later call returns the same status (participant index, tick time, static message, and the FMU `last_error` text) until `reset()`.
* Reset: `reset()` calls `fmi3Reset` on every participant, then initializes again. It clears the timeline and the step counts. A run after reset reproduces the run before it (Catch2 case "reset restores the timeline and reproduces the run exactly").
* Allocation: the scheduler allocates in its constructor and in `initialize()`. `advance_to` does not allocate, and the output cache is a preallocated vector per participant. The publish path (rclcpp serialization and the Fast DDS send) allocates inside the middleware and is outside this guarantee.
* Determinism: the schedule and the exchange order are fixed by the configuration. The same configuration and inputs give the same output sequence (tested).

## Clock Mapping (FMI 3.0)

The thermal FMU is a Co-Simulation FMU with `fixedInternalStepSize="0.1"` and `canHandleVariableCommunicationStepSize="false"`. It declares no clock variables, so it does not use FMI 3.0 clocks or Scheduled Execution (`fmi3InstantiateScheduledExecution` and `fmi3ActivateModelPartition` are not implemented in the FMU).

The master maps the scheduled-variable discipline onto `fmi3DoStep` for this participant type as follows:

| FMI 3.0 scheduled-variable step | Master action in slice 1 |
|:---|:---|
| Clock tick of the participant partition | A step point of the schedule table (every 100 ms of master time for the thermal FMU) |
| Input update before the step | `fmi3SetFloat64` for the stimuli and the wired inputs, at the step point, before `fmi3DoStep` |
| Activation of the partition | `fmi3DoStep(currentCommunicationPoint = t_k, communicationStepSize = 0.1 s)`, one call per step point |
| Output read after the step | `fmi3GetFloat64` of the outputs after the step, cached until the next step point |
| Clock variables of the model | None declared by the FMU. The master-side periodic clock (the base tick, 10 ms) is the master timeline only |

A Scheduled Execution FMU (a model with clock variables) would map a clock tick to `fmi3ActivateModelPartition(clockReference, activationTime)`, and the master would call `fmi3GetClock`/`fmi3SetClock` at the same points. That path is not built in slice 1.

The publish rate is a master design choice. The master base tick is 10 ms (100 Hz planned rate), which gives 10 publish points per FMU step. The FMU is stepped every tenth tick. The rate matches the 10-minute baseline (60000 ticks per topic). A rate of 10 Hz (one tick per FMU step) would give 6000 messages per topic, which is too few for a p99 estimate. The 100 Hz rate is also below the bridge rates (500 Hz) and above the FMU step.

## Message Contract

| Topic | Type | Publish rate | Content |
|:---|:---|:---|:---|
| `/srtra/fmi/master/clock` | `srtra_fmi_master/msg/MasterClock` | 100 Hz | `header.stamp` (source stamp), `tick`, `master_time_ns` (the timeline time of the tick), `scheduled_steady_ns` (the steady-clock instant that the tick was scheduled for) |
| `/srtra/fmi/participant/thermal_pennes` | `srtra_fmi_master/msg/ParticipantState` | 100 Hz | `header.stamp`, `tick`, `steps`, `fmu_time_s`, and the held outputs `t_max_k`, `t_mean_k`, `v60_mm3`, `v_lesion_mm3` |

Both topics are reliable with a keep-last queue of 1000. The two messages of one tick share the same `header.stamp`, so a subscriber matches them by tick and stamp.

Source stamps: `header.stamp` carries the master steady clock (ns since the steady clock epoch) taken immediately before publish. On Windows, MSVC `steady_clock` and CPython `perf_counter` both read QueryPerformanceCounter, so the harness compares its arrival time with the stamp directly. The harness checks this epoch at the first message (the first arrival minus the first stamp is within 50 ms). The master records one anchor pair (system clock and steady clock) at start in its run summary, as in the bridge v3 capture.

## Measurement Definitions (single node)

* Clock skew (per message): arrival time (harness `perf_counter_ns` at callback entry) minus the source stamp. On one node the reference clock and the master read the same counter, so this value is the one-way delivery time plus the epoch error. It is an upper bound on the skew between the master clock and the reference clock. The distribution is reported with the variation about the median (`skew_variation_about_median_ms`), which removes the constant delivery offset.
* Message jitter (per topic): the arrival interval minus the nominal period (10 ms). The source-stamp interval minus the nominal period is reported beside it, which separates master pacing jitter from delivery jitter.
* Publish pacing: the source stamp minus `scheduled_steady_ns` for the clock messages.
* Pass criteria (fixed before the 10-minute run): the maximum absolute skew over all messages is at most 1 ms, and the maximum absolute arrival-interval jitter of each topic is at most 1 ms. The p95 and p99 values are reported for comparison.

## Inter-Node Protocol Sketch (three-node run, later slice)

The three-node run of gate G2.6 needs a clock that is not the master clock. The sketch below is a plan, not an implementation.

* Nodes: the master node (scheduler and FMUs), a participant node for each additional plant model (task 2.7 FMUs), and a reference node that publishes `/srtra/fmi/reference/clock` at the master tick rate with its own steady-clock stamp.
* Tick identity: every message carries `tick` and the master timeline time `master_time_ns`. The harness pairs messages from the three nodes by `tick`.
* Reference clock: the reference node stamps its messages on its own host. Clock offset between the master and the reference is estimated from paired stamps with a round-trip exchange on a separate topic (`/srtra/fmi/sync/ping` and `/srtra/fmi/sync/pong`). The offset estimate is the midpoint of the round trip, and its uncertainty is half the round trip.
* Skew: the master stamp minus the reference stamp at the same tick, corrected by the offset estimate, with its uncertainty reported beside it.
* Jitter: per topic, as in the single-node definition, on the arrival times at the harness.
* Recording: per-message stamps (tick, source stamp, arrival, node name) in the bridge v3 sidecar encoding.

## Single-Node Measurement

Run: 600 s at the 100 Hz planned rate, `timer_mode` high_resolution, 60000 ticks per topic, FMU stepped 6000 times, host state recorded before and after. Record `SNDEV/logs/fmi-master-measure-600s-high_resolution-2026-11-06T015357Z.json` (UTC time of the run, 2026-11-06 01:53 to 02:04 UTC), sidecar `...messages.json` (2.85 MB). The run is contended: Warhammer3 ran for the whole run at about one core (CPU time 22588.9 s before and 23174.3 s after). No Slicer process was seen at the two snapshots. The host was not sampled during the run, so a Slicer start inside the run window is not excluded.

| Measure (ms) | Clock topic | State topic | Bound |
|:---|---:|---:|---:|
| Skew (arrival minus source stamp): mean | 0.445 | 0.560 | 1 |
| Skew: p50 / p95 / p99 | 0.430 / 0.624 / 0.765 | 0.538 / 0.780 / 0.945 | 1 |
| Skew: max absolute | 5.592 | 5.750 | 1 |
| Skew variation about median: p99 / max | 0.334 / 5.161 | 0.407 / 5.212 | 1 |
| Arrival-interval jitter: p50 / p95 / p99 | 0.029 / 0.354 / 0.519 | 0.027 / 0.383 / 0.570 | 1 |
| Arrival-interval jitter: max absolute | 4.923 | 4.962 | 1 |
| Source-stamp interval jitter: max absolute | 4.526 | 4.526 | 1 |
| Publish pacing (stamp minus scheduled): mean / p99 / max | 0.297 / 0.637 / 4.864 | not recorded | not applicable |

Verdict as pre-registered: skew FAIL (maximum 5.75 ms), arrival jitter FAIL (maximum 4.96 ms), message counts and consecutive tick sequences PASS (60000 per topic), epoch check PASS (first arrival minus first stamp 0.43 ms). Six clock ticks were published more than 1 ms late, with the worst at 4.86 ms, so the master pacing contributed to both the publish-time tail and the arrival jitter.

Interpretation. The skew median of about 0.5 ms is one-way delivery time on this single node, not clock error. The skew bound as defined is therefore not a clock-skew measurement on one node. The variation about the median (p99 0.41 ms) is the delivery-time spread. The maxima of about 5 ms come from a small number of late publishes on a host that was not idle. Separating the master clock from the reference clock needs the three-node run.

The FMU state at the end of the run is consistent with the case B1 behavior: T_max 310.33 K (the tissue has cooled to the arterial temperature), V_lesion 480 mm3 (the same lesion volume as check case B1).
