# SRS v1.3 Change Proposal (SurgiTwin-RTA)

Proposal only. SRS.md stays at v1.2.0 until the document owner applies the amendment.

Target document: SRS.md v1.2.0. Every line number below refers to that version. The amended cell is the Section 5 Target Acceptance Metric cell of FR-MS-002 (line 93). The Section 3.1 FR-MS-002 clause (line 40) does not change.

Decision record: the document owner decided on 2026-11-05 that the FR-MS-002 acceptance metric adopts a p95 plus outlier-budget criterion instead of the every-step (max) reading.

Findings: VAL-029 is new with this proposal. The baseline register (VAL-001 through VAL-025) is `SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md` and is unchanged. VAL-026 through VAL-028 closed in SRS v1.2.0.

Evidence (accessed 2026-11-05): the 30-minute G2.2 load case log `SNDEV/docs/impl-2026-11-05-g22-30min-load-case.md` and its capture `SNDEV/logs/sofa-2026-11-05-g22-30min-160000steps.json`.

Prepared: 2026-11-05.

Conventions used in the tables:

* Current text strings are quoted exactly from SRS.md v1.2.0 and shortened to the relevant cell.
* SRS Section 5 holds six columns: Requirement ID, Subsystem / Module, Regulatory / Standard Mapping, CSA Risk Classification, Verification Method & Toolchain, and Target Acceptance Metric. This proposal changes the Target Acceptance Metric cell of one row. It changes no other cell.

## 1. Scope and decision status

Decided on 2026-11-05: the FR-MS-002 acceptance metric is restated from an every-step (max) budget reading to a p95 plus outlier-budget reading. The clause text, the divergence definition, the 16.7 ms frame budget, and the 30-minute load case stay as they are. The outlier cap of 0.1 percent is the owner decision of 2026-11-05 and may be adjusted at application (Section 4, margin note).

Out of scope: the FR-MS-002 Verification Method & Toolchain cell and the VTM method cell. The OQ test rework is a follow-on record update (Section 6), not SRS text.

## 2. Finding register

| Finding ID | SRS location (section and line) | Current text (quoted from SRS.md v1.2.0) | Proposed replacement text | Rationale | Impact on the VTM |
| :--- | :--- | :--- | :--- | :--- | :--- |
| VAL-029 | Section 5, FR-MS-002 row, Target Acceptance Metric cell, line 93 | `Solver step completes within the 16.7 ms frame budget of 60 FPS on the pinned reference scene, and no divergence (defined as non-finite output or a monotonically growing strain-energy norm over successive steps) occurs in a 30-minute load case` | The Section 3 text, which replaces the whole cell | The every-step (max) reading fails on the 2026-11-05 load case (max 41.520 ms) while p95 passes (12.430 ms). The max is set by host scheduling stalls, not by solver cost. Section 4 gives the measured numbers and the reasoning. | The VTM row FR-MS-002 metric cell (`vv/traceability/vtm.md` line 10) follows under VTM owner scope at application. No other VTM row changes. |

Totals: 1 finding row. VAL-029 carries 1 Target Acceptance Metric cell replacement. No clause text, no other Section 5 cell, and no other row changes.

## 3. Proposed replacement metric text (VAL-029)

The replacement text for the FR-MS-002 Target Acceptance Metric cell (SRS.md line 93) is:

```text
Solver step time stays within the 16.7 ms frame budget of 60 FPS on the pinned reference scene as follows: at most 16.7 ms at p95 across a 30-minute load case, at most 0.1 percent of steps above 16.7 ms in the load case with the maximum step time recorded, and no divergence (defined as non-finite output or a monotonically growing strain-energy norm over successive steps) in the load case.
```

The three conditions are the p95 statistic, the outlier fraction with the maximum recorded, and the divergence check. The divergence definition is the one already in SRS v1.2.0.

## 4. Rationale

Measured values, from the 2026-11-05 run (160,000 steps, 30.9 min of measured stepping, pinned reference scene, 16.7 ms budget):

* Mean 11.604 ms, p95 12.430 ms, max 41.520 ms, min 10.830 ms.
* Over-budget steps: 127 of 160,000 (0.079 percent), spread across 72 of 160 blocks of 1,000 steps. The first five blocks have none.
* PCG solver iterations: 26 on every one of the 160,000 steps (min 26, max 26).
* Divergence: finite outputs, no monotonic growth over the second half of the run. Result PASS.

Why p95 plus an outlier budget. The every-step reading fails this run because one step reaches 41.520 ms and 127 steps exceed the budget. The p95 statistic reports the typical step cost across the 30-minute window, and p95 is 4.27 ms below budget. The outlier budget then bounds how often a slow step can occur.

Solver cost is stable. The PCG iteration count is 26 on every step, so the solver does the same numerical work on every step. Over-budget steps therefore come from outside the solver, and the evidence points to host scheduling stalls. The two worst steps (5320 at 41.52 ms and 5321 at 33.43 ms) are adjacent, which fits one stall event. The host is a non-real-time Windows host with other processes resident. The run did not record a scheduler trace, so the stall attribution is an inference from these facts and not a measured cause.

Consistency across the frame-budget chain. NFR-PERF-003 already requires the 60 FPS frame counter at p95 over a 10-minute run. Restating FR-MS-002 at p95 gives the solver step and the rendered frame the same statistic.

Safety-critical timing. The safety-critical timing requirement is carried by FR-RTA-002, which bounds the forward state inside the candidate RTA decision deadline derived from the Phase 3 WCET measurement. The simulation frame rate of FR-MS-002 is not the decision-loop deadline, so FR-MS-002 is not the basis for the safety timing claim.

Alternative considered and rejected: the strict max reading (every step within 16.7 ms). The measured run fails it. Removing the scheduling stalls would require controlling OS scheduling on the host, which is outside solver scope and is not a property a solver change can deliver. A max criterion on this host would fail on stalls that do not reflect solver behavior.

Margin note. The measured outlier rate is 0.079 percent against the 0.1 percent cap. At 160,000 steps the cap is 160 steps and the run has 127, so the run passes with 33 steps of headroom. The margin is thin. The gate records the over-budget count and the maximum step time on every run, so a drift toward the cap is visible in the record. The 0.1 percent value is the owner decision of 2026-11-05 and may be adjusted at application.

## 5. Revision-history row proposal

When the document owner applies the amendment, line 4 becomes:

```markdown
**Document Version:** 1.3.0 (FR-MS-002 acceptance metric restated per VAL-029 (p95 and outlier budget); Major and Minor findings remain open)
```

Add this row to the Section 6 table:

```markdown
| 1.3.0 | 2026-11-05 | Seth Nenninger | FR-MS-002 acceptance metric restated per VAL-029 (p95 and outlier budget): the Section 5 Target Acceptance Metric cell is replaced with a p95 bound, a 0.1 percent outlier budget with the maximum step time recorded, and the unchanged divergence check. Clause text and all other rows are unchanged. |
```

## 6. Follow-on record updates (not SRS text)

* `vv/traceability/vtm.md` row FR-MS-002 (line 10): the metric cell is set to the Section 3 text at application. This is VTM owner scope.
* `DEVELOPMENT_PLAN.md` gate G2.2 metric cell: done in the change that carries this proposal, marked `(proposed, VAL-029 pending application)`.
* `vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py`: the assertion changes from the current max-step check to the VAL-029 criterion (p95 at or below 16.7 ms, outlier fraction at or below 0.1 percent with the maximum recorded, and the divergence check). Tracked as a Phase 2 follow-up on task 2.2.
* The slice-1 and slice-2 captures in `SNDEV/logs/` remain historical evidence and are not changed.

## 7. Approval checklist

Items the document owner confirms before SRS.md becomes v1.3.0:

* The Section 3 metric text is accepted verbatim.
* The 0.1 percent outlier cap and the margin note in Section 4 are accepted, or the cap is adjusted at application and the margin note is updated to match.
* The OQ test rework is assigned as a Phase 2 follow-up on task 2.2.
* No other requirement row changes. NFR-PERF-003 already reads p95 at 60 FPS, so it needs no amendment.

## 8. Status

Draft prepared 2026-11-05. The amendment is ready for owner application. SRS.md stays at v1.2.0 until the document owner applies it. Implementation log: `SNDEV/docs/impl-2026-11-05-val029-proposal.md`.
