Title: Open-source tooling procurement guide for Phase 2
Date: 2026-10-14T22:40:49Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: user procurement request 2026-10-14; DEVELOPMENT_PLAN.md Phase 2 preconditions
Summary: Adds docs/procurement-guide.md, an open-source-only install guide for the Phase 2 tooling (Pulse, SOFA, Slicer, ROS 2 Jazzy in WSL2, SlicerROS2, FMI 3.0), with research verdicts on SlicerROS2 and FMI-LS-BUS.

## Task Reference

* User procurement request dated 2026-10-14: a human-executable guide for the open-source tooling that unblocks Phase 2 of SurgiTwin-RTA, with no commercial license.
* Plan-owner decision of 2026-10-14: no commercial licenses in development. Commercial tools are adoption options for licensees only.
* DEVELOPMENT_PLAN.md Phase 2 tasks 2.1 to 2.8 and gates G2.1 to G2.6, and the task 2.6 real-engine run. The plan was read only and not edited. Its owner maintains it.
* Deliverable: `docs/procurement-guide.md` (new, untracked before this commit).

## Specification Summary

* Front matter: purpose, host assumptions (Windows 11 Pro, Ryzen 9 3900X, 48 GB, MSVC 19.44, CMake 3.31.6, Docker Desktop 25.0.3 with a healthy PostgreSQL 15 container, PowerShell, Python 3.11.9 venvs, WSL not provisioned), the rule that every installed item lands in `sim/SOUP.md` with its pin as an agent follow-up, and the rule that agents verify each item automatically.
* One section per tool in priority order: Pulse, SOFA v26.06.00, 3D Slicer, ROS 2 Jazzy in WSL2, SlicerROS2, FMI 3.0 tooling. Each section gives human steps, expected disk and time, done-when, and agent verification.
* Procurement sequence table with the human or agent split, disk, time, done-when, and the tasks and gates each item clears. A closing section lists what stays blocked by hardware or effort.
* Constraints: all web facts cite a URL and the access date 2026-10-14. Markers "(confirm)" stay where a primary source was not read. No banned words, no em or en dashes, straight quotes only, ASCII only, no emoji.

## Implementation Notes

### Sources consulted (all accessed 2026-10-14)

* SOFA download page: https://www.sofa-framework.org/download/ (v26.06.00 binaries, Windows assets, published SHA256 values, LGPL-2.1 statement, GPL statement for the applications folder, plugin list, source tag v26.06.00).
* SOFA Windows build page: https://www.sofa-framework.org/community/doc/getting-started/build/windows/ (Visual Studio 2017, 2019, 2022 support, Pixi route, long-path advice, Build Tools guidance). The page body was read from a saved tool output because the navigation dominated the fetch.
* 3D Slicer download page: https://download.slicer.org (stable 5.12.4 revision 34645 built 2026-09-09 for Windows, preview 5.13.0 built 2026-10-14, Windows SHA512 for both, older-releases list containing 5.12.0 marked unsupported, naming convention).
* 3D Slicer about page: https://slicer.readthedocs.io/en/latest/user_guide/about.html (BSD-style license description, OSI review result, research-use note).
* SlicerROS2 repository: https://github.com/rosmed/slicer_ros2_module (MIT license, Linux-first README, CI badges for Ubuntu 24.04 with Jazzy and Slicer 5.10 and 5.12, 734 commits on main, 6 open issues). The repository page was fetched through the web fetch tool; the last-commit date was not captured.
* SlicerROS2 docs: https://slicer-ros2.readthedocs.io/en/devel/pages/getting-started.html and https://slicer-ros2.readthedocs.io/en/devel/pages/compatibility.html (Ubuntu Linux prerequisite, Slicer built from source, tested tags v5.10.0 and v5.12.0, Jazzy on Ubuntu 24.04, colcon build, ROS category, WSL and Windows not listed).
* SlicerROS2 URL check: https://github.com/SlicerROS2/SlicerROS2 returned HTTP 404 in this research. The plan's name points to the rosmed repository.
* ROS 2 Jazzy install page: https://docs.ros.org/en/jazzy/Installation.html (binary packages, Windows 10 binary entry). The page was fetched through a bot check, so its body was taken from a search result.
* ros2/ros2 releases: https://github.com/ros2/ros2/releases (Windows binaries not included in a Jazzy patch release after Windows 10 EOL). Taken from a search result.
* Jazzy LTS date: https://discourse.openrobotics.org/t/ros-2-jazzy-jalisco-released/37862 (supported until May 2029). Taken from a search result.
* Lyrical Luth: https://docs.ros.org/en/rolling/Releases/Release-Lyrical-Luth.html (released May 2026, LTS to May 2031). Taken from a search result.
* Kilted Kaiju end of life: research brief gives 2026-12-31. A secondary source gives November 2026: https://iotdigitaltwinplm.com/ros2-kilted-to-lyrical-luth-migration-2026/. The Vulcanexus distribution table, https://docs.vulcanexus.org/en/jazzy/ros2_documentation/source/Releases.html, was read and its Kilted date was truncated in the fetched text. The conflict is recorded in the guide, and the date needs confirmation on the ROS 2 Kilted page.
* WSL install: https://learn.microsoft.com/en-us/windows/wsl/install (wsl --install, wsl --list --online, wsl --install -d, WSL 2 default for new installs).
* FMI FAQ: https://fmi-standard.org/faq/ (standard free of charge; tool vendors may charge).
* FMI-LS-BUS v1.0 release news: https://fmi-standard.org/news/2025-07-21-fmi-ls-bus-v1.0-release/ (v1.0 covers Physical Signal Abstraction and CAN, CAN FD, CAN XL network abstraction; FlexRay and Ethernet in v1.1.0-beta pre-release; supported tools).
* FMI-LS-BUS repository: https://github.com/modelica/fmi-ls-bus (2-Clause BSD for code, CC BY-SA 4.0 for documentation, "current prototype draft" wording in README, C headers and schema, tools table, Wireshark plugin, no DDS transport).
* FMI-LS-BUS examples: https://github.com/modelica/fmi-ls-bus-examples (CAN and FlexRay demo FMUs only).
* fmi4cpp: https://github.com/NTNU-IHB/FMI4cpp (MIT license, "This project is no longer maintained", FMI 2.0 implementation, repository archived read-only on 2026-08-24).
* fmi4c: https://github.com/fmi-tools/fmi4c (C library importing FMI 1.0, 2.0, 3.0; FMI 3.0 co-simulation, model exchange, and scheduled execution; forked from robbr48/fmi4c; 315 commits on main). The page shows a LICENSE link without a license name, so the license is recorded as not confirmed.
* FMPy: https://pypi.org/project/FMPy/ (version 0.3.32, released 2026-09-09, Python 3.10 or later, wheel SHA-256 b379deb9417b842028003a288d00c1c5f138d1580e1ff12cc6c42a98719cecf0) and https://github.com/CATIA-Systems/FMPy (supports FMI 1.0, 2.0, and 3.0; fmpy info and fmpy simulate commands). The BSD-3-Clause statement came from a search result for the project documentation at https://fmpy.readthedocs.io/, which was not fetched directly.
* Reference FMUs: https://github.com/modelica/Reference-FMUs (2-Clause BSD license, FMI 2 and FMI 3 reference FMUs, CMake build with output in build/fmus, latest-release ZIP link). The URL https://github.com/modelica/reference-fmu returned HTTP 404; the Reference-FMUs repository is the correct location.

### Per-tool research results

* Pulse Physiology Engine: Pulse pin REL_4_3_2 (`middleware/Dockerfile.pulse` line 25, clone at line 111). Gateway vendored copy declares project version 4.3.2 and carries an Apache-2.0 LICENSE. The copy has 1814 files under `.pulse/src` and no `.git` metadata, so no commit pin exists. Verified beyond the brief: the Gateway log `SNDEV/docs/impl-2026-07-28-pulse-segfault-diag-plan.md` records IQ-4, OQ-16, PQ-2, and PQ-6 at 19 of 19 PASS in the image, with the Docker build gate printing `ENGINE INIT OK`. The RTA Dockerfile already uses the full bullseye runtime base that this fix requires.
* SOFA: v26.06.00 is current. Windows binaries and published SHA256 values are confirmed on the download page. License LGPL-2.1 or later is stated; the applications folder is GPL-2.0 or later. The plan's "(confirm)" marker stays until the SOUP entry checks the pinned tag's LICENSE file. The Windows bundled Python version is not stated.
* 3D Slicer: stable 5.12.4 (revision 34645, built 2026-09-09). The guide recommends pinning 5.12.0 for both task 2.1 and task 2.4 so one Slicer version is in SOUP, and keeps 5.12.4 as the alternative. This choice is open. License: BSD-style per the about page, and the about page states the OSI review result. Slicer is free of charge and open source by description, not OSI-approved.
* ROS 2: Jazzy pinned in WSL2 Ubuntu 24.04, RMW `rmw_fastrtps_cpp`. Lyrical Luth verified as LTS to May 2031 and not chosen because SlicerROS2 tests only Jazzy. Kilted not chosen.
* SlicerROS2 (verdict): the repository is https://github.com/rosmed/slicer_ros2_module, license MIT. Platform is Ubuntu Linux with ROS 2 Jazzy, Slicer built from source at v5.10.0 or v5.12.0. Windows is not a supported platform. The Windows installer cannot host the module. The build runs in the WSL2 layout from Section 4. The networked bridge variant (Slicer on Windows, ROS 2 in WSL2) is not verified. The fallback is a direct Fast DDS topic bridge, recorded as a deviation. G2.4 measures at the ROS 2 subscriber, so that measurement point is unchanged under the fallback.
* FMI tooling: picks are FMPy 0.3.32 (validator, BSD-3-Clause, FMI 3.0), Reference FMUs (scaffold, BSD-2-Clause, FMI 3.0), and fmi4c (candidate import library for the master, FMI 3.0 co-simulation and scheduled execution, license not confirmed, clock support not stated). fmi4cpp is rejected: MIT, FMI 2.0 only, archived on 2026-08-24.
* FMI-LS-BUS (verdict): no usable open-source reference implementation of FMI-LS-BUS over Fast DDS exists. The published spec (v1.0.0) is a bus-emulation layer for automotive networks over FMI 3.0 binary variables. It does not define a DDS transport. The plan's Section 2 wording "FMI-LS-BUS 1.0 over Fast DDS" does not match the spec. The fallback is scheduled-variable co-simulation over the pinned ROS 2 and Fast DDS layer, with the deviation recorded in the Phase 2 log, following the VAL-005 pattern.

### Local files read or checked

* `middleware/Dockerfile.pulse` (read in full, 225 lines): ARG lines 24 to 26, COPY of `.pulse` at line 49, the `local` and `git` builder stages, the IQ-4 build gate at lines 208 to 218 that prints `ENGINE INIT OK`, the header tag comment at line 18 (`surgitwin-pulse`).
* `docs/migration-map.md` rows at lines 29 to 32 (FR-MS-006 files) and line 131 (the Pulse source and build row is OPEN, `.pulse/` is an external prerequisite).
* `.dockerignore` (read): excludes `.git`, `build/`, `rta/`, `sim/`, `edge/`, `frontend/`, `vv/`, `SNDEV/`, and `docs/`. It does not exclude `.pulse`. The `vv/` exclusion is why the guide runs the test suites from a bind mount.
* `.gitignore`: contains `.pulse/` and `SNDEV/logs/*` with `!SNDEV/logs/.gitkeep`.
* `middleware/requirements.txt` (no pytest) and `middleware/requirements-test.txt` (`-r requirements.txt`, `pytest==8.3.4`, `httpx==0.28.1`, `ruff==0.8.4`, `mypy==1.13.0`).
* `middleware/Pulse/__init__.py` exists (shim copied by the Dockerfile at line 174).
* `vv/tests/IQ/test_iq4_pulse_engine_init.py` (line 16 `pytest.importorskip("pulse")`), `vv/tests/OQ/test_oq16_pulse_state_serialization.py` (line 11), `vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py` (skipif on bindings present), `vv/tests/PQ/test_pq_fr_ms_006_heartbeat_gap.py` (environment variables at lines 11 to 12 and 58 to 59; capture path `SNDEV/logs/pq-<UTC date>-fr-ms-006-<run id>.json` at lines 114 to 118).
* `sim/sofa/CMakeLists.txt`, `sim/bridge/CMakeLists.txt`, and `sim/fmi/CMakeLists.txt` are placeholders with no targets. Root `CMakeLists.txt` defines `SRTA_BUILD_SOFA`, `SRTA_BUILD_FMI`, and `SRTA_BUILD_BRIDGE`, all default OFF.
* `SNDEV/docs/impl-2026-10-14-phase2-kickoff.md` (preflight table, read lines 1 to 120): host state, CMake 3.31.6, MSVC toolset 14.44.35207, Docker 25.0.3, PostgreSQL 15.19 healthy.
* `DEVELOPMENT_PLAN.md` (read only): Section 2 rows at lines 35 to 44 and 50 to 57, Phase 2 tasks at lines 199 to 206, gates G2.1 to G2.6 at lines 212 to 217, Phase 4 task 4.5 at line 275, gate G6.1 at line 350, and the Phase 2 risk rows around lines 477 to 500.
* Gateway repository, read or checked: `.pulse/CMakeLists.txt` (`project(Pulse VERSION 4.3.2 LANGUAGES C CXX)`), `.pulse/LICENSE` (Apache License 2.0 header), `.pulse/ReadMe.md` (MSVC 2017 and later, CMake 3.12 or later), `.pulse/src` file count (1814), no `.git` under `.pulse`, `middleware/Dockerfile.pulse` (ARG `PULSE_VERSION=REL_4_3_2`), `.github/workflows/pulse-engine.yml` (CI build with `--build-arg VARIANT=git`, runs pytest in the image with `PYTHONPATH=/repo/middleware:/repo`), `SNDEV/scripts/build-pulse.sh` (container run and pytest invocation), Gateway logs `impl-2026-07-27-R1-pypulse-binary.md`, `impl-2026-07-27-r1-pulse-binary.md`, `impl-2026-07-28-pulse-build-fix.md`, `impl-2026-07-28-pulse-docker-ssl-fix.md`, `impl-2026-07-28-pulse-segfault-diag-plan.md`, and `impl-2026-07-28-pulse-segfault-fix.md`.

### Divergences from the brief

* Author header: the brief specified "Seth Nenninger (MiMo-V2.6-Pro Agent)". This log records "Claude Haiku 5.5 Agent", which is the model that produced the work. The kickoff log uses the same convention. The user may change the field.
* Pulse verification: the brief lists `pytest` commands. The image excludes `vv/` from its build context, and the three IQ and OQ tests import `engine.pulse` and skip without `pulse`. The guide therefore runs the suites inside the image with a bind mount and a `PYTHONPATH` that keeps the `/pulse` entries. The Gateway CI step replaces `PYTHONPATH`, which would drop them. This is recorded as a risk in the guide.
* Pulse tag: the brief uses `docker build -t biosync-pulse`. The header comment in `middleware/Dockerfile.pulse` names `surgitwin-pulse`. The guide uses the brief's tag. The header is a follow-up.
* SlicerROS2 repository: the plan's name points to a URL that returned 404. The guide uses `rosmed/slicer_ros2_module`.
* FMI-LS-BUS over Fast DDS: the brief asked for a reference-implementation verdict. The verdict is that none exists for a Fast DDS transport, and the spec does not define one.
* Pulse verification and the Gateway log: the brief stated the acceptance as "IQ-4, OQ-16, PQ-2, PQ-6 against the real engine". The Gateway log `impl-2026-07-28-pulse-segfault-diag-plan.md` records that result as 19 of 19 PASS, and the guide cites it.

### Commit state during the run

* HEAD was `189df07` at the start of the run and moved to `2ae3d4e` during it. A parallel agent committed. This implementation did not change any tracked file. The only changes are the two new files named below.

## Verification

### Checks on the guide

* Banned-word scan against the word list and the copula rules in AGENTS.md section 1: no matches in the guide or this log.
* Dash scan for em and en dashes: no matches.
* Curly-quote scan: no matches.
* Non-ASCII scan: no matches.
* Line count of `docs/procurement-guide.md`: 464.

### Claims and their checks

| Claim in guide | Check | Result |
|:---------------|:------|:-------|
| Pulse `REL_4_3_2` default and clone target | Read `middleware/Dockerfile.pulse` lines 25 and 110 to 111 | Confirmed |
| Pulse version 4.3.2 | Read `BioSync-Gateway\.pulse\CMakeLists.txt` | Confirmed |
| Pulse license Apache-2.0 (copy only) | Read `BioSync-Gateway\.pulse\LICENSE` header | Confirmed for the copy; tag still "(confirm)" |
| `.pulse/` gitignored in both repositories | `.gitignore` in each | Confirmed |
| `.pulse` not excluded from the build context | Read `.dockerignore` | Confirmed |
| In-image IQ-4 and OQ-16 need a bind mount for `vv/` | `.dockerignore` excludes `vv/`; tests import `engine.pulse` | Confirmed |
| pytest is not in the runtime image; installed from `/app/requirements-test.txt` | `middleware/requirements.txt` has no pytest; `requirements-test.txt` pins pytest 8.3.4 | Confirmed |
| Gateway CI overrides `PYTHONPATH` | Read `.github/workflows/pulse-engine.yml` | Confirmed |
| Real-engine PASS 19 of 19 in Gateway | Read `impl-2026-07-28-pulse-segfault-diag-plan.md` lines 147 to 159 | Confirmed (Gateway log, not re-run here) |
| SOFA v26.06.00 Windows binary and checksums | Read the download page | Confirmed (checksums published by SOFA; human recomputes) |
| SOFA LGPL-2.1 or later, GPL applications folder | Read the download page | Confirmed as stated; "(confirm)" kept |
| Slicer stable 5.12.4 built 2026-09-09 and SHA512 | Read download.slicer.org | Confirmed |
| Slicer 5.12.0 in older releases | Read download.slicer.org | Confirmed as listed; Windows package not downloaded |
| Slicer license BSD-style, not OSI-approved | Read the about page | Confirmed as the page states |
| SlicerROS2 MIT, Linux-first, tested tags | Read repository and docs | Confirmed |
| SlicerROS2 URL in plan returns 404 | webfetch of github.com/SlicerROS2/SlicerROS2 | Confirmed 404 |
| Jazzy LTS to May 2029, Windows binaries dropped from patch releases | Discourse and ros2/ros2 releases | Confirmed from sources cited |
| Lyrical LTS to May 2031 | docs.ros.org rolling page | Confirmed from search result |
| Kilted EOL date | Two sources disagree (2026-12-31 in brief; November 2026 secondary) | Not resolved; recorded |
| WSL install commands | Read learn.microsoft.com page | Confirmed |
| FMPy 0.3.32, released 2026-09-09, Python 3.10 or later | Read PyPI page | Confirmed; wheel SHA-256 read from the PyPI release table |
| FMPy FMI 3.0 support | Read GitHub README | Confirmed |
| FMPy BSD-3-Clause | Search result for the FMPy documentation | Confirmed from search result only |
| Reference FMUs BSD-2-Clause and FMI 3 examples | Read GitHub repository | Confirmed |
| fmi4cpp MIT, FMI 2.0 only, archived 2026-08-24 | Read GitHub repository | Confirmed |
| fmi4c FMI 3.0 features | Read GitHub repository | Confirmed; license not confirmed |
| FMI-LS-BUS v1.0.0 scope and license | Read news page and GitHub repository | Confirmed |
| FMI-LS-BUS has no Fast DDS transport | Read GitHub repository, news page, and examples repository | Confirmed by absence in the sources read |

### Not run

* No `docker` command, no `pytest`, no package install, and no download of SOFA, Slicer, ROS 2, or FMPy was run. The brief excluded installs, and the guide's verification steps are for the agents after the human installs.
* No `DEVELOPMENT_PLAN.md` edit. The file is read-only in this task.

## Follow-ups

### Agent follow-ups after the human installs

* `sim/SOUP.md`: add or update rows for Pulse (Gateway HEAD and tag `REL_4_3_2`, Apache-2.0 "confirm"), SOFA v26.06.00 (LGPL-2.1 "confirm", applications folder GPL note), Slicer (5.12.0 or 5.12.4 per the decision), SlicerROS2 (MIT per repository, tag pin), ROS 2 Jazzy (distribution and Fast DDS version from `dpkg`), FMPy 0.3.32 (BSD-3-Clause, wheel hash), Reference FMUs (release tag), fmi4c (commit, license name), and FMI-LS-BUS (spec v1.0.0, no DDS transport).
* `docs/migration-map.md`: add a row for the `.pulse/` copy with origin path `I:\Documents\GitHub\BioSync\BioSync-Gateway\.pulse` and the Gateway HEAD recorded by the human.
* Run the verification commands in Section 1 of the guide after the image builds. Record PASS or FAIL with captured output under `SNDEV/logs/`.
* Add the `find_package` change in `sim/sofa/CMakeLists.txt` under task 2.2, then run the configure check in Section 2.
* Write the `PythonSlicer` segmentation test under task 2.1.
* Run the WSL round-trip check and record the latency under task 2.4.
* Record the FMI check results under task 2.7 and the fmi4c evaluation under task 2.8.

### Open items for the human

* Slicer pin: 5.12.0 (recommended, one SOUP entry) or 5.12.4 (second pin for the bridge).
* Docker data volume: confirm about 20 GB free before the Pulse build.
* WSLg: confirm that Slicer GUI runs from WSL2 on this host before the SlicerROS2 build.
* SOFA Windows Python version: record the bundled interpreter before any SofaPython3 script is written.
* Kilted Kaiju end-of-life date: confirm on the ROS 2 Kilted page.

### Items for the plan owner (not edited here)

* `DEVELOPMENT_PLAN.md` Section 2 row for Co-simulation and Phase 2 task 2.8 use the wording "FMI-LS-BUS 1.0 over Fast DDS". The published spec has no Fast DDS transport. The owner should amend the wording and record the scheduled-variable fallback.
* Section 2 row for SlicerROS2 gives its license as "(confirm)". The repository states MIT. The owner should decide whether the marker stays until the SOUP entry is closed.
* Section 2 row for 3D Slicer gives a BSD-style license. The about page says the license is not OSI-approved. The owner should confirm that free-of-charge status satisfies the procurement rule for this item.
* Section 2 HIL options (Speedgoat, dSPACE, NI SLSC) are commercial. Under the 2026-10-14 decision, task 4.5 needs an open-source or non-licensed bench target. The owner should decide this before Phase 3 ends.
* SlicerROS2 runs only on Linux. The plan's "Tagged releases pinned in `sim/bridge/`" should name the WSL2 Ubuntu 24.04 environment.
* The plan's G2.6 requires "FMUs pass FMI 3.0 import checks" without a definition. The guide defines the path in Section 6. The owner should record that definition.
* Phase 6 gate G6.1 and tasks 3.7 and 3.8 name no tool in this guide. Plan Section 2 already names open-source paths for them. A follow-up guide should select those tools.

### Repository hygiene

* The Gateway repository was not changed by this run. The Gateway CI `PYTHONPATH` override is a finding for the Gateway owner.
* The header tag in `middleware/Dockerfile.pulse` (line 18) names `surgitwin-pulse`. The RTA owner should correct it. This run did not edit that file.
