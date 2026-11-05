Title: VAL-031 G2.1 acceptance-metric restatement
Date: 2026-11-05T23:52:05Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: VAL-031
Summary: Drafts and applies the per-structure G2.1 acceptance-metric restatement decided by the document owner on 2026-11-05 to the VTM row FR-MS-001 and plan gate G2.1, with no SRS.md text change.

## Task Reference

VAL-031 (document owner decision, 2026-11-05). Proposal: `docs/val-031-g21-metric-proposal.md`. Records changed: `vv/traceability/vtm.md` row FR-MS-001, and `DEVELOPMENT_PLAN.md` gate G2.1, task 2.1, Phase 2 status, and Sections 6.2 and 6.3.

## Specification Summary

The document owner decided on 2026-11-05 that the G2.1 metric is per structure, with a recall-weighted vascular clause. The tumor clause is operator-seeded with lesion detection excluded. The parenchyma floor stays at 0.90, and slice-5 method work is funded. The owner authorized drafting and application. Requested work:

* Draft the proposal in the format of `docs/srs-v1.4-change-proposal.md`, with a finding register, the clause text, rationale, margin notes on the adjustable markers, follow-on record updates, an approval checklist, a status section, and an evidence appendix.
* Replace the VTM row FR-MS-001 metric cell with the clause text, and note VAL-031 provenance in that row.
* Replace the plan gate G2.1 acceptance metric and status cells, append to the task 2.1 estimate cell and the Phase 2 status paragraph, and add VAL-031 rows to Sections 6.2 and 6.3.
* Edit no SRS.md text, and do not touch `sim/`, `env/`, or the `SNDEV/docs/impl-2026-11-05-task21-*` logs. Commit in two path-scoped commits and do not push.

## Implementation Notes

Files changed:

* `docs/val-031-g21-metric-proposal.md` (new): the proposal. Commit A.
* `SNDEV/docs/impl-2026-11-05-val031-metric-restate.md` (new): this log. Commit A.
* `vv/traceability/vtm.md`: row FR-MS-001, metric cell only. Commit B.
* `DEVELOPMENT_PLAN.md`: gate G2.1 acceptance metric and status cells, task 2.1 estimate cell, one sentence in the Phase 2 status paragraph, one VAL-031 row in Section 6.2, and one VAL-031 row in Section 6.3. Commit B.

Not changed: `SRS.md`. The acceptance metric is VTM-resident per SRS Section 5 (line 89 names `vv/traceability/vtm.md` as the authoritative matrix and the Section 5 table as a non-authoritative extract). Also not changed: `sim/`, `env/`, and the `SNDEV/docs/impl-2026-11-05-task21-*` logs.

Clause handling: the clause text is verbatim in the VTM cell. The plan gate replaces each bracketed marker with "(adjustable)", as the plan style requires.

Measurements: none rerun in this change set. All measured values are copied from `SNDEV/docs/impl-2026-11-05-task21-slice4-method.md`. Values derived from the reported Dice and volumes (intersection, false positive and false negative volumes, and the volume reduction needed to reach 0.90) are labeled as derived in the proposal.

Evidence links:

* Slice-4 log: `SNDEV/docs/impl-2026-11-05-task21-slice4-method.md`
* Phase quantification: `SNDEV/logs/probe9b-phase-hu-2026-11-05.json`
* Final pipeline run: `SNDEV/logs/segment-run-tcia-hcc-tace-seg-hcc001-20261105T184041Z.log`
* Final evaluation: `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261105T184142Z.log`
* Variant V1 scored run: `SNDEV/logs/segment-run-tcia-hcc-tace-seg-hcc001-20261105T182720Z.log` and `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261105T182838Z.log`

## Verification

* Style scan of the added lines in `vv/traceability/vtm.md` and `DEVELOPMENT_PLAN.md`, and of both new files: PASS. No banned word from AGENTS.md Section 1, no em dash, en dash, or curly quote.
* Scope: `git status --short` shows four paths (two modified, two new). `git diff --stat` for the tracked files reports 6 insertions and 4 deletions. `SRS.md`, `sim/`, `env/`, and the `SNDEV/docs/impl-2026-11-05-task21-*` logs are unchanged: PASS.
* VTM: row FR-MS-001 is the only row with changed text. The metric cell carries the Section 3 clause verbatim: PASS.
* Plan: gate G2.1 metric and status cells, task 2.1 estimate cell, Phase 2 status paragraph (one appended sentence), and the Section 6.2 and 6.3 VAL-031 rows: PASS by diff review.
* Line endings: git warns that LF will be replaced by CRLF for the two tracked files. The diff is limited to the changed lines, so no whole-file rewrite occurred. Recorded as a working-copy condition, not a gate failure.
* Holdout: no script was run and no reference label was read in this change set: PASS.
* Measurement gate: not run. The gate G2.1 stays OPEN, and its verdict is the slice-4 reading against the restated clauses.

Discrepancy recorded: the previous gate G2.1 status cell listed a slice-2 vascular Dice of 0.0449. The owner's evidence and the slice-4 V0 row give 0.0543 for the same chain. The proposal uses 0.0543. The old cell text is replaced in this change set, so the 0.0449 reading is no longer in the plan. The source of 0.0449 is not traced in this change set.

Result: PASS for all checks above. FAIL: none.
