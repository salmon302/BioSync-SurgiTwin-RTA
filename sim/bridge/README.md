# ROS 2 Bridge Node (Fast DDS)

Package `srtra_bridge` (ament_cmake). The node publishes tool-tip pose, 6-axis wrench, and mesh deformation state to ROS 2 nodes over Fast DDS (SRS FR-MS-004, VAL-027 Option B). SlicerROS2 is not used, and WSL2 is not used. Build and runtime come from the locked pixi environment in `env/ros2-jazzy/` (ROS 2 Jazzy, CPython 3.12.16, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`).

Status: slice 1 (package, messages, node, rate measurement, 60 s smoke runs). Slice 2 (G2.4 gate run on the synthetic source). Slice 3a (per-message capture schema v3, and the replay source that is the SOFA integration contract).

## Layout

* `package.xml`, `CMakeLists.txt`: ament_cmake package. The C++ standard is C++17. The build type must be Release or RelWithDebInfo (configure stops otherwise).
* `msg/MeshDeformationState.msg`: mesh message (see contract below).
* `include/srtra_bridge/bridge_node.hpp`, `src/bridge_node.cpp`, `src/bridge_node_main.cpp`: the `BridgeNode` class and the `bridge_node` executable.
* `build.ps1`: one-command build.
* `tools/measure_rate.py`: rclpy subscriber that measures rate, presence, gaps, and (with `--expect-csv`) the value of every received message. Writes the JSON record and a per-message sidecar.
* `tools/window_min.py`: codec for the per-message sidecar and the 1-minute window statistic. Re-checks a record from its sidecar.
* `tools/make_replay_capture.py`: writes a replay capture from the synthetic trajectories (synthetic data, not SOFA data).
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

The binary is `sim\bridge\build\install\srtra_bridge\lib\srtra_bridge\bridge_node.exe`. To run it by hand, source `sim\bridge\build\install\local_setup.ps1` first, with `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, so the ROS DLLs are on the path.

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
* `uint32 node_count`: number of mesh nodes in the modal basis (default 4096).
* `float32[<=16] mode_coefficients`: modal amplitudes. Synthetic mode publishes 8. Replay publishes the number of `mode_` columns in the capture (1 to 16).

Size budget: under 200 bytes per serialized message, about 100 kB/s per topic at 500 Hz. Nodal displacement arrays were not used because they scale with the mesh node count (4096 nodes times 3 floats is 48 kB per tick).

Node parameters (`--ros-args -p name:=value`):

* `rate_hz` (int, default 500, range 1 to 1000)
* `duration_s` (int, default 0, unbounded)
* `reference_frame` (string, default `srtra_world`)
* `mesh_node_count` (int, default 4096)
* `wait_for_subscribers` (bool, default true): the tick schedule starts after each publisher has a matched subscription (up to 30 s).
* `timer_mode` (string, default `high_resolution`): `high_resolution` waits on a high-resolution waitable timer (`CreateWaitableTimerExW` with `CREATE_WAITABLE_TIMER_HIGH_RESOLUTION`, Windows 10 1803 or later). If the timer cannot be created, the node falls back to `sleep_until` with `timeBeginPeriod(1)`. `sleep` forces the fallback path (slice 1 behavior, kept for comparison). The mechanism that took effect is logged at start and at exit.
* `source` (string, default `synthetic`): `synthetic` publishes the deterministic trajectories. `replay` publishes the rows of `replay_file`. See the replay section.
* `replay_file` (string, required when `source` is `replay`): path to the capture CSV.
* `replay_loop` (bool, default false): with `source` set to `replay`, return to row 0 after the last row. Without it, the node stops after the last row. Ignored in synthetic mode.

Data source. Synthetic (slice 1 and 2): each value is a function of the tick index, so two runs at the same rate produce the same sample values. Replay (slice 3a): the values come from a capture file, and the capture is the interface that the SOFA side produces.

## Replay source (SOFA integration contract)

Setting `source` to `replay` and `replay_file` to a capture path makes the node publish the capture rows at the `rate_hz` real-time schedule, in place of the synthetic generator. The tick schedule, the `timer_mode` behavior, and the late-tick count are the same as in synthetic mode.

This section is the interface the SOFA side writes. A SOFA run writes one capture file in the schema below. Live coupling (SOFA publishing into the node while the node runs) is a later slice. Replay is the testable path for the same message contract, and the path that NFR-PERF-002 timing work uses.

Capture schema: CSV, UTF-8, one header row, one data row per tick. A leading UTF-8 byte-order mark and CRLF line endings are accepted. Blank lines are skipped. Comment lines are not supported. Header (exact column names, in this order):

| Column | Unit | Meaning |
|:-------|:-----|:--------|
| `tick` | integer | Tick index. Row 0 is tick 0. Consecutive, no gaps. |
| `time_s` | s | Simulation time of the row, equal to `tick / rate_hz` within 1 us. Checked at load. Not published. |
| `pos_x`, `pos_y`, `pos_z` | m | Tool-tip position in `srtra_world`. |
| `quat_x`, `quat_y`, `quat_z`, `quat_w` | unitless | Tool-tip orientation as a unit quaternion (norm equal to 1 within 1e-6). |
| `force_x`, `force_y`, `force_z` | N | Wrench force. |
| `torque_x`, `torque_y`, `torque_z` | N m | Wrench torque. |
| `mode_0` to `mode_(M-1)` | m | Modal deformation coefficients. M is between 1 and 16. |

The `rate_hz` parameter must be the grid the file was written for. A row whose `time_s` is off that grid stops the node at load. Every value must be finite. A violation stops the node before the publish loop starts, with the file line number in the error.

Node behavior: the file is read in two passes at load (count the rows, then parse and check). The parsed rows are stored in a table reserved once, and the publish loop indexes that table. The loop does not allocate replay data. The message stamp is the node clock at publish, as in synthetic mode. The `tick` field of the mesh message is the publish tick index, which keeps counting in loop mode. The row used for a tick is `tick` modulo the row count.

Size: a 60 s capture at 500 Hz with 8 modes is 30000 rows, about 10.4 MB as CSV written with 12 significant digits.

Generator for the SIL check: `tools/make_replay_capture.py --rate 500 --duration 60 --out <file.csv>` writes the capture and a `.meta.json` sidecar that records the provenance (`synthetic`). The generator output is synthetic data and is not SOFA data.

Run the replay from the repository root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File sim\bridge\tools\run_smoke.ps1 -Rates 500 -Duration 60 -Source replay -ReplayFile SNDEV\logs\replay-synthetic-500hz-60s.csv
```

Add `-ReplayLoop` to repeat the capture. The subscriber then compares each received message with the row it should carry (`--expect-csv`), and the record reports mismatches per topic.

## Measurement

Run the 60 second smoke pair (100 Hz and 500 Hz) from the repository root:

```
powershell -NoProfile -ExecutionPolicy Bypass -File sim\bridge\tools\run_smoke.ps1
```

Options: `-Rates "100,500"` (comma-separated string), `-Duration 60` (seconds), `-LogDir <path>`, `-TimerMode high_resolution|sleep` (node timer), `-Spin wait|poll` (subscriber executor loop), `-Source synthetic|replay`, `-ReplayFile <csv>`, `-ReplayLoop`. The script writes, per rate, a JSON record `bridge-smoke-<rate>hz-<duration>s-source-<source>-timer-<mode>-spin-<spin>-<UTC>.json`, a per-message sidecar `<same stem>.messages.json`, and transcripts to `SNDEV/logs/`.

The subscriber (`tools/measure_rate.py`) runs in the pixi CPython 3.12.16 interpreter. Arrival times are taken with `time.perf_counter_ns()` at callback entry. `time.monotonic()` is not used for arrival times on Windows because it has a 15.625 ms resolution there (`GetTickCount64()`). The record (schema `srtra-bridge-rate-measure/3`) reports:

* arrival-interval statistics (mean, p50, p95, p99, min, max) from the subscriber clock
* source-stamp interval statistics from `header.stamp` (node clock)
* agreement: the mean difference as a fraction of the nominal period (tolerance 1 percent) and the p95 difference in ms (tolerance 1.0 ms). `passed` is true only when both hold.
* per-topic message counts matched to source stamps
* ticks where all three streams are present (matched by `header.stamp`), mesh tick-index gaps and duplicates, and the achieved mean rate over the wrench stream
* `window_statistic`: the 1-minute window rate (see below)
* `value_check`: present only with `--expect-csv`, with the message count checked and the mismatch count per topic

Per-message capture (schema `srtra-bridge-messages/1`, the sidecar). Each message keeps its arrival time (`perf_counter_ns` at callback entry) and its source stamp (`header.stamp` in ns). The mesh messages also keep their tick index. Each list is stored as a first value and integer differences to the previous message of the same topic. The record holds a clock anchor, taken once per run: `wall_utc_ns` and `perf_counter_ns` recorded together, with `arrival_utc_ns = wall_utc_ns + (arrival_perf_ns - perf_counter_ns)`. The record names the sidecar and its SHA-256.

Size budget: about 16.7 bytes per message in the sidecar. A 60 s run at 500 Hz on three topics is 90000 messages and about 1.5 MB. A 600 s run is 900000 messages and about 15 MB. The record itself is a few kB.

1-minute window rate (G2.4 pre-registered statistic). A tick is complete when pose, wrench, and mesh messages with the same source stamp all arrive. Its time is the wrench arrival. `t_first` is the wrench arrival of the first complete tick. Window k covers `[t_first + 60 k s, t_first + 60 (k+1) s)`. The window count is `floor((t_last - t_first) / 60 s) + 1`, which gives 10 windows for a 600 s run. The statistic is the minimum over windows of complete ticks divided by 60 s. The record stores every window.

Re-check a record from its sidecar (the SHA-256 is verified, and the statistic is recomputed and compared with the stored value):

```
pixi run --manifest-path env\ros2-jazzy\pixi.toml -- python sim\bridge\tools\window_min.py <record.json>
```

Smoke results, the slice 2a timing runs, and the observed limitations are recorded in `SNDEV/docs/impl-2026-11-05-task24-slice1-bridge.md` and `SNDEV/docs/impl-2026-11-05-task24-slice2a-timing.md`. The slice 3a verification is recorded in `SNDEV/docs/impl-2026-11-05-task24-slice3a-capture.md`.

## Slice 2 plan (G2.4 gate)

* Gate G2.4 (SRS): wrench publish rate of at least 500 Hz sustained for 10 minutes, measured at the ROS 2 subscriber, with pose and mesh deformation state present on every publish tick.
* Run: `run_smoke.ps1 -Rates 500 -Duration 600` on a quiet host, with the same subscriber and node. Acceptance uses the subscriber JSON: achieved rate, complete ticks equal to the expected count, zero mesh tick-index gaps.
* Source data: the synthetic trajectories in the G2.4 run. The replay capture (slice 3a) is the path for SOFA data. The SOFA-sourced gate run is repeated when the SOFA side provides captures.
* Timing: the node reports late ticks. Slice 2a moved the default to the high-resolution waitable timer, which gave 0 late ticks in the 60 s verification at 500 Hz (the slice 1 path gave 636 to 787). The 600 s run must repeat the late-tick count.
* Test configuration record: the subscriber (`tools/measure_rate.py`) runs under CPython 3.12.16 in `env/ros2-jazzy`. The qualification driver runs under `.venv-qual311` (CPython 3.11.9) and parses the JSON captures in `SNDEV/logs/`. The two interpreters are separate. The record names both and the pixi lock revision.
