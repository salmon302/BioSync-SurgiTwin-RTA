Title: VAL-029 application to SRS v1.3.0
Date: 2026-11-05T16:10:14Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: VAL-029 application, SRS v1.3.0
Summary: Applies the approved FR-MS-002 p95 plus outlier-budget acceptance metric from docs/srs-v1.3-change-proposal.md to SRS.md, the VTM row, and the DEVELOPMENT_PLAN.md gate G2.2 and task 2.2 records.

## Task Reference

Document owner decision of 2026-11-05 adopting the p95 plus outlier-budget criterion for FR-MS-002, as recorded in `docs/srs-v1.3-change-proposal.md` (commit `a11a58b`) and `SNDEV/docs/impl-2026-11-05-val029-proposal.md`. Application follows the v1.1 precedent (`docs(srs): apply approved v1.1 amendment set (VAL-001 to VAL-004)`).

## Specification Summary

Replace the FR-MS-002 Target Acceptance Metric with the approved clause:

Solver step time stays within the 16.7 ms frame budget of 60 FPS on the pinned reference scene as follows: at most 16.7 ms at p95 across a 30-minute load case, at most 0.1 percent of steps above 16.7 ms in the load case with the maximum step time recorded, and no divergence (defined as non-finite output or a monotonically growing strain-energy norm over successive steps) in the load case.

Record the change as SRS v1.3.0 in the document version line and the Section 6 revision history. Update the VTM row FR-MS-002 metric cell (`vv/traceability/vtm.md`), and move VAL-029 from the open Major Findings table (DEVELOPMENT_PLAN.md Section 6.2) to the resolved table (Section 6.3). Update gate G2.2 and task 2.2 in `DEVELOPMENT_PLAN.md`.

The FR-MS-002 clause in Section 3.1 and all other Section 5 rows are unchanged.

## Implementation Notes

Files changed (exactly these, path-scoped commit):

* `SRS.md`: line 4 Document Version set to 1.3.0 with the VAL-029 label. Section 5 FR-MS-002 Target Acceptance Metric cell replaced with the approved clause text. Section 6 revision row 1.3.0 added. No other cell changed.
* `vv/traceability/vtm.md`: row FR-MS-002 acceptance metric cell set to the approved clause text. The existing provenance marker is kept and extended with "restated in SRS v1.3.0 per VAL-029". The VTM has no separate provenance column, so the marker sits in the metric cell. No other row changed.
* `DEVELOPMENT_PLAN.md`: gate G2.2 Acceptance Metric marker changed to "(VAL-029, applied in SRS v1.3.0)". Gate G2.2 Status cell extended with the application and gate result sentences. Task 2.2 Est. parenthetical replaced. VAL-029 row removed from Section 6.2 and added to Section 6.3.
* `SNDEV/docs/impl-2026-11-05-val029-apply.md`: this log.

Not changed, per scope: `sim/`, `env/`, `docs/`, and `vv/tests/`. The OQ test rework is already in commit `fb1e025`.

Verification steps:

* Clause text compared against `docs/srs-v1.3-change-proposal.md` Section 3. The SRS, VTM, and plan cells contain the same string.
* The v1.3.0 version line and revision row match the proposal Sections 5 text.
* Grep for `proposed, VAL-029 pending application` and for the v1.2.0 FR-MS-002 wording returned no matches in the three target files after the edits.
* Staged files checked with `git diff --cached --name-only` before commit (see the commit record below).

Open items noted at application, not changed:

* DEVELOPMENT_PLAN.md gate G2.2 Status cell still begins with "OPEN." The instructed sentence states "PASS with recorded boundaries". The owner should decide whether the leading status word is updated.
* DEVELOPMENT_PLAN.md Section 6.3 heading and column header still read "Resolved by SRS v1.2.0" and "Resolution in SRS v1.2.0". The VAL-029 row reads "Resolved by SRS v1.3.0".
* DEVELOPMENT_PLAN.md header lines 5 and 6 still read "Derived From: SRS.md v1.2.0" and the v1.2.0 status text. These lines were outside the approved edit list.
* The 0.1 percent cap is kept at the owner value (no adjustment at application). The margin is 33 steps.
