Title: VAL-032 final vascular values and Phase 2 record consolidation
Date: 2026-11-06T11:56:00Z
Author: Seth Nenninger (Builder_Int29 Agent)
Contribution Type: Implementation
Ticket/Context: VAL-032 final values and Phase 2 record consolidation
Summary: Applies the 2026-11-05 owner ruling (0.47 gate plus 0.95 data-side aspiration) to the G2.1 record and consolidates the Phase 2 slice closures of tasks 2.4, 2.7, and 2.8 in the plan.

## Task Reference

Owner ruling of 2026-11-05 ("0.47 gate + aspiration"), quoted in `docs/val-032-g21-metric-recenter.md` (addendum, final values). Phase 2 consolidation request from the parent session: plan tasks 2.4, 2.7, and 2.8 in `DEVELOPMENT_PLAN.md` Section 4 and gate G2.1 in the verification gates table.

## Specification Summary

Part 1, VAL-032 final values:

* `docs/val-032-g21-metric-recenter.md`: append the addendum with the final values (gated recall at or above 0.47, measured 0.476216 at the 3.0 mm floor; volume at most 7.5 times, measured 7.2384 at 293.024 mL margin-inclusive; the 1.0 mm margin contributes 78.16 mL; the 0.95 aspiration is a data-side work item).
* `vv/traceability/vtm.md` row FR-MS-001: clause (b) carries the grounded values, and the provenance note is updated to the final values.
* `DEVELOPMENT_PLAN.md` gate G2.1: acceptance metric cell with "(adjustable)" parentheticals, status cell `PASS with recorded boundaries` with the boundary list.

Part 2, Phase 2 consolidation:

* Task 2.4 estimate cell: slice 3a at 93f436b.
* Task 2.7 estimate cell: slice 1 at 27f68bd.
* Task 2.8 estimate cell: slice 1 at 762954f, with the measured single-node skew and jitter numbers from `SNDEV/docs/impl-2026-11-05-task28-slice1-master.md`.
* Phase 2 status paragraph: one appended sentence on the three slice closures and the G2.1 close.
* Section 7.2: regulatory risk row for the MSVC Community license terms.
* Section 7.1: thin-branch residual risk row extended, and a data-side aspiration row added.

Part 3, commits: Commit A (VAL-032 final values, G2.1 cells, and this log) and Commit B (Phase 2 consolidation rows and risk rows). Path-scoped staging only, with the sign-off `Signed-off-by: Seth Nenninger <sethnenninger@gmail.com>`.

## Implementation Notes

Scope limits: `SRS.md`, `sim/`, `env/`, and `SNDEV/logs/` are not edited. No push.

Files changed (planned): `docs/val-032-g21-metric-recenter.md`, `vv/traceability/vtm.md`, `DEVELOPMENT_PLAN.md`, `SNDEV/docs/impl-2026-11-05-val032-final-consolidation.md`.

Verification steps: style check of the edited text (no em dashes, straight quotes, banned-word search), grep of the VTM row and the G2.1 cell for the final values, `git diff --cached --name-only` before each commit.

Evidence: `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261106T024206Z.log` (parenchyma and vascular values), `SNDEV/docs/impl-2026-11-05-task21-slice7-vessels.md` (Pareto), `SNDEV/docs/impl-2026-11-05-task28-slice1-master.md` (task 2.8 numbers).

Results:

* Diff scope: 2 lines changed in `DEVELOPMENT_PLAN.md` (G2.1 status cell and the G2.1 acceptance cell unchanged), 2 lines in `vv/traceability/vtm.md` (FR-MS-001 provenance note only, clause (b) kept with the `[adjustable]` markers), and the addendum appended to `docs/val-032-g21-metric-recenter.md`. PASS.
* Style scan of the added lines: no em dashes, no curly quotes, no banned words. PASS.
* Clause (b) in the VTM: the text already matches the grounded values (0.47, 3.0 mm, 7.5 times). The `[adjustable]` markers are kept, as the VAL-032 proposal Section 3 requires for the VTM.
* Plan Phase 2 consolidation rows (tasks 2.4, 2.7, 2.8), the Phase 2 status sentence, the Section 7.1 rows, and the Section 7.2 row are applied in commit B.
* Task 2.8 numbers inserted from `SNDEV/docs/impl-2026-11-05-task28-slice1-master.md`: the 1 ms bounds FAIL on that run (contended host). Recorded as FAIL in the task 2.8 cell.
