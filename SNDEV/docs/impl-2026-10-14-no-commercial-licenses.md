Title: No commercial licenses in development; open-source substitutes and recorded deviations
Date: 2026-10-14T22:35:52Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: plan-owner decision 2026-10-14 (no commercial licenses in development)
Summary: DEVELOPMENT_PLAN.md restates the commercial-tool rows, gates, and risks as open-source substitutes with recorded deviations, and leaves commercial tools as adopter options.

## Task Reference

Plan-owner decision by the user, 2026-10-14: no commercial licenses are used in this project's development. The commercial tools named in the plan (Parasoft C/C++test or QA-MISRA, VectorCAST, Cantata, Jama, and Polarion) are adoption options for licensees of the software, not development preconditions. Development uses open-source substitutes. Where no open-source substitute exists, the gap is recorded as a deviation in the plan and the risk file, following the existing pattern for the Python MC/DC gap and the VAL-024 partitioning item.

## Specification Summary

Edit the development plan so that:

1. Section 2 commercial rows record "not procured in development" and an adoption option for licensees. The version cell names the open-source substitute.
2. Section 5.1 names the pinned open-source check set (candidates cppcheck and clang-tidy, selected in task 3.7) and records that neither candidate implements MISRA C++:2023.
3. Section 5.2 names gcov-family tooling with Catch2 and CTest for High Process Risk C++, and records the MC/DC target as a deviation.
4. Gates G3.1, G6.1, G6.4, and G6.5 are restated with measurable acceptance statements and their requirement IDs.
5. Tasks 3.7, 3.8, 6.2, 6.5, and 6.6 are restated for open-source tooling.
6. Section 7.2 proprietary-tool qualification mitigation records the decision. Section 7.3 license procurement risk is removed.
7. The header Status line and the Phase 3 status paragraph carry a one-clause pointer to this log.

Scope limit: SRS.md, vv/traceability/vtm.md, docs/migration-map.md, docs/procurement-guide.md, and sim/SOUP.md are not edited. The SRS and VTM metric cells that assume commercial tooling are listed under Document owner follow-up.

## Implementation Notes

File changed: `DEVELOPMENT_PLAN.md` only. Plan edits are listed in the order they appear in the file.

| Edit | Location | Change |
|:-----|:---------|:-------|
| E0 | Header Status line | Added the 2026-10-14 decision clause with a pointer to this log. Existing status sentences unchanged. |
| E0b | Section 1.2 principle 5 | "checked against MISRA C++:2023" became "checked with an open-source static analysis set"; MISRA conformity stated as adopter-supplied. Added for consistency with E1 to E10. |
| E1 | Section 2, static analysis row | License cell: not procured in development, adoption option for licensees only. Version cell: development pins the task 3.7 open-source check set. |
| E1 | Section 2, coverage and timing row | License cell: not procured, adoption option (Vector Informatik, QA Systems). Version cell: development pins gcov-family tooling with Catch2 and CTest (task 3.8). |
| E1 | Section 2, trace management row | License cell: not procured, adoption option. Version cell: development pins the repository-native trace store; Jama or Polarion push is optional. |
| E2 | Section 4 Phase 3 goal | "with MISRA, WCET, and MC/DC evidence first" became "with static analysis, WCET, and MC/DC evidence first". |
| E2 | Section 5.1 table | Tool column for `rta/` and `sim/sofa`, `sim/bridge`, `sim/fmi` rows now names the pinned open-source set (candidates cppcheck and clang-tidy). Check column states zero findings. |
| E2 | Section 5.1, paragraph after the table | Recorded gap sentence: neither candidate implements MISRA C++:2023; gates G3.1 and G6.1 are restated; MISRA conformity is adopter-supplied. |
| E3 | Section 5.2, High Process Risk C++ row | Coverage target marks MC/DC as a recorded deviation. Test method names gcov-family tooling (gcov or llvm-cov) with CTest and Catch2. |
| E3 | Section 5.2, High Process Risk Python row | Added "pytest-cov, pinned in task 3.8 or earlier". Target unchanged at statement and branch. |
| E3 | Section 5.2, paragraph after the table | MC/DC deviation paragraph: gcov-family tooling reports statement and branch; task 3.8 evaluates Clang 19 or newer llvm-cov MC/DC reporting as a candidate, not a commitment; deviation recorded until verified or an adopter supplies a tool. |
| E4 | Phase 3 table, G3.1 | Restated (see Restated gate texts). |
| E5 | Phase 3 table, task 3.7 | Retitled as the open-source static analysis gate; tool versions pinned; deviation register kept in `vv/traceability/`. |
| E6 | Phase 3 table, task 3.8 | gcov-family plus Catch2 and CTest for statement and branch; MC/DC evaluation recorded as a work item; pytest-cov pinned. |
| E6b | Phase 3 CSA annotation | "require 100% statement, branch, and MC/DC coverage on VectorCAST or Cantata" became statement and branch on gcov-family tooling, with MC/DC as a recorded deviation. |
| E6c | Phase 3 status paragraph | Added the no-commercial-license clause with a pointer to this log. Existing sentence unchanged. |
| E7 | Phase 6 status | "Requires the license procurement in Section 7.3" became "No license procurement is required (decision of 2026-10-14)." |
| E7 | Phase 6 tasks 6.2, 6.5, 6.6 | 6.2: open-source static analysis gate on every C++ core. 6.5: gcov-family coverage reporting in CI. 6.6: writes links to the repository-native store; Jama or Polarion push is an optional adapter. |
| E8 | Phase 6 gates G6.1, G6.4, G6.5 | Restated (see Restated gate texts). |
| E9 | Section 5.4 item 5 | Replaced the "until the ALM tool is licensed" sentence with the repository-native store statement. Added for consistency with E7. |
| E10 | Section 7.2, proprietary tool qualification row | Mitigation records the decision: no commercial tool in development; conformity claims limited to the open-source set; deviations in risk file and deviation register; adopter note points at the optional commercial path. Impact, risk name, and the other rows unchanged. |
| E11 | Section 7.3, license procurement row | Row deleted. The decision removes the procurement risk, so no residual line is kept in the table. |

Not changed, and out of scope for this decision: Section 2 HIL target row (hardware order and vendor XIL software), Section 2 Omniverse row (NVIDIA license terms), Section 2 XIL row, and Section 7.3 HIL lead-time row. These are hardware or runtime items, not the commercial tool set named in the decision. Section 7.2 Python MC/DC row and C++17 row unchanged.

## Restated gate texts

G3.1 Simplex core (FR-RTA-001): Zero findings from the pinned open-source check set on `rta/` with the deviation register attached; 100% statement and branch coverage, and the MC/DC target recorded as a deviation (Section 5.2) until an MC/DC path is verified; zero heap allocations in the decision path under an allocator hook. MISRA C++:2023 conformity is verified only if an adopter runs a conforming tool.

G6.1 Static analysis (FR-VV-001): Zero findings from the pinned open-source check set on every commit across `rta/`, `sim/sofa`, `sim/bridge`, and `sim/fmi`, with the C++17 pin verified and the deviation register attached. MISRA C++:2023 conformity is verified only if an adopter runs a conforming tool.

G6.4 Coverage and timing (FR-VV-004): 100% statement and branch coverage on High Process Risk C++ modules, with the MC/DC target carried as a recorded deviation (Section 5.2) until an MC/DC path is verified, and a WCET bound with its statistic reported for each timed task.

G6.5 Traceability (FR-VV-005): 31 of 31 defined IDs have forward and backward trace links, zero unlinked dead-code findings from the named tool, and every link hash is recorded. The store is the repository-native one (VTM and protocol register).

## Verification

Run on the working tree after the plan edits, before commit.

| Check | Command or method | Result |
|:------|:------------------|:-------|
| Commercial names appear only as adopter options | `Select-String` on DEVELOPMENT_PLAN.md for Parasoft, QA-MISRA, VectorCAST, Cantata, Jama, Polarion. Lines 50, 51, 57 (Section 2, adoption option cells), 342 (task 6.6, optional adapter), 433 (Section 5.4, optional adapter), 492 (Section 7.2, adopter note). No Section 5.1 table cell names a commercial tool. | PASS |
| No sentence states a commercial tool is procured or required for development | Same grep; the only "required" or "procurement" wording left is "No license procurement is required (decision of 2026-10-14)" at Phase 6 status. | PASS |
| Restated gates name requirement ID and measurable acceptance | G3.1 (FR-RTA-001), G6.1 (FR-VV-001), G6.4 (FR-VV-004), G6.5 (FR-VV-005) each show a numeric or count-based acceptance statement. | PASS |
| G6.4 keeps statement and branch with MC/DC as deviation | Gate text above. | PASS |
| SRS.md and vv/traceability/vtm.md untouched | `git diff --stat` before commit shows only DEVELOPMENT_PLAN.md. The final check is repeated after commit. | PASS |
| Other protected files untouched | `git diff --stat` shows no change to docs/migration-map.md, docs/procurement-guide.md, or sim/SOUP.md. | PASS |
| Banned words in inserted text | Grep of added lines against the full banned-word list in the agent documentation constraints (21 terms). | PASS, zero matches |
| Em dashes and en dashes in inserted text | Grep of added lines for U+2014 and U+2013. | PASS, zero matches |
| Curly quotes in inserted text | Grep of added lines for U+201C, U+201D, U+2018, U+2019. | PASS, zero matches |

## Document owner follow-up

The SRS.md v1.1.0 and vv/traceability/vtm.md metric or method cells below still assume commercial tooling or the MC/DC obligation. They are not edited here. The document owner decides on an SRS v1.2 amendment or an adopter-facing deviation note, following the VAL-024 precedent.

SRS.md v1.1.0, Section 5 table (quoted cells):

* FR-RTA-001 (line 97). Metric cell: "Zero MISRA C++:2023 violations on `rta/` under the C++17 pin with every deviation recorded in the register, 100% statement, branch, and MC/DC coverage, and zero heap allocations in the decision path under an allocator hook". Method cell: "Static Analysis (Parasoft/QA-MISRA) + ... (VectorCAST)", with the middle words elided.
* FR-VV-001 (line 105). Metric cell: "Zero MISRA C++:2023 violations on every commit across the C++17-pinned safety cores with the deviation register attached". Method cell: "Parasoft C/C++test or QA-MISRA run on every commit across `rta/`, `sim/sofa/`, `sim/bridge/`, and `sim/fmi/` under the C++17 pin, with a documented deviation register".
* FR-RTA-002 (line 98). Method cell: "Scripted fault-injection timing test (ASAM XIL EES Port) with VectorCAST or Cantata coverage on the C++ predictor". Metric cell names no tool.
* FR-VV-005 (line 106). Method cell: "Automated CI/CD Traceability Audit (Jama / Polarion API)". Metric cell names no tool.

SRS.md v1.1.0, clause text (not in Section 5):

* Line 19, numbered item 4 of the SRS list: "enforces MISRA C++:2023 static analysis, structural coverage (MC/DC), and bidirectional requirements traceability".
* Line 30, Section 2.2 High Process Risk definition: "100% statement, branch, and Modified Condition/Decision Coverage (MC/DC)". Document-level, applies to all High Process Risk rows.
* Line 68, FR-VV-001 requirement: "(via **Parasoft C/C++test** or **QA-MISRA**)".
* Line 71, FR-VV-004 requirement: "(**VectorCAST**, **Cantata**, **Catch2**, **CTest**, and **Pytest**)" and "enforce 100% statement, branch, and **MC/DC** structural coverage".
* Line 72, FR-VV-005 requirement: "(**Jama** or **Polarion**)".

vv/traceability/vtm.md (quoted cells):

* FR-RTA-001 (line 16). Method cell: "MISRA C++:2023 static analysis (Parasoft C/C++test or QA-MISRA, C++17 pin, deviation register) plus structural coverage with VectorCAST or Cantata, Catch2, and CTest". Metric cell: "...100% statement, branch, and MC/DC coverage...".
* FR-VV-001 (line 29). Method cell: "Parasoft C/C++test or QA-MISRA run on every commit...". Metric cell: "Zero MISRA C++:2023 violations on every commit across the C++17-pinned safety cores...".
* FR-VV-004 (line 32). Method cell: "VectorCAST or Cantata with Catch2, CTest, and Pytest...". Metric cell: "100% statement, branch, and MC/DC coverage reported for each High Process Risk C++ module...". No SRS Section 5 row exists for FR-VV-004; the VTM row is the only metric.
* FR-VV-005 (line 33). Method cell: "...pushing links to Jama or Polarion when the ALM tool is licensed (task 6.6)...".
* MC/DC coverage obligation in the method cell (not the metric cell): FR-MS-002 (line 10), FR-MS-003 (line 11), FR-MS-004 (line 12), FR-MS-007 (line 15), FR-RTA-002 (line 17, also VectorCAST or Cantata), FR-RTA-003 (line 18), FR-RTA-004 (line 19), FR-RTA-006 (line 21), NFR-PERF-002 (line 35), and NFR-REL-001 (line 39).

Requirement IDs for the follow-up list: FR-RTA-001, FR-RTA-002, FR-RTA-003, FR-RTA-004, FR-RTA-006, FR-MS-002, FR-MS-003, FR-MS-004, FR-MS-007, FR-VV-001, FR-VV-004, FR-VV-005, NFR-PERF-002, NFR-REL-001.

Also note: the VTM line 45 explanatory note states that the folded metrics are "approved for gate use". The FR-RTA-001 and FR-VV-001 metrics carry the VAL-016 and VAL-024 fold-in. Any SRS v1.2 change must update the VTM rows in the same change.

Cross-check result: the SRS grep found MC/DC or tool names in lines 19, 30, 68, 71, 72, 97, 98, 105, 106. The VTM grep found 15 matching lines (10 to 19, 21, 29, 32, 33, 35, 39), and the grep of SRS table rows for FR-VV-004 returned no match, which confirms the SRS has no FR-VV-004 Section 5 row.
