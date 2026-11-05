# SRS v1.2 Change Proposal (SurgiTwin-RTA)

Proposal only. SRS.md remains v1.1.0 until the document owner applies the approved amendments.

Target document: SRS.md v1.1.0, 120 lines. Every line number below refers to that version.
Decision record: the document owner approved the RoboStack provisioning change on 2026-11-04 and confirmed on 2026-11-04 that `ros-jazzy-rmw-fastrtps-cpp` publishes a `win-64` build in the `robostack-jazzy` channel.
Findings: VAL-026 and VAL-027 are new with this proposal. The baseline register (VAL-001 through VAL-025) is `SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md`.
Replacement text sources: `vv/traceability/vtm.md` (rows FR-MS-004, FR-MS-005, FR-MS-007, NFR-PERF-002) and `docs/procurement-guide.md` Sections 4, 5, 6, and 7.
Evidence (all accessed 2026-11-04): the RoboStack channel list and conda install guide (`https://robostack.github.io/`, `https://robostack.github.io/conda.html`), the `robostack-jazzy` package page for `ros-jazzy-rmw-fastrtps-cpp` (`https://prefix.dev/channels/robostack-jazzy/packages/ros-jazzy-rmw-fastrtps-cpp`), the ROS 2 Jazzy Windows binary install page (`https://docs.ros.org/en/jazzy/Installation/Windows-Install-Binary.html`), and the Isaac Sim ROS 2 installation page (`https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_ros.html`).
Prepared: 2026-11-04.

Conventions used in the tables:

* Current text strings are quoted exactly from SRS.md v1.1.0 and shortened to the relevant clause or cell.
* SRS Section 5 holds six columns: Requirement ID, Subsystem / Module, Regulatory / Standard Mapping, CSA Risk Classification, Verification Method & Toolchain, Target Acceptance Metric. This proposal changes Verification Method & Toolchain cells and one Subsystem / Module cell name. It changes no acceptance metric.
* One approved amendment (VAL-026) and one pending decision (VAL-027) are carried here. Section 3 holds ready-to-apply clause text for both outcomes of VAL-027, so the document owner selects a variant during the SlicerROS2 research without further drafting.

## 1. Scope and decision status

Approved on 2026-11-04: ROS 2 Jazzy is provisioned natively on Windows through pixi with the RoboStack `robostack-jazzy` conda channel (conda-forge backend), with `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`. This supersedes the WSL2 Ubuntu 24.04 route of `docs/procurement-guide.md` Section 4 (procurement items 4 and 5) as the ROS 2 provisioning route for Phase 2 task 2.4, Phase 2 task 2.8, and Phase 7 task 7.1. The Fast DDS middleware named in FR-MS-004, FR-MS-007, and NFR-PERF-002 keeps its name; the distribution and its provisioning route are what this proposal adds to the SRS cells.

Pending, opened 2026-11-04: the FR-MS-004 SlicerROS2 clause (VAL-027). The document owner is researching the significance of SlicerROS2 to the project and records that alternative project goals may be needed. Task 2.4 does not start and gate G2.4 stays OPEN until one variant of Section 3 is selected.

Out of scope, referenced: the FR-MS-007 FMI-LS-BUS transport wording and the leftover `quantization-error-free` phrase in its clause (Section 6).

## 2. Finding register and amendment rows

| Finding ID | SRS location (section and line) | Current text (quoted from SRS.md v1.1.0) | Proposed replacement text | Rationale | Impact on the VTM |
| :--- | :--- | :--- | :--- | :--- | :--- |
| VAL-026 | Section 5 Verification Method & Toolchain cells: FR-MS-004 row, line 94; FR-MS-007 row, line 96; NFR-PERF-002 row, line 108. Clause context: lines 42, 45, and 79 name Fast DDS and ROS2 nodes with no pinned distribution and no provisioning route | Line 94: `Scripted SIL publish-rate test at the ROS 2 subscriber (Pytest over Fast DDS)`. Line 96: `Multi-Node Distributed Clock Sync Test (Fast DDS)`. Line 108: `Locust WSS relay measurement plus HIL bench edge measurement at named points (task 1.6 configuration; task 4.6 bench)` | Line 94 becomes `Scripted SIL publish-rate test at the ROS 2 subscriber (Pytest over Fast DDS; ROS 2 Jazzy via RoboStack on Windows)`. Line 96 becomes `Multi-Node Distributed Clock Sync Test (Fast DDS; ROS 2 Jazzy via RoboStack on Windows)`. Line 108 becomes `Locust WSS relay measurement plus HIL bench edge measurement at named points (task 1.6 configuration; task 4.6 bench; Fast DDS leg on ROS 2 Jazzy via RoboStack on Windows)` | The recorded provisioning route (WSL2 Ubuntu 24.04, `docs/procurement-guide.md` Section 4) is superseded by the approved RoboStack route. Evidence, all accessed 2026-11-04: the `robostack-jazzy` channel publishes `win-64` builds of the Jazzy stack and of `ros-jazzy-rmw-fastrtps-cpp` (the channel package page, confirmed by the document owner on 2026-11-04); the ROS 2 Jazzy Windows binary install page installs its dependencies through pixi with conda-forge as the package backend and names Fast DDS as the default middleware; the Isaac Sim ROS 2 installation page documents a native Windows pixi workspace built on RoboStack conda packages, states that WSL2 is not required, and marks its WSL2 install method deprecated, which covers the FR-MS-005 leg of Phase 7. Consequences recorded: WSL2 and Ubuntu 24.04 are no longer preconditions for tasks 2.4, 2.8, and 7.1; SlicerROS2 (VAL-027) is the only remaining item that needs them. Interpreter split: RoboStack Jazzy builds target CPython 3.12 while the middleware and qualification suites run on Python 3.11.9; the SRS wording `Python 3.11+` at lines 26 and 58 admits 3.12, and ROS-side test processes run inside the conda environment with results passed to the 3.11 suites as JSON captures in `SNDEV/logs/`, following the `sim/sofa/src/run_reference_scene.py` pattern. Exact package pins and the environment lock land in `sim/SOUP.md` and `DEVELOPMENT_PLAN.md` Section 2 (Section 5 below) | Method cells of VTM rows FR-MS-004 (line 12), FR-MS-005 (line 13), FR-MS-007 (line 15), and NFR-PERF-002 (line 35) carry the same parenthetical under VTM owner scope. Acceptance metrics do not change |
| VAL-027 | FR-MS-004 clause, line 42; Section 5 row name cell, line 94; VTM row FR-MS-004, line 12 | Clause (line 42): `The system shall deploy the **SlicerROS2** module over **Fast DDS** to publish real-time Cartesian tool-tip positions, volumetric mesh deformation states, and calculated 6-axis haptic force feedback (wrench data) to **ROS2** nodes at high frequencies`. Row name cell (line 94): ``M&S / SlicerROS2 middleware bridge over Fast DDS (`sim/bridge/`)`` | Two prepared variants in Section 3. Option A leaves both strings unchanged. Option B replaces the clause with `The system shall deploy a ROS 2 bridge node over **Fast DDS** to publish real-time Cartesian tool-tip positions, volumetric mesh deformation states, and calculated 6-axis haptic force feedback (wrench data) to **ROS2** nodes at high frequencies` under the title `**FR-MS-004 (ROS 2 Middleware Bridge):**`, and replaces the row name cell with ``M&S / ROS 2 middleware bridge over Fast DDS (`sim/bridge/`)`` | Open question: is the SlicerROS2 module a project-goal-level requirement of FR-MS-004, or does the requirement cover the bridge function with any conforming ROS 2 publisher? SlicerROS2 supports Ubuntu Linux with ROS 2 and a 3D Slicer source build only (`docs/procurement-guide.md` Section 5: `SlicerROS2 cannot run in the Windows installer path.`), at about 40 GB of disk and a build the SlicerROS2 Getting Started page records as "a few hours" (procurement item 5, status `PENDING, depends on item 4`). The RoboStack decision removes WSL2 from every other task, so the module is the only remaining Linux cost and the decision is now about project goals rather than tooling. Document owner research opened 2026-11-04. Interim handling: gate G2.4 measures the wrench rate at the ROS 2 subscriber and that measurement point is the same under both variants (`docs/procurement-guide.md` Section 5 fallback note: `Gate G2.4 measures the wrench rate at the ROS 2 subscriber, so the gate's measurement point does not change under this fallback.`), so the gate text needs no change; task 2.4 output naming follows the selected variant; the SlicerROS2 row of `sim/SOUP.md` stays PENDING until the decision | Option A: none. Option B: the Subsystem / Module cell of row FR-MS-004 is renamed and the SlicerROS2 name leaves its method cell. The acceptance metric (VAL-022 fold, SRS v1.1.0) is unchanged under both |

Totals: 2 finding rows. VAL-026 carries 3 Verification Method & Toolchain cell replacements. VAL-027 carries 2 prepared variants (Option A: no text edits; Option B: 1 clause replacement and 1 row name cell replacement).

## 3. Prepared FR-MS-004 variants (VAL-027)

Option A, SlicerROS2 retained.

SRS text changes: none. The FR-MS-004 clause (line 42) and the Section 5 row name cell (line 94) stay as written.

Choose this variant when SlicerROS2 is a project-goal-level deliverable, for example when the product identity includes Slicer-integrated workflows or the SlicerROS2 ROS category is a promised operator interface. Costs and consequences:

* Procurement item 5 reopens: WSL2 Ubuntu 24.04, a 3D Slicer v5.12 source build (`docs/procurement-guide.md` Section 5, `Expected disk: about 40 GB for the Slicer source and build (estimate)`), and the WSLg display path for the Slicer GUI.
* Two Slicer pins exist from then on: the native Windows 5.12.4 package for FR-MS-001 segmentation and a v5.12 source tag in WSL2 for the SlicerROS2 build, as `sim/SOUP.md` already anticipates.
* The SlicerROS2 publisher runs in WSL2 while the ROS 2 subscribers run on Windows through the VAL-026 route. The procurement guide records the mirror variant (Slicer on Windows, ROS 2 in WSL2, joined over DDS through the WSL network) as unverified with the words `Do not use it without a separate test.`, and the same boundary applies here. A cross-boundary DDS round-trip test joins the gate G2.4 test configuration as a separate recorded case.

Option B, SlicerROS2 replaced by a ROS 2 bridge node.

The FR-MS-004 clause (line 42) becomes:

```markdown
* **FR-MS-004 (ROS 2 Middleware Bridge):** The system shall deploy a ROS 2 bridge node over **Fast DDS** to publish real-time Cartesian tool-tip positions, volumetric mesh deformation states, and calculated 6-axis haptic force feedback (wrench data) to **ROS2** nodes at high frequencies.
```

The Section 5 row name cell (line 94) becomes ``M&S / ROS 2 middleware bridge over Fast DDS (`sim/bridge/`)``. The VTM row FR-MS-004 Subsystem / Module cell follows under VTM owner scope. All other cells of the row stay as written.

Choose this variant when FR-MS-004 covers the bridge function and SlicerROS2 is one implementation choice among conforming ROS 2 publishers. Basis: `docs/procurement-guide.md` Section 5 fallback, ``Build a direct Fast DDS topic bridge as a plain ROS 2 node in the `sim/bridge/` path (or inside the task 2.8 master work) that publishes tool-tip pose, mesh deformation, and wrench topics.`` The amendment makes that fallback normative, so task 2.4 records no deviation when it builds the node. FR-MS-001 (line 39) is unchanged: DICOM ingestion and segmentation stay on the native Windows 3D Slicer 5.12.4 pin; only the ROS bridge changes. Procurement item 5 is marked dropped, and WSL2 leaves the plan entirely.

If the research concludes that neither variant serves the project goals, the third outcome is to restate FR-MS-004 at the goal level or drop the bridge requirement. That outcome needs its own finding and clause drafting and is not prepared here. If the 3D Slicer ecosystem itself leaves the project scope, FR-MS-001 and its VTM row change too, under a separate finding.

## 4. Revision-history row proposal

When the document owner applies the approved amendments, line 4 becomes:

```markdown
**Document Version:** 1.2.0 (ROS 2 provisioning pinned to RoboStack on Windows per VAL-026; FR-MS-004 SlicerROS2 clause open per VAL-027; Major and Minor findings remain open)
```

If the VAL-027 variant is selected before the application, the label clause reads `FR-MS-004 SlicerROS2 clause closed per VAL-027 (Option A)` or `FR-MS-004 SlicerROS2 clause closed per VAL-027 (Option B)` instead.

Add this row to the Section 6 table:

```markdown
| 1.2.0 | 2026-11-04 | Seth Nenninger | Pinned ROS 2 provisioning to ROS 2 Jazzy natively on Windows via pixi and the RoboStack robostack-jazzy conda channel with rmw_fastrtps_cpp (VAL-026), superseding the WSL2 Ubuntu 24.04 route of the procurement guide for tasks 2.4, 2.8, and 7.1; named the provisioning in the FR-MS-004, FR-MS-007, and NFR-PERF-002 Verification Method & Toolchain cells. Opened VAL-027 on the FR-MS-004 SlicerROS2 clause with prepared variants pending document-owner research. |
```

## 5. Follow-on record updates (not SRS text)

* `DEVELOPMENT_PLAN.md` Section 2, Robotics middleware row: the version constraint names ROS 2 Jazzy via the RoboStack `robostack-jazzy` channel with `rmw_fastrtps_cpp` and the matching Fast DDS package version from the resolved environment; the precondition column drops WSL2 and keeps SlicerROS2 pending under VAL-027.
* `docs/procurement-guide.md` Sections 4, 5, and 7 rows 4 and 5: item 4 changes from "WSL2 Ubuntu 24.04 and ROS 2 Jazzy" to the pixi plus RoboStack install with a pub/sub round-trip done-when check; item 5 stays PENDING under VAL-027 Option A or is marked dropped under Option B.
* `sim/SOUP.md`: the ROS 2 and Fast DDS rows move from "not selected" to the resolved pins (the `ros-jazzy` package versions, the `rmw_fastrtps_cpp` version, the Fast DDS version, Apache-2.0), and a RoboStack provenance row records the channel URL, the package list source, and the conda-forge-only channel policy from the RoboStack conda guide (``To avoid accidental violation of the Anaconda ToS, remove the `defaults` channel``).
* `vv/traceability/vtm.md`: method cells of rows FR-MS-004, FR-MS-005, FR-MS-007, and NFR-PERF-002 carry the VAL-026 parenthetical (VTM owner scope).
* Verification environment record: ROS-side subscriber and bag tooling run under the conda environment at CPython 3.12; the OQ suites under `.venv-qual311` (Python 3.11.9) drive them and parse JSON captures in `SNDEV/logs/`, following the `sim/sofa/src/run_reference_scene.py` pattern. The gate G2.4 and G2.6 test configuration records name this split.
* Reproducibility rule (AGENTS.md section 6): the resolved environment lock (`pixi.lock` or a conda explicit spec) is committed alongside the SOUP row, so nothing floats.
* Finding register: `SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md` stays as written (overwrite policy); VAL-026 and VAL-027 live in this proposal and enter the open-questions table of `DEVELOPMENT_PLAN.md` Section 6 when the plan is updated.

## 6. Related items outside this proposal

* FR-MS-007 (line 45) names `the **FMI-LS-BUS** layered standard over Fast DDS`, and the published FMI-LS-BUS 1.0 defines no DDS transport (`docs/procurement-guide.md` Section 6, recorded 2026-10-14). The task 2.8 fallback is scheduled-variable co-simulation over the pinned ROS 2 and Fast DDS layer, which is the VAL-026 route. The clause replacement needs its own amendment row.
* The FR-MS-007 clause retains `to guarantee quantization-error-free synchronization across distributed edge nodes` (line 45) although the v1.1.0 metric fold (VAL-005) replaced the acceptance metric with 1 ms clock-skew and message-jitter bounds. The clause phrase is aligned in the same future amendment.
* The no-commercial-licenses decision of 2026-10-14 is unaffected: RoboStack, conda-forge, and Fast DDS are open source (Apache-2.0 for the ROS 2 packages and Fast DDS), and the conda-forge-only channel policy above keeps the environment clear of the Anaconda Terms of Service.

## 7. Approval checklist

Items the document owner confirms before SRS.md becomes v1.2.0:

* The VAL-026 amendment set is accepted as written: three Verification Method & Toolchain cell replacements at lines 94, 96, and 108, with one judgment call decided. The judgment call: name the full route (`ROS 2 Jazzy via RoboStack on Windows`) in the SRS cells as proposed, or shorten the cells to `ROS 2 Jazzy on Windows` and keep the RoboStack channel pin in `DEVELOPMENT_PLAN.md` Section 2 and `sim/SOUP.md` only.
* The RoboStack provisioning decision is accepted as the verification-environment record for tasks 2.4, 2.8, and 7.1: ROS 2 Jazzy native on Windows via pixi and `robostack-jazzy`, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, WSL2 no longer a precondition except under VAL-027 Option A.
* The VAL-027 variant selection is pending the document owner's SlicerROS2 research. Whichever variant is selected is applied from Section 3 with no further wording drafting. If the application of VAL-026 lands first, the version label keeps the `VAL-027 open` marker until the variant is applied.
* The follow-on record list in Section 5 is assigned before gate G2.4 or G2.6 is measured on the RoboStack environment, so the SOUP pin and the test configuration records exist when the first timing numbers are captured.

## 8. Status

Draft prepared 2026-11-04. VAL-026 is approved by the document owner (2026-11-04) and ready to apply. VAL-027 is open pending the document owner's research into the significance of SlicerROS2 to the project; its variants need a selection, not further drafting. SRS.md stays at v1.1.0 until the document owner applies the approved set. Implementation log: `SNDEV/docs/impl-2026-11-04-srs-v1.2-proposal.md`.
