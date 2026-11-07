Title: consolidation of the task 2.7 FMU slice records (slices 2 and 3)
Date: 2026-11-07T06:58:06Z
Author: Seth Nenninger (Builder_Int29 Agent)
Contribution Type: Implementation
Ticket/Context: task 2.7 slice-2 and slice-3 record consolidation
Summary: Records the mechanical SOFA FMU (f01be28) and the Pulse IPC-proxy FMU (3016551) in the plan: the task 2.7 row and the Phase 2 status paragraph in `DEVELOPMENT_PLAN.md`. No code or FMU is changed.

## Task Reference

Plan task 2.7 in `DEVELOPMENT_PLAN.md` (Phase 2 row "2.7 Package the thermal ablation, mechanical (SOFA), and physiology (Pulse) plant models as FMI 3.0 FMUs"). Slice records: `SNDEV/docs/impl-2026-11-07-task27-slice2-mechanical-fmu.md` (commit f01be28) and `SNDEV/docs/impl-2026-11-07-task27-slice3-pulse-fmu.md` (commit 3016551).

## Specification Summary

* Edit the task 2.7 row Est. cell to record slices 2 and 3, the cut-event restart contract boundary, and the remaining items.
* Append one sentence to the Phase 2 Status paragraph covering the two FMU slices, their key numbers, the disclosed check changes, and the Pulse determinism finding.
* Make no change to `SRS.md`, `vv/`, `sim/`, `middleware/`, `env/`, `SNDEV/logs/`, or `SNDEV/research/`.

## Implementation Notes

Files changed: `DEVELOPMENT_PLAN.md` (task 2.7 row, Est. cell; Phase 2 Status paragraph, one appended sentence) and this log.

Source facts used (from the two slice records):

* Slice 2 (f01be28): mechanical SOFA FMU, 46010 bytes. Five import checks pass (M1 to M5). M1 deviation 4.99e-7 m against 1e-6 m. M3 step mean 11.22 ms, p95 11.53 ms, max 25.12 ms with one step over the 16.7 ms budget. The SOFA runtime is a host dependency. Cut events are outside the FMU contract; a co-simulation-level restart contract is required for the task 2.8 master.
* Slice 3 (3016551): Pulse IPC-proxy FMU, 29763 bytes, 15 variables. Five P-cases pass (P1, P1b, P2, P3, P4). P4 DoStep mean 2.219 ms, p99 3.838 ms, zero steps over 10 ms. Check changes disclosed: the P1b SpO2 scaling defect was in the check and was fixed; the P1 engine-time rule was weakened to non-decreasing and at most one step behind; P2 excludes the wall-time output and compares NaN as a token. Determinism: P2 output-level reset is exact, while the serialized engine state differs between fresh engines in five fields. `arterial_o2_partial_pressure` is NaN in every REL_4_3_2 step.

Verification steps:

* Read both slice records and the current plan rows before editing.
* After the edits, check with `git diff` that only the two named files changed, and that the Est. cell and status sentence contain the figures above.
* Commit path-scoped with exactly `DEVELOPMENT_PLAN.md` and this log. Verify the staged set with `git diff --cached --name-only` before committing.

Status of the verification gate: documentation-only change, no build or test gate applies. The FMU check results are as recorded in the two slice records and their `SNDEV/logs/` captures; this log does not re-run them.
