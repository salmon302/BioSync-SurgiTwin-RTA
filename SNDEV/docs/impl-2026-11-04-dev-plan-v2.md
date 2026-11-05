Title: Re-baseline DEVELOPMENT_PLAN.md to SRS v1.2.0
Date: 2026-11-05T02:22:23Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc (2026-11-04 development shift to SRS v1.2.0)
Summary: DEVELOPMENT_PLAN.md raised to version 2.0 against SRS.md v1.2.0, with VAL-026, VAL-027 (Option B), and VAL-028 folded into the stack table, Phase 2 tasks and gates, and a new record-sync task 2.0.

## 1. Task Reference

Direct user instruction of 2026-11-04: coordinate a development plan against the provided SRS 1.2.0, with minimal code and planning as the goal. SRS.md v1.2.0 is applied in the working tree (uncommitted) and closes VAL-026, VAL-027 (Option B), and VAL-028. Source records: `docs/srs-v1.2-change-proposal.md` and `SNDEV/docs/impl-2026-11-04-srs-v1.2-proposal.md`.

## 2. Specification Summary

The plan revision re-baselines `DEVELOPMENT_PLAN.md` from SRS v1.0.0 to SRS v1.2.0 and refreshes Phase 2 status to the current repository state. Scope items:

- ROS 2 provisioning pinned to ROS 2 Jazzy natively on Windows via pixi and the RoboStack `robostack-jazzy` conda channel with `rmw_fastrtps_cpp` (VAL-026). The WSL2 Ubuntu 24.04 route is removed as a precondition from tasks 2.4, 2.8, and 7.1.
- SlicerROS2 replaced by a native ROS 2 bridge node in `sim/bridge/` (VAL-027 Option B). Procurement item 5 is marked dropped and one Slicer pin remains (5.12.4 native, FR-MS-001).
- FR-MS-007 restated as FMI 3.0 scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer with 1 ms clock-skew and message-jitter bounds (VAL-028). FMI-LS-BUS leaves the plan and the `quantization-error-free` phrase is gone.
- Phase 2 status refreshed to task 2.2 slice 1 (commit `3beb6f0`) with the slice-1 step-timing captures and their open budget finding.
- New Phase 2 task 2.0 (1.5 d) carries the SRS v1.2.0 record sync named in the change proposal Section 5 follow-on list.

Out of scope by instruction: code changes. Task 2.0 is planned, not executed. No file outside `DEVELOPMENT_PLAN.md` and this log was touched.

## 3. Implementation Notes

Files changed:

- `DEVELOPMENT_PLAN.md` (version 2.0 header and status; Section 2 stack rows for SOFA, 3D Slicer, the ROS 2 bridge, ROS 2 Jazzy / Fast DDS, FMI 3.0, and the interpreter split; Section 3.1 tier mapping, Section 3.2 topology, and two new Section 3.3 design decisions; Phase 2 goal, status, estimate 43.0 d to 44.5 d, tasks 2.0.1 to 2.0.5 added, tasks 2.4 and 2.8 rewritten, gate rows G2.2, G2.4, and G2.6 updated; Phase 7 task 7.1 note; Section 6.3 findings-resolved table for VAL-026, VAL-027, and VAL-028; VAL-005 row note; Section 7.1 risk rows for the live SOFA timing signal, the bounded FMI sync risk, and the new RoboStack drift risk).
- `SNDEV/docs/impl-2026-11-04-dev-plan-v2.md` (this log).

Verification steps and evidence:

- Two read-only subagent audits grounded the revision. The Phase 2 audit reported per-task status with commit and log evidence (`ses_e567ffd83ffe8OqxmJVgRaLNaQ`); the provisioning and traceability audit quoted the superseded procurement, SOUP, and VTM text with file and line references (`ses_e567ffd83ffdQsanxIHOJAIzjH`).
- Grep over `DEVELOPMENT_PLAN.md` for `SlicerROS2|WSL2|FMI-LS-BUS|quantization` after the edits returns 18 matches, all in resolution records, dropped-item notes, the historical VAL-005 row, or the unrelated TFLM quantization wording. No live task or gate names SlicerROS2, WSL2, or FMI-LS-BUS as a requirement.
- Day-sum arithmetic in the Phase 2 estimate recomputed: done rows 2.0 + 4.0 = 6.0 d; open rows 1.5 + 5.0 + 8.0 + 6.0 + 4.0 + 6.0 + 8.0 = 38.5 d; total 44.5 d.
- Gate status PASS or FAIL is recorded only where evidence exists. G2.2 stays OPEN with the slice-1 captures cited (max 23.910 ms on the 2000-step run, 7 of 2000 steps over the 16.7 ms budget).

Open items carried into the plan:

- Task 2.0.1 to 2.0.5 (record sync, 1.5 d) await approval and dispatch. They cover the SRS v1.2.0 baseline commit, `docs/procurement-guide.md`, `sim/SOUP.md` with the lockfile, `vv/traceability/vtm.md` cells, and the residual SlicerROS2 and FMI-LS-BUS text in the README and CMake files.
- Task 2.2 slice 2 holds the 30-minute G2.2 load case, re-measurement on the G2.1 meshes, and the max versus p95 gate-wording decision.
- The RoboStack environment resolution (task 2.0.3) is a prerequisite for tasks 2.4, 2.8, and 7.1 and for gate G2.4 and G2.6 measurements.

## 4. Addendum (task 2.0 dispatch)

Execution of task 2.0 was approved by the user on 2026-11-04 and dispatched as parallel work packages. Status at this commit: 2.0.1 (this commit sequence), 2.0.2 (procurement sync), 2.0.4 (VTM sync), and 2.0.5 (text hygiene) are done; 2.0.3 (ROS 2 environment resolution) is in progress in a separate work package. Correction records are in `SNDEV/docs/impl-2026-11-04-task201-baseline-commit.md`.
