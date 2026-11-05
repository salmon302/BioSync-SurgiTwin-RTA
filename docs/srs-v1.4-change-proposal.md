# SRS v1.4 Change Proposal (SurgiTwin-RTA)

Proposal and application record for VAL-030. Target document: SRS.md v1.3.0. Every line number below refers to that version. The amended clause is the Section 3.1 FR-MS-001 bullet (line 39). The Document Version line (line 4) and the Section 6 revision history change too.

Decision record: the document owner decided on 2026-11-05 that the TCIA HCC-TACE-Seg set (patient HCC_001) becomes the G2.1 reference DICOM set, and that the FR-MS-001 example clause names that set in place of the Kitware TAIR example. The owner's selection included application, so this proposal is applied in the same change set (Section 8).

Findings: VAL-030 is registered here. The plan already refers to it (gate G2.1 and task 2.1). The baseline register (VAL-001 through VAL-025) is unchanged.

Prepared: 2026-11-05.

Conventions used in the tables:

* Current text strings are quoted exactly from SRS.md v1.3.0. Clause quotes omit the leading list marker.
* This proposal changes the example phrase inside one Section 3.1 bullet. It changes no Section 5 cell, because the Section 5 extract has no FR-MS-001 row.

## 1. Scope and decision status

Decided on 2026-11-05: the FR-MS-001 example in Section 3.1 names the TCIA HCC-TACE-Seg set (patient HCC_001) in place of Kitware TAIR. The clause structure, the "such as" framing, the 3D Slicer ingestion method, and the mesh targets stay as they are.

Out of scope: the Section 5 table. SRS.md has no FR-MS-001 row in its Section 5 extract, and the VTM row FR-MS-001 is updated under VTM scope (Section 6). The Kitware TAIR release is not removed from the project record. It is recorded as evaluated and out of scope for this clause.

## 2. Finding register

| Finding ID | SRS location (section and line) | Current text (quoted from SRS.md v1.3.0) | Proposed replacement text | Rationale | Impact on the VTM |
| :--- | :--- | :--- | :--- | :--- | :--- |
| VAL-030 | Section 3.1, FR-MS-001 bullet, line 39 | `**FR-MS-001 (Anatomical Ingestion):** The system shall ingest patient-specific volumetric medical imaging (CT/MRI DICOM data, including open-access benchmark datasets such as **Kitware TAIR**) via the native Windows **3D Slicer** ecosystem to generate segmented 3D meshes of target parenchymal organs (liver/breast), tumors, and critical vascular keep-out zones.` | The Section 3 clause, which replaces the whole bullet. The only changed words are the example phrase `such as **Kitware TAIR**`, which becomes `such as the **TCIA HCC-TACE-Seg** set (patient HCC_001, expert liver, tumor, and vessel reference labels)`. | The Kitware TAIR release is NIfTI cerebrovascular CTA and MRA with no parenchymal organ or tumor labels, so it cannot support the G2.1 Dice metric. The TCIA HCC-TACE-Seg HCC_001 set is DICOM CT with expert liver, tumor, and vessel SEG reference objects. Section 4 gives the facts. | VTM row FR-MS-001 (`vv/traceability/vtm.md` line 9) names the HCC_001 series and the held-out labels, applied under VTM owner scope in the same change set. No other VTM row changes. |

Totals: 1 finding row. VAL-030 replaces one example phrase in one Section 3.1 bullet. The change also sets the Document Version label and adds one revision row. No Section 5 cell and no other clause changes.

## 3. Proposed replacement clause (VAL-030)

The replacement text for SRS.md line 39 is:

```text
* **FR-MS-001 (Anatomical Ingestion):** The system shall ingest patient-specific volumetric medical imaging (CT/MRI DICOM data, including open-access benchmark datasets such as the **TCIA HCC-TACE-Seg** set (patient HCC_001, expert liver, tumor, and vessel reference labels)) via the native Windows **3D Slicer** ecosystem to generate segmented 3D meshes of target parenchymal organs (liver/breast), tumors, and critical vascular keep-out zones.
```

The clause keeps the "such as" framing. The named set is an example, so other conforming benchmark sets remain admissible under the same clause. A DICOM benchmark set with expert parenchyma, tumor, and vessel reference labels is one such set.

## 4. Rationale

Format. FR-MS-001 names DICOM. The Kitware TAIR "Multimodal Imaging Dataset for Cerebrovascular Disease" is NIfTI for CTA and MRA. The TCIA HCC-TACE-Seg CT series is DICOM.

Content. The TAIR release holds cerebrovascular CTA and MRA (500 studies in the current release) and X-ray fluoroscopy video. It has no liver, breast, or tumor labels. Its anatomical models (segmented, centerlined CTA) are announced for December 2026 and are not released. G2.1 needs a Dice score against parenchyma, tumor, and vascular reference labels, and TAIR supplies no released reference labels for any of the three.

Size. The TAIR download is one 70 GB zip. The HCC_001 CT zip is 17,780,801 bytes and the HCC_001 SEG zip is 36,327 bytes.

Label holdout. The HCC_001 SEG objects carry expert liver, tumor, and vessel labels. G2.1 needs those labels held out of pipeline inputs, so the Dice score is not a self-comparison. Slice 1 read only the CT series and did not read the SEG objects (`SNDEV/docs/impl-2026-11-05-task21-slice1-segmentation.md`, item 7).

Existing evidence. The slice-1 pipeline ran end to end on HCC_001 on 2026-11-05 with exit 0. The two zips have SHA-256 checksums recorded in the task 2.1 log and in `sim/segmentation/data/PROVENANCE.md`.

Licence. TCIA HCC-TACE-Seg is CC BY 4.0 (DOI 10.7937/TCIA.5FNA-0924). TAIR is also CC BY 4.0, so the licence does not separate the two sets.

Metadata note (unverified). The TAIR dataset page lists "Created" and "Last update" as November 13, 2026, which is later than the 2026-11-05 retrieval date. This date is recorded as an unverified metadata note. The decision does not rest on it, because format and label content decide it.

TAIR is not excluded by the clause text. It does not meet the G2.1 reference requirement because it carries no parenchyma, tumor, or vessel reference labels.

Alternative considered and rejected: keep Kitware TAIR as the example. The clause would then name a dataset that the G2.1 Dice metric cannot use, and the NIfTI format would still conflict with the DICOM wording of FR-MS-001.

## 5. Revision-history row proposal

When the document owner applies the amendment, line 4 becomes:

```markdown
**Document Version:** 1.4.0 (FR-MS-001 benchmark example restated per VAL-030 (TCIA HCC-TACE-Seg reference set); Major and Minor findings remain open)
```

Add this row to the Section 6 table:

```markdown
| 1.4.0 | 2026-11-05 | Seth Nenninger | FR-MS-001 benchmark example restated per VAL-030: the Section 3.1 example names the TCIA HCC-TACE-Seg set (patient HCC_001, expert liver, tumor, and vessel reference labels) in place of Kitware TAIR, which is NIfTI and carries no parenchymal, tumor, or vessel reference labels. The clause structure and all other clauses and Section 5 rows are unchanged. |
```

## 6. Follow-on record updates (not SRS text)

Applied in the same change set:

* `vv/traceability/vtm.md` row FR-MS-001 (line 9): the reference-set wording names the TCIA HCC-TACE-Seg HCC_001 series with the expert SEG reference labels held out of pipeline inputs, and the row notes VAL-030 and SRS v1.4.0. No other row changes.
* `DEVELOPMENT_PLAN.md`: header version 2.2 (draft) and a status sentence for SRS v1.4.0; gate G2.1 acceptance metric names the HCC_001 series and the held-out labels; task 2.1 estimate cell replaces the open dataset decision with the VAL-030 provenance and holdout bookkeeping; Section 6.3 gains a VAL-030 row.
* `SNDEV/docs/impl-2026-11-05-val030-proposal-apply.md` (new): the implementation log.

Recorded for later (not in this change set):

* Slice 2 adds the held-out SEG reference objects to segmentation provenance with `is_g21_reference` set to true. The slice-1 manifest sets the flag to false on its three generated segments, which are not reference objects.
* The slice-2 Dice evaluation records the held-out rule and the labels it used in its log.
* The task 2.1 slice-1 log is not edited, per the overwrite policy in AGENTS.md Section 6. The TAIR rejection and the VAL-030 decision are recorded in the slice-2 log, which cites this proposal.
* The G2.1 Status cell in `DEVELOPMENT_PLAN.md` still reads that the reference dataset choice is open. It is rewritten when slice 2 records status.
* `sim/segmentation/README.md` (line 54) still lists the TAIR dataset decision as open. It is outside this change set's file scope and is updated in slice 2.

## 7. Approval checklist

Items the document owner confirms for SRS.md v1.4.0:

* The Section 3 clause text is accepted verbatim.
* The owner decision of 2026-11-05 is accepted as the basis for Sections 1 and 4.
* The Document Version label and the 1.4.0 revision row in Section 5 are accepted.
* The follow-on record updates in Section 6 are accepted, and the VTM and plan edits ship in the same change set.

## 8. Status

Drafted 2026-11-05. The owner approved the amendment on 2026-11-05, and the owner's selection included application. The amendment is applied in the second commit of the same change set, which sets SRS.md to v1.4.0. Implementation log: `SNDEV/docs/impl-2026-11-05-val030-proposal-apply.md`.
