Title: VAL-029 FR-MS-002 acceptance-metric change proposal (SRS v1.3 draft)
Date: 2026-11-05T15:57:05Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: VAL-029 proposal drafting, gate G2.2 (task 2.2)
Summary: Drafts the SRS v1.3 change proposal restating the FR-MS-002 acceptance metric as a p95 plus outlier-budget criterion, per the document owner decision of 2026-11-05, and updates the gate G2.2 row, task 2.2 note, and Section 6.2 findings in DEVELOPMENT_PLAN.md.

## Task Reference

* Document owner decision of 2026-11-05: the FR-MS-002 acceptance metric adopts a p95 plus outlier-budget criterion instead of the every-step (max) reading.
* Evidence: `SNDEV/docs/impl-2026-11-05-g22-30min-load-case.md` and capture `SNDEV/logs/sofa-2026-11-05-g22-30min-160000steps.json` (gitignored), accessed 2026-11-05.
* Template: `docs/srs-v1.2-change-proposal.md`.
* Predecessor: `SNDEV/docs/impl-2026-11-05-g22-30min-load-case.md` (commit `9d438f6`).

## Specification Summary

* Draft `docs/srs-v1.3-change-proposal.md` against SRS.md v1.2.0. The proposal restates only the Section 5 Target Acceptance Metric cell of FR-MS-002 (SRS.md line 93). The Section 3.1 clause (line 40) does not change.
* Proposed metric text (verbatim): `Solver step time stays within the 16.7 ms frame budget of 60 FPS on the pinned reference scene as follows: at most 16.7 ms at p95 across a 30-minute load case, at most 0.1 percent of steps above 16.7 ms in the load case with the maximum step time recorded, and no divergence (defined as non-finite output or a monotonically growing strain-energy norm over successive steps) in the load case.`
* The 0.1 percent cap is the owner decision of 2026-11-05 and may be adjusted at application.
* Record the finding VAL-029 as new with this proposal. The baseline register `SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md` is unchanged.
* Update `DEVELOPMENT_PLAN.md` gate G2.2 metric and status cells, task 2.2 remaining-items note, and Section 6.2 findings table. Do not edit `SRS.md` or `vv/traceability/vtm.md`.
* Commit the three files with the sign-off line after verification.

## Implementation Notes

Files created or changed:

* `SNDEV/docs/impl-2026-11-05-val029-proposal.md` (this log, created before the proposal)
* `docs/srs-v1.3-change-proposal.md` (new proposal)
* `DEVELOPMENT_PLAN.md` (gate G2.2 row, task 2.2 row note, Section 6.2 findings table)

Not changed: `SRS.md`, `vv/traceability/vtm.md`, `vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py` (the OQ rework is a Phase 2 follow-up on task 2.2).

Measured values used in the proposal (from the 2026-11-05 load case): 160000 steps, mean 11.604 ms, p95 12.430 ms, max 41.520 ms, 127 of 160000 steps over 16.7 ms (0.079 percent), 72 of 160 blocks, PCG iterations constant at 26, divergence PASS.

Verification steps and results are recorded below after the quality checks run.

* Metric text check: the proposal and the log contain the verbatim replacement text, and the DEVELOPMENT_PLAN.md gate row carries the same text with the proposed marker appended. Result: PASS.
* Style check on the new proposal and this log (no em dashes, no en dashes, no curly quotes, banned word list). Result: PASS (no matches).
* Staged file check: `git diff --cached --name-only` is compared with the three-file list before the commit. Result: recorded in the commit step.
* Not checked by this log: the working tree holds unrelated uncommitted changes (`env/ros2-jazzy/`, `sim/segmentation/`, and two other `SNDEV/docs/` logs). They are not staged and not edited.
