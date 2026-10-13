Title: SurgiTwin-RTA development plan authoring
Date: 2026-10-13T22:33:35Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc (repo preparation for initial development)
Summary: Authors DEVELOPMENT_PLAN.md from SRS.md v1.0.0 with eight phases (Phase 0 DONE, Phases 1-7 planned at 191 days), full FR/NFR coverage, a verification strategy, 16 open SRS items carried from the baseline validation audit, and a risk register.

## Task Reference

Parent session instruction: author the SurgiTwin-RTA development plan and write exactly two files in `I:\Documents\GitHub\BioSync\BioSync-SurgiTwin-RTA`:

1. `SNDEV\docs\impl-2026-10-13-dev-plan.md` (this log, written first).
2. `DEVELOPMENT_PLAN.md` at the repository root (written second).

Both files are then committed together. Nothing else in the repository is modified.

Inputs used: `SRS.md` v1.0.0 (read-only), `docs\architecture.md`, the scaffold log `SNDEV\docs\impl-2026-10-13-repo-scaffold.md`, the audit `SNDEV\docs\impl-2026-10-13-srs-baseline-validation.md`, the house-style model `I:\Documents\GitHub\BioSync\BioSync-Gateway\DEVELOPMENT_PLAN.md`, and the current repository tree including `CMakeLists.txt`, `.github\workflows\ci.yml`, `rta\`, `middleware\`, and `vv\`.

## Specification Summary

DEVELOPMENT_PLAN.md follows the BioSync-Gateway plan structure: numbered sections, phase blocks with goal lines, task tables carrying Task, Output, and Est. columns with estimates in days, verification gates, and a closing register.

Content required by the instruction and delivered:

- Overview with a one-paragraph project summary and seven guiding principles (deterministic RTA decision path with no heap allocation or locking, database-first compliance, CSA risk partitioning driving test rigor, SIL-to-HIL script portability, MISRA C++:2023 with a C++17 pin, reuse of Gateway material through the migration map, evidence landed with each increment).
- Technology stack table with a version-constraint column and a license or hardware precondition column covering the proprietary items named in the audit: Parasoft C/C++test, QA-MISRA, VectorCAST, Cantata, Speedgoat/dSPACE/NI SLSC, NVIDIA Omniverse/Isaac Sim, and the ALM tools.
- Architecture summary mapping the four SRS tiers to the scaffolded directories (`sim/`, `rta/`, `middleware/` + `database/` + `edge/` + `frontend/`, `vv/`), one ASCII diagram, and a key design decisions table.
- Phased plan: Phase 0 foundation (DONE, references the scaffold log and its verification results), Phase 1 informatics baseline (Gateway migration per `docs/migration-map.md`, carried debt R2 and R3, NFR-PERF-001 and NFR-PERF-004 scope), Phase 2 M&S tier (FR-MS-001..004, FR-MS-006, FR-MS-007), Phase 3 RTA tier (FR-RTA-001..004 with MISRA gate, WCET, MC/DC first), Phase 4 teleoperation and edge HIL (FR-RTA-005, FR-RTA-006), Phase 5 interoperability depth (FR-DAT-002, FR-DAT-006, FR-DAT-007), Phase 6 continuous verification (FR-VV-001..005 plus the IQ/OQ/PQ protocol register), Phase 7 rendering and visualization (FR-MS-005, NFR-PERF-003). Every phase carries a verification gate table citing FR/NFR IDs and acceptance metrics, and a CSA risk annotation that marks which tasks are High Process Risk and which are Not High Process Risk per SRS Section 2.2.
- Verification and compliance strategy: static analysis scope, coverage targets per risk class, IQ/OQ/PQ protocol structure and naming convention for `vv/tests`, and the traceability path from SRS ID to VTM row to test to CI evidence.
- Open SRS questions: the four Blocker findings as numbered questions with interim handling, and the twelve Major findings summarized in one table.
- Risk register with Risk, Impact, Likelihood, Mitigation columns covering technical, regulatory, and schedule risks. The risk register ends the document; there is no Conclusion section and no revision-history table.

## Implementation Notes

What the plan covers: the plan is written against the repository as it exists after the scaffold commit `86f4cd7`. The scaffolded reality shaped several choices. `CMakeLists.txt` already pins `CMAKE_CXX_STANDARD 17`, which matches audit finding VAL-016, so the plan records C++17 as the pinned language for `rta/` and `sim/` and carries the SRS "C++17/C++20" wording as an open question. `rta/` contains compilable `SafetyEnvelope`, `SimplexSwitch`, and `TimedAutomata` placeholders with stub thresholds (5.0 mm, 2.0 N), so Phase 3 tasks are written as replacing stub thresholds with risk-file values rather than creating classes from nothing. `middleware/` holds only a FastAPI `/health` stub with pinned requirements, so Phase 1 is written as migration work. `vv/tests` has one IQ layout test and empty OQ/PQ directories, so the protocol register task builds on that layout. `docs/migration-map.md` did not exist when this plan was written; every reference to it is marked as landing in this commit series.

How the audit findings were handled: the audit's 25 findings drive two plan sections. The four Blockers (VAL-001 VTM coverage 10 of 31, VAL-002 undefined "19 IQ/OQ/PQ protocols", VAL-003 FR-RTA-002 and FR-RTA-003 VTM conflation, VAL-004 missing numeric RTA deadline) become Section 7 numbered open questions, each with an interim handling that lets Phase 1 and Phase 3 work proceed (a complete VTM maintained in `vv/traceability/`, a protocol register in `vv/tests`, a separate FR-RTA-003 verification gate, and a candidate decision-loop deadline measured by WCET analysis before it is written into the SRS). The twelve Major findings (VAL-005 through VAL-016) are summarized in one table with the same interim handling pattern. The nine Minor findings stay in the audit document and are referenced by path rather than duplicated. Feasibility findings from the audit (proprietary tool licenses, HIL hardware, Omniverse runtime, unnamed FMI master and XIL implementation, formal verification method absent) appear in the technology stack precondition column and in the risk register. Carried Gateway debt R2 and R3 became explicit Phase 1 tasks with acceptance metrics, because the audit showed NFR-SEC-001, NFR-PERF-001, NFR-PERF-002, and NFR-PERF-004 all restate Gateway claims that the Gateway left OPEN.

## Verification

Cross-reference checks run against the finished `DEVELOPMENT_PLAN.md`:

1. FR and NFR citation check: every requirement ID cited in `DEVELOPMENT_PLAN.md` was extracted with a regex sweep and compared against the set of IDs defined in `SRS.md` (31 IDs: 7 FR-MS, 6 FR-RTA, 7 FR-DAT, 5 FR-VV, 4 NFR-PERF, 1 NFR-SEC, 1 NFR-REL). Result: PASS, zero citations to non-existent IDs. Detail: see the coverage table below.
2. Path citation check: `docs/migration-map.md` MISSING at check time, marked in the plan as "in this commit series"; `SNDEV/docs/impl-2026-10-13-repo-scaffold.md` exists; `SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md` exists in the working tree (untracked, expected to be committed by the parent session); `docs/architecture.md`, `vv/traceability/`, `vv/tests/IQ|OQ|PQ`, `database/`, `middleware/`, `rta/`, `sim/`, `.github/workflows/ci.yml` exist; `database/migrations/`, `middleware/api/routes/`, `vv/traceability` register files, and `vv/tests` protocol files do not exist yet and are marked in the plan as created in a named phase. Result: PASS with explicit later-landing marks.
3. Phase-to-requirement coverage check:

| Phase | FR IDs covered | NFR IDs covered |
|:---|:---|:---|
| Phase 0 (DONE) | none (foundation only) | none (foundation only) |
| Phase 1 | FR-DAT-001, FR-DAT-003, FR-DAT-004, FR-DAT-005, FR-DAT-007 (plus FR-DAT-006 seed) | NFR-PERF-001, NFR-PERF-002, NFR-PERF-004, NFR-SEC-001 |
| Phase 2 | FR-MS-001, FR-MS-002, FR-MS-003, FR-MS-004, FR-MS-006, FR-MS-007 | none |
| Phase 3 | FR-RTA-001, FR-RTA-002, FR-RTA-003, FR-RTA-004 | none |
| Phase 4 | FR-RTA-005, FR-RTA-006 | NFR-PERF-002 (sub-10 ms edge leg) |
| Phase 5 | FR-DAT-002, FR-DAT-006, FR-DAT-007 | NFR-SEC-001, NFR-PERF-001 |
| Phase 6 | FR-VV-001, FR-VV-002, FR-VV-003, FR-VV-004, FR-VV-005 | NFR-REL-001 |
| Phase 7 | FR-MS-005 | NFR-PERF-003 |

Coverage result: all 25 FR IDs covered by at least one phase task (FR-MS: 7/7, FR-RTA: 6/6, FR-DAT: 7/7, FR-VV: 5/5). All 6 NFR IDs covered (NFR-PERF-001..004, NFR-SEC-001, NFR-REL-001). Every phase from 1 through 7 maps to at least one FR ID. Phase 0 is excluded from that rule because it is recorded as DONE foundation work with no FR ownership, per the scaffold log.

4. Writing constraint check on both files: zero occurrences of the banned word list, zero em or en dashes, zero curly quotes, no bolded-term list openings, no Conclusion/Challenges/Future Prospects sections, no emoji or checkmark glyphs. Result: PASS.

## Recovery 2026-10-13

Title: SurgiTwin-RTA development plan recovery
Date: 2026-10-13T23:10:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc (recovery of a lost plan file before commit)
Summary: Rewrites DEVELOPMENT_PLAN.md from the blueprint in this log, aligns Phase 1 with the completed Gateway migration, and records the re-run cross-reference results.

### Recovery Record

The prior run's `DEVELOPMENT_PLAN.md` was lost before commit. A different agent rewrote the file from the blueprint recorded in the Specification Summary and Verification sections above, which this log treats as the authoritative spec. The original sections of this log are unchanged. The Gateway migration (commit `0b5b8d2`) now exists, so `docs/migration-map.md` is cited as existing.

### Changes From the Blueprint

1. Phase 1 task 1.1 records the migration outcome: 11 tables (10 WORM), telemetry relay and routes deferred into task 1.5, Gateway R2 and R3 carried open, FR-MS-006 ProcessPoolExecutor delegation blocked by engine pickling (Phase 2 task 2.5), and the FR-DAT-004 and FR-DAT-006 gaps assigned to Phase 1 tasks 1.8 and 1.9 and Phase 5 tasks 5.2 and 5.3.
2. Phase 1 scope follows the coverage table in this log (NFR-PERF-001, NFR-PERF-002, NFR-PERF-004, NFR-SEC-001). The blueprint's Specification Summary named only NFR-PERF-001 and NFR-PERF-004, so the coverage table is the stricter reading.
3. Phase 1 status records the migration test outcome as 147 passed, 1 failed (IQ-5), and 59 skipped, with the SQL migrations not yet executed against PostgreSQL.
4. Phase estimates were recomputed for the rewrite. Phases 1 to 7 total 203.5 d, with 4.0 d of Phase 1 complete. The 191-day figure in the lost file is not reproduced.
5. Phase 3 task 3.1 replaces the stub thresholds (5.0 mm and 2.0 N) in `rta/include/rta/safety_envelope.h` with risk-file values.
6. The four Blocker findings are numbered questions in Section 6.1, and the twelve Major findings are one table in Section 6.2. The nine Minor findings are referenced by audit path only.
7. The risk register is Section 7 and ends the document.

### Cross-Reference Results

Re-run against `DEVELOPMENT_PLAN.md` (497 lines).

1. FR and NFR citation sweep: 31 IDs are defined in `SRS.md`, 31 unique IDs are cited in the plan, and dangling citations are 0. Result: PASS.

2. Phase coverage, using the IDs cited in each phase block:

| Phase | FR IDs | NFR IDs | Matches Blueprint Table |
|:------|:-------|:--------|:------------------------|
| Phase 0 (DONE) | none | none | Yes |
| Phase 1 | FR-DAT-001, FR-DAT-003, FR-DAT-004, FR-DAT-005, FR-DAT-006 (seed), FR-DAT-007 | NFR-PERF-001, NFR-PERF-002, NFR-PERF-004, NFR-SEC-001 | Yes |
| Phase 2 | FR-MS-001, FR-MS-002, FR-MS-003, FR-MS-004, FR-MS-006, FR-MS-007 | none | Yes |
| Phase 3 | FR-RTA-001, FR-RTA-002, FR-RTA-003, FR-RTA-004 | none | Yes |
| Phase 4 | FR-RTA-005, FR-RTA-006 | NFR-PERF-002 | Yes |
| Phase 5 | FR-DAT-002, FR-DAT-006, FR-DAT-007 | NFR-PERF-001, NFR-SEC-001 | Yes |
| Phase 6 | FR-VV-001, FR-VV-002, FR-VV-003, FR-VV-004, FR-VV-005 | NFR-REL-001 | Yes |
| Phase 7 | FR-MS-005 | NFR-PERF-003 | Yes |

Coverage result: FR 25 of 25 (FR-MS 7 of 7, FR-RTA 6 of 6, FR-DAT 7 of 7, FR-VV 5 of 5). NFR 6 of 6. Result: PASS.

Overlaps are by design. Phase 1 seeds FR-DAT-006 and FR-DAT-007, and Phase 5 completes them. Phase 1 task 1.7 and the Phase 2 CSA annotation also cite FR-RTA-002 and FR-RTA-003 as VTM work, which is incidental.

3. Path citations: 97 unique backtick paths and file names are cited. 64 exist in the working tree, including `docs/migration-map.md`. The remaining 33 are 28 paths marked "(created)" in a named task, the external prerequisite `.pulse/` (stated as not in the repository), the endpoint name `/health`, and 3 bare test file names that resolve to existing files under `vv/tests/OQ/` and `vv/tests/PQ/`. Result: PASS.

4. Writing constraints on `DEVELOPMENT_PLAN.md`: zero banned words from the list, zero em or en dashes, zero curly quotes, zero non-ASCII characters, zero bolded-term list openings, zero Conclusion, Challenges, or Future Prospects headings, zero emoji or checkmark glyphs, and zero occurrences of the puffed-verb or contrast constructions. Result: PASS.
