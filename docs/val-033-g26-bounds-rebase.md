# VAL-033 G2.6 Bounds Rebase at the Schedule Rate (SurgiTwin-RTA)

Proposal and application record for VAL-033. Target records: SRS.md Section 3.1 (FR-MS-007, no text change), SRS.md Section 5 (FR-MS-007 Target Acceptance Metric cell), SRS.md Section 6 (revision row 1.5.0), the VTM row FR-MS-007 in `vv/traceability/vtm.md`, gate G2.6 and tasks 2.7 and 2.8 in `DEVELOPMENT_PLAN.md`, and the Section 6.2 and 6.3 rows of `DEVELOPMENT_PLAN.md`.

Decision record: the owner ruled on 2026-11-12, quoted here as the authorization for this proposal:

1. "VAL-033 rebases the FR-MS-007 and G2.6 clock-skew and message-jitter bounds at the schedule rate."
2. "The gate claim runs on the three-node topology with pipelined remote steps."

## 1. Scope and decision status

Decided on 2026-11-12 by the document owner (ruling quoted above). This record drafts and applies the clause. The FR-MS-007 clause in SRS Section 3.1 already carries the scheduled-variable wording (SRS v1.2.0, VAL-028), so only the Section 5 acceptance metric changes in SRS.md.

In scope: the SRS.md Section 5 FR-MS-007 Target Acceptance Metric cell, a Section 6 revision row (1.5.0), and the Document Version line. The VTM row FR-MS-007 metric cell. The plan gate G2.6 acceptance metric and status cells, the task 2.7 and 2.8 rows (status text only), the Section 6.2 and 6.3 rows, and one Phase 2 status sentence.

Out of scope: the FR-MS-007 clause text in Section 3.1, the Section 5 Verification Method cell (its text is kept), `sim/sofa/`, `sim/bridge/`, `env/`, and the multi-host network case (recorded as unmeasured, see Section 6).

## 2. Finding register

| Finding ID | Location (section and line) | Current text (quoted) | Proposed replacement | Rationale | Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| VAL-033 | SRS.md Section 5, row FR-MS-007, Target Acceptance Metric cell (line 96 of SRS.md v1.4.0). VTM row FR-MS-007 metric cell. Plan gate G2.6 acceptance metric cell (line 225 of `DEVELOPMENT_PLAN.md`). | `All FMUs pass FMI 3.0 import checks, and measured clock skew and message jitter are each at most 1 ms across a 10-minute three-node Fast DDS co-simulation run against a reference clock, with per-message timestamps recorded` | The clause in Section 3 of this record, used verbatim. | A 1 ms arrival-jitter bound is not reachable on a schedule whose participant steps take 10 ms or more (Section 4). The bound is restated at the schedule rate, and the physically meaningful claims are kept. | SRS.md Section 5 FR-MS-007 cell, SRS.md Section 6 (new row 1.5.0), SRS.md Document Version line, VTM row FR-MS-007 metric cell, plan gate G2.6 acceptance metric and status cells, plan task rows 2.7 and 2.8 (status text), plan Section 6.2 and 6.3 rows, one Phase 2 status sentence. |

Totals: 1 finding. The SRS.md Section 3.1 clause is not changed. The Section 5 Verification Method cell is not changed.

## 3. Proposed clause (VAL-033)

The replacement FR-MS-007 Target Acceptance Metric, used verbatim:

> All plant FMUs pass their FMI 3.0 import checks. Across a 10-minute co-simulation run against a reference clock on the pinned ROS 2 / Fast DDS layer: (a) clock skew (arrival minus source stamp) is at most 2 ms at p99 and the maximum is recorded; (b) message jitter (arrival interval deviation from the schedule grid) is at most 1.5 times the schedule tick at p99 and the maximum is recorded; (c) every scheduled participant step executes exactly as scheduled with zero reply timeouts; and (d) per-message timestamps resolve at least 1 ms. The schedule tick is set by the slowest participant step (mechanical DoStep, measured 11.2 ms mean at the 1230-tet reference scene).

In the plan cell and the VTM cell the two numeric multipliers are carried with the parenthetical "(adjustable)", as the plan style requires (Section 5).

## 4. Rationale

The 1 ms arrival-jitter bound assumed a master tick of 1 ms. The schedule tick is set by the slowest participant step, and the mechanical FMU DoStep is 11.2 ms mean on the 1230-tet reference scene (`SNDEV/logs/fmi-mechanical-check-2026-11-07.json`, check M3). A co-simulation master cannot publish a schedule tick faster than its slowest step, so any arrival-interval measurement against a 1 ms grid fails by construction. The slice-2 evidence shows the failure is the schedule, not the transport:

* Single node, quiet host (`SNDEV/logs/fmi-multirate-single-node-quiet-600s-2026-11-12T021833Z.json`): 50,224 master ticks in 600 s (83.7 Hz, mean tick 11.95 ms). Arrival-interval jitter median 10.6 ms, p99 14.9 ms, max 21.6 ms, on the 1 ms nominal grid. Skew p99 0.46 to 0.95 ms, max absolute 1.68 to 2.00 ms.
* Three nodes, pipeline off (attempt 1, `SNDEV/logs/fmi-three-node-g26-attempt1-600s-2026-11-12T024234Z.json`): 17,495 master ticks in 600 s (29.2 Hz). Each tick waits for the remote mechanical reply, a serialized round trip of 31 ms (15.5 ms request transit, 10.6 ms FMU step, 5.0 ms reply transit). Arrival-interval jitter median 30.2 ms, p99 62.3 ms, max 77 ms. Skew p50 0.26 to 0.66 ms, p99 0.55 to 1.05 ms, max absolute 1.39 to 1.82 ms. Zero reply timeouts over 19,245 round trips, and each participant stepped exactly as scheduled.

The rebased clause keeps the three things that the evidence measures correctly:

* (a) Bounded skew. Skew is independent of the schedule rate. It is the delivery and epoch offset of each stamp. The 2 ms p99 bound is the bound the evidence supports on one host over loopback, with the maximum recorded.
* (b) Bounded jitter at the schedule rate. Jitter is measured against the schedule grid that the master actually runs. The 1.5 times the schedule tick bound at p99 holds the master to its own grid and no tighter.
* (c) Exact schedule adherence and zero timeouts. These are the co-simulation correctness claims, independent of timing magnitude.
* (d) Sub-millisecond stamp resolution. The stamps use the steady clock (QueryPerformanceCounter on this host), which resolves below 1 ms.

The measurement and physics honesty mirrors the VAL-029 frame-budget rebase (SRS v1.3.0): the bound is stated at the rate the physics allows, and the measured value is reported beside it rather than hidden.

## 5. Margin notes on the adjustable markers

The owner's markers are the numeric multipliers in the clause: 2 ms at p99 for skew, and 1.5 times the schedule tick at p99 for jitter. They are the owner's values and are not derived from a fixed standard in this record. The margin notes below record what they rest on, so the owner can change them with the evidence in view.

* Skew 2 ms at p99. The slice-2 p99 skew is 0.46 to 0.95 ms on one node and 0.55 to 1.05 ms on three nodes. The 2 ms marker leaves about a factor of two of headroom over the three-node p99. It is grounded on a single host over loopback, where the stamp epoch and the delivery path are the same machine. A multi-host network adds delivery variance this run does not measure.
* Jitter 1.5 times the schedule tick at p99. At the 11.95 ms tick the marker is 17.9 ms. The slice-2 jitter p99 is 14.9 ms on one node and 62.3 ms on three nodes with the serialized loop; with pipelining (slice 3) the schedule tick is still set by the mechanical step, so the marker is tested against the pipelined master, not the serialized one. The 1.5 multiplier allows one-and-a-half ticks of arrival spread at p99.
* Grounding limit. Both markers are grounded on one host over loopback single-machine Fast DDS. The claim is a single-host claim. The multi-host case is listed as unmeasured in Section 6.

## 6. Follow-on record updates (not SRS text)

* `vv/traceability/vtm.md`, row FR-MS-007: metric cell set to the clause of Section 3 with the "(adjustable)" markers, and the VAL-033 provenance appended to the row's provenance text.
* `DEVELOPMENT_PLAN.md`, gate G2.6: acceptance metric cell set to the clause of Section 3 with the parentheticals. Status cell records the slice-2 baseline FAIL against the old 1 ms clause (attempt 1, `SNDEV/logs/fmi-three-node-g26-attempt1-600s-2026-11-12T024234Z.json`) and the slice-3 run under the rebased clause (numbers appended after that run).
* `DEVELOPMENT_PLAN.md`, Section 6.2: a row recording that the 1 ms clause is unreachable with 10 ms-class participant steps.
* `DEVELOPMENT_PLAN.md`, Section 6.3: a row recording the resolution (the schedule-rate rebase, the pipelined master) and the residual actions: the slice-3 run under the rebased bounds, and the multi-host network case, which remains unmeasured.
* Task 2.7 and 2.8 rows: the status text records the rebased clause and the slice-3 result.
* Unmeasured: the multi-host network case. It needs a second physical host or a network emulation, and is not claimed here.

## 7. Approval checklist

* Owner ruling 2026-11-12 on record (Section 1): done.
* Clause text used verbatim (Section 3): done, to be verified against the applied cells.
* Section 3.1 SRS clause unchanged (its scheduled-variable wording is from v1.2.0): verified in the apply step.
* Section 5 Verification Method cell unchanged: verified in the apply step.
* Section 6 revision row 1.5.0 added, Document Version line updated: applied in this change set.
* Margin notes recorded with the owner's markers (Section 5): done.
* Slice-3 run under the rebased bounds: pending (Part 2 of the 2026-11-12 brief).

## 8. Status

Drafted 2026-11-12 with the owner ruling of the same date. Applied to SRS.md, the VTM, and the plan in the commit that adds this record. The slice-3 numbers are appended to the plan gate G2.6 status cell after the run.

## Appendix A. Evidence

* Single-node quiet reference, 600 s: `SNDEV/logs/fmi-multirate-single-node-quiet-600s-2026-11-12T021833Z.json` and sidecar, launcher `fmi-multirate-single-node-quiet-launcher-2026-11-11.txt`.
* Three-node attempt 1, 600 s: `SNDEV/logs/fmi-three-node-g26-attempt1-600s-2026-11-12T024234Z.json` and sidecar, launcher `fmi-three-node-g26-attempt1-launcher-2026-11-12.txt`, per-node transcripts `...-node1-master.txt`, `...-node2-mechanical.txt`, `...-node3-pulse.txt`.
* Mechanical DoStep cost (check M3): `SNDEV/logs/fmi-mechanical-check-2026-11-07.json`.
* FMU import-check suites: thermal five cases `SNDEV/logs/fmi-thermal-pennes-check-slice2-2026-11-07.json`; mechanical five cases `SNDEV/logs/fmi-mechanical-check-2026-11-07.json`; Pulse six cases `SNDEV/logs/fmi-pulse-check-pao2-fix-final-2026-11-07.json`.
* Slice-2 log: `SNDEV/docs/impl-2026-11-11-task28-slice2-multirate.md`.

## Addendum (owner ruling 2026-11-12): clause (c) clarification and measured adherence

Ruling quoted: "VAL-033 clause (c) counts schedule adherence at the schedule rate: every scheduled participant step executes exactly once per its schedule period with zero timeouts, and the step-count reconciliation uses the master tick count."

Applied wording (SRS Section 5, v/traceability/vtm.md row FR-MS-007, and the plan gate G2.6): "every scheduled participant step executes exactly once per its schedule period with zero reply timeouts, with the step-count reconciliation performed at the master tick rate (the schedule rate); the 1 ms-grid step count is reported as information only". The SRS revision note is recorded under the 1.5.0 row as a clarification, not a new version.

Measured adherence (three-node run, 600 s, SNDEV/logs/fmi-three-node-g26-val033-pipelined-600s-2026-11-12T105252Z.json): the master ran 600,001 ticks on its 1 ms schedule with 600,001 mechanical step points and 60,001 Pulse step points. The mechanical participant executed 6,731 steps and Pulse executed 32,220. Zero reply timeouts.

Reconciliation discrepancy (recorded for the owner, not resolved here). The ruling gives 6,731 steps as one per master tick at an 11 ms tick. The master did not run an 11 ms tick: the code that produced the run has a 1 ms tick (sim/fmi/master/src/three_node_master.cpp). At 11 ms, 600 s gives about 53,600 ticks, not 6,731. So the executed schedule reconciles at 6,731 of 600,001 mechanical step points (1.1 percent) and 32,220 of 60,001 Pulse step points (53.7 percent), not 6,731 of 6,731. Under the clause as ruled, adherence is not met on the measured schedule. The verdict on (c) is FAIL as measured; the owner is asked to rule whether a re-stated reconciliation (the rate ratio as the result) or a design change (the pipeline executing the mechanical step at the schedule rate) is the closure path.

## Addendum 2 (owner ruling 2026-11-12): rate-ratio clause (c) and the factor marker

Ruling: clause (c) is rewritten as a rate-ratio requirement: "every remote participant executes its scheduled steps with zero reply timeouts, no lost or duplicated steps, and its achieved step rate is within a factor of [FACTOR] of its scheduled rate (the rate ratio is recorded per participant; the 1 ms-grid step count is reported as information only)". The factor marker is set at 3.0 for the record. It is an owner-set marker, adjustable at application.

Applied text: SRS Section 5 (FR-MS-007), v/traceability/vtm.md (row FR-MS-007), and the SRS 1.5.0 revision note (clarification 2) use the same text with [FACTOR] = 3.0.

Boundary text (owner-supplied, recorded as given): "the remote mechanical step rate is limited by the loopback round trip (about 31 ms pipelined: 22.0 ms request transit, 4.5 ms FMU step, 4.2 ms reply transit); a real network or the modal-reduction follow-on improves the ratio; the single-host loopback topology and the unmeasured network latency and separate clocks remain recorded boundaries".

Measured rate ratios (three-node run, 600 s, SNDEV/logs/fmi-three-node-g26-val033-pipelined-600s-2026-11-12T105252Z.json; serialized single-node baseline, 600 s, SNDEV/logs/fmi-multirate-single-node-quiet-val033-600s-2026-11-12T104127Z.json):

* Mechanical: 6,731 steps executed of 600,001 step points on the 1 ms grid. Mean period 89.1 ms, achieved rate 11.2 Hz. Against the serialized single-node baseline of 83.2 Hz (49,921 steps in 600 s), the ratio is 7.4. Against the 1 kHz grid the ratio is 89. Against the 11.2 ms schedule tick (89 Hz) the ratio is 8.0. At factor 3.0 the mechanical ratio exceeds the marker.
* Pulse: 32,220 steps executed of 60,001 step points at the 10 ms period. Mean period 18.6 ms, achieved rate 53.7 Hz against 100 Hz scheduled. Ratio 1.9, within 3.0.
* Pipelined round-trip split (master summary): request transit 22.0 ms, FMU step 4.5 ms, reply transit 4.2 ms (sum 30.7 ms, about 31 ms).

Checks that the owner ruling depends on, recorded as found:

* The ruling's "3.2x slower than the 12 ms tick" does not reproduce. 89.1 ms over 12 ms is 7.4. The 89x against the 1 ms grid is correct.
* The boundary text attributes the mechanical rate to the 31 ms loopback round trip. A 31 ms round trip with one step in flight gives about 32 Hz, but the measured mechanical rate is 11.2 Hz (mean period 89 ms, about three times the round trip). The round trip does not account for the whole mean period in this run. The attribution is recorded as supplied and is not verified here.
* Remote steps: the master counted 38,949 round trips against 38,951 executed steps (6,731 mechanical plus 32,220 Pulse). The two-step difference is not explained by the record, so "no lost or duplicated steps" is not fully verified.

Verdict under the ruling at factor 3.0: clauses (a), (b), and (d) PASS (unchanged from Addendum 1). Clause (c) FAIL: the mechanical ratio of 7.4 exceeds 3.0, and the no-lost-or-duplicated-steps check is not closed (two-step difference). G2.6 is therefore NOT MET at factor 3.0. The factor marker is the owner's; the close-out does not change it. Owner options: (1) set the factor at a value the measured ratio meets (the record needs at least 7.5), recorded as a new ruling; (2) keep 3.0 and keep G2.6 open until a remote step rate is measured under a real network or the modal-reduction follow-on.

## Addendum 3 (owner ruling 2026-11-12): factor 8.0 and the open boundaries

Ruling: the rate-ratio factor of clause (c) is 8.0. It is owner-set and adjustable at application, and it is a clean ceiling above the measured mechanical ratio. It supersedes the factor 3.0 marker of Addendum 2.

Applied text: SRS Section 5 (FR-MS-007), v/traceability/vtm.md (row FR-MS-007), and the SRS 1.5.0 revision note (clarification 2) read "within a factor of 8.0 of its scheduled rate (owner-set 2026-11-12, adjustable; the rate ratio is recorded per participant; the 1 ms-grid step count is reported as information only)".

Measured ratios against the 8.0 factor (three-node run, 600 s, SNDEV/logs/fmi-three-node-g26-val033-pipelined-600s-2026-11-12T105252Z.json):

* Mechanical: 7.4 against the 83.2 Hz serialized single-node baseline (11.2 Hz pipelined). Within 8.0, with a margin of 0.6. Against the 11.2 ms schedule tick the ratio is 8.0 (7.96), at the edge of the factor. PASS.
* Pulse: 1.9 (53.7 Hz against 100 Hz scheduled). Within 8.0. PASS.
* Zero reply timeouts (master summary).

Clause (c) is PASS at factor 8.0 with the two open items below recorded as boundaries.

Open item 1, unattributed rate cost (open mechanism item). The mechanical mean period is 89.1 ms. The pipelined round trip is about 31 ms (22.0 ms request transit, 4.5 ms FMU step, 4.2 ms reply transit). With one step in flight, a 31 ms round trip predicts about 32 Hz, but the measured rate is 11.2 Hz. The round trip does not explain the period, so about 58 ms of the period is an unattributed cost. The mechanism is not identified. The owner's boundary text attributes the rate to the round trip; that attribution is recorded as given and is not supported by the measurement. Closure needs a measurement of the cost outside the round trip.

Open item 2, round-trip count discrepancy. The master counted 38,949 remote round trips against 38,951 executed steps (6,731 mechanical plus 32,220 Pulse). The two-step difference is not explained by the record. The no-lost-or-duplicated-steps check is therefore not fully closed. The owner accepted this as a recorded boundary.

Boundaries that remain recorded: single-host loopback topology (three nodes on one machine); network latency and separate clocks are not measured; the multi-host case is unmeasured. The improvement path is a real network or the modal-reduction follow-on, neither of which is measured here.

Verdict: G2.6 PASS with recorded boundaries under the VAL-033 schedule-rate clause, with clause (c) at the owner-set factor 8.0. Clauses (a), (b), and (d) PASS (Addendum 1 numbers unchanged).
