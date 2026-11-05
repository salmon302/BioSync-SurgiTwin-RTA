# ROS 2 Bridge Node (Fast DDS)

Package `srtra_bridge` (ament_cmake). The node publishes tool-tip pose, 6-axis wrench, and mesh deformation state to ROS 2 nodes over Fast DDS (SRS FR-MS-004, VAL-027 Option B). SlicerROS2 is not used, and WSL2 is not used. Build and runtime come from the locked pixi environment in `env/ros2-jazzy/` (ROS 2 Jazzy, CPython 3.12.16, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`).

Status: slice 1 (package, messages, node, rate measurement, 60 s smoke runs). The 10 minute 500 Hz gate run (G2.4) is slice 2.

## Layout

* `package.xml`, `CMakeLists.txt`: ament_cmake package. The C++ standard is C++17. The build type must be Release or RelWithDebInfo (configure stops otherwise).
* `msg/MeshDeformationState.msg`: mesh message (see contract below).
* `include/srtra_bridge/bridge_node.hpp`, `src/bridge_node.cpp`, `src/bridge_node_main.cpp`: the `BridgeNode` class and the `bridge_node` executable.
* `build.ps1`: one-command build.
* `tools/measure_rate.py`: rclpy subscriber that measures rate, presence, and gaps. Writes JSON.
* `tools/run_smoke.ps1`: runs the subscriber and the node for each rate and writes captures to `SNDEV/logs/`.
* `build/`: colcon build base, install tree, and logs. Gitignored.

The root option `SRTA_BUILD_BRIDGE` (top-level `CMakeLists.txt`, default OFF) still gates `add_subdirectory(sim/bridge)`. The supported build is `build.ps1`, not the top-level CMake configure.

## Build

One command, from the repository root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File sim\bridge\build.ps1
```

`build.ps1` does the following:

1. Finds `pixi.exe` (default `C:\Users\salmo\AppData\Local\pixi\bin\pixi.exe`).
2. Finds MSVC through `vswhere` and imports the `vcvars64.bat` environment (x64, VS 2022 Community).
3. Runs `pixi run --manifest-path env\ros2-jazzy\pixi.toml -- colcon --log-base sim\bridge\build\log build --base-paths sim\bridge --packages-select srtra_bridge --build-base sim\bridge\build\b --install-base sim\bridge\build\install --cmake-args -G Ninja -DCMAKE_BUILD_TYPE=Release`.

`-G Ninja` is needed because colcon-cmake selects a Visual Studio generator on Windows otherwise, and that generator ignores `CMAKE_BUILD_TYPE` at build time. The build base is `build\b` because longer object paths trigger a CMake warning about `CMAKE_OBJECT_PATH_MAX`.

The binary is `sim\bridge\build\install\srtra_bridge\lib\srtra_bridge\bridge_node.exe`.

## Message contract

All three streams are published on every tick. Tick identity: the three messages of one tick carry the same `header.stamp`.

| Topic | Type | Content | Units and frame |
|:------|:-----|:--------|:----------------|
| `/srtra/bridge/tool_tip_pose` | `geometry_msgs/msg/PoseStamped` | Tool-tip position and orientation | Position in meters. Orientation is a unit quaternion (x, y, z, w). Frame `reference_frame`. |
| `/srtra/bridge/tool_wrench` | `geometry_msgs/msg/WrenchStamped` | 6-axis haptic wrench | Force in newtons, torque in newton-meters. Frame `reference_frame`. |
| `/srtra/bridge/mesh_deformation` | `srtra_bridge/msg/MeshDeformationState` | Modal deformation state | `mode_coefficients` in meters. |

`MeshDeformationState` fields:

* `std_msgs/Header header`: `header.frame_id` equals `reference_frame`.
* `uint64 tick`: publish tick index. Starts at 0 for each run.
* `string reference_frame`: default `srtra_world`.
* `uint32 node_count`: number of mesh nodes the modal basis represents (default 4096).
* `float32[<=16] mode_coefficients`: modal amplitudes. Slice 1 publishes 8.

Size budget: under 200 bytes per serialized message, about 100 kB/s per topic at 500 Hz. Nodal displacement arrays were not used because they scale with the mesh node count (4096 nodes times 3 floats is 48 kB per tick).

Node parameters (`--ros-args -p name:=value`):

* `rate_hz` (int, default 500, range 1 to 1000)
* `duration_s` (int, default 0, unbounded)
* `reference_frame` (string, default `srtra_world`)
* `mesh_node_count` (int, default 4096)
* `wait_for_subscribers` (bool, default true): the tick schedule starts after each publisher has a matched subscription (up to 30 s).

Data source (slice 1): deterministic synthetic trajectories. Each value is a function of the tick index, so two runs at the same rate produce the same sample values. Slice 2 replaces the source with SOFA tool-tip and wrench outputs.

## Measurement

Run the 60 second smoke pair (100 Hz and 500 Hz) from the repository root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File sim\bridge\tools\run_smoke.ps1
```

Options: `-Rates "100,500"` (comma-separated string), `-Duration 60` (seconds), `-LogDir <path>`. The script writes, per rate, a JSON record `bridge-smoke-<rate>hz-<duration>s-<UTC>.json` and transcripts (`-subscriber.txt`, `-node.txt`, and their stderr files) to `SNDEV/logs/`.

The subscriber (`tools/measure_rate.py`) runs in the pixi CPython 3.12.16 interpreter. It records arrival times per message, counts ticks where all three streams are present (matched by `header.stamp`), counts mesh tick-index gaps and duplicates, and reports:

* achieved mean rate over the wrench stream (count minus one, divided by wall time between first and last arrival)
* arrival-interval statistics (mean, p50, p95, p99, min, max) at the subscriber
* source-stamp interval statistics (from `header.stamp`)
* missing complete ticks against `rate * duration`

Smoke results and the observed limitations are recorded in `SNDEV/docs/impl-2026-11-05-task24-slice1-bridge.md`.

## Slice 2 plan (G2.4 gate)

* Gate G2.4 (SRS): wrench publish rate of at least 500 Hz sustained for 10 minutes, measured at the ROS 2 subscriber, with pose and mesh deformation state present on every publish tick.
* Run: `run_smoke.ps1 -Rates 500 -Duration 600` on a quiet host, with the same subscriber and node. Acceptance uses the subscriber JSON: achieved rate, complete ticks equal to the expected count, zero mesh tick-index gaps.
* Source data: replace the synthetic trajectories with SOFA tool-tip and wrench outputs, and a modal reduction from the SOFA nodal state to `mode_coefficients` (FR-MS-002).
* Timing: the node reports late ticks (slice 1 saw 787 of 30000 at 500 Hz). Slice 2 evaluates a high-resolution waitable timer in place of the 1 ms `timeBeginPeriod` schedule, and records the result.
* Test configuration record: the subscriber (`tools/measure_rate.py`) runs under CPython 3.12.16 in `env/ros2-jazzy`. The qualification driver runs under `.venv-qual311` (CPython 3.11.9) and parses the JSON captures in `SNDEV/logs/`. The two interpreters are separate. The record names both and the pixi lock revision.
