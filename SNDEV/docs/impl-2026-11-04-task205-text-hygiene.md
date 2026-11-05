Title: Task 2.0.5 residual SlicerROS2 and FMI-LS-BUS text cleanup
Date: 2026-11-05T02:43:28Z
Author: Seth Nenninger (Builder_Int29 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.0.5
Summary: Removes live SlicerROS2, WSL2, and FMI-LS-BUS wording from the M&S README files and the SRTA_BUILD_BRIDGE option description, aligned to SRS v1.2.0 VAL-027 Option B and VAL-028.

## Task Reference

Plan task 2.0.5 in `DEVELOPMENT_PLAN.md` (Phase 2 record sync): clean residual SlicerROS2 and FMI-LS-BUS text in `README.md`, `sim/README.md`, `sim/bridge/README.md`, `sim/fmi/README.md`, and the `SRTA_BUILD_BRIDGE` option description in `CMakeLists.txt`. Findings VAL-027 and VAL-028 in `DEVELOPMENT_PLAN.md` Section 6.3.

## Specification Summary

SRS.md v1.2.0 closes VAL-027 (Option B): the SlicerROS2 module is replaced by a native ROS 2 bridge node over Fast DDS in `sim/bridge/`, and WSL2 leaves the plan. SRS.md v1.2.0 closes VAL-028: FR-MS-007 is FMI 3.0 scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer with 1 ms clock-skew and message-jitter bounds, and FMI-LS-BUS is dropped because the published FMI-LS-BUS 1.0 defines no DDS transport.

Edit scope: `README.md`, `sim/README.md`, `sim/bridge/README.md`, `sim/fmi/README.md`, and `CMakeLists.txt` (option description string only). SNDEV logs, SRS.md, and the `docs/srs-*` change proposals are not edited.

## Implementation Notes

Files changed (5 in edit list, plus this log):

* `README.md` line 7: M&S tier list now reads "ROS 2 bridge node" in place of "SlicerROS2 bridge".
* `sim/README.md` line 10: `bridge/` entry now reads "ROS 2 bridge node over Fast DDS (SRS FR-MS-004)".
* `sim/bridge/README.md`: title changed to "ROS 2 Bridge Node (Fast DDS)". The body now describes a native ROS 2 bridge node on the pinned RoboStack Jazzy environment with `rmw_fastrtps_cpp`, and states that no SlicerROS2 module or WSL2 build is used (VAL-027 Option B). The file had no other live SlicerROS2 or WSL2 instructions, so no historical note was kept.
* `sim/fmi/README.md` line 5: FMI-LS-BUS replaced by scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer (VAL-028), with the 1 ms clock-skew and message-jitter bounds stated. The file had no `quantization` reference.
* `CMakeLists.txt` line 11: description string changed to "Build the ROS 2 / Fast DDS bridge stubs". The option name, default (OFF), and all other lines are unchanged.

Verification:

* Grep for `SlicerROS2|WSL2|FMI-LS-BUS|quantization` (case-insensitive) over the five edit-list files after the edits: PASS for `README.md`, `CMakeLists.txt`, `sim/README.md`, and `sim/fmi/README.md` (no hits). `sim/bridge/README.md` has one hit, the intentional negative statement that the SlicerROS2 module and WSL2 build are not used.
* Style check on the edited text: no em dashes, no emojis, straight quotes only.
* Quality gates (build, lint, tests): not applicable to documentation and one option description string. CMake was not re-configured. The option name and default are unchanged, so no build behavior changes.
* No commit made.

Live references outside the edit list (reported, not edited):

* `sim/bridge/CMakeLists.txt` line 1: `# Placeholder for the SlicerROS2 / Fast DDS bridge (FR-MS-004).` This comment needs the same wording change. The file is not in the task 2.0.5 edit list.
* `sim/SOUP.md` lines 17 to 24: SlicerROS2, WSL2, and FMI-LS-BUS rows. Owned by task 2.0.3.
* `vv/traceability/vtm.md` lines 12 and 15: FR-MS-004 name cell and FR-MS-007 class cell. Owned by task 2.0.4.
* `docs/procurement-guide.md`: WSL2 route and SlicerROS2 sections. Owned by task 2.0.2 (superseded or marked dropped there).
* Historical and resolution records, left as-is by rule: `SRS.md`, `DEVELOPMENT_PLAN.md` resolution rows (VAL-027, VAL-028, Section 2 dropped-item notes), `docs/srs-v1.1-change-proposal.md`, `docs/srs-v1.2-change-proposal.md`, and the `SNDEV/docs` logs.
