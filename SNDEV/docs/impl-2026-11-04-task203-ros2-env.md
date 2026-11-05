Title: ROS 2 Jazzy pixi environment with RoboStack and Fast DDS lock (task 2.0.3)
Date: 2026-11-05T02:43:27Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.0.3
Summary: Declares and locks a native Windows ROS 2 Jazzy environment through pixi on the conda-forge and robostack-jazzy channels, with RMW_IMPLEMENTATION=rmw_fastrtps_cpp, and records the resolved pins in sim/SOUP.md.

## Task Reference

Plan task 2.0.3 in `DEVELOPMENT_PLAN.md`. The request is to resolve and lock the ROS 2 verification environment, and to update `sim/SOUP.md` with the resolved ROS 2 and Fast DDS pins. The requirement driver is VAL-026 of `SRS.md` v1.2.0 (`RMW_IMPLEMENTATION=rmw_fastrtps_cpp`). VAL-027 (SlicerROS2 Option B) and VAL-028 (FMI-LS-BUS) are recorded as dropped.

## Specification Summary

* Install ROS 2 Jazzy natively on Windows (win-64) through pixi, using the RoboStack `robostack-jazzy` channel with the conda-forge backend.
* Channels: `conda-forge` and `robostack-jazzy` only. The `defaults` channel is excluded per the RoboStack guide warning about the Anaconda Terms of Service.
* CPython 3.12 for the ROS 2 environment.
* Dependencies: `ros-jazzy-ros-base` and `ros-jazzy-rmw-fastrtps-cpp`, with pixi tasks that set `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`.
* Deliverables: `env/ros2-jazzy/pixi.toml`, `env/ros2-jazzy/pixi.lock`, a `.pixi/` entry in `.gitignore`, a pub/sub round-trip transcript in `SNDEV/logs/`, and the `sim/SOUP.md` update.

## Implementation Notes

Preflight (2026-11-05T02:43Z, UTC clock read with `[DateTime]::UtcNow`): `pixi` is not on PATH (`Get-Command pixi` returned nothing, `pixi --version` was not recognized). `SNDEV/docs/` and `SNDEV/logs/` exist. `env/ros2-jazzy/` did not exist. `.gitignore` already ignores `SNDEV/logs/*` (keeping `.gitkeep`). Pre-existing uncommitted changes in the working tree, not made by this task: `DEVELOPMENT_PLAN.md` and `SRS.md` modified; `SNDEV/docs/impl-2026-11-04-dev-plan-v2.md`, `SNDEV/docs/impl-2026-11-04-srs-v1.2-proposal.md`, and `docs/srs-v1.2-change-proposal.md` untracked.

Source pages consulted:

* RoboStack conda guide, `https://robostack.github.io/conda.html` (read 2026-11-05). Source of the `defaults` channel removal quote and of the `robostack-jazzy` channel usage.
* RoboStack Getting Started, `https://robostack.github.io/GettingStarted.html` (read 2026-11-05). Source of the pixi workflow, the `robostack-jazzy` channel, and the `ros-jazzy-*` package naming. This page lists `ros-jazzy-desktop` in its multi-distro example. This task uses `ros-jazzy-ros-base` as specified.
* ROS 2 Jazzy Windows binary install page, `https://docs.ros.org/en/jazzy/Installation/Windows-Install-Binary.html`. NOT READ. Two fetches (2026-11-05) returned the Anubis bot-check page with no content. The ROS-side install steps were not verified. The pixi route follows the RoboStack guide only. Rerun this task with the ROS page read before relying on its details.

pixi installation:

* `pixi` was not on PATH (`Get-Command pixi` returned nothing).
* Command: `winget install --exact --id prefix-dev.pixi --source winget --accept-package-agreements --accept-source-agreements`. Outcome: installed `prefix-dev.pixi` 0.81.0 from the MSI at `https://github.com/prefix-dev/pixi/releases/download/v0.81.0/pixi-x86_64-pc-windows-msvc.msi` (installer hash verified by winget).
* Binary: `C:\Users\salmo\AppData\Local\pixi\bin\pixi.exe`, `pixi --version` gives `pixi 0.81.0`. The shell session did not pick up the new PATH entry, so the full path is used below.
* `pixi info`: platform win-64, virtual packages `__win=10.0.22621`, `__cuda=13.3`, `__archspec=1=x86_64_v3`.

Manifest (`env/ros2-jazzy/pixi.toml`):

* Channels: `conda-forge`, `robostack-jazzy`. The `defaults` channel is not listed.
* Platforms: `win-64`.
* First version used ranges (`python = "3.12.*"`, `ros-jazzy-ros-base = "*"`, `ros-jazzy-rmw-fastrtps-cpp = "*"`). The first solve resolved these, and the lock file was then read for exact versions. The final manifest pins them to `==3.12.16`, `==0.11.0`, and `==8.4.4`.
* `[activation.env]` sets `RMW_IMPLEMENTATION = "rmw_fastrtps_cpp"`. Tasks `ros2-env-check`, `pubsub-talker`, and `pubsub-listener` also set `env`.

Commands and outcomes:

1. `pixi lock` in `env/ros2-jazzy` with ranges. Outcome: EXIT 0, solve succeeded. Output saved to `SNDEV/logs/ros2-jazzy-pixi-lock-2026-11-05.txt`. The lock lists 378 unique conda package URLs.
2. Manifest edited to exact pins. `pixi lock` then reported `Lock-file was already up-to-date`, which means the locked versions satisfy the `==` specs. Output saved to `SNDEV/logs/ros2-jazzy-pixi-lock-exact-2026-11-05.txt`.
3. `pixi install` in `env/ros2-jazzy`. Outcome: EXIT 0, "The default environment has been installed." Output saved to `SNDEV/logs/ros2-jazzy-pixi-install-2026-11-05.txt`.
4. Environment check (`pixi run -- cmd /c ...`, then `python -c "import rclpy ..."`). Outcome: `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, `rclpy OK 3.12.16`. The `ros2 --version` probe was not a valid flag in this CLI (`unrecognized arguments: --version`, exit 2). It is not a failure of the environment. Output: `SNDEV/logs/ros2-jazzy-pubsub-2026-11-05.txt`.
5. `ros2 doctor --report` (`SNDEV/logs/ros2-jazzy-doctor-2026-11-05.txt`). Outcome: `ROS_DISTRO=jazzy`, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, middleware name `rmw_fastrtps_cpp`. The report also lists `rmw_fastrtps_cpp` latest 8.4.5 against local 8.4.4. The pin stays at 8.4.4. This is advisory only.
6. Pub/sub round trip over Fast DDS. The listener `ros2 topic echo /srtra/smoke std_msgs/msg/String --once` was started in the background. After 20 s, `ros2 topic pub --times 10 --rate 2 /srtra/smoke std_msgs/msg/String "{data: 'srtra-smoke'}"` ran. Outcome: PASS. Listener output `data: srtra-smoke`, listener exited. Transcripts: `SNDEV/logs/ros2-jazzy-pubsub-2026-11-05.txt` (env and publisher), `SNDEV/logs/ros2-jazzy-pubsub-echo-2026-11-05.txt` (listener stdout), `SNDEV/logs/ros2-jazzy-pubsub-echo-err-2026-11-05.txt` (listener stderr).
7. `pixi task list`. Outcome: lists `pubsub-listener`, `pubsub-talker`, and `ros2-env-check`. The `pubsub-talker` task was not run. The round trip above used the direct `ros2` command.

Resolved versions from `env/ros2-jazzy/pixi.lock`:

* ROS 2 direct: `ros-jazzy-ros-base` 0.11.0 (`h9490d1a_25`), `ros-jazzy-rmw-fastrtps-cpp` 8.4.4 (`h9490d1a_25`).
* ROS 2 transitive, examples: `ros2-rmw-fastrtps-cpp` 8.4.4, `ros2-rmw-fastrtps-dynamic-cpp` 8.4.4, `ros2-rmw-fastrtps-shared-cpp` 8.4.4, `ros2-rosidl-typesupport-fastrtps-cpp` 3.6.4, `ros2-rosidl-typesupport-fastrtps-c` 3.6.4, `ros2-rosidl-dynamic-typesupport-fastrtps` 0.1.0. The full list is in the lock.
* Fast DDS: `ros2-fastrtps` 2.14.7 (`h679732a_25`), `ros2-fastrtps-cmake-module` 3.6.4, `ros2-fastcdr` 2.2.8, `ros2-foonathan-memory-vendor` 1.3.1 (`ros2-foonathan-memory-vendor-1.3.1-np2py312hdd89193_25`), `foonathan-memory` 0.7.4.
* Python: `python` 3.12.16 (`hb12b558_0_cpython`), `python_abi` 3.12.

Note on the `ros-jazzy-*` package naming. The lock stores the ROS packages as `ros2-*` (RoboStack naming for the packages) and the `ros-jazzy-*` names are the metapackages (`ros-jazzy-ros-base`, `ros-jazzy-rmw-fastrtps-cpp`). Only the `ros-jazzy-*` names above are the direct dependencies.

Interpreter split: this environment runs CPython 3.12.16 (`env/ros2-jazzy`, pixi). The qualification suites run under `.venv-qual311` (Python 3.11.9) and parse JSON captures in `SNDEV/logs/`. The two interpreters are separate. This task did not change `.venv-qual311`. The existence of that venv was not re-checked in this task.

Repo changes in this task:

* `env/ros2-jazzy/pixi.toml` (new), `env/ros2-jazzy/pixi.lock` (new, generated by pixi).
* `.gitignore`: added `.pixi/` under a comment (`pixi local environments (ROS 2 Jazzy environment under env/ros2-jazzy/, task 2.0.3)`).
* `sim/SOUP.md`: ROS 2 row and Fast DDS row replaced with resolved pins. RoboStack provenance row added. SlicerROS2 and FMI-LS-BUS rows removed from the active table and recorded under "Dropped records" with VAL-027 and VAL-028. The phrase "(WSL2 bridge pin pending procurement item 5)" removed from the 3D Slicer pin status cell.
* `SNDEV/logs/*` captures listed above (gitignored).
* `SNDEV/docs/impl-2026-11-04-task203-ros2-env.md` (this log).

Open items:

* The 3D Slicer version cell (the Version or commit pin column) still says "The SlicerROS2 WSL2 build pins its own Slicer source tag on the v5.12 line when procurement item 5 starts." The task scoped the edit to the pin-status cell, so this sentence was left as is. It refers to a dropped item and should be removed in a follow-up edit.
* The ROS 2 Jazzy Windows install page was not read (see Source pages). It needs a rerun when the page is reachable.
* `pixi.lock` is not committed. Committing is left to the user, as instructed.
* The `DEVELOPMENT_PLAN.md` task 2.0.3 status, `docs/procurement-guide.md`, and `vv/traceability/vtm.md` were not edited, per the scope in the task.

Verification gate results:

* Lock resolution: PASS (`pixi lock`, exit 0).
* Install: PASS (`pixi install`, exit 0).
* Environment and rclpy import: PASS (`RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, `rclpy` imports on CPython 3.12.16).
* `ros2 doctor --report`: PASS (RMW middleware `rmw_fastrtps_cpp`).
* Fast DDS pub/sub round trip: PASS (`data: srtra-smoke` received).
* Manifest check: PASS (no floating `*` or `.*` specs remain in `pixi.toml`).
* Banned character scan (em dash, en dash, curly quotes) on the changed files: PASS (no matches).
* Commit: not performed.

## Addendum (install-page verification, 2026-11-05)

The ROS 2 Jazzy Windows binary install page at docs.ros.org sits behind an Anubis JavaScript bot-check and cannot be fetched as text. Its content was retrieved instead from the documentation source: `https://raw.githubusercontent.com/ros2/ros2_documentation/jazzy/source/Installation/Windows-Install-Binary.rst` (retrieved 2026-11-05).

The page documents the binary variant: pixi with conda-forge for dependencies, plus a pre-built `ros2-{DISTRO}-*-windows-release-amd64.zip` from `https://github.com/ros2/ros2/releases` unpacked at `C:\pixi_ws\ros2-windows`. VAL-026 pins the RoboStack variant instead (full ROS 2 from the `robostack-jazzy` channel through pixi), which is the route installed in this task. The two variants agree on the frontend (pixi) and on Fast DDS as the default middleware. The pub/sub round trip in this task matches the verification intent of the page's talker and listener example.

Page statements recorded for later tasks. The binary variant states Windows 10 as its supported system requirement. Its binary packages are not relocatable and the page asks for `C:\pixi_ws` because of Windows path-length limits. Downstream C++ binaries must use the MSVC Release or RelWithDebInfo configuration for ABI compatibility with the pre-built ROS 2 binaries. The ABI note is carried into plan task 2.4 for the C++ bridge build configuration.

Verification gap closed: the install page content is recorded from the documentation source because the rendered page cannot be fetched.
