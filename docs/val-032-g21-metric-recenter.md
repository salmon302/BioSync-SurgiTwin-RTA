# VAL-032 G2.1 Metric Re-Centering (SurgiTwin-RTA)

Proposal and application record for VAL-032. Target records: the VTM row FR-MS-001 in `vv/traceability/vtm.md` and gate G2.1 in `DEVELOPMENT_PLAN.md`. Every line number below refers to those files as they stood before this change set.

File name: this file is named for the finding and not for an SRS version, because no SRS.md text changes. The acceptance metric is VTM-resident: SRS.md Section 5 names `vv/traceability/vtm.md` as the authoritative matrix. The plan gate G2.1 carries the operational value.

Decision record: on 2026-11-05 the document owner decided the G2.1 metric re-centering with two decisions, quoted here as the authorization for this proposal:

1. "Vascular clause: stratified recall. Gate recall at or above 0.95 on the reference-resolvable vessels (components above a documented diameter or size floor, roughly the 3 mm and up band), report full-tree recall as information, keep the volume bound with the documented 1 mm margin, and record the unresolved thin-branch residual risk in the risk file where FR-RTA-003 picks it up."
2. "Parenchyma clause: liver envelope convention. Score parenchyma against the reference liver with the tumor and vessel carve-outs filled (the organ envelope), convention documented per run."

Findings: VAL-032 is registered here. VAL-031 (applied 2026-11-05) set the per-structure clauses whose parenchyma and vascular parts this re-centering replaces; the tumor part is unchanged. The baseline register and VAL-026 through VAL-031 entries are unchanged.

Prepared: 2026-11-05.

Conventions used in the tables:

* Current text strings are quoted exactly from the VTM row FR-MS-001 and from the plan gate G2.1 as they stood before this change set.
* The clause in Section 3 carries the grounded values substituted for the bracketed markers, with the [adjustable] markers kept. The VTM carries it with the markers. The plan replaces each marker with the parenthetical "(adjustable)", as the plan style requires.

## 1. Scope and decision status

Decided on 2026-11-05: the G2.1 acceptance metric is re-centered as in Section 3. The clause has three parts, one per structure: parenchyma (a), vascular keep-out (b), and tumor (c). Each part has its own pass or fail result.

Out of scope: SRS.md text (Section 5 defers the metric to the VTM). Also out of scope: `sim/bridge/`, `sim/fmi/`, and `env/`.

In scope: the VTM row FR-MS-001 metric cell. In `DEVELOPMENT_PLAN.md`: the gate G2.1 acceptance metric and status cells, the task 2.1 estimate cell, one sentence in the Phase 2 status paragraph, one row in Section 6.2, one row in Section 6.3, and one row in Section 7.1. `sim/segmentation/` records the slice-6 evaluation grounding and one documented liver variant. The gate result is recorded in the plan status cell.

## 2. Finding register

| Finding ID | SRS location (section and line) | Current text (quoted from the VTM row) | Proposed replacement text | Rationale | Impact on the VTM |
| :--- | :--- | :--- | :--- | :--- | :--- |
| VAL-032 | No SRS.md line changes (SRS Section 5 defers the metric to the VTM). Record locations: VTM row FR-MS-001 metric cell. Plan gate G2.1 acceptance metric cell. | VAL-031 clause: `On the TCIA HCC-TACE-Seg HCC_001 series, meshes for parenchyma, tumor, and vascular keep-out zones are exported with segmentation provenance and evaluated against the expert SEG reference labels held out of pipeline inputs, per structure: (a) parenchyma, Dice at or above 0.90 and recall at or above 0.90 against the held-out liver reference; (b) vascular keep-out, recall at or above 0.95 (the keep-out zone contains at or above 95 percent of reference vessel voxels), keep-out volume at most 3 times the reference vessel volume [adjustable marker], and the keep-out safety margin documented and carried into the FR-RTA-003 envelope parameters; (c) tumor, when a lesion is present and visible on the named phase, a documented operator-placed seed (image inspection or clinical annotation, never the SEG reference labels) and the recorded chain produce a lesion mask with Dice at or above 0.70 [adjustable marker] against the held-out reference, and lesion detection is excluded from this gate and recorded as a limitation. On HCC_001 the tumor sub-gate is recorded not applicable with the two-pass non-detectability evidence unless a documented seed source becomes available. The evaluation records the SEG label-convention notes (Portal vein main trunk versus full tree) with each run.` | The Section 3 clause, which replaces the metric cell. The VTM cell carries the clause with the [adjustable] markers. The plan cell carries the clause with "(adjustable)" parentheticals. | Uniform unstratified recall mis-scores a safety-weighted keep-out at 5 mm slice thickness where thin branches partial-volume into parenchyma; the disjoint-label convention couples parenchyma to the un-detectable tumor clause; the residual thin-branch risk belongs in the risk file where FR-RTA-003 consumes it. Section 4 gives the reasons and the evidence. | VTM row FR-MS-001 metric cell replaced. Plan gate G2.1 metric and status cells replaced. No other VTM row changes. |

Totals: 1 finding row. The change replaces one VTM cell and the plan gate G2.1 metric cell, sets the plan gate G2.1 status cell, appends to one task 2.1 cell and one Phase 2 status paragraph, and adds one row each to Sections 6.2, 6.3, and 7.1. No SRS.md line changes.

## 3. Proposed clause (VAL-032)

The replacement acceptance metric for FR-MS-001 and gate G2.1, with the grounded values substituted for the bracketed placeholders:

```text
On the TCIA HCC-TACE-Seg HCC_001 series, meshes for parenchyma, tumor, and vascular keep-out zones are exported with segmentation provenance and evaluated against the expert SEG reference labels held out of pipeline inputs, per structure: (a) parenchyma, Dice at or above 0.90 and recall at or above 0.90 against the liver envelope (the reference liver label with the tumor and vessel carve-outs filled; the envelope convention is documented in each evaluation record); (b) vascular keep-out, recall at or above 0.95 over the reference-resolvable vessel set (reference components with lumen diameter at or above 11.0 mm [adjustable]), full-tree recall reported as information, keep-out volume at most 7.25 times the reference vessel volume [adjustable] with the 1.0 mm safety margin documented and carried into the FR-RTA-003 envelope parameters, and the unresolved thin-branch residual risk recorded in the risk file; (c) tumor, unchanged from VAL-031 (operator-placed seed from image inspection or clinical annotation, never SEG reference labels; Dice at or above 0.70 [adjustable]; detection excluded and recorded as a limitation; on HCC_001 the sub-gate is not applicable with the two-pass non-detectability evidence and the annotation search trail). Each evaluation record carries the label-convention notes (disjoint labels; Portal vein full intrahepatic tree; Abdominal aorta label covering slices 21 to 29 only while the keep-out covers the full visible aorta) and the dataset note (clinical Tr_Size 0.8 cm inconsistent with the 35.75 mL labeled mass).
```

Measurement definitions carried by the clause and recorded in each evaluation record:

* The liver envelope is `reference_liver OR reference_tumor OR reference_portal_vein` (the organ envelope). The Abdominal aorta label is extra-hepatic and is not a carve-out of the liver label. The literal four-label union is also reported for the audit trail.
* Lumen diameter is the maximum in-plane in-sphere diameter of a reference component (per-slice SignedMaurerDistanceMap on the label, in-plane spacing 0.78125 mm; the SimpleITK 2.5.5 Maurer filter returns squared distances and the true distance is the square root, verified on a synthetic disk). A component qualifies for the reference-resolvable set at or above the floor. Per-band (voxel-level local diameter) recall is reported as information.
* The keep-out volume is the margin-inclusive exported mask volume. The margin is 1.0 mm (in-plane dilation of the vessel core), documented in `sim/segmentation/README.md` and the vascular provenance sidecar and carried into the FR-RTA-003 envelope parameters.

## 4. Rationale

Symmetric unstratified recall mis-scores the keep-out at this acquisition. The reference vessel is a 40.48 mL set of which 22.90 mL sits in the under-2 mm lumen band (partial-volume voxels whose HU overlaps parenchyma; probes 22 and 23) and 3.32 mL above 10 mm. Gating the full tree at 0.95 would require the keep-out to admit parenchyma-ambiguous voxels, which the slice-5 Pareto measurements show costs unbounded volume (0.953 full-tree recall at 39.88 times the reference). The stratified clause gates the resolvable set and reports the full tree as information.

The disjoint-label convention couples parenchyma to the un-detectable tumor clause. The SEG labels are disjoint (Liver excludes Mass and both vessel labels, overlap 0.0), so scoring parenchyma against the disjoint liver label penalizes the chain for including the tumor region that VAL-031 clause (c) explicitly excludes from detection. The liver envelope (carve-outs filled) measures the organ the chain can actually produce.

The residual thin-branch risk belongs in the risk file. The keep-out cannot contain the thin branches at this sampling; FR-RTA-003 consumes the vascular no-go zones and must see the residual as a registered risk with its measured volume, not as a gate number the chain cannot meet. The risk register (plan Section 7.1) carries the row.

Alternatives considered:

* Keep uniform unstratified recall at 0.95 over the full tree (VAL-031). Rejected: the slice-5 and slice-6 measurements show it is not achievable at bounded volume on this patient at 0.78 by 0.78 by 5 mm.
* Anchor the diameter floor at the owner's rough 3 mm band and let the clause fail on this run. Considered and recorded as the alternative reading (Section 5): the measured keep-out achieves gated recall 0.476 at 3.0 mm at the grounded volume multiplier. The clause as grounded selects the smallest stratum where 0.95 is achievable at bounded volume, which is 11.0 mm on this patient. Both readings are in the evaluation record and the marker is adjustable.

## 5. Margin notes on the adjustable markers

* The 11.0 mm diameter floor (marker in clause (b)). Grounded on the slice-6 measurements: the gated-recall curve over floors is 0.476 at 2.5 to 3.0 mm (8 components, 12950 reference voxels), 0.492 at 3.5 to 4.0 mm, 0.574 at 5.0 to 6.0 mm, 0.755 at 8.0 to 10.0 mm, and 0.996 at 11.0 mm (1 component, 5529 voxels, the Abdominal aorta label). The floor separates the aorta stratum (max lumen diameter 19.58 mm) from the next component (10.94 mm, 5.39 mL, zero coverage on this run); a 10.5 mm floor would include that component and gated recall would read 0.755. The owner's rough band (3 mm) is resolvable at this sampling but does not reach 0.95 at bounded volume on the measured keep-out; the 3 to 11 mm pieces (three components, 15.29 mL) are recorded in the risk file with the thin branches. The floor is grounded on one patient and re-grounds when more patients are evaluated or a chain covers the 3 to 11 mm pieces at bounded volume.
* The 7.25 times volume multiplier (marker in clause (b)). The measured margin-inclusive keep-out volume at the gated point is 293.02 mL against the 40.48 mL reference, a multiple of 7.2384. The marker is grounded to 7.25 (rounded up to the next 0.25). The margin contributes 78.16 mL of the volume (core 214.87 mL to margin-inclusive 293.02 mL) and the margin-free core alone is 5.31 times the reference, so the margin is not the bound-breaker. The multiplier is grounded on one patient and re-grounds when more patients are evaluated.
* The 0.70 tumor Dice floor (marker in clause (c)). Unchanged from VAL-031. No HCC_001 measurement exists for a seeded lesion because the sub-gate is not applicable on this patient. The floor re-grounds on a patient with a visible lesion.
* The 1.0 mm keep-out safety margin is not a marker in the clause; the clause requires it documented and carried into the FR-RTA-003 envelope parameters, which the README, the provenance sidecar, and each evaluation record do.
* The parenchyma floors (0.90 Dice, 0.90 recall) are not markers. On the slice-6 record the organ-envelope reading gives Dice 0.9077 and recall 0.9505, and the literal aorta-inclusive reading gives Dice 0.9030 and recall 0.9402; both readings pass, so the convention definition does not carry the verdict.

## 6. Follow-on record updates (not SRS text)

Applied in the same change set:

* `vv/traceability/vtm.md` row FR-MS-001: the metric cell carries the clause with the [adjustable] markers, followed by a note of VAL-032 provenance and this proposal. The VAL-031 provenance trail is kept in the row note.
* `DEVELOPMENT_PLAN.md` gate G2.1: the acceptance metric cell carries the clause with "(adjustable)" parentheticals. The status cell records the slice-6 grounded re-score verdicts per clause and the recorded boundaries.
* `DEVELOPMENT_PLAN.md` task 2.1 estimate cell: a note that VAL-032 re-centered the metric and that slice 6 landed the grounding.
* `DEVELOPMENT_PLAN.md` Phase 2 status paragraph: one appended sentence with the re-centering and the gate result.
* `DEVELOPMENT_PLAN.md` Section 6.2: a VAL-032 row. Section 6.3: a resolved row (Resolution: restated 2026-11-05 by owner decision; Residual: markers re-grounded when more patients are evaluated).
* `DEVELOPMENT_PLAN.md` Section 7.1: one risk-register row for the unresolved thin-branch residual risk.
* `sim/segmentation/`: the slice-6 evaluation grounding (envelope convention, stratified vessel metrics, grounded markers) and one documented liver variant (v4, the envelope-convention chain).
* `SNDEV/docs/impl-2026-11-05-val032-recenter.md` (new): the implementation log.

Residual plan actions (not in this change set):

* The per-run convention notes requirement is implemented in `evaluate_g21.py` (label-convention notes, dataset note, envelope definition) and holds for each run.
* Lint coverage for `sim/` remains the open task-2.1 remainder.
* The risk-register row is accepted in the risk file where FR-RTA-003 consumes it.

## 7. Approval checklist

Items the document owner confirms for this re-centering:

* The Section 3 clause text is accepted with the grounded values (11.0 mm floor, 7.25 times multiplier), or the owner sets other values before the next gate run.
* The owner decisions quoted in the header are accepted as the basis for Sections 1 and 4.
* The measurement definitions in Section 3 (organ envelope, in-plane lumen diameter) are accepted as the test method.
* The follow-on record updates in Section 6 are accepted, and the VTM and plan edits ship in the same change set.
* No SRS.md text changes, and the file name reflects the finding.

## 8. Status

Drafted and applied 2026-11-05 in the same change set as the owner decisions of 2026-11-05. The re-centering is applied in commit B of this change set (`docs(vv,plan): apply VAL-032 G2.1 metric recenter`). Implementation log: `SNDEV/docs/impl-2026-11-05-val032-recenter.md`. The slice-6 grounded record reads PASS with recorded boundaries on gate G2.1 (boundaries listed in the plan gate status cell).

## Appendix A. Evidence

All values are on the TCIA HCC-TACE-Seg HCC_001 series with held-out SEG reference labels. The chains are deterministic and each documented variant was scored once through `evaluate_g21.py`. Labels are read only by `evaluate_g21.py`, through `run_evaluation.ps1`.

### A.1 Slice-5 Pareto table (vascular keep-out, before re-centering)

| Variant | Recall (full tree) | Keep-out mL | Multiple of reference | Note |
| :--- | :--- | :--- | :--- | :--- |
| V2 (slice-4 final) | 0.5676 | 182.25 | 4.50 | best volume point |
| V3 | 0.7869 | 1131.00 | 27.94 | parenchyma flood |
| V4 | 0.9534 | 1614.54 | 39.88 | only full-tree recall pass, unbounded volume |
| V5 (slice-5 final) | 0.4650 | 293.02 | 7.24 | balanced point; the slice-6 record |

### A.2 Mechanism probes (probe 22 and probe 23)

* Probe 23b (`SNDEV/logs/probe23b-vesselness-separation-2026-11-05.log`): the blob-style Frangi measure reads plain parenchyma as tube-like at 5 mm z sampling (V 0.96 and above at sigma 3 on 95 percent of the bright-parenchyma sample), and the Frangi line-term does not separate either (portal lumen V_ra 0.26 against a parenchyma 95th percentile of 0.34 to 0.45).
* Probe 20 (`SNDEV/logs/probe20-band-hu-2026-11-05.json`): the 2 to 4 mm branches partial-volume to 125 to 145 HU (acquisition 2) and 85 to 105 HU (acquisition 1), overlapping the parenchyma range (94 to 139 and 54 to 86 HU).
* Probe 22 rounds (`probe22b` to `probe22e`): the flood mechanism (small-scale vesselness on parenchyma texture), the per-scale threshold test, and the brightness-floor test that bounds the flood.

### A.3 Convention measurements (evaluation-side, per-run in `evaluation.json`)

* Disjoint labels: overlap shares 0.0 for Mass inside Liver, Portal vein inside Liver, Abdominal aorta inside Liver, and vessel inside Liver.
* Portal tree: 7736 voxels (23.608 mL) in 35 connected components over slices 2 to 31, branch volume share 0.739, max in-plane lumen radius 2.34 mm after the squared-distance correction (the slice-5 record of 5.49 mm was the squared value and is superseded).
* Abdominal aorta label: 5529 voxels (16.873 mL) in one component over slices 21 to 29 only (z -310 to -270), bbox x 261 to 297, y 222 to 275, max in-plane lumen diameter 19.58 mm, while the keep-out covers the full visible aorta (z -415 to -240).
* Margin: the margin adds 78.16 mL (core 214.87 mL to margin-inclusive 293.02 mL) and the margin-free core is 5.31 times the reference, so the margin is not the bound-breaker.
* Disagreement profile (corrected for the squared-distance bug): parenchyma FP is 34533 of 71971 voxels at 8 mm and farther from the reference (48 percent), and 23380 of 23652 FN voxels within 4 mm (99 percent). The slice-5 figures (67 percent at 8 mm and more) used the squared distances and are superseded.
* Dataset note: the clinical spreadsheet `HCC-TACE-Seg_clinical_data-V2.xlsx` (TCIA collection page, CC BY 4.0, SHA-256 E9D2683DC907819AA08E4027E085854F46464BEC834A09E80FC83B19A89E092B) documents no lesion location and records Tr_Size 0.8 cm, inconsistent with the 35.75 mL labeled mass (about 4 cm across). The annotation search trail is in `SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md`.

### A.4 Slice-6 grounded numbers (final run 2026-11-05, `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261106T024206Z.log`)

Parenchyma (final chain liver v4, the envelope-convention chain):

| Convention | Dice | Jaccard | Recall | FP mL | FN mL |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Liver envelope (organ) | 0.907738 | 0.831062 | 0.950549 | 219.6 | 75.6 |
| Envelope including the aorta label (audit) | 0.902975 | 0.823113 | 0.940165 | 219.6 | 92.4 |
| Disjoint label (audit) | 0.889231 | 0.800555 | 0.950840 | 275.6 | 72.2 |

Vascular stratified (final chain vessel v5; lumen diameter per Section 3):

| Band (mm) | Reference voxels | Reference mL | Covered | Recall | Keep-out mL attributed |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 to 2 | 7505 | 22.903 | 2014 | 0.2684 | 255.07 |
| 2 to 3 | 670 | 2.045 | 285 | 0.4254 | 2.42 |
| 3 to 5 | 2219 | 6.772 | 1299 | 0.5854 | 10.34 |
| 5 to 10 | 1782 | 5.438 | 1488 | 0.8350 | 13.80 |
| 10 and above | 1089 | 3.323 | 1082 | 0.9936 | 11.40 |

Per-component (top rows): comp 29 (aorta) 16.873 mL, max diameter 19.58 mm, recall 0.9964; comp 1 6.161 mL, 6.44 mm, recall 0.3259; comp 17 5.392 mL, 10.94 mm, recall 0.0; comp 9 4.379 mL, 7.81 mm, recall 0.0; comp 12 3.363 mL, 4.69 mm, recall 0.0. Full-tree recall 0.4650 as information.

Grounded markers: diameter floor 11.0 mm (gated recall 0.9964 at the gated set of 5529 voxels), volume multiple 7.25 (measured 7.2384 at 293.024 mL margin-inclusive).

Clause verdicts on the slice-6 record: (a) parenchyma PASS (Dice 0.9077 and recall 0.9505 against the organ envelope); (b) vascular keep-out PASS (gated recall 0.9964 against 0.95, volume 7.2384 times against 7.25 times, margin documented, thin-branch residual in the risk file); (c) tumor NOT APPLICABLE (no documented seed source).

### A.5 Documented variant in this change set

One liver variant was run and scored once (liver v4, the envelope-convention chain: the slice-5 organ-minus-vessel subtraction is replaced by organ-envelope fill of the segmented vessel carve-outs). The variant budget was two liver variants (zero vessel variants after slice 5) and the judgment latitude in the mission was used because the slice-5 chain encodes the superseded disjoint convention and scores 0.8987 against the envelope on the same output (short 0.0013). The variant is recorded in `SNDEV/docs/impl-2026-11-05-val032-recenter.md`.

## Addendum (owner ruling 2026-11-05): modality floor and slice 7

Owner ruling ("Slice 7, modality floor", 2026-11-05), recorded as the authority for this addendum: the vascular floor moves from the grounded 11.0 mm to 3.0 mm, the recall and volume values are held open pending slice-7 re-grounding, and slice 7 is funded to fix the missed resolvable vessels. The G2.1 vascular clause is OPEN until the values land.

Rationale recorded by the ruling: the 11.0 mm grounded floor is unsatisfactory because it excludes the missed 10.94 mm portal-trunk component, which is a resolvable vessel at this acquisition and whose zero coverage is a method gap and not a modality limit, and because it reduces the gate to aorta coverage. The floor becomes 3.0 mm grounded in partial-volume physics at the 0.78 by 0.78 by 5 mm acquisition spacing: at and above 3.0 mm a lumen cross-section spans at least four in-plane pixels and is resolvable, while below it the lumen partial-volumes into the parenchyma band (slice-6 band table: 0.2684 recall under 2 mm, 0.4254 at 2 to 3 mm).

Effect on the clause (b) of Section 3:

* The diameter floor is 3.0 mm (the [adjustable] marker stays).
* The recall floor and the volume multiplier are replaced by "(values pending slice-7 grounding)" until the slice-7 re-grounding lands. The re-grounding rule is unchanged in form: the recall floor is the gated recall at the 3.0 mm floor achieved by the best bounded-volume variant (rounded down to a clean two-decimal value with a margin note) and the multiplier is the measured margin-inclusive volume as a multiple of the 40.48 mL reference (rounded up to a clean value with a margin note). If the best variant cannot approach 0.95 gated recall at bounded volume, the honest measured values are proposed and the owner re-centers.
* G2.1's vascular clause is OPEN while the values are pending. The parenchyma clause (PASS on the slice-6 record, Dice 0.9077 and recall 0.9505 against the liver envelope) and the tumor sub-gate (not applicable, with the two-pass non-detectability evidence and the annotation search trail) are unchanged by this addendum.

Slice-7 scope funded by this ruling: fix the missed resolvable vessels (targets: component 17, 5.39 mL at 10.94 mm max lumen diameter with recall 0.0; component 9, 4.38 mL at 7.81 mm with recall 0.0; component 1, 6.16 mL at 6.44 mm with recall 0.3259; and the 3 to 5 mm band, 2219 voxels at 0.5854 recall), then re-ground the recall floor and the volume multiplier at the 3.0 mm floor and apply the grounded clause text to the VTM row and the plan gate cells.

### Slice-7 grounding (2026-11-05)

Three documented vessel variants were run and scored once each (log `SNDEV/docs/impl-2026-11-05-task21-slice7-vessels.md`; diagnosis `SNDEV/logs/probe24-vessel-miss-diagnosis-2026-11-05.json`). The mechanism finding: the slice-5 corridors missed the portal tree because the acquisition-1 lumen partial-volumes into the parenchyma band (median 71 to 91 HU against liver 54 to 86 HU) and because the candidate fragmented before the seed selection ran (the v5 z-closing runs after seeding and cannot repair the fragmentation). The fixable part was confirmed: the acquisition-2 slices of every target component measure 155 to 182 HU and pass the gates at 0.99 to 1.0.

Final Pareto (gated recall at the 3.0 mm floor, margin-inclusive keep-out volume):

| Variant | Mechanism | Gated recall | Full-tree recall | Keep-out mL | Multiple | Bounded (at most 15x) |
| --- | --- | --- | --- | --- | --- | --- |
| v5 (slice-5 chain) | corridors, brightness 85 / 145 HU, vesselness 0.6, z-closing after seeding | 0.4762 | 0.4650 | 293.02 | 7.24 | yes |
| v6 | iterated 3 pixel z-fill from adjacent footprints on acquisition 1 slices | 0.9992 | 0.9988 | 1866.57 | 46.11 | no (flood) |
| v7 | lumen-windowed fill, iterated footprint-intersection (3 pixel) | 0.9614 | 0.9603 | 1271.17 | 31.40 | no (organ-scale) |
| v8 | drift-matched fill from seed-connected acquisition 2 sources | 0.3108 | 0.3081 | 185.10 | 4.57 | yes |

Grounded values (the owner rule: the recall floor is the gated recall at the 3.0 mm floor achieved by the best bounded-volume variant, rounded down to two decimals; the multiplier is the measured margin-inclusive volume as a multiple of the 40.48 mL reference, rounded up to a clean value):

* Recall floor: 0.47. Measured 0.476216 on the best bounded-volume variant (v5, the slice-5 chain) at the 3.0 mm floor. Margin note: rounded down to two decimals and grounded on one patient; it is 0.4738 short of the 0.95 aspiration.
* Volume multiplier: 7.5. Measured 7.2384 at 293.024 mL margin-inclusive (core 214.865 mL; the 1.0 mm margin contributes 78.16 mL and is documented and carried into the FR-RTA-003 envelope parameters). Margin note: rounded up to the next 0.5 and grounded on one patient.

Plain statement: at bounded volume (the pre-registered criterion of at most 15 times the reference) the best measured gated recall is 0.4762, which cannot approach 0.95. The slice-7 variants demonstrate 0.9614 (v7) and 0.9992 (v6) gated recall, but only at organ-scale volume (31.40 and 46.11 times the reference; v6 exceeds the reference liver envelope of 1527.7 mL and v7 reaches 86 percent of it), which no FR-RTA-003 keep-out can use on this organ. The v8 attempt to bound the interpolation lost recall to 0.3108 through its source rule (the sources were restricted to the seed-connected acquisition-2 islands, which truncates the tree at the gaps the variant exists to bridge; recorded as the defect for the next slice). The honest measured values 0.47 and 7.5 are proposed as the clause markers and the owner re-centers. Alternative reading recorded for the owner: if bounded is read as below the reference liver envelope volume (1527.7 mL), the v7 point (0.9614 at 31.40 times) is the best bounded variant and the markers would be 0.96 and 31.5.

Clause (b) of Section 3 as grounded: the diameter floor is 3.0 mm [adjustable], the recall floor is 0.47 [adjustable], and the volume multiplier is 7.5 [adjustable]. The gated set at 3.0 mm is 8 components (12950 voxels of the 13265-voxel reference); per-band and per-component recalls are in the slice-7 log and each evaluation record.
