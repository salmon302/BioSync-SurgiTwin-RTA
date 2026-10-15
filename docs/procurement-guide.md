# Open-source tooling procurement guide for Phase 2

Status: draft for human execution. Every web source below was accessed 2026-10-14, and each source is cited by URL in the section that uses it. The phase plan is `DEVELOPMENT_PLAN.md` (read-only in this guide; its owner maintains it).

## Purpose

This guide removes or reduces the Phase 2 tooling blockers listed in `DEVELOPMENT_PLAN.md` without a commercial license.

The plan owner decided on 2026-10-14 that no commercial licenses are used in development. Commercial tools (Parasoft C/C++test, QA-MISRA, VectorCAST, Cantata, Jama, Polarion, and HIL vendor stacks) are adoption options for licensees only. Every item in this guide is open source under an OSI-approved license, an open standard, or free-of-charge tooling. No purchase orders and no license forms are needed for any item below.

One item, 3D Slicer, is free of charge and open source by its own description but is not OSI-approved. Section 3 states the details.

## Host assumptions

* Windows 11 Pro, AMD Ryzen 9 3900X (12 cores, 24 threads), 48 GB RAM.
* MSVC 19.44 from Visual Studio 2022 (toolset 14.44.35207), CMake 3.31.6.
* Docker Desktop 25.0.3 with the `biosync-surgitwin-rta-postgres-1` container (`postgres:15`) healthy.
* PowerShell as the shell.
* Python 3.11.9 virtual environments `.venv-qual311` and `.venv-pq-load`.
* WSL is not provisioned. Section 4 covers provisioning.

These assumptions come from the preflight table in `SNDEV/docs/impl-2026-10-14-phase2-kickoff.md`. Disk and time figures are estimates unless a source is named. None of them was measured on this host.

## Rules for every item

* After an item is installed, the agents record its exact pin in `sim/SOUP.md`. The human does not edit that file.
* After an item is present, the agents verify it automatically and record PASS or FAIL in the Phase 2 implementation log. The human's done-when check is the smaller check named in each section.
* Pins are exact. Nothing floats (AGENTS.md section 6, reproducibility).
* Commands below use PowerShell unless a section says otherwise. The repository root is `I:\Documents\GitHub\BioSync\BioSync-SurgiTwin-RTA`.

## 1. Pulse Physiology Engine

Unblocks task 2.6 (real-engine run on the pinned build), the FR-MS-006 heartbeat evidence in gate G2.5, and IQ-4 and OQ-16 on the pinned build.

### Pin and license

* Source: Kitware Pulse, tag `REL_4_3_2`. This is the `PULSE_VERSION` default in `middleware/Dockerfile.pulse` (line 25) and the clone target in the `git` stage (line 111, `https://gitlab.kitware.com/physiology/engine`).
* Version: the vendored `CMakeLists.txt` in `BioSync-Gateway\.pulse\` declares `project(Pulse VERSION 4.3.2 LANGUAGES C CXX)`.
* License: Apache License 2.0, per the vendored file `BioSync-Gateway\.pulse\LICENSE`. This is the Gateway copy and not the `REL_4_3_2` tag. Keep the plan's "(confirm)" marker until the SOUP row checks the tag.
* Provenance gap: the vendored copy has no `.git` metadata, so no engine commit hash is recorded. The Gateway repository HEAD (step 2 below) is the origin reference.

### Why Docker

The Gateway repository records IQ-4, OQ-16, PQ-2, and PQ-6 at 19 of 19 PASS against the real engine in the image, after a segfault fix (`SNDEV/docs/impl-2026-07-28-pulse-segfault-diag-plan.md`, lines 147 to 159, in the Gateway repository). The Gateway venvs have no native Windows PyPulse (per the Phase 2 research brief), so the Docker path is the proven one. Native Windows is an unproven option (see Alternatives). The SurgiTwin-RTA `middleware/Dockerfile.pulse` already carries the runtime base fix that the segfault log describes (full `python:3.11-bullseye` runtime).

### Human steps

1. Confirm the source copy exists.

   ```powershell
   Test-Path I:\Documents\GitHub\BioSync\BioSync-Gateway\.pulse\CMakeLists.txt
   ```

   Expected output: `True`.

2. Record the Gateway commit as the origin reference. Give the hash to the agents.

   ```powershell
   git -C I:\Documents\GitHub\BioSync\BioSync-Gateway rev-parse HEAD
   ```

3. Copy the directory. The `.pulse/` path is gitignored in both repositories (`.gitignore` in each).

   ```powershell
   Copy-Item -Recurse -Path I:\Documents\GitHub\BioSync\BioSync-Gateway\.pulse -Destination I:\Documents\GitHub\BioSync\BioSync-SurgiTwin-RTA\.pulse
   ```

   If the destination already exists, stop and ask the agents. Do not overwrite it.

4. Confirm the copy is ignored and the repository is otherwise unchanged.

   ```powershell
   git -C I:\Documents\GitHub\BioSync\BioSync-SurgiTwin-RTA status --short
   ```

   Expected output: no line that names `.pulse`.

5. Check Docker resources. Run `docker system df` for free space, and set Docker Desktop memory to at least 8 GiB (the figure in the Gateway R1 log for its CI runner).

6. Build the image from the repository root.

   ```powershell
   cd I:\Documents\GitHub\BioSync\BioSync-SurgiTwin-RTA
   docker build -f middleware/Dockerfile.pulse -t biosync-pulse .
   ```

   The build fails unless the engine initializes. The `RUN` step at the end of the Dockerfile prints `ENGINE INIT OK`.

Expected time: 30 to 90 minutes for a cold build (estimate in `SNDEV/docs/impl-2026-07-27-r1-pulse-binary.md` in the Gateway repository). One builder-stage run in the Gateway log `impl-2026-07-28-pulse-build-fix.md` completed in about 235 seconds, with cache state not recorded, so this figure is not a cold-build time.

Expected disk: plan for about 20 GB free on the Docker data volume, including build cache (estimate). The Gateway logs do not record the final image size.

Done when: the build finishes, the log contains `ENGINE INIT OK`, and `docker images biosync-pulse` lists the image.

### Alternatives

* CI or no local copy: `docker build -f middleware/Dockerfile.pulse --build-arg VARIANT=git -t biosync-pulse:ci .` clones `REL_4_3_2` from `gitlab.kitware.com` inside the builder stage. It needs network access during the build. The Gateway `pulse-engine.yml` workflow uses this path.
* Native Windows build: unproven in either repository. The Pulse CMake project supports MSVC 2017 and later and CMake 3.12 or later (`ReadMe.md` in the vendored copy). The host has MSVC 19.44 and CMake 3.31.6, so a native build may work. It would also need the data generation step that the Dockerfile performs with the Java API.

### Verification (agents, after the build)

The image excludes `vv/` from its build context (`.dockerignore`), so the test suites run from a bind mount of the repository. The `PYTHONPATH` value keeps the `/pulse` entries. The Gateway CI step replaces `PYTHONPATH` and drops them.

```powershell
docker run --rm biosync-pulse python -c "import pulse; print('import pulse OK')"
```

```powershell
docker run --rm -v "${PWD}:/repo" -e PYTHONPATH=/pulse/python:/pulse/bin:/repo/middleware:/repo -w /repo biosync-pulse sh -c "pip install --no-cache-dir -q -r /app/requirements-test.txt && python -m pytest vv/tests/IQ/test_iq4_pulse_engine_init.py vv/tests/OQ/test_oq16_pulse_state_serialization.py vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py -v"
```

Expected: IQ-4 and OQ-16 pass with no skips. The fail-closed OQ test skips by design when the bindings are present (`_pulse_bindings_present()` in the test file).

```powershell
docker run --rm -v "${PWD}:/repo" -e PYTHONPATH=/pulse/python:/pulse/bin:/repo/middleware:/repo -e BIOSYNC_PQ_MS006_DURATION_S=600 -e BIOSYNC_PQ_MS006_RUN_ID=vtm-600s -w /repo biosync-pulse sh -c "pip install --no-cache-dir -q -r /app/requirements-test.txt && python -m pytest vv/tests/PQ/test_pq_fr_ms_006_heartbeat_gap.py -v"
```

Expected: the real-engine heartbeat test runs for 600 seconds. Its capture file is written to `SNDEV/logs/pq-<UTC date>-fr-ms-006-vtm-600s.json`, which is gitignored.

If the agents see `No module named pulse`, the `PYTHONPATH` override is the first suspect.

### Agent follow-ups for this item

* Add the `sim/SOUP.md` row with the Gateway HEAD commit, the `REL_4_3_2` tag, and the Apache-2.0 license (still "confirm" until the tag is checked).
* Add a `docs/migration-map.md` row for the `.pulse/` copy with its origin path and the Gateway HEAD commit.
* Correct the header comment in `middleware/Dockerfile.pulse` (line 18). It names the tag `surgitwin-pulse`, but the build command in this guide uses `biosync-pulse`.

## 2. SOFA v26.06.00

Unblocks task 2.2 (hyperelastic FEM scene with an implicit solver, and the SOUP opening), task 2.3 (contact and cutting tooling; the effort is still open, see Section 7), and the mechanical plant model of task 2.7.

### Pin and license

* Release: SOFA v26.06.00 (June 2026). The download page at `https://www.sofa-framework.org/download/` lists "SOFA binaries (v26.06.00)" with Windows assets `SOFA_v26.06.00_Win64.exe` and `SOFA_v26.06.00_Win64.zip`, and the GitHub tag `v26.06.00`.
* Published SHA256 for the Windows installer: `3332ee66a6d6bfbcc14af7505063d9b66a969f291e6bd018c76423602c19885a`. For the zip: `b60889416a70e0f18638995ba53f1fadcdb1eef9c8a9936a1ed31f3523fca7b5`. The download page publishes these values. The human recomputes them (step 2 below).
* License: the download page states that SOFA "can be redistributed and/or modified under the terms of the GNU Lesser General Public License ... version 2.1 ... or (at your option) any later version". It also states that the SOFA "applications" folder is GPL-2.0 or later. The plan's SOFA row keeps "(confirm)". The SOUP entry closes the marker after checking the `LICENSE` file in the pinned tag, and it records which parts the project links.
* The binary plugin list on the same page includes SofaPython3, SoftRobots, and BeamAdapter, among others. The HyperElastic components used by the plan (for example `TetrahedronHyperelasticityFEMForceField` and `NeoHookeanMaterial`) appear in the SOFA component documentation at `https://www.sofa-framework.org/community/doc/`.

### Human steps (Windows installer, the default route)

1. Download `SOFA_v26.06.00_Win64.exe` from the download page (or the GitHub release `https://github.com/sofa-framework/sofa/releases/tag/v26.06.00`).
2. Verify the checksum.

   ```powershell
   Get-FileHash .\SOFA_v26.06.00_Win64.exe -Algorithm SHA256
   ```

   Compare the output with the published value above.

3. Run the installer and choose a short install path such as `C:\SOFA\v26.06.00`. The SOFA Windows build page reports long-path failures, and a short path avoids them.
4. Start `runSofa` from the install's binary directory. The exact executable name depends on the installed tree, so check it after install.
5. Open a bundled scene from the install's examples folder and run it. Record the install path and scene name for the agents.

Expected disk: plan for about 2 GB free for the installer and its unpacked tree (estimate; sizes are not on the download page).

Expected time: about 15 minutes (estimate).

Done when: `runSofa` opens a bundled scene and the simulation steps.

### Source build route (only when a required plugin is absent from the binary)

Use this route only when the plugin list on the download page does not cover a needed plugin.

* Source: `git clone -b v26.06.00 https://github.com/sofa-framework/sofa.git sofa/src` (the download page gives this command). Use a short root path such as `C:\sofa`.
* Compiler: the SOFA Windows build page lists Visual Studio 2017, 2019, and 2022 as supported. Use Visual Studio 2022 (MSVC 19.44 on this host). Build Tools only is supported. Ninja is the recommended generator for Build Tools only.
* Route: the page documents a Pixi route (install Build Tools, Git, and Pixi, then run `pixi run -e supported-plugins runSofa`). Pixi is the shortest documented route. The manual CMake route is also documented.
* Long paths: enable Windows long paths and `git config --global core.longpaths true` before cloning, as the SOFA build page advises.

Expected disk: about 20 GB for source and build (estimate). Expected time: hours (estimate; the SOFA build page says to plan time for a long build).

### Scene location and CMake hook

* Scene sources live under `sim/sofa/src/` (plan task 2.2). The human creates no files in the repository.
* `sim/sofa/CMakeLists.txt` is a placeholder with no targets today. The CMake check below needs the `find_package` change from task 2.2 first.

Verification (agents, after task 2.2 adds the find logic):

```powershell
cmake -S . -B build\sofa-check -DSRTA_BUILD_SOFA=ON -DSofa_DIR=C:\SOFA\v26.06.00\<package config directory>
```

The root `CMakeLists.txt` gates `sim/sofa` on `SRTA_BUILD_SOFA` (default OFF). Replace the placeholder path with the directory that holds the SOFA package config file in the installed tree. Confirm the file name there before the check is written.

Done when: the configure step reports that the SOFA package is found.

Open check for the human: the Windows binary's bundled Python version is not stated on the download page (the Linux packages list Python 3.10 and 3.12). Record it before any SofaPython3 script is written, because the Phase 2 venv is Python 3.11.9.

## 3. 3D Slicer

Unblocks task 2.1 (DICOM ingestion and segmented meshes), and the segmentation input for gate G2.1.

### Pin decision

* Current stable release: 5.12.4, revision 34645, Windows package built 2026-09-09 (`https://download.slicer.org`, accessed 2026-10-14). The download page lists the Windows SHA512 for this build.
* Preview release: 5.13.0, built 2026-10-14. Not recommended as a pin.
* Decision needed. SlicerROS2 tests against Slicer tags `v5.10.0` and `v5.12.0` only (Section 5). The download page lists 5.12.0 among older releases that it marks as unsupported (`https://download.slicer.org`).

Recommended: pin 5.12.0 for both task 2.1 (Windows installer) and task 2.4 (source build in WSL2), so the SOUP inventory holds one Slicer entry. Confirm that a Windows 5.12.0 package exists in the older-releases list before the pin.

Alternative: pin 5.12.4 for task 2.1 and build the bridge from the `v5.12.0` source tag. This keeps the stable release for segmentation, but it creates two Slicer pins and a second version to re-verify on every change.

The steps below use the recommended pin. Substitute 5.12.4 if the alternative is chosen.

### License

Slicer's own about page describes the license as "a BSD-style open source license" with no restrictions on legal uses (`https://slicer.readthedocs.io/en/latest/user_guide/about.html#license`, accessed 2026-10-14). The same page states that the OSI license review concluded the bundled contribution agreement makes the license non-approvable. Slicer is therefore free of charge and open source by description, but it is not OSI-approved. The plan owner's rule accepts free-of-charge tooling, and this guide applies that reading. The plan owner should confirm the reading.

Slicer also states that it is not approved for clinical use. Phase 2 uses it for research and simulation inputs only.

### Human steps (Windows)

1. Download the Windows installer. The naming convention on the download page is `Slicer-X.Y.Z-<os>-<arch>.<extension>`, for example `Slicer-5.12.0-win-amd64.exe`. Use the download page for the exact file.
2. Verify the SHA512 for the file.

   ```powershell
   Get-FileHash .\Slicer-5.12.0-win-amd64.exe -Algorithm SHA512
   ```

   For 5.12.4, the download page lists `5ba320cb67f0acdaacf0a31380e9cf3b9f46d05f57a53da7e04ebcd9490251ecbe998bfefdbdab1f747e038653177868cdb0ad30986473b9d68efba0f4c6045c` for the Windows package. The checksum for 5.12.0 is not captured in this guide. Take it from the release page.
3. Run the installer with the default path.
4. Start Slicer. Open the DICOM module and load a study. Use the reference DICOM set named in gate G2.1 if it is on disk. If it is not, use a sample study from the Sample Data module (confirm the module and dataset names in the installed version).
5. Create a segment in the Segment Editor, paint or threshold it, and export the segmentation as a labelmap through Slicer's segmentation export.
6. Record the install directory for the agents. They use it for `PythonSlicer` scripting in task 2.1.

Expected disk: plan for about 2 GB installed (estimate; the download page does not list the size). Expected time: about 20 minutes (estimate).

Done when: Slicer launches, the DICOM module loads a sample study, and the Segment Editor writes a labelmap file.

Verification (agents, later): a `PythonSlicer` script imports the reference DICOM and exports a segmentation. The agents write that test in task 2.1. Confirm the `PythonSlicer` executable name in the installed `bin` directory.

## 4. ROS 2 Jazzy in WSL2 (Ubuntu 24.04)

Unblocks task 2.4 (tool-tip pose, mesh deformation, and wrench publish over ROS 2) and task 2.8 (FMI-LS-BUS transport over the ROS 2 layer, and the three-node clock test in G2.6).

### Pin and platform

* Distribution: ROS 2 Jazzy Jalisco, an LTS release supported until May 2029 (`https://discourse.openrobotics.org/t/ros-2-jazzy-jalisco-released/37862`, accessed 2026-10-14).
* Platform: Ubuntu 24.04. The Jazzy install page lists binary packages, including a Windows 10 binary (`https://docs.ros.org/en/jazzy/Installation.html`, accessed 2026-10-14).
* Windows binaries: the ros2/ros2 release notes state that Windows binaries "are not included in this patch release following the Platform EOL policy ... as Windows 10 ... is EOL" (`https://github.com/ros2/ros2/releases`, accessed 2026-10-14). The Windows route is therefore not used.
* Middleware: pin `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`. It uses the eProsima Fast DDS release that the Jazzy binary packages bundle, so no separate Fast DDS install is needed. The bundled version is recorded in the SOUP inventory from the package list (step 5).

### Why WSL2, why Jazzy

* WSL2 is the Linux route on this Windows host. SlicerROS2 is Linux-only (Section 5), so its Linux toolchain must sit beside Slicer and ROS 2.
* Jazzy is chosen over Lyrical Luth. Lyrical Luth was released May 22, 2026 and is an LTS to May 2031 (`https://docs.ros.org/en/rolling/Releases/Release-Lyrical-Luth.html`, accessed 2026-10-14). The SlicerROS2 tested combination is Ubuntu 24.04 with Jazzy (`https://slicer-ros2.readthedocs.io/en/devel/pages/compatibility.html`, accessed 2026-10-14). No SlicerROS2 release tested against Lyrical was found. Lyrical becomes an option when SlicerROS2 tests it.
* Kilted Kaiju is not chosen. The research brief gives end of life as 2026-12-31. A secondary source gives November 2026 (`https://iotdigitaltwinplm.com/ros2-kilted-to-lyrical-luth-migration-2026/`, accessed 2026-10-14). Confirm the date on the ROS 2 Kilted page. Either date falls before the Phase 2 exit.

### Human steps

1. Enable WSL and install Ubuntu 24.04. Open PowerShell as administrator. The Microsoft install page (`https://learn.microsoft.com/en-us/windows/wsl/install`, accessed 2026-10-14) documents `wsl --list --online` for distribution names and `wsl --install -d <DistroName>` for installing one. The distribution is usually named `Ubuntu-24.04`. Confirm the name in the list.

   ```powershell
   wsl --list --online
   wsl --install -d Ubuntu-24.04
   ```

   Restart when Windows asks. On first launch, create the Linux user and password.

2. Confirm the version and WSL 2.

   ```powershell
   wsl --list --verbose
   ```

   Expected: `Ubuntu-24.04` with VERSION 2.

3. Inside Ubuntu, confirm the release with `lsb_release -a`. The output must report Ubuntu 24.04.
4. Install ROS 2 Jazzy by following the official Ubuntu package instructions linked from `https://docs.ros.org/en/jazzy/Installation.html`. Install the `ros-base` variant. Add the extra packages named in Section 5. The desktop variant is optional and adds RViz.
5. Add these lines to `~/.bashrc`, then open a new shell.

   ```bash
   source /opt/ros/jazzy/setup.bash
   export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
   ```

   Confirm with `printenv RMW_IMPLEMENTATION`. Expected: `rmw_fastrtps_cpp`.

6. Record the installed versions for the agents.

   ```bash
   dpkg -l | grep -i -E "fast|ros-jazzy-rmw"
   ```

Expected disk: about 10 GB for WSL Ubuntu and the ROS 2 base install (estimate). Expected time: 30 to 60 minutes, network dependent (estimate).

### Round-trip check

Terminal 1:

```bash
ros2 topic pub /ping std_msgs/msg/String "data: hello" -r 10
```

Terminal 2:

```bash
ros2 topic echo /ping
```

Expected: `data: hello` messages arrive at about 10 per second.

For latency, publish a stamped message (for example `geometry_msgs/msg/PoseStamped` at 100 Hz) and run `ros2 topic delay` on it. Confirm the subcommand with `ros2 topic --help` in the installed version. Record the reported delay in the Phase 2 log.

Done when: the echo receives the published messages and the latency is recorded.

### Docker alternative for headless use

The `osrf/ros:jazzy-ros-base` image is the lighter alternative for headless runs (confirm the tag on Docker Hub; the tag was not checked in this research). Docker Desktop is already healthy on the host. DDS discovery across the container boundary on Windows needs a separate check before the three-node test in G2.6.

## 5. SlicerROS2

Unblocks task 2.4 (the Slicer side of the ROS 2 bridge, and the wrench measurement at the ROS 2 subscriber in gate G2.4).

### Verified facts (accessed 2026-10-14)

* Repository: `https://github.com/rosmed/slicer_ros2_module`. The module is named SlicerROS2 in the plan. License: MIT (repository page). The URL `https://github.com/SlicerROS2/SlicerROS2` returned HTTP 404 in this research, so do not use it.
* Documentation: `https://slicer-ros2.readthedocs.io` (devel branch).
* Platform: the Getting Started page states the prerequisites as "Ubuntu Linux with ROS 2" and "3D Slicer built from source". Windows is not listed as a supported platform.
* Compatibility matrix: SlicerROS2 1.2 targets Ubuntu 24.04, ROS 2 Jazzy, and Slicer `v5.10.0` or `v5.12.0`, marked "Current release target (Tested)". SlicerROS2 1.1 targets Slicer 5.10.0 only. SlicerROS2 1.0 covers Ubuntu 20.04, 22.04, and 24.04 with Galactic, Humble, and Jazzy, and is marked historical.
* Build model: SlicerROS2 contains C++ loadable modules, so Slicer must be built from source. The Windows installer cannot host it.
* Maintenance: the repository README shows CI badges for Ubuntu 24.04 with Jazzy and Slicer 5.10 and 5.12. The repository has 734 commits on main and 6 open issues. The date of the last commit was not captured in this research.

Verdict: SlicerROS2 cannot run in the Windows installer path. It runs in the WSL2 Ubuntu 24.04 environment from Section 4, against a Slicer v5.12.0 source build.

### Build path in WSL2

1. Install the packages the SlicerROS2 Getting Started page lists, including `python3-colcon-common-extensions libassimp-dev mold` and the ROS package list on that page (`https://slicer-ros2.readthedocs.io/en/devel/pages/getting-started.html`). Use the Ubuntu Qt packages from apt. Do not install Qt from the Qt site.
2. Clone and check out Slicer.

   ```bash
   git clone https://github.com/slicer/slicer
   cd Slicer
   git checkout v5.12.0
   ```

3. Build Slicer from source with the Slicer Linux developer build instructions (`https://slicer.readthedocs.io/en/latest/developer_guide/build_instructions/linux.html`, linked from the SlicerROS2 page). Set `Slicer_USE_SYSTEM_OpenSSL=ON` after the first CMake run, as the SlicerROS2 page instructs. Use `make -j12` (about half of the 24 threads, following the SlicerROS2 advice to avoid saturating memory).

   Expected disk: about 40 GB for the Slicer source and build (estimate). Expected time: "a few hours" (SlicerROS2 Getting Started page).

4. Clone the module into a ROS 2 workspace and pin it to a tag. Confirm the tag for SlicerROS2 1.2 in the repository.

   ```bash
   source /opt/ros/jazzy/setup.bash
   mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
   git clone https://github.com/rosmed/slicer_ros2_module
   ```

5. Build the module with colcon, pointing at the Slicer build directory.

   ```bash
   cd ~/ros2_ws
   colcon build --cmake-args -DSlicer_DIR:PATH=<path to Slicer-build> -DCMAKE_BUILD_TYPE=Release
   ```

6. Launch Slicer through the wrapper.

   ```bash
   source ~/ros2_ws/install/setup.bash
   ros2 run slicer_ros2_module slicer
   ```

Done when: Slicer starts through `ros2 run slicer_ros2_module slicer`, and the ROS category appears in the Modules menu (SlicerROS2 Getting Started page).

Display: running Slicer from WSL2 needs a Linux GUI path on Windows 11. WSLg is the expected route. Confirm it on the host before the build.

### Networked bridge variant

The alternative of running Slicer on Windows and ROS 2 in WSL2, joined over DDS through the WSL network, was not verified. Do not use it without a separate test.

### Fallback if the extension cannot build in this layout

Build a direct Fast DDS topic bridge as a plain ROS 2 node in the `sim/bridge/` path (or inside the task 2.8 master work) that publishes tool-tip pose, mesh deformation, and wrench topics. Record the deviation in the Phase 2 log with the reason. Gate G2.4 measures the wrench rate at the ROS 2 subscriber, so the gate's measurement point does not change under this fallback.

## 6. FMI 3.0 tooling

Unblocks task 2.7 (FMU packaging of the thermal, mechanical, and physiology plant models), gate G2.6 (FMU import checks), and task 2.8 (co-simulation master with clocks and scheduled variables).

### Standard

The FMI standard is free of charge, though tool vendors may charge for FMI-supporting tools (`https://fmi-standard.org/faq/`, accessed 2026-10-14).

### Picks

| Role | Pick | Version or commit | License | FMI 3.0 status | Source (accessed 2026-10-14) |
|:-----|:-----|:------------------|:--------|:---------------|:-----------------------------|
| FMU import check (G2.6, task 2.7) | FMPy | 0.3.32 (PyPI, released 2026-09-09) | BSD-3-Clause (`https://fmpy.readthedocs.io/`) | Supported. The README states "supports FMI 1.0, 2.0, and 3.0". | `https://pypi.org/project/FMPy/`, `https://github.com/CATIA-Systems/FMPy` |
| FMU packaging scaffold (task 2.7) | Reference FMUs | Pin the release tag at download. The repository ships FMI 2 and FMI 3 reference FMUs with CMake. | BSD-2-Clause (repository) | Supported. Examples target FMI 3.0. | `https://github.com/modelica/Reference-FMUs` |
| C++ import library for the master (task 2.8) | fmi4c (candidate, not selected) | Pin a commit at evaluation | Not confirmed. The repository has a LICENSE file, and its name must be read from that file before the SOUP entry. | Supported for FMI 3.0 co-simulation, model exchange, and scheduled execution (README). Clock support is not stated in the README. | `https://github.com/fmi-tools/fmi4c` |

Rejected: fmi4cpp (`https://github.com/NTNU-IHB/FMI4cpp`). It is MIT licensed, but its README describes it as an FMI 2.0 implementation, and the repository was archived read-only on 2026-08-24. It does not support FMI 3.0.

### Human steps

1. Create a validator environment with the same interpreter as the Phase 2 venv. Confirm Python 3.11 with `py -0`.

   ```powershell
   py -3.11 -m venv .venv-fmi
   .\.venv-fmi\Scripts\python.exe -m pip install "fmpy==0.3.32"
   .\.venv-fmi\Scripts\fmpy.exe --help
   ```

   Done when `fmpy --help` prints the command list. The wheel SHA256 is `b379deb9417b842028003a288d00c1c5f138d1580e1ff12cc6c42a98719cecf0` (PyPI release files). Expected disk: under 1 GB (estimate).

2. Download the Reference FMUs release from `https://github.com/modelica/Reference-FMUs/releases/latest/download/Reference-FMUs.zip` (or from the tag page). Extract it to a tools folder outside the repository, such as `C:\tools\fmi\Reference-FMUs`. The repository builds with CMake.

   ```powershell
   cd C:\tools\fmi\Reference-FMUs
   cmake -B build .
   cmake --build build
   ```

   Done when `build\fmus` contains FMU files. Expected disk: under 500 MB (estimate).

3. Clone fmi4c for evaluation under the tools folder and record the commit.

   ```powershell
   git clone https://github.com/fmi-tools/fmi4c C:\tools\fmi\fmi4c
   git -C C:\tools\fmi\fmi4c rev-parse HEAD
   ```

   Done when the commit hash is recorded. The agents evaluate the build and the license in task 2.8.

### Import-check path for gate G2.6

1. Package the FMU for each plant model in `sim/fmi/` (task 2.7). The Reference FMUs are the layout reference.
2. Run `fmpy info <fmu>` on each FMU. The output lists the FMI version and the FMU kind. The FMPy README shows this command.
3. Run the FMPy validation subcommand for the pinned version. Confirm the subcommand name with `fmpy --help` before the check is scripted.
4. Simulate each FMU with `fmpy simulate <fmu>` and compare its result with the Reference FMU control run for the same sample.

Gate G2.6 requires "FMUs pass FMI 3.0 import checks". This path defines the import checks as steps 2 to 4 above.

### FMI-LS-BUS availability and fallback

* Spec status: FMI-LS-BUS v1.0.0 was released 2025-07-21. It covers the Physical Signal Abstraction for all bus types and the Network Abstraction for CAN, CAN FD, and CAN XL (`https://fmi-standard.org/news/2025-07-21-fmi-ls-bus-v1.0-release/`, accessed 2026-10-14). FlexRay and Ethernet are pre-release in v1.1.0-beta on the same page.
* License: code is BSD-2-Clause and documentation is CC BY-SA 4.0 (`https://github.com/modelica/fmi-ls-bus`, accessed 2026-10-14).
* Transport: the standard emulates bus traffic with FMI 3.0 binary variables that model automotive networks. Neither the repository nor the release page defines a DDS or Fast DDS transport. The plan's wording "FMI-LS-BUS 1.0 over Fast DDS" does not match the published spec.
* Open material: C headers, schemas, and tests in the repository; demo FMUs for CAN and FlexRay in `https://github.com/modelica/fmi-ls-bus-examples` (accessed 2026-10-14); a Wireshark plugin for captures.

Verdict: no usable open-source reference implementation of FMI-LS-BUS over Fast DDS exists. The demo FMUs model CAN and FlexRay bus behavior and do not connect to DDS.

Fallback for task 2.8: implement scheduled-variable co-simulation directly over the pinned ROS 2 and Fast DDS layer (Section 4). Use FMI 3.0 clocks and scheduled execution in the master, with ROS 2 topics as the transport. Record the deviation in the Phase 2 log, using the same pattern as the VAL-005 clock-skew handling: bounded skew and jitter limits, measured in gate G2.6 on the three-node Fast DDS test.

## 7. Procurement sequence

Order follows the priority list. Item 4 must finish before item 5 starts, because the SlicerROS2 build runs in the WSL2 environment from item 4. The other items are independent.

| Order | Item | Who | Disk (estimate) | Wall clock (estimate unless sourced) | Done when | Clears | Status (2026-10-14) |
|:------|:-----|:----|:----------------|:-------------------------------------|:----------|:-------|:--------------------|
| 1 | Pulse engine: copy `.pulse/`, then build `biosync-pulse` | Human: steps 1 to 6 in Section 1. Agents: import check, IQ-4, OQ-16, fail-closed OQ, 600 s heartbeat run, SOUP and migration-map rows | About 20 GB Docker data | 30 to 90 min cold build (Gateway log estimate) | Build log contains `ENGINE INIT OK`; image `biosync-pulse` exists | Task 2.6 real-engine run; FR-MS-006 heartbeat evidence in G2.5; IQ-4; OQ-16 | DONE. `.pulse/` copied and `biosync-pulse` built; `import pulse OK`; engine suites 11 passed, 1 skipped. Heartbeat run `vtm-600s` FAILED: 239.357 ms against the 50 ms bound (stub 73.225 ms). Diagnosis in progress. |
| 2 | SOFA v26.06.00 installer | Human: download, checksum, install, `runSofa`. Agents: CMake find check after task 2.2, SOUP entry | About 2 GB | About 15 min | `runSofa` opens a bundled scene and steps | Task 2.2; task 2.3 tooling (contact and cutting effort is still open); mechanical FMU of task 2.7 | DONE. Installed at `C:\Users\salmo\SOFA\v26.06.00`; `runSofa.exe` present. Bundled scene run recorded 2026-10-15: `runSofa.exe -g batch` stepped the bundled `TetrahedronHyperelasticityFEMForceField.scn` 50 steps (evidence in `SNDEV/docs/impl-2026-10-15-sofa-scene-slice1.md`). |
| 3 | 3D Slicer 5.12.0 (recommended) installer | Human: download, SHA512 check, DICOM load, labelmap export. Agents: `PythonSlicer` segmentation test | About 2 GB | About 20 min | Slicer starts, DICOM study loads, labelmap file is written | Task 2.1; segmentation input for G2.1 | DONE with alternate pin. 5.12.4 installed at `I:\Library\3D Slicer 5.12.4` instead of the recommended 5.12.0; `Slicer.exe` present. DICOM load not yet recorded. The WSL2 bridge pins its own v5.12 source tag in item 5. |
| 4 | WSL2 Ubuntu 24.04 and ROS 2 Jazzy | Human: WSL install, ROS 2 base install, RMW setting, round-trip check. Agents: Fast DDS version record in SOUP | About 10 GB | 30 to 60 min (estimate) | Echo receives published messages at about 10 Hz; latency recorded | Task 2.4 ROS 2 transport; task 2.8 transport; three-node test in G2.6 | PENDING, user decision on 2026-10-14. Deferred for disk space and install time. No Ubuntu 24.04 WSL2 distribution is present. |
| 5 | SlicerROS2 in WSL2 | Human: Slicer v5.12.0 source build, colcon build, launch check. Agents: bridge code in `sim/bridge/`, wrench-rate test in G2.4 | About 40 GB | A few hours (SlicerROS2 Getting Started page) | `ros2 run slicer_ros2_module slicer` opens with the ROS category visible | Task 2.4 bridge; G2.4 wrench measurement at the ROS 2 subscriber | PENDING, depends on item 4 (user decision on 2026-10-14). |
| 6 | FMI tooling: FMPy, Reference FMUs, fmi4c clone | Human: `.venv-fmi`, Reference FMU build, fmi4c commit. Agents: FMU packaging, import checks, master import library, FMI-LS-BUS fallback record | About 1 GB | About 30 min | `fmpy --help` runs; Reference FMUs build; fmi4c commit recorded | Task 2.7; G2.6 import checks; task 2.8 master import library; FMI-LS-BUS fallback decision | PARTIAL. FMPy 0.3.32 installed in the host Python 3.14 user site, not a repository venv. Reference FMU build and fmi4c clone not reported. |

## Remaining board after this guide

These items are not cleared by the tooling in this guide.

* Task 4.5 (Phase 4): procure and integrate the Phase 3 HIL target. The HIL options in plan Section 2 (Speedgoat, dSPACE, and NI SLSC) are commercial. Under the 2026-10-14 decision, none can be procured for development. Task 4.5 needs a plan-owner decision on an open-source or non-licensed bench target. The plan also names hardware lead time as a risk.
* Task 2.2 solver effort (8.0 days) and task 2.3 contact, culling, continuous collision detection, puncture, and cutting (6.0 days) are engineering effort after the tooling is in place. Gates G2.2 and G2.3 measure that work.
* Tasks 3.7 and 3.8 (open-source static analysis, and gcov-family coverage with Catch2 and CTest) and task 6.6 (repository-native trace store) are open source by the plan's Section 2 rows. This guide does not select their tools. A separate guide covers them.
* Phase 7 (task 7.1, Omniverse and Isaac Sim): the license terms for these NVIDIA products were not researched here. Check them before Phase 7.
* Phase 5 (SiLA 2 SDK): the plan confirms the SDK license at selection. This guide does not cover it.
