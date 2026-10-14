Title: Phase 1 closure: tasks 1.6 and 1.11, gate G1.8, plan and migration map updates
Date: 2026-10-14T20:48:26Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 closure (tasks 1.6, 1.11; gate G1.8)
Summary: Marks Phase 1 tasks 1.6 and 1.11 and gate G1.8 closed at commit `7508b91` in the plan, records the G1.8 boundaries, and updates the migration map.

## Task Reference

DEVELOPMENT_PLAN.md Phase 1 task 1.6 (test configuration for NFR-PERF-001, NFR-PERF-002, NFR-PERF-004), task 1.11 (1,000,000-row PQ-3 check on a dedicated database), and gate G1.8 (performance scope). Evidence: commit `7508b91` (`test(pq): NFR performance config, G1.8 relay run, 1M-row chain check (1.6, 1.11)`), the run record `SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md`, and the configuration record `SNDEV/docs/impl-2026-10-14-pq-config.md`.

## Specification Summary

Close the three open Phase 1 items in the plan and bring the plan text and the migration map into line with the recorded evidence. The change is documentation only. No code was edited and no tests were run. The gate results come from the cited logs.

Recorded G1.8 boundaries:

* The run measured 10 points per second aggregate offered load. The 50 ms p95 bound fails at 20 points per second and above on this host because of broadcast fan-out serialization (findings 1 and 2 of the run record).
* The relay ran with `DB_SSLMODE=disable` against the plaintext container. This deviates from NFR-SEC-001 for the measurement only (finding 7).
* NFR-PERF-001 ingestion measured about 12,600 points per second against the 100,000 points per second target. This is below target and is not claimed. Offered 20,000 points per second produced 29.5% HTTP 503 backpressure (finding 3).

## Implementation Notes

### Files changed

* `DEVELOPMENT_PLAN.md` (edit)
* `docs/migration-map.md` (edit, minimal)
* `SNDEV/docs/impl-2026-10-14-phase1-closure.md` (this file, new)

### Per-row change record: DEVELOPMENT_PLAN.md

| Location | Change |
|:---------|:-------|
| Header Status line | Records Phase 0 complete, Phase 1 complete with G1.1 to G1.8 closed (G1.8 with recorded boundaries), Phase 2 in progress with its kickoff log, and SRS.md v1.1.0 applied 2026-10-14 closing VAL-001 to VAL-004 (Major and Minor findings open). |
| Phase 1 heading | `(IN PROGRESS)` changed to `(DONE)`. |
| Phase 1 status paragraph | The sentence "only tasks 1.6 and 1.11 and the G1.8 run remain" replaced with the closure sentence citing `7508b91` and both evidence logs. All earlier commit and evidence citations are kept. |
| Phase 1 estimate line | Recomputed: 25.5 d complete, 0.0 d remaining, total 25.5 d. |
| Task 1.6 row | `2.0d` changed to `2.0d (done, commit 7508b91, configuration record SNDEV/docs/impl-2026-10-14-pq-config.md)`. |
| Task 1.11 row | `1.0d` changed to `1.0d (done, commit 7508b91, run record SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md, 1,000,000 rows verified in 5.84 s against the 60 s bound)`. The Output cell names `SNDEV/logs/` for the run record, but the record is in `SNDEV/docs/`. The Output cell now names the docs path. Raw captures stay in `SNDEV/logs/`. |
| Gate G1.8 row | OPEN replaced with PASS with recorded boundaries (`7508b91`), with the parity counts, p95 1.46 ms, and boundaries (a) to (c). |
| Section 6.1 items 1 to 4 | One disposition line each: VAL-001 (VTM authoritative, extract non-authoritative), VAL-002 (protocol register reference in FR-VV-005 and NFR-REL-001), VAL-003 (separate FR-RTA-002 and FR-RTA-003 rows), VAL-004 (deadline clause with [RTA_DEADLINE_MS], filled from task 3.6). |
| Section 6.2 VAL-009 row | Note added that the FR-RTA-002 extract row carries the VTM mapping cell with the VAL-009 note. VAL-009 stays open. |
| Phase 2 status line | `Not started.` changed to in progress, with the kickoff log, and the G1.1 to G1.3 prerequisites stated as PASS. |
| Section 7.1 Gateway R3 row | Stale "pending" G1.8 wording replaced with R3 closed at task 1.5, G1.8 PASS with recorded boundaries, and NFR-PERF-001 not met. |

### Per-row change record: docs/migration-map.md

| Location | Change |
|:---------|:-------|
| Table 2, Gateway load and soak tests row | Task 1.6 and task 1.11 marked done at `7508b91`, with the two record paths. The row stays deferred for the Gateway suites. |
| Table 3, Gateway R3 row | OPEN (carried) changed to CLOSED (task 1.5, gate G1.8 at `7508b91` with recorded boundaries). The "stays OPEN until G1.8" sentence is replaced. |
| Table 3, surgical telemetry ingestion row | Status changed to OPEN (measured below target). The "not measured" sentence is replaced with the measured figure, about 12,600 points per second. |
| Table 4, shared 5432 container row | Appended the measurement-only deviation: the G1.8 and NFR-PERF runs used `DB_SSLMODE=disable` against this container (finding 7 of the run record). |
| Table 4, new row | "NFR-PERF-001 ingestion throughput below target", OPEN (measured, not claimed). Revisit at Phase 5 task 5.6 and with relay tuning. |

No table was restructured and no unrelated row was reworded.

## Verification

| Check | Method | Result |
|:------|:-------|:-------|
| Estimate arithmetic | 12 done rows: 4.0 + 1.5 + 1.0 + 3.0 + 4.0 + 2.0 (1.6) + 2.0 (1.7) + 3.0 + 2.0 + 1.5 + 1.0 (1.11) + 0.5 = 25.5 d. Open rows: none, 0.0 d. Total 25.5 d. | PASS |
| Evidence paths exist (Test-Path from the repo root) | `SNDEV/docs/impl-2026-10-14-pq-config.md`, `SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md`, `SNDEV/docs/impl-2026-10-14-task-completion.md`, `SNDEV/docs/impl-2026-10-14-gate-status.md`, `vv/tests/PQ/locustfile.py`, `vv/tests/PQ/test_pq_relay_sessions.py`, `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py`, `vv/traceability/vtm.md`, `SRS.md`, `docs/migration-map.md`, `DEVELOPMENT_PLAN.md`, `docs/srs-v1.1-change-proposal.md`, `SNDEV/logs/pq-2026-10-14-g18-run1.json`, `SNDEV/logs/pq-2026-10-14-1m-pytest.txt`, `SNDEV/logs/pq-2026-10-14-ingest-run1_stats.csv` | PASS (all True) |
| Parallel-agent cross-references | `SNDEV/docs/impl-2026-10-14-phase2-kickoff.md` and `SNDEV/docs/impl-2026-10-14-srs-v1.1-apply.md` | PENDING at check time (not yet written by the parallel agents). Recheck before commit. |
| Commit `7508b91` resolves | `git log --oneline` | PASS (`7508b91 test(pq): NFR performance config, G1.8 relay run, 1M-row chain check (1.6, 1.11)`) |
| Consistency: no OPEN or not-done wording for 1.6, 1.11, or G1.8 | `Select-String` on DEVELOPMENT_PLAN.md for tasks 1.6, 1.11, G1.8, "pending", "not done", "OPEN" | PASS (no remaining OPEN or pending wording for these items; the G1.8 row keeps its original requirement and acceptance metric text, which is not a status) |
| Writing constraints on added lines | Banned-word list, em and en dashes, curly quotes, and a Conclusion heading, swept over `git diff` added lines of both files | PASS (0 banned words, 0 dashes, 0 curly quotes, 0 Conclusion headings) |
| Tests and code | No code edits and no test runs, per the brief | Not applicable |

## Findings for the plan owner

These items were not changed by this log.

* SRS.md on disk still reads `1.0.0 (Baseline Validated)` at line 4, and FR-VV-005 and NFR-REL-001 still say "19" protocols. The header and Section 6.1 text in this change describe SRS v1.1.0 as applied, per the brief. The apply log `SNDEV/docs/impl-2026-10-14-srs-v1.1-apply.md` was not present at check time.
* The v1.1 change proposal (`docs/srs-v1.1-change-proposal.md`) says the Section 5 extract covers 10 of 31 IDs. The brief says 20 of 31. The 6.1 item 1 text uses 20, per the brief. Confirm the applied figure.
* The G1.8 acceptance metric says "audit rows equal to completed requests". The run record counts completed WebSocket sessions, two audit rows each, because the relay writes no per-frame audit row. The gate text should be confirmed against this reading.
* The migration map Table 4 row for the shared 5432 container says it is R2 residue. The measurement deviation was added there, not as a new row.
* The run record's finding 1 (fan-out tail latency) names a candidate cause that was not isolated (client-side queueing). The plan states the boundary as fan-out serialization, which the run record lists as the limit. Confirm the wording.
* `vv/traceability/vtm.md` still lists tasks 1.6 as "planned" for NFR-PERF-001, NFR-PERF-003, and NFR-PERF-004 rows (for example, "load definition planned (task 1.6)"). That file is owned by another stream and was not edited.
