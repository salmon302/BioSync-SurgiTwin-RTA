Title: Procurement guide sync to SRS v1.2.0 (VAL-026, VAL-027, VAL-028)
Date: 2026-11-05T02:43:34Z
Author: Seth Nenninger (Builder_Int29 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.0.2
Summary: Marks the WSL2, SlicerROS2, and FMI-LS-BUS text of docs/procurement-guide.md as superseded or dropped under VAL-026, VAL-027 Option B, and VAL-028, without deleting history.

## Task Reference

Plan task 2.0.2 in `DEVELOPMENT_PLAN.md`. Inputs: `SRS.md` v1.2.0 (applied 2026-11-04), `docs/srs-v1.2-change-proposal.md`.

## Specification Summary

* VAL-026: ROS 2 Jazzy is provisioned natively on Windows through pixi and the `robostack-jazzy` conda channel (conda-forge only), with `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`. The WSL2 Ubuntu 24.04 route is superseded for tasks 2.4, 2.8, and 7.1 (the G2.6 three-node test included). Replacement work is plan task 2.0.3.
* VAL-027 Option B: the SlicerROS2 module is dropped. A native ROS 2 bridge node over Fast DDS in `sim/bridge/` is normative in task 2.4. Procurement item 5 is dropped. FR-MS-001 stays on native Windows 3D Slicer 5.12.4.
* VAL-028: FMI-LS-BUS is removed from the design. Scheduled-variable co-simulation over the pinned ROS 2 and Fast DDS layer, with 1 ms clock-skew and message-jitter bounds, is normative. The decision is closed.

## Implementation Notes

Files changed: `docs/procurement-guide.md` (only). This log file is new. No commit was made.

Sections touched in `docs/procurement-guide.md`:

* Host assumptions (line 20): WSL2 Section 4 marked superseded by VAL-026.
* Section 3 pin decision (lines 198 and 200): the WSL2 source build and the v5.12.0 bridge tag are marked superseded by VAL-027 Option B.
* Section 4 (ROS 2 Jazzy in WSL2): status banner SUPERSEDED by VAL-026; the unblock statement is restated as historical with tasks 2.4, 2.8, the G2.6 three-node test, and 7.1 moved to the RoboStack route. The steps are kept and marked not to be followed.
* Section 5 (SlicerROS2): status banner DROPPED by VAL-027 Option B; the Fast DDS bridge fallback is normative in task 2.4; the unblock statement is restated as historical. Analysis and WSL2 build steps are kept.
* Section 6 (FMI-LS-BUS availability and fallback): decision CLOSED by VAL-028 paragraph added above the findings; the fallback is normative.
* Section 7 (procurement sequence): dependency line rewritten (item 4 unblocks tasks 2.4 and 2.8; item 5 dropped); item 3 WSL2 pin clause removed; item 4 replaced with the RoboStack route, status IN PROGRESS under plan task 2.0.3, with the 2026-10-14 entry kept as superseded; item 5 marked DROPPED; item 6 Clears marks the FMI-LS-BUS fallback cleared by VAL-028.

Sections not edited: the historical decision prose in Sections 1, 2, and 6 that records the 2026-10-14 decisions, and the remaining board at the end of the file.

Live WSL2 or SlicerROS2 instructions outside the named sections: the Section 3 pin text (fixed above). No other live instruction was found by search of the file for WSL, SlicerROS2, and Ubuntu 24.04.

Verification: the edited file was reviewed by reading it back after each edit. No build or test gate applies to a documentation change. Style check: no em dashes, no emojis, straight quotes only in the new prose.

Result: PASS for the documentation edits. Open item for plan task 2.0.3: the RoboStack lockfile and the pub/sub round trip over Fast DDS are not yet produced.
