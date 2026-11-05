Title: ROS 2 bridge node slice 1 (plan task 2.4, package, messages, synthetic publisher, rate smoke)
Date: 2026-11-05T15:53:25Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.4 slice 1
Summary: Converts sim/bridge/ into an ament_cmake ROS 2 package (srtra_bridge) with three publish streams, a synthetic-data BridgeNode, an rclpy rate measurement script, and 100 Hz and 500 Hz smoke captures over rmw_fastrtps_cpp.

## Task Reference

Plan task 2.4 in `DEVELOPMENT_PLAN.md`, slice 1 (node and build wiring plus a smoke measurement, about 2 of the 4.0 day estimate). Requirement FR-MS-004 in `SRS.md` v1.2.0 (VAL-027 Option B). Gate G2.4 is a later slice. Environment: `env/ros2-jazzy/` (pixi, `ros-jazzy-ros-base` 0.11.0, `ros-jazzy-rmw-fastrtps-cpp` 8.4.4, CPython 3.12.16). Predecessor record: `SNDEV/docs/impl-2026-11-04-task203-ros2-env.md`.

## Specification Summary

* Deploy a ROS 2 bridge node over Fast DDS (`rmw_fastrtps_cpp`) that publishes tool-tip pose, 6-axis wrench, and mesh deformation state on every publish tick.
* SlicerROS2 is not used. WSL2 is not used.
* Slice 1 scope: `ament_cmake` package at `sim/bridge/`, the three message streams, a `BridgeNode` with a configurable rate (default 500 Hz), preallocated buffers, a deterministic synthetic trajectory source, an `rclpy` subscriber that measures rate, and 60 s smoke runs at 100 Hz and 500 Hz.
* Out of scope (slice 2): the 10 minute 500 Hz G2.4 gate run on a quiet host.
* Build type: Release or RelWithDebInfo only, for ABI compatibility with the pinned ROS 2 binaries (`impl-2026-11-04-task203-ros2-env.md`, addendum).
* Approval gate: this slice touches more than 5 files in `sim/bridge/` and `SNDEV/`. The work proceeds on the direct instruction of the parent session, which assigned the file set and the scope.

## Implementation Notes

Preflight. Read `env/ros2-jazzy/pixi.toml`, `sim/SOUP.md`, and the task 2.0.3 record. Pre-existing `sim/bridge/` content: `CMakeLists.txt` (placeholder, no targets, 3 lines) and `README.md` (placeholder status). `SNDEV/logs/` exists and holds prior captures. This log was created before any other change.

Root `CMakeLists.txt` line 11 defines `option(SRTA_BUILD_BRIDGE ... OFF)` and line 28 calls `add_subdirectory(sim/bridge)` inside `if(SRTA_BUILD_BRIDGE)`. This option is kept and its meaning is unchanged: it gates the bridge package on the host CMake path. The colcon build in `sim/bridge/` does not use the root CMake project, so the option only matters for a configure that includes the root project.

Toolchain probe (2026-11-05). The locked environment provides `ament_cmake`, `ament_index`, `rosidl_default_generators`, `rosidl_default_runtime`, `ros2.exe`, and CMake 4.4 (`env/ros2-jazzy/.pixi/envs/default/Library/bin/cmake.exe`). It does not provide colcon or ninja. The lock has no `colcon` or `ninja` entry. MSVC is present at `C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe`. A stray `I:\LLM\x64\cl.exe` is also on PATH, so `build.ps1` selects the MSVC toolchain through `vcvars64.bat` rather than relying on PATH.

Dependency decision (re-lock). The task requires `colcon build`, which the locked environment cannot run. Two pins are added to `env/ros2-jazzy/pixi.toml`, both from conda-forge, both exact:

* `colcon-common-extensions` `==0.3.0` (conda-forge). Pulls colcon-core, colcon-cmake, and the ament_cmake build task through colcon-ros. Search result: conda-forge lists `colcon-core` 0.21.3, `colcon-ros` 0.5.0, `colcon-cmake` 0.2.30, `colcon-common-extensions` 0.3.0. The `robostack-jazzy` channel has no colcon packages.
* `ninja` `==1.13.2` (conda-forge). Without ninja, colcon uses the Visual Studio generator, which is multi-config and ignores `CMAKE_BUILD_TYPE` at build time. The Ninja generator honors `-DCMAKE_BUILD_TYPE=Release`.

Pre-change snapshots (for diff): `SNDEV/logs/ros2-jazzy-pixi-lock-before-task24-2026-11-05.lock.txt` and `SNDEV/logs/ros2-jazzy-pixi-toml-before-task24-2026-11-05.txt`.

Re-lock result (`pixi add --no-install colcon-common-extensions==0.3.0 ninja==1.13.2`, then `pixi install`). Transcripts: `SNDEV/logs/ros2-jazzy-pixi-add-colcon-ninja-2026-11-05.txt` and `SNDEV/logs/ros2-jazzy-pixi-install-task24-2026-11-05.txt`. Diff of conda package URLs between the snapshot and the new lock: 380 entries before, 408 after. No ROS, Fast DDS, rmw, or CPython pin changed. Added: colcon-core 0.21.3, colcon-cmake 0.2.30, colcon-ros 0.5.0, colcon-common-extensions 0.3.0, and their plugin and test dependencies, plus ninja 1.13.2, pyreadline3, pywin32, coverage, and colcon-notification. One transitive pin moved: setuptools 84.2.1 to 79.0.1, because colcon-core 0.21.3 requires `setuptools>=30.3.0,<80`. The setuptools move is recorded here. `sim/SOUP.md` is outside this task's assigned directories, so its ROS 2 row (lock revision, the new colcon and ninja pins, and the setuptools move) needs an update by the owner of that file. Verified after install: `colcon 0.21.3` plugins listed, `ninja 1.13.2`, `cmake 4.4.5`.

Package files created in `sim/bridge/`:

* `package.xml` (format 3, ament_cmake, MIT, maintainer per AGENTS.md section 7). Dependencies: geometry_msgs, rclcpp, std_msgs, rosidl_default_generators (build), rosidl_default_runtime (exec).
* `CMakeLists.txt` (replaces the placeholder). Sets `CMAKE_CXX_STANDARD 17`. Defaults `CMAKE_BUILD_TYPE` to Release and stops configure with FATAL_ERROR for any type other than Release or RelWithDebInfo. Generates `srtra_bridge/msg/MeshDeformationState` and builds the `bridge_node` executable. `/W4 /permissive-` on MSVC, no `/WX`.
* `msg/MeshDeformationState.msg`, `include/srtra_bridge/bridge_node.hpp`, `src/bridge_node.cpp`, `src/bridge_node_main.cpp` (all carry `SPDX-License-Identifier: MIT`).
* `build.ps1` and `README.md` (see below).

Root option. `SRTA_BUILD_BRIDGE` (root `CMakeLists.txt`, line 11, default OFF) still gates `add_subdirectory(sim/bridge)` at line 28. The root file was not edited because it is outside the assigned directories. With the option ON, the top-level configure reaches this package's `CMakeLists.txt`, which needs `CMAKE_PREFIX_PATH` pointing at `env/ros2-jazzy/.pixi/envs/default/Library`. The supported build route is `build.ps1` (colcon). The option is documented as a gate only, and a replacement for the root wiring is listed under slice 2 in the README.

Message contract (initial, to be carried into the README):

* Topic `/srtra/bridge/tool_tip_pose`, `geometry_msgs/msg/PoseStamped`. Position in meters, orientation as a unit quaternion (x, y, z, w), frame `reference_frame` (default `srtra_world`).
* Topic `/srtra/bridge/tool_wrench`, `geometry_msgs/msg/WrenchStamped`. Force in newtons, torque in newton-meters, same frame.
* Topic `/srtra/bridge/mesh_deformation`, `srtra_bridge/msg/MeshDeformationState`. Fields: `std_msgs/Header header`, `uint64 tick`, `string reference_frame`, `uint32 node_count`, `float32[<=16] mode_coefficients` (modal amplitudes in meters).
* Tick identity: the three messages of one tick share one `header.stamp` value. The mesh message also carries `tick`, which starts at 0 for each run and increases by 1 per tick.

Mesh message choice. The message carries modal deformation-mode coefficients, not nodal displacements. Nodal displacement arrays scale with the mesh node count (4096 nodes times 3 floats is 48 kB per tick, about 24 MB/s at 500 Hz), which is not bounded in a useful way. The mode count is bounded at 16, with 8 used in slice 1 (`kModeCount`). Budget: header about 40 bytes with frame_id, tick 8 bytes, reference_frame about 20 bytes, node_count 4 bytes, coefficients at most 64 bytes. Serialized size is below 200 bytes, about 100 kB/s at 500 Hz. The mapping from nodal state to modal coefficients is a slice 2 item (the SOFA reduced basis, FR-MS-002).

Node behavior (`BridgeNode`, `srtra_bridge` executable `bridge_node`):

* Parameters (ROS 2 parameters, set with `--ros-args -p name:=value`): `rate_hz` (int, default 500, range 1 to 1000), `duration_s` (int, default 0 meaning unbounded), `reference_frame` (string, default `srtra_world`), `mesh_node_count` (int, default 4096). Integer parameters are used because rclcpp declares them as int64 and `-p rate_hz:=100` gives the expected type.
* Publish loop: fixed-period schedule from `std::chrono::steady_clock`, period in integer nanoseconds (100 Hz is 10 ms, 500 Hz is 2 ms). `std::this_thread::sleep_until` on each tick. A tick that starts at least one period late increments `late_ticks_`, reported at exit.
* Source data: deterministic synthetic trajectories. Each value is a function of the tick index (`t = tick / rate_hz`) and not of the wall clock, so two runs at the same rate give the same sample values. Tool tip: a 0.2 Hz Lissajous path (x amplitude 0.02 m, y 0.01 m at twice the frequency, z near 0.10 m), yaw 0.3 rad amplitude. Wrench: force about 1.5 N to 2.0 N with sinusoidal components, torque at the 0.01 N m to 0.02 N m level. Mesh: 8 modal coefficients, amplitude 0.002 m divided by mode index.
* Allocation: the three message objects are members, sized once in the constructor (`mode_coefficients.assign(8, 0.0F)`). The hot loop assigns fields only, with no `new`, no `push_back`, and no string construction. The publisher call uses `publish(const T &)` with intra-process communication off (rclcpp default), so rclcpp does not copy the message. Serialization and buffer work inside Fast DDS is outside this code.
* Queue: reliable, keep-last depth 100 on each publisher.

Build verification, attempts (transcripts in `SNDEV/logs/`):

* Attempt 1 (`bridge-build-2026-11-05-attempt1.txt`): FAIL. `colcon --log-base` is a top-level option, so it was moved before `build`. Not a build failure.
* Attempt 2 (`bridge-build-2026-11-05-attempt2.txt`): EXIT 0 with Visual Studio generator. Warnings: C4244 (`int64_t` to `int`) at the parameter declarations in `bridge_node.cpp` lines 26 and 39. The generator is Visual Studio 17 2022 because colcon-cmake selects a Visual Studio generator on Windows unless `-G` is present in `--cmake-args`. With a multi-config generator `CMAKE_BUILD_TYPE` is ignored at build time, so the Release requirement was not enforced.
* Attempt 3 (`bridge-build-2026-11-05-attempt3.txt`): EXIT 0. Warning: CMake `object file directory ... has 161 characters` near `CMAKE_OBJECT_PATH_MAX`.
* Attempt 4 (`bridge-build-2026-11-05-attempt4.txt`): PASS. EXIT 0, no stderr, no compiler warnings (`grep warning` on the colcon `stdout_stderr.log` gives 0 matches). CMakeCache: `CMAKE_GENERATOR=Ninja`, `CMAKE_BUILD_TYPE=Release`, `CMAKE_CXX_FLAGS_RELEASE=/O2 /Ob2 /DNDEBUG`, compiler `cl.exe` from Visual Studio 2022 Community 14.44.35207.

Changes made to fix attempts 2 and 3: (a) `build.ps1` passes `--cmake-args -G Ninja -DCMAKE_BUILD_TYPE=Release`. The task text listed only `-DCMAKE_BUILD_TYPE=Release`. The `-G Ninja` addition is required because colcon-cmake otherwise selects Visual Studio, and the Release requirement must hold. (b) The three parameters are declared as `std::int64_t`. (c) The build base is `sim/bridge/build/b` (`colcon-build` was too long for the object path limit).

Smoke-run defects found and fixed before the measured runs:

* Pretest 1 (5 s, 100 Hz, `pretest` scratch directory, not in `SNDEV/logs/`): the node reported `late_ticks=177`, and the source stamps stepped in 15 to 16 ms increments. Cause: the default Windows timer resolution is about 15.6 ms, so `sleep_until` returned late and the loop caught up with back-to-back publishes. Fix: `TimerResolutionGuard` in `bridge_node.cpp` calls `timeBeginPeriod(1)` for the lifetime of `run()` (link `winmm` in `CMakeLists.txt`). Result: `late_ticks=0`, source stamp p95 11.0 ms.
* Pretest 2: the subscriber joined about 0.8 s after the node started, so ticks 0 to 76 were missing and the mesh topic matched one tick after the other two topics (one partial tick). Fix: the node waits for at least one matched subscription on each of the three publishers before its first tick (`wait_for_subscribers`, default true, 30 s limit). The subscriber writes a ready file after its subscriptions exist (`--ready-file`), and `run_smoke.ps1` waits for that file before it starts the node. Result: 500 of 500 ticks complete, no partial ticks, zero gaps.
* `Start-Process` returned a null `ExitCode` in this host, even for `cmd /c "exit 3"`. The driver runs the node synchronously and reads `$LASTEXITCODE`. The subscriber is judged by the presence of its JSON record.
* Driver invocation error: `-Rates 100,500` under `powershell -File` bound as the single integer 100500. The node rejected `rate_hz=100500` (exit 1) and the subscriber timed out with zero messages after its 120 s startup limit. Fix: `-Rates` is now a comma-separated string. The failed run artifacts are kept as recorded: `SNDEV/logs/bridge-smoke-100500hz-60s-2026-11-05T160651Z*` (9 files, all with the zero-message JSON).
* The subscriber also calls `timeBeginPeriod(1)` through `ctypes` (winmm) for its own arrival timestamps.

Smoke run (not the G2.4 gate). Command: `powershell -NoProfile -ExecutionPolicy Bypass -File sim\bridge\tools\run_smoke.ps1 -Rates "100,500" -Duration 60`. Driver transcript: `SNDEV/logs/bridge-smoke-run-2026-11-05.txt` (EXIT 0). Build transcripts: `bridge-build-2026-11-05-final.txt`. Per-rate captures:

| Item | 100 Hz | 500 Hz |
|:-----|:-------|:-------|
| JSON record | `SNDEV/logs/bridge-smoke-100hz-60s-2026-11-05T160903Z.json` | `SNDEV/logs/bridge-smoke-500hz-60s-2026-11-05T161011Z.json` |
| Node transcript | `...-node-stderr.txt` (same stem) | `...-node-stderr.txt` (same stem) |
| Subscriber transcript | `...-subscriber.txt` | `...-subscriber.txt` |
| Ticks published (node) | 6000 | 30000 |
| Messages received (pose, wrench, mesh) | 6000, 6000, 6000 | 30000, 30000, 30000 |
| Ticks with all three streams | 6000 | 30000 |
| Missing complete ticks vs expected | 0 | 0 |
| Partial ticks | 0 | 0 |
| Mesh tick-index gaps and duplicates | 0, 0 | 0, 0 |
| Wrench wall duration (first to last arrival) | 59.985 s | 60.000 s |
| Wrench achieved mean rate | 100.008 Hz | 499.983 Hz |
| Subscriber arrival interval (mean, p50, p95, p99, max) | 10.00, 15.0, 16.0, 16.0, 16.0 ms | 2.00, 0.0, 16.0, 16.0, 16.0 ms |
| Source stamp interval (mean, p95, max) | 10.00, 11.03, 11.60 ms | 2.00, 3.00, 4.02 ms |
| Node `late_ticks` | 0 | 787 (2.6 percent) |
| Non-finite messages | 0 | 0 |
| Stop reason | idle_timeout (3 s after the last message) | idle_timeout |

Interpretation.

* Presence: every tick carried pose, wrench, and mesh at both rates.
* Rate: the node schedule holds. The source stamps place the ticks at 10.0 ms and 2.0 ms on average, and the subscriber count over wall time agrees to 0.01 percent.
* Subscriber arrival intervals are not a valid p95 measure at this stage. The arrivals come in batches on each rclpy wake-up (at 500 Hz, the p50 is 0.0 ms and the p95 is 16 ms), while the source stamps are tight. The receive-side p95 therefore reflects subscriber wake-up batching, not publish jitter. The source-stamp statistics are the publish-side jitter measure. Slice 2 must address this before the arrival p95 is used as evidence.
* Node late ticks at 500 Hz: 787 of 30000 ticks began at least one period late, with a maximum source-stamp interval of 4.02 ms. Delivery still reached 30000 of 30000 ticks, but the 1 ms `timeBeginPeriod` schedule leaves jitter that slice 2 should measure under the 10 minute run.

Build and RMW warnings. Final build (`bridge-build-2026-11-05-final.txt`): EXIT 0, no CMake warning, no compiler warning. The RMW stack emitted no warnings in the captured node or subscriber stderr. The native stderr lines appear in PowerShell as `NativeCommandError` records (rclcpp writes INFO logs to stderr). This is a display effect of the PowerShell host and does not affect the exit code.

Verification gates (slice 1):

* Build (`sim/bridge/build.ps1`): PASS. EXIT 0, Release, Ninja, MSVC 14.44.35207.
* Compiler warnings: PASS (0 in the final log).
* Locked environment: PASS. Re-lock changed only the new colcon and ninja entries and the setuptools move. ROS and Fast DDS pins unchanged.
* Smoke run at 100 Hz (60 s): PASS as a smoke record. All 6000 ticks complete, zero missing.
* Smoke run at 500 Hz (60 s): PASS as a smoke record. All 30000 ticks complete, zero missing.
* Banned-character and banned-word scan (em dash, en dash, curly quotes, listed vocabulary) over `sim/bridge/`: PASS (no matches). Applied again to this log.
* Commit: not performed, as instructed.

Files changed or created in this task:

* Created: `sim/bridge/package.xml`, `sim/bridge/CMakeLists.txt` (replaces the placeholder), `sim/bridge/msg/MeshDeformationState.msg`, `sim/bridge/include/srtra_bridge/bridge_node.hpp`, `sim/bridge/src/bridge_node.cpp`, `sim/bridge/src/bridge_node_main.cpp`, `sim/bridge/build.ps1`, `sim/bridge/tools/measure_rate.py`, `sim/bridge/tools/run_smoke.ps1`, `sim/bridge/README.md` (replaces the placeholder).
* Created in `sim/bridge/build/` (gitignored): colcon build base, install tree, logs, and the scratch pretest directory.
* Modified: `env/ros2-jazzy/pixi.toml` (two exact pins added), `env/ros2-jazzy/pixi.lock` (re-locked).
* Created in `SNDEV/logs/` (gitignored): lock snapshots before the change, the `pixi add` and `pixi install` transcripts, build transcripts (attempts 1 to 4, final), the driver transcript, the node and subscriber transcripts, the JSON records (including the failed 100500 run).
* This log.
* Cleanup: two colcon probes run from `env/ros2-jazzy` (`colcon version-check` and `colcon build --help`) wrote a default `log/` directory there. It was removed at the end of the task (it held one `version-check` log and `COLCON_IGNORE`). Future colcon calls pass `--log-base` under `sim/bridge/build/`.

Not changed, by scope: `sim/segmentation/`, `DEVELOPMENT_PLAN.md`, `sim/SOUP.md`, the root `CMakeLists.txt`, and the `.gitignore`.

Open items for slice 2:

* G2.4 run: 500 Hz for 600 s at the subscriber on a quiet host. The run command is `run_smoke.ps1 -Rates 500 -Duration 600`. Acceptance uses the subscriber JSON.
* Replace the synthetic source with SOFA tool-tip, wrench, and modal mesh outputs (FR-MS-002 reduction).
* Subscriber arrival-time method: the receive-side p95 reflects rclpy wake-up batching. Choose a method (for example, per-tick completion time from the source stamps) before any arrival p95 is used as evidence.
* Node timing: measure the 500 Hz late-tick rate over 600 s. If it is not acceptable, test a high-resolution waitable timer.
* `sim/SOUP.md`: add the colcon 0.21.3 and ninja 1.13.2 pins and the setuptools 84.2.1 to 79.0.1 move to the ROS 2 row (owner of that file).
* Root `CMakeLists.txt`: the `SRTA_BUILD_BRIDGE` wiring still points at `add_subdirectory(sim/bridge)`. Decide whether the root option should call `build.ps1` or be removed. Not changed in this slice.
* `DEVELOPMENT_PLAN.md` task 2.4 status: not edited (owned by another builder).
