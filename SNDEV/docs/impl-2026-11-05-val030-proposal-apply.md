Title: VAL-030 proposal draft and application (FR-MS-001 reference set)
Date: 2026-11-05T16:24:27Z
Author: Seth Nenninger (Builder_Int34 Agent)
Contribution Type: Implementation
Ticket/Context: VAL-030, draft and apply
Summary: Drafts the SRS v1.4 proposal that restates the FR-MS-001 example as the TCIA HCC-TACE-Seg set (HCC_001) per the 2026-11-05 owner decision, then applies it to SRS.md, the VTM row, and the development plan.

## Task Reference

* VAL-030: FR-MS-001 reference dataset. Owner decision of 2026-11-05: the TCIA HCC-TACE-Seg set (patient HCC_001) becomes the G2.1 reference DICOM set, and the FR-MS-001 example clause names that set in place of Kitware TAIR. The owner's selection included application.
* Plan gate G2.1 and task 2.1 in `DEVELOPMENT_PLAN.md`.
* Prior record: `SNDEV/docs/impl-2026-11-05-task21-slice1-segmentation.md` (TAIR search trail and the open dataset decision, items 1 to 7 and the decision section).

## Specification Summary

1. Draft `docs/srs-v1.4-change-proposal.md` in the v1.3 proposal format, with the owner decision, the VAL-030 finding row, the rationale, the 1.4.0 revision row, follow-on record updates, an approval checklist, and a status section.
2. Apply to `SRS.md`: replace the example phrase `such as **Kitware TAIR**` in the FR-MS-001 bullet (Section 3.1, line 39), set the Document Version line to 1.4.0, and add the 1.4.0 row to the Section 6 revision history.
3. Apply to `vv/traceability/vtm.md` row FR-MS-001: name the HCC_001 series and the held-out expert SEG labels, and note VAL-030 and SRS v1.4.0.
4. Apply to `DEVELOPMENT_PLAN.md`: header version 2.2 (draft), the status sentence for SRS v1.4.0, the G2.1 acceptance metric cell, the task 2.1 estimate cell, and a VAL-030 row in Section 6.3.
5. Two path-scoped commits with the sign-off, no push.

Out of scope: `sim/`, `env/`, and `SNDEV/docs/impl-2026-11-05-task24-*` (a builder is active there). The working tree also holds uncommitted `sim/bridge/` edits and the task 24 log from that builder. None of them are staged in this change set.

## Implementation Notes

Commit A (drafting): `docs/srs-v1.4-change-proposal.md` (new) and this log (new). No SRS, VTM, or plan text changed in this commit.

Pre-draft checks, run on 2026-11-05 against the working tree:

* `SRS.md` Section 5 extract: a search for `FR-MS-001` matched only line 39 in `SRS.md`, so the extract has no FR-MS-001 row. No Section 5 cell changes. Result: PASS (the brief expected this).
* `SRS.md` line 4 already reads `1.3.0`. The v1.4.0 line replaces it at application. Result: noted (the brief assumed 1.3.0 as the current version, which matches).
* `vv/traceability/vtm.md` row FR-MS-001 is at line 9. Its Acceptance Metric cell says `reference DICOM set` and names no dataset. Result: confirmed for the edit.
* `DEVELOPMENT_PLAN.md`: header version at line 3, status sentence at line 6, task 2.1 at line 207, gate G2.1 at line 220, Section 6.3 table at lines 485 to 490.
* Fact check of the dataset claims against the task 2.1 log: TAIR is NIfTI CTA and MRA with no organ or tumor labels, 70 GB, CC BY 4.0, anatomical models not released (log items 4 and 5). HCC_001 is DICOM CT with SEG objects, CC BY 4.0, and the CT zip (17,780,801 bytes) and SEG zip (36,327 bytes) carry the checksums recorded in the log. Result: PASS.
* The TAIR page metadata lists "Created" and "Last update" as November 13, 2026, after the retrieval date. Recorded as an unverified metadata note in the proposal (Section 4). Result: recorded.

Commit A verification (docs only, no code gates apply): banned-word and dash scan on the two new files, run with the AGENTS.md word list, the em and en dashes, and curly quotes. Result: PASS, no matches.

Application (commit B, after commit A `51608bc`):

* `SRS.md` line 39, Section 3.1 FR-MS-001: the example phrase `such as **Kitware TAIR**` is replaced with `such as the **TCIA HCC-TACE-Seg** set (patient HCC_001, expert liver, tumor, and vessel reference labels)`. Every other word of the bullet is unchanged, and the bullet keeps its list marker and bold formatting. Result: PASS (the diff shows that phrase only).
* `SRS.md` line 4: Document Version is `1.4.0 (FR-MS-001 benchmark example restated per VAL-030 (TCIA HCC-TACE-Seg reference set); Major and Minor findings remain open)`. Result: PASS (grep).
* `SRS.md` Section 6: the 1.4.0 row is appended after the 1.3.0 row, with date 2026-11-05 and author Seth Nenninger. Result: PASS. The file has no newline at end of file, as before, so the new row also ends without one.
* `SRS.md` Section 5: no change. The extract has no FR-MS-001 row. Result: PASS.
* Kitware TAIR in `SRS.md` now appears only in the 1.2.0 history row (historical text, unchanged) and in the 1.4.0 row, which names it as the replaced example. Result: PASS.
* `vv/traceability/vtm.md` row FR-MS-001 (line 9): the Acceptance Metric cell names the expert SEG reference labels held out of pipeline inputs and the TCIA HCC-TACE-Seg HCC_001 series, and notes VAL-030 and SRS v1.4.0. The row's other cells and every other row are unchanged. Result: PASS (the diff shows one changed line).
* `DEVELOPMENT_PLAN.md` header: Version is `2.2 (draft)`. Result: PASS.
* `DEVELOPMENT_PLAN.md` Status line: the v1.4.0 sentence is inserted immediately before `No commercial licenses are used in development`. Result: PASS.
* `DEVELOPMENT_PLAN.md` gate G2.1 Acceptance Metric: `from the TCIA HCC-TACE-Seg HCC_001 series (VAL-030)` and `overlap with the expert SEG reference labels held out of pipeline inputs` replace the two named phrases, and nothing else in the cell changes. Result: PASS.
* `DEVELOPMENT_PLAN.md` task 2.1 Est. cell: the clause now reads `the VAL-030 provenance flag and label-holdout bookkeeping (VAL-030 applied in SRS v1.4.0)`. Result: PASS.
* `DEVELOPMENT_PLAN.md` Section 6.3: the VAL-030 row is added after the VAL-029 row, with the Resolution and Residual plan action text from the proposal. Result: PASS.

Not changed, recorded as open:

* `DEVELOPMENT_PLAN.md` gate G2.1 Status cell still reads `the reference dataset choice is open (VAL-030)`. The brief did not list this cell, so it is left as written and is rewritten when slice 2 records status.
* `sim/segmentation/README.md` line 54 still lists the TAIR dataset decision as open. It is outside this change set's file scope and is updated in slice 2.
* The task 2.1 slice-1 log is not edited (overwrite policy, AGENTS.md Section 6).

Verification summary:

* `git diff --check` on the three edited files reports trailing whitespace on `DEVELOPMENT_PLAN.md` line 3 only. That is the two-space markdown line break on the Version line, which the header lines already use. Result: PASS with that note.
* Style scan of the added lines in the diff (AGENTS.md word list, em and en dashes, curly quotes): no matches. Result: PASS. The scan covered added lines only, because the existing text in these files already contains terms such as "Dynamic SIL Testing".
* Build, lint, typecheck, and test gates: not applicable. No code or configuration changed, and no gate in `DEVELOPMENT_PLAN.md` covers these documents.

Scope and staging:

* Commit B is path-scoped to `SRS.md`, `vv/traceability/vtm.md`, `DEVELOPMENT_PLAN.md`, and this log. This log is in commit B so its final notes are recorded in the repository. That goes one file beyond the brief's commit B list, and it is noted here.
* The working tree holds uncommitted `sim/bridge/` edits and the task 24 log from the active builder. None are staged or changed by this work. `sim/` and `env/` were not touched.
* Nothing was pushed.
