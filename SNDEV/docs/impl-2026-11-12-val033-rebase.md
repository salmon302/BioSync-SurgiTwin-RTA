Title: VAL-033 rebase of the FR-MS-007 and G2.6 clock skew and jitter bounds, and the pipelined three-node master (plan task 2.8 slice 3)
Date: 2026-11-12T09:00:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: VAL-033 (owner ruling 2026-11-12); plan task 2.8 slice 3; middleware no-metrics-yet default (follow-up to commit 6cf0b4a)
Summary: Drafts and applies VAL-033, which rebases the FR-MS-007 and G2.6 clock skew and message jitter acceptance bounds at the schedule rate, implements the pipelined remote step on the three-node master with a stale-input test, reruns the quiet single-node reference and the ten-minute three-node run under the rebased clauses, and makes the middleware no-metrics-yet state explicit unavailability.

## Task Reference

Owner ruling of 2026-11-12: (1) VAL-033 rebases the FR-MS-007 and G2.6 clock skew and message jitter bounds at the schedule rate; (2) the gate claim runs on the three-node topology with pipelined remote steps. Evidence: `SNDEV/docs/impl-2026-11-11-task28-slice2-multirate.md` (attempt 1 and the quiet single-node reference). Plan task 2.8 in `DEVELOPMENT_PLAN.md`. Requirement FR-MS-007 in `SRS.md` v1.4.0 (to be v1.5.0). Gate G2.6 in `DEVELOPMENT_PLAN.md`.

## Specification Summary

Part 1 (VAL-033): draft `docs/val-033-g26-bounds-rebase.md` in the v1.4 proposal format; apply the clause to the FR-MS-007 acceptance metric in `SRS.md` (Section 5 cell; Section 6 revision row 1.5.0; Document Version line); apply it to the FR-MS-007 row of `vv/traceability/vtm.md`; apply it to gate G2.6 and to the task rows and VAL rows of `DEVELOPMENT_PLAN.md`.

Part 2 (slice 3): pipeline the mechanical remote step (request one tick ahead, read the output at the next step point), document the one-step stale state and the zero-order hold, add a stale-input test, keep the three-node topology and the harness, run the quiet single-node reference and the ten-minute three-node run, and report both against the rebased clauses.

Part 3: `middleware/engine/pulse.py` `_m` default: the no-metrics-yet state produces explicit `None` values instead of 0.0.

## Preflight

* Evidence read: `SNDEV/docs/impl-2026-11-11-task28-slice2-multirate.md` (quiet single-node reference, three-node attempt 1, the round-trip split). Format read: `docs/val-032-g21-metric-recenter.md` (v1.4 proposal shape).
* Target cells read before editing: SRS.md Section 5 FR-MS-007 row (one occurrence of the 1 ms clause), the Document Version line (1.4.0), the Section 6 revision table (last row 1.4.0); vtm.md FR-MS-007 metric cell (one occurrence); DEVELOPMENT_PLAN.md G2.6 row (line 225), task 2.8 row (line 214), the Section 6.2 table (VAL-032 last), the Section 6.3 table (VAL-032 last), and the Phase 2 status paragraph (line 194).

## Implementation Notes

Part 1, VAL-033 (Commit A):

* `docs/val-033-g26-bounds-rebase.md` drafted (v1.4 proposal format). Clause text as ruled by the owner, used verbatim in SRS.md, vtm.md, and the plan (checked: one occurrence each, identical string). The two numeric multipliers (2 ms at p99 for skew, 1.5 times the schedule tick at p99 for jitter) carry the "(adjustable)" marker in all three records and margin notes in the proposal.
* SRS.md: Section 5 FR-MS-007 Target Acceptance Metric cell replaced; Section 3.1 clause unchanged; Section 5 Verification Method cell unchanged (checked); Document Version line set to 1.5.0 with the owner's label; Section 6 revision row 1.5.0 (2026-11-12, Seth Nenninger) added above 1.4.0.
* vtm.md: FR-MS-007 metric cell replaced; the prior provenance "(folded into SRS v1.1.0 per VAL-005)" kept, with the VAL-033 provenance appended.
* DEVELOPMENT_PLAN.md: G2.6 acceptance metric replaced with the clause; G2.6 status cell records the slice-2 attempt 1 FAIL against the superseded 1 ms clause, with the slice-3 numbers pending; task 2.8 row gains the slice-2 record and the VAL-033 pointer; Section 6.2 row VAL-033 added (the 1 ms clause unreachable at 10 ms-class steps); Section 6.3 row VAL-033 added (resolved by the schedule-rate rebase; residual: the slice-3 run and the unmeasured multi-host case); the Phase 2 status paragraph gains one VAL-033 sentence.

Verification: the old 1 ms phrase is absent from SRS.md (count 0); the clause string occurs once in each of the three target files; the staged list is exactly the five Commit A paths. Style scan of the new and edited text: no banned word, no em dash. The scan flagged existing SRS.md lines (pre-existing text outside the edits) and a substring match on "physics" in the proposal (false positive, checked).

Commit A subject: `docs(srs,vv): draft and apply VAL-033 G2.6 bounds rebase at the schedule rate`.

Parts 2 and 3 are recorded below as they complete.
