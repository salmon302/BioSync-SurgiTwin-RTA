Title: Validation protocol register creation (VAL-002 mitigation)
Date: 2026-10-14T17:56:26Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 6 task 6.1 brought forward; audit finding VAL-002
Summary: Creates vv/tests/protocol-register.md listing 40 existing and 27 planned protocol rows, and corrects a stale TLS comment in middleware/tests/dbsupport.py.

## 1. Task Reference

DEVELOPMENT_PLAN.md Phase 6 task 6.1 (brought forward) and Section 5.3. Audit finding VAL-002: SRS.md NFR-REL-001 and FR-MS-006 cite "19 IQ/OQ/PQ validation protocols" without defining them.

## 2. Specification Summary

* Create `vv/tests/protocol-register.md`. Each row gives the protocol ID, phase, status, file path, and requirement IDs. Rows are sorted by phase, then protocol ID.
* Add planned protocols from the VTM rows whose test method cell reads "planned (task N.N)", marked PLANNED, without inventing requirement mappings.
* Open the register with a summary block of counts by phase and status.
* Correct the module docstring in `middleware/tests/dbsupport.py`, which said the application-role module skips under TLS. Commit 99ec666 made that matrix run under TLS through SET ROLE with zero skips. The change is a comment only.

## 3. Implementation Notes

Files changed:

* `vv/tests/protocol-register.md` (new)
* `middleware/tests/dbsupport.py` (docstring lines 15 and 16 rewritten; no code change)
* `SNDEV/docs/impl-2026-10-14-protocol-register.md` (new)

Enumeration method: PowerShell `Get-ChildItem` over `vv/tests/IQ`, `vv/tests/OQ`, `vv/tests/PQ`, `middleware/tests`, and `rta/tests`, excluding `__pycache__`. Each file's docstring and comments were searched with `Select-String` for FR-, NFR-, VAL-, IQ, OQ, PQ, and gate labels. Totals found: 7 IQ modules, 11 OQ modules under `vv/tests/OQ`, 3 OQ modules under `middleware/tests` (Gateway-numbered), 3 PQ modules, 15 unit and integration modules under `middleware/tests`, and 1 C++ smoke suite under `rta/tests`. Support modules (two `conftest.py` files, `middleware/tests/dbsupport.py`, and `vv/tests/PQ/locustfile.py`) are listed in a separate table and are not counted as protocols.

Mapping authority: the interim VTM at `vv/traceability/vtm.md`. A file's requirement IDs come from its VTM cell where the VTM cites that file. For fifteen files that the VTM does not cite, the IDs come from the file docstring, and the register marks those rows "Docstring only, not in VTM". Three files cite no SRS requirement and are marked infrastructure: IQ-2, IQ-5, and UT-SMOKE.

Protocol ID derivation: IQ from the file number; Gateway-numbered OQ and PQ files keep their numbers; new-named files use the requirement ID and topic from the file name, uppercase with hyphens; unit modules use the prefix UT- followed by the file name without `test_`.

Count reconciliation: the VTM contains 33 "planned (task N.N)" citations. The register contains 27 PLANNED rows. The difference is accounted for as follows:

* 2 duplicate citations. Task 3.8 is cited for FR-RTA-001 and FR-VV-004, and both point to `rta/tests/`, so they share one row. Task 3.9 is cited for FR-RTA-002 and FR-RTA-004, and both point to `vv/xil/`, so they share one row.
* 3 citations of task 1.6 for `vv/tests/PQ/locustfile.py`. The file exists and is listed as a support module.
* 1 citation of task 1.8 for `vv/tests/OQ/test_oq_fr_dat_004_audit_capture.py`. The file exists and is listed as EXISTING.

Result: 27 + 2 + 3 + 1 = 33.

Open items recorded in the register: the FR-DAT-006 planned file for task 1.9 may duplicate the existing access-control module, and the plan marks task 1.9 done. The register does not merge the two rows. The two untracked PQ files and the modified 1M-row PQ file were present on disk at the time of enumeration.

## 4. Verification

Method: PowerShell checks run against the working tree. No tests were executed, per the task instruction.

* Row count: 67 rows, equal to 40 EXISTING plus 27 PLANNED. Protocol IDs are unique (67 of 67). Phase counts: IQ 7 existing; OQ 14 existing and 14 planned; PQ 3 existing and 6 planned; unit 16 existing and 4 planned; unspecified 3 planned. Result: PASS.
* File paths: all 40 EXISTING paths resolve with `Test-Path`. Result: PASS.
* Planned paths: none of the 27 planned file paths exists in the repository, so each is marked PLANNED. Result: PASS.
* Citation reconciliation: the 33 VTM citations reconcile to the register as shown in section 3. Result: PASS.
* Writing constraints: a scan of `vv/tests/protocol-register.md` found no banned words, no em or en dashes, no curly quotes, and no check glyphs. Result: PASS.
* Comment-only change: `git diff` on `middleware/tests/dbsupport.py` limited to docstring text. Result: PASS (checked before commit).
* Gate runs: not executed. No test evidence is claimed by this log.
