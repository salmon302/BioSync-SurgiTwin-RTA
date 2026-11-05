# VAL-031 G2.1 Acceptance-Metric Proposal (SurgiTwin-RTA)

Proposal and application record for VAL-031. Target records: the VTM row FR-MS-001 in `vv/traceability/vtm.md` and gate G2.1 in `DEVELOPMENT_PLAN.md`. Every line number below refers to those files as they stood before this change set.

File name: this file is named for the finding and not for an SRS version, because no SRS.md text changes. The acceptance metric is VTM-resident: SRS.md Section 5 (line 89) names `vv/traceability/vtm.md` as the authoritative matrix and the Section 5 table as a non-authoritative extract. The plan gate G2.1 carries the operational value.

Decision record: on 2026-11-05 the document owner decided that the G2.1 metric is per structure, with a recall-weighted vascular clause. The tumor clause is operator-seeded, and lesion detection is excluded from the gate. The parenchyma floor stays at 0.90, and slice-5 method work is funded. The owner's selection included application, so this proposal is applied in the same change set (Section 8).

Findings: VAL-031 is registered here. The slice-4 log (`SNDEV/docs/impl-2026-11-05-task21-slice4-method.md`, line 10) already refers to this restatement as pending. The baseline register (VAL-001 through VAL-025) and the applied entries VAL-026 through VAL-030 are unchanged.

Prepared: 2026-11-05.

Conventions used in the tables:

* Current text strings are quoted exactly from the VTM row FR-MS-001 and from the plan gate G2.1 as they stood before this change set.
* The clause in Section 3 is verbatim. The VTM carries it verbatim. The plan replaces each bracketed marker with the parenthetical "(adjustable)", as the plan style requires.

## 1. Scope and decision status

Decided on 2026-11-05: the G2.1 acceptance metric is restated as in Section 3. The clause has three parts, one per structure: parenchyma (a), vascular keep-out (b), and tumor (c). Each part has its own pass or fail result.

Out of scope: SRS.md text. No SRS.md line changes, for the reason given in the file header. Also out of scope: `sim/`, `env/`, and the task 2.1 slice-4 log, which record the measurements that this proposal cites.

In scope: the VTM row FR-MS-001 metric cell. In `DEVELOPMENT_PLAN.md`: the gate G2.1 acceptance metric and status cells, the task 2.1 estimate cell, one sentence in the Phase 2 status paragraph, and one row each in Sections 6.2 and 6.3. The gate stays OPEN.

## 2. Finding register

| Finding ID | SRS location (section and line) | Current text (quoted from the VTM row and the plan gate) | Proposed replacement text | Rationale | Impact on the VTM |
| :--- | :--- | :--- | :--- | :--- | :--- |
| VAL-031 | No SRS.md line changes (Section 5 defers the metric to the VTM, line 89). Record locations: VTM row FR-MS-001 (`vv/traceability/vtm.md` line 9, metric cell). Plan gate G2.1 (`DEVELOPMENT_PLAN.md` line 220, acceptance metric cell). | VTM: `Dice score of at least 0.90 against the expert SEG reference labels for the parenchyma, tumor, and vascular keep-out meshes segmented from the TCIA HCC-TACE-Seg HCC_001 series, with the reference labels held out of pipeline inputs and segmentation provenance recorded per mesh (proposed; VAL-030, restated in SRS v1.4.0)`. Plan: `Meshes for parenchyma, tumor, and vascular keep-out zones are exported from the TCIA HCC-TACE-Seg HCC_001 series (VAL-030) with segmentation provenance, and overlap with the expert SEG reference labels held out of pipeline inputs is a Dice score of 0.90 or higher (proposed)`. | The Section 3 clause, which replaces both cells. The VTM cell carries the clause verbatim. The plan cell carries the clause with "(adjustable)" parentheticals. | Uniform symmetric Dice mis-scores the vascular keep-out zone, whose purpose is containment (FR-RTA-003), and it scores tumor detection as if it were segmentation. Section 4 gives the reasons and the evidence. | VTM row FR-MS-001 metric cell replaced. Plan gate G2.1 metric and status cells replaced. No other VTM row changes. |

Totals: 1 finding row. The change replaces one VTM cell and the plan gate G2.1 metric cell, sets the plan gate G2.1 status cell, appends to one task 2.1 cell and one Phase 2 status paragraph, and adds one row each to Sections 6.2 and 6.3. No SRS.md line changes.

## 3. Proposed clause (VAL-031)

The replacement acceptance metric for FR-MS-001 and gate G2.1 is:

```text
On the TCIA HCC-TACE-Seg HCC_001 series, meshes for parenchyma, tumor, and vascular keep-out zones are exported with segmentation provenance and evaluated against the expert SEG reference labels held out of pipeline inputs, per structure: (a) parenchyma, Dice at or above 0.90 and recall at or above 0.90 against the held-out liver reference; (b) vascular keep-out, recall at or above 0.95 (the keep-out zone contains at or above 95 percent of reference vessel voxels), keep-out volume at most 3 times the reference vessel volume [adjustable marker], and the keep-out safety margin documented and carried into the FR-RTA-003 envelope parameters; (c) tumor, when a lesion is present and visible on the named phase, a documented operator-placed seed (image inspection or clinical annotation, never the SEG reference labels) and the recorded chain produce a lesion mask with Dice at or above 0.70 [adjustable marker] against the held-out reference, and lesion detection is excluded from this gate and recorded as a limitation. On HCC_001 the tumor sub-gate is recorded not applicable with the two-pass non-detectability evidence unless a documented seed source becomes available. The evaluation records the SEG label-convention notes (Portal vein main trunk versus full tree) with each run.
```

The clause is one acceptance statement with three per-structure parts. The parenchyma part keeps the 0.90 Dice floor of the original metric. The vascular part replaces Dice with a containment test. The tumor part applies only when a lesion is visible on the named phase.

## 4. Rationale

Symmetric Dice is the wrong measure for the vascular keep-out zone. FR-RTA-003 uses the keep-out zone to bound the safety envelope, so its purpose is containment. A missed vessel voxel is the hazard, and extra keep-out volume is an accepted cost. Dice weighs the two errors equally, and it also penalizes the 1 mm safety margin, because the reference labels have no margin. On HCC_001 the vascular mask has recall 0.5676 and a volume of 182.25 mL against a 40.48 mL reference. That is about 159 mL of false positives (derived) against about 17.5 mL of false negatives (derived). A Dice score of 0.2063 reports that imbalance as a failure of segmentation. The restated vascular part asks the question the keep-out zone must answer: does it contain the vessels, and is it bounded in size?

Detection is a different capability from segmentation. A Dice score on a tumor mask presumes that the lesion is visible on the image and asks the pipeline to find it. On HCC_001 no lesion is visible on either available phase (Appendix A.3). A Dice gate on that case measures detection, which the pipeline does not claim, and it conflates detection with segmentation. The operator-seeded clause measures segmentation given a seed that a person placed from the image or a clinical annotation, without reading the reference labels. Detection is recorded as a limitation.

The parenchyma floor is reachable method work, not measurement noise. The chains are deterministic, so the same inputs and parameters give the same masks, and the slice-4 reading of 0.8915 is a fixed value. From the reported figures (derived), the intersection is about 1364 mL, the false positives are about 228 mL, and the false negatives are about 104 mL. Reaching 0.90 with the intersection unchanged requires about 29 mL fewer false positives. The gap is at the boundary scale, and the slice-5 work in Section 6 targets it. The recall of the parenchyma part is 0.9290, which already meets its 0.90 recall floor.

Alternatives considered:

* Keep one uniform Dice floor of 0.90 for all structures. Rejected: it mis-scores the containment purpose of the vascular zone, and the tumor gate cannot be met on HCC_001 by any CT-only method.
* Lower the parenchyma Dice floor to match the measured value. Rejected: the owner kept the floor at 0.90.

The vascular part is stricter than the old Dice floor on recall and looser on volume, because it allows a mask up to 3 times the reference volume. The restatement changes the measure to match the containment role of the zone. The slice-4 vascular result fails both sub-criteria.

## 5. Margin notes on the adjustable markers

The clause has two bracketed markers, and the owner listed one more adjustable value. Each value may be adjusted at application, and each should be re-grounded when more patients are evaluated. A single patient gives one sample, so none of the values below is a distribution.

* The 3 times vessel volume bound (marker in clause (b)). The reference vessel volume is 40.48 mL, so the bound is 121.44 mL. The slice-4 vessel mask of 182.25 mL is 4.5 times the reference and fails this sub-criterion as well as the recall sub-criterion. The multiplier is a judgment, not a measured value.
* The 0.70 tumor Dice floor (marker in clause (c)). No HCC_001 measurement exists for a seeded lesion, because the tumor sub-gate is not applicable on this patient. The floor should be re-grounded on a patient with a visible lesion.
* The 0.95 vessel recall floor. The clause text has no bracket on this value, but the owner's adjustable list includes it. The slice-4 vessel recall is 0.5676. Reaching 0.95 requires an intersection of about 38.5 mL, which is about 15.5 mL more than the slice-4 intersection (derived).
* The clause (c) phrase "the named phase" does not name a phase. The evaluation record names the acquisition and its phase determination for each run (Appendix A.2), and that record supplies the name.
* The 1 mm safety margin of the vascular chain is not fixed by the clause. The clause requires the margin to be documented and carried into the FR-RTA-003 envelope parameters. The envelope parameters are set when the envelope is specified.

## 6. Follow-on record updates (not SRS text)

Applied in the same change set:

* `vv/traceability/vtm.md` row FR-MS-001: the metric cell carries the clause verbatim, followed by a note of VAL-031 provenance and this proposal. No other row changes.
* `DEVELOPMENT_PLAN.md` gate G2.1: the acceptance metric cell carries the clause with "(adjustable)" parentheticals. The status cell records the restatement, the slice-4 readings against the restated clauses, and that the gate stays OPEN.
* `DEVELOPMENT_PLAN.md` task 2.1 estimate cell: a note that VAL-031 restated the metric and that slice 5 is the funded remainder.
* `DEVELOPMENT_PLAN.md` Phase 2 status paragraph: one appended sentence with the restatement and the funded remainder.
* `DEVELOPMENT_PLAN.md` Section 6.2: a VAL-031 row. Section 6.3: a VAL-031 row with the resolution and the residual plan action.
* `SNDEV/docs/impl-2026-11-05-val031-metric-restate.md` (new): the implementation log.

Slice-5 work funded by the owner, recorded as the residual plan action (not in this change set):

* Parenchyma: liver boundary refinement to remove about 29 mL of false positives without losing intersection, and an agreed rule for the liver label at the porta, the gallbladder bed, and the caudate.
* Vascular: seed-subtree selection to remove the mesenteric and lumbar branches, and smaller vesselness scales for 2 to 4 mm branches, to reach recall 0.95. The SEG "Portal vein" label convention (main trunk versus full tree) is resolved before precision work.
* Tumor: an operator-seed attempt only if the dataset clinical annotation documents a lesion location. A clinical annotation is a legitimate seed source under clause (c). The SEG reference labels never are.
* Evaluation: each run records the SEG label-convention notes, as clause (c) requires.

## 7. Approval checklist

Items the document owner confirms for this restatement:

* The Section 3 clause text is accepted verbatim.
* The owner decision of 2026-11-05 is accepted as the basis for Sections 1 and 4.
* The adjustable values in Section 5 are accepted at the stated values, or the owner sets other values before the next gate run.
* The follow-on record updates in Section 6 are accepted, and the VTM and plan edits ship in the same change set.
* No SRS.md text changes, and the file name reflects the finding.

## 8. Status

Drafted 2026-11-05. The owner decided the restatement on 2026-11-05, and the owner's selection included application. The restatement is applied in commit B of this change set (`docs(vv,plan): apply VAL-031 G2.1 metric restatement`). Implementation log: `SNDEV/docs/impl-2026-11-05-val031-metric-restate.md`. Gate G2.1 stays OPEN until the clauses are measured on the final chains.

## Appendix A. Evidence

All values are on the TCIA HCC-TACE-Seg HCC_001 series with held-out SEG reference labels. The chains are deterministic, and no variant was tuned on Dice after scoring. Labels were read only by `evaluate_g21.py`, through `run_evaluation.ps1`.

### A.1 Scored results

* Slice 2 baseline: liver Dice 0.6745, tumor Dice 0.0000, vascular Dice 0.0543.
* Slice 3a V0 on the SEG-referenced input (confound fixed): liver Dice 0.7108 with recall 0.7778; tumor Dice 0.0000; vascular Dice 0.0543 with recall 0.3098, 421.13 mL against a 40.48 mL reference.
* Slice 4 final chains:

| Structure | Chain | Dice | Jaccard | Recall | Pipeline mL | Reference mL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| parenchyma_liver | V0 (slice 3a) | 0.7108 | 0.5514 | 0.7778 | 1745.15 | 1468.28 |
| parenchyma_liver | V1 (minus vessel core dilated 3 mm) | 0.7225 | 0.5656 | 0.5968 | 957.28 | 1468.28 |
| parenchyma_liver | V2 (final) | 0.8915 | 0.8042 | 0.9290 | 1591.81 | 1468.28 |
| tumor_hypoattenuating | V0 (slice 2) | 0.0000 | 0.0000 | 0.0000 | 1.72 | 35.75 |
| tumor_hypoattenuating | V1 (final, empty by confirmation rule) | 0.0000 | 0.0000 | 0.0000 | 0.00 | 35.75 |
| vascular_keepout_bone_excluded | V0 (slice 3a) | 0.0543 | 0.0279 | 0.3098 | 421.13 | 40.48 |
| vascular_keepout_bone_excluded | V1 (recall priority) | 0.0842 | 0.0440 | 0.7169 | 648.48 | 40.48 |
| vascular_keepout_bone_excluded | V2 (final) | 0.2063 | 0.1150 | 0.5676 | 182.25 | 40.48 |

* Final liver (V2): Dice 0.8915 against the 0.90 floor (FAIL), recall 0.9290 against 0.90 (PASS).
* Final vessel (V2): Dice 0.2063. Recall 0.5676 against 0.95 (FAIL). Volume 182.25 mL against the 121.44 mL bound (FAIL).
* Final tumor: chain empty by its confirmation rule, Dice 0.0000, 0.00 mL against 35.75 mL.

### A.2 Phase quantification

Values are 7 by 7 pixel ROI means (5.5 by 5.5 mm) at z -320 mm unless noted. Source: `SNDEV/logs/probe9b-phase-hu-2026-11-05.json`.

* Acquisition 1 is late arterial: aorta lumen 224.1 to 224.7 HU, liver parenchyma 54 to 74 HU.
* Acquisition 2 is portal venous: liver parenchyma 94 to 139 HU, aorta lumen 160 to 166 HU.
* The CT carries no contrast phase tags, so the determination rests on image HU and organ enhancement. Structure identity is confirmed on the zoomed crops in `SNDEV/logs/probe8-png/`.

### A.3 Tumor non-detectability

Two independent full-volume passes covered 36 staged slices (z -415 to -240 mm; 21 on acquisition 2 and 15 on acquisition 1), with soft-tissue and liver windows, zoomed crops, and body-masked deviation scans at 10 to 15 HU against a 3 mm Gaussian background, for components of 2 to 500 mL. Neither pass found a mass signature. The four chain candidates (13.26, 9.12, 4.77, and 3.16 mL) lie at vessel-adjacent and liver-edge locations and do not form a rounded mass. An isoattenuating lesion on both phases would evade both passes, and the available late arterial and portal venous data cannot exclude one.

### A.4 Metric-definition mismatches

* The SEG "Portal vein" label convention (main trunk versus full tree) is unresolved. The convention decides which vessel voxels count as reference, so it is needed before vessel precision work can be scored (slice-4 log, vessel section).
* The pipeline's 1 mm safety margin is penalized by symmetric Dice against a margin-free reference, although FR-RTA-003 wants keep-out zones to over-cover.
