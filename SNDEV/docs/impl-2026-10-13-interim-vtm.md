Title: Interim complete VTM for SurgiTwin-RTA SRS v1.0.0
Date: 2026-10-14T00:41:21Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 task 1.7 (closes VAL-001, VAL-003; mitigates VAL-005..016)
Summary: Published vv/traceability/vtm.md with exactly one row for each of the 31 requirement IDs defined in SRS.md Sections 3 and 4, each row carrying a test method and a measurable acceptance metric.

## Task Reference

DEVELOPMENT_PLAN.md Phase 1 task 1.7: "Publish the interim complete VTM with 31 rows, each carrying a measurable acceptance metric and a test method. Rename the FR-RTA-002 row to state prediction and add the FR-RTA-003 row (VAL-001, VAL-003)." Output: `vv/traceability/vtm.md`. Findings source: `SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md`.

## Specification Summary

SRS.md v1.0.0 defines 31 requirement IDs in Sections 3 and 4 (7 FR-MS, 6 FR-RTA, 7 FR-DAT, 5 FR-VV, 4 NFR-PERF, 1 NFR-SEC, 1 NFR-REL) but its Section 5 VTM (lines 89-100) carries rows for only 10 of them. This task published a complete interim VTM in `vv/traceability/vtm.md` with one markdown table of 31 rows. Each row carries: the requirement ID, the subsystem or module, one IEC 62304 class per row, the CSA risk classification from SRS Section 2.2, the verification method with concrete toolchain names from DEVELOPMENT_PLAN.md Section 2 (including the coverage obligation for High Process Risk rows), a test method citing real or planned files under the Section 5.3 naming convention, and a measurable acceptance metric (quantity, unit, and test condition). The VTM is marked interim: SRS.md v1.0.0 stays "draft with open validation findings" until SRS v1.1 incorporates the open items.

## Implementation Notes

Finding-by-finding handling in `vv/traceability/vtm.md`:

- VAL-001 (VTM covers 10 of 31 IDs): closed on an interim basis. All 31 defined IDs now have a row with a test method and an acceptance metric. The six NFRs, which had no row, now each carry a measurement point and a statistic.
- VAL-003 (FR-RTA-002 and FR-RTA-003 conflated): the FR-RTA-002 row is named "Timed Automata state prediction" and verifies bounded prediction under injected lag and delay. A separate FR-RTA-003 row verifies the biomechanical and spatial safety envelope, measured as minimum Euclidean distance to segmented vascular no-go zones (mm) and tissue wrench and shear thresholds (N) from the risk management file, with boundary cases one step below and one step above each threshold (gate G3.3).
- VAL-004 (no numeric RTA deadline): the FR-RTA-002 and FR-RTA-004 metrics are written against the candidate decision deadline derived from the Phase 3 WCET measurement (task 3.6). The number enters the VTM when that measurement lands; both metrics are marked proposed.
- VAL-005 ("zero quantization error" on FR-MS-007): replaced by a bounded clock-skew and message-jitter limit of at most 1 ms on a three-node Fast DDS co-simulation run with a reference clock and per-message timestamps (gate G2.6).
- VAL-006 (FR-MS-002 row numbers absent from the requirement, divergence undefined): the FR-MS-002 metric is a 16.7 ms solver step budget on the pinned reference scene plus a 30-minute load case with divergence defined as non-finite output or a monotonically growing strain-energy norm (gate G2.2).
- VAL-007 ("zero main-loop blocking" on FR-MS-006): replaced by a maximum event-loop heartbeat gap of at most 50 ms during a 10-minute run with 10 concurrent physiological simulations (gate G2.5).
- VAL-008 (IEC 62304 class attribution): every row states one class. Class C is used for High Process Risk rows per the SRS header. The three rows the audit flagged (FR-MS-002 with the "B/C" range, FR-MS-006 and FR-VV-005 with no class) are marked "(provisional)" and resolved to Class C, with the risk-file decision recorded as an open question for SRS v1.1. Not High Process Risk rows are marked "(provisional)" Class B.
- VAL-009 (DO-178C DAL A and ISO 26262 ASIL D): not carried as certification targets, per the DEVELOPMENT_PLAN.md Section 6.2 interim handling. IEC 62304 Class C governs; the FR-RTA-001 and FR-RTA-002 rows note the dropped citations.
- VAL-010 (FR-DAT-004 contradiction between mutation rejection and old/new capture): the metric is split into 100% rejection of UPDATE and DELETE on the WORM tables (existing OQ-7 and OQ-8) plus 100% audit-row capture with prior and new values for permitted changes on non-WORM tables (task 1.8, gate G1.2).
- VAL-011 (fallback controller verification unnamed): the FR-RTA-004 verification method names model checking of the discrete switch logic and a Lyapunov stability argument for the PID or LQR law (task 3.5).
- VAL-012 (no SOUP requirements): no SOUP row exists because SOUP is not one of the 31 defined IDs, and this VTM does not invent IDs. The gap is recorded here and stays open for the SRS v1.1 amendment.
- VAL-013 (OAuth unspecified, verify-full not demonstrated): the NFR-SEC-001 metric is 100% rejection of wrong-audience, expired, and unsigned tokens, plus TLS 1.3 with client-certificate verify-full as the production default and zero xfail markers in `middleware/tests/test_db_ssl_config.py` (gates G1.7 and G5.5).
- VAL-014 (unconditioned latency bounds): the NFR-PERF-002 metric names the measurement points, message format, load, and statistic: p95 WSS relay latency of at most 50 ms at 500 concurrent sessions, and p99 edge command latency of at most 10 ms over 10,000 MessagePack commands at the MCU-bridge point with the worst case reported (tasks 1.6 and 4.6, gates G1.8 and G4.3). The FR-RTA-006 row defers its latency leg to the same test.
- VAL-015 ("100% detection of below-application-layer tampering"): restated as detection of 100% of injected cases in the VAL-015 injection suite of task 1.2, which fixes row counts and tamper types, with the broken row ID reported within one nightly-verification cycle (gate G1.3).
- VAL-016 (MISRA C++:2023 against C++17/C++20): the FR-RTA-001 and FR-VV-001 metrics are written against the C++17 pin with a documented deviation register, per gate G3.1 and G6.1.
- VAL-017 (SiLA 2 label on the FR-DAT-007 row): the FR-DAT-007 row is labeled HL7 FHIR R4 mapping only, and FR-DAT-002 has its own SiLA 2 row.
- VAL-018 (throughput gate on the Not High FR-DAT-007 row): the throughput condition moved to the NFR-PERF-001 row; the FR-DAT-007 metric is schema validity, HTTP 422 with OperationOutcome, and value-set rejection (gates G1.6 and G5.4).
- VAL-019 (FR-RTA-006 baselines unnamed): the FR-RTA-006 metric names the JSON payload baseline for the 70% compression claim, the float32 model baseline for the 75% size claim, the accuracy floor set in task 4.4, and the 100%-of-1,000-trials offline fallback with bit-identical output (gates G4.2 and G4.4).
- VAL-020 (trace-link hashing and dead code undefined): the FR-VV-005 metric requires the stored hash of each trace link and zero unlinked dead-code findings from the named tool (task 6.6, gate G6.5).
- VAL-022 (FR-MS-004 "high frequencies"): the 500 Hz wrench publish rate now sits in the FR-MS-004 row, sustained for 10 minutes and measured at the ROS 2 subscriber (gate G2.4).
- VAL-023 (no window for "zero unresolved SIGSEGV"): the NFR-REL-001 metric fixes the window at a 24-hour sanitizer-enabled soak with the release exit condition, and replaces the "19 protocols" count with a 100% pass rate across every protocol in `vv/tests/protocol-register.md` (task 6.7, gate G6.6).

Test-method citations follow DEVELOPMENT_PLAN.md Section 5.3. Files that exist on disk at publication time: the seven IQ files, `test_oq_fr_dat_005_hash_crosscheck.py`, `test_oq_fr_dat_007_fhir_http.py`, `test_oq_fr_ms_006_pulse_fail_closed.py`, `test_oq_fr_rta_005_one_euro.py`, `test_oq_nfr_sec_001_jwt_secret.py`, `test_oq16_pulse_state_serialization.py`, `test_oq6_ema_convergence.py`, the two FR-DAT-005 PQ files, `rta/tests/test_smoke.cpp`, the Gateway-numbered `middleware/tests/test_oq7_update_rejection.py`, `test_oq8_delete_rejection.py`, `test_oq9_tamper_detection.py`, `test_api_auth.py`, `test_db_ssl_config.py`, `test_uvloop_enabled.py`, and `.github/workflows/ci.yml`. Files that do not exist yet are cited as "planned (task N.N)". Only FR-MS-005 uses "exploratory (not scripted)", which SRS Section 2.2 permits for Not High Process Risk rendering features.

## Verification

ID counts and set equality. Method: PowerShell `Select-String` over `SRS.md` with the regex `(FR-MS-\d{3}|FR-RTA-\d{3}|FR-DAT-\d{3}|FR-VV-\d{3}|NFR-PERF-\d{3}|NFR-SEC-\d{3}|NFR-REL-\d{3})` produced 41 total matches resolving to 31 distinct IDs (the 21 surplus matches are the 10 Section 5 VTM rows and in-text restatements). Definitions were isolated with the pattern `^\* \*\*(FR|NFR)-` on Sections 3 and 4: 31 definitions. The VTM table first column was extracted the same way from `vv/traceability/vtm.md`: 31 rows. Set comparison in both directions (every defined ID in the table, every table ID defined): PASS, 31 = 31, zero missing, zero dangling.

Test-path check: PASS. Every cited path either exists on disk (verified with `git ls-files` and `Get-ChildItem`) or carries the "planned (task N.N)" or "exploratory (not scripted)" marker.

Writing-constraint check: PASS. Both files were swept for the banned vocabulary list, em and en dashes, curly quotes, emojis, and checkmark glyphs; none present. Verification gates run: no build or test gate applies to this documentation-only change; `git status` and `git log --oneline` recorded at commit time. Note: this log uses the actual UTC timestamp 2026-10-14T00:41:21Z while keeping the 2026-10-13 file-naming date of the task-1.7 work batch.
