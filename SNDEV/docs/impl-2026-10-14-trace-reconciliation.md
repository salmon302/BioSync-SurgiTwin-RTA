Title: VTM and protocol register reconciliation
Date: 2026-10-14T18:20:00Z
Author: Seth Nenninger (MiMo Agent)
Contribution Type: Implementation
Ticket/Context: Traceability gaps recorded in SNDEV/docs/impl-2026-10-14-protocol-register.md
Summary: Resolves the fifteen docstring-only register rows, the task 1.9 overlap on FR-DAT-006, the PQ-1/PQ-8 citations in test_uvloop_enabled.py, and the pending-amendment pointer, bringing vv/traceability/vtm.md and vv/tests/protocol-register.md into agreement.

## 1. Task Reference

The uncertainty list in `SNDEV/docs/impl-2026-10-14-protocol-register.md` (section 3, open items) and the open mapping items in `vv/tests/protocol-register.md`. Ground truth was taken from the test code of the files named below, from `DEVELOPMENT_PLAN.md` Phase 1 (task 1.9 done at f4b9d8f, gates G1.1 through G1.8) and Section 5.3, and from `SRS.md` Sections 3 and 4. No test runs and no source code edits were performed.

## 2. Specification Summary

* For each of the fifteen rows marked "Docstring only, not in VTM", read the file's assertions and fixtures, decide which requirement IDs the assertions actually cover, then apply one of: (a) append the file path to the VTM test method cell of each covered requirement while keeping the cell's other content, (b) correct the register row's requirement IDs, or (c) mark the row "infrastructure" when no SRS requirement is exercised.
* Resolve the task 1.9 overlap: the VTM FR-DAT-006 cell cites a planned `vv/tests/OQ/test_oq_fr_dat_006_unique_credentials.py`, but task 1.9 is done at f4b9d8f and the unique-credential and shared-account rejection cases live in `vv/tests/OQ/test_oq_fr_dat_006_access_control.py`. Update the VTM cell to cite the existing file and either mark the planned register row DONE-BY or merge it.
* Re-map `middleware/tests/test_uvloop_enabled.py` in the register from the Gateway identities PQ-1 and PQ-8 to its SurgiTwin identity: gate G1.5 verification, requirement FR-DAT-001, and the NFR-PERF-002 relay path. Align the VTM FR-DAT-001 and NFR-PERF-002 cells.
* Point the register summary at `docs/srs-v1.1-change-proposal.md` (commit e5b0b14) as the pending SRS amendment artifact instead of only DEVELOPMENT_PLAN.md Section 6.
* Note any planned register row whose file name conflicts with the DEVELOPMENT_PLAN.md Section 5.3 naming convention, without renaming planned files.

## 3. Implementation Notes

Files changed:

* `vv/traceability/vtm.md` (test method cells of 11 rows edited: FR-DAT-001, FR-DAT-003, FR-DAT-004, FR-DAT-005, FR-DAT-006, FR-DAT-007, FR-RTA-005, NFR-PERF-001, NFR-PERF-002, NFR-PERF-004, NFR-SEC-001)
* `vv/tests/protocol-register.md` (15 mapping rows updated, 1 planned row merged away, 1 row re-mapped, summary counts and pointer updated, open items rewritten)
* `SNDEV/docs/impl-2026-10-14-trace-reconciliation.md` (this log)

### 3.1 Per-file resolution of the fifteen docstring-only rows

Resolution key: (a) appended to the VTM test method cell for the requirement, register mapping source changed to VTM; (b) register requirement IDs corrected to what the assertions cover, then the corrected IDs appended to the VTM cells; (c) marked infrastructure.

| File | Resolution | Requirement IDs after reconciliation | Evidence (assertion or fixture) |
| :--- | :--- | :--- | :--- |
| vv/tests/OQ/test_oq_fr_dat_004_truncate_cascade_devices.py | (a) | FR-DAT-003, FR-DAT-004 | test_truncate_cascade_on_devices_rejected: `assert "append-only" in message.lower()`, `assert after == before` |
| vv/tests/OQ/test_oq_fr_dat_005_json_types.py | (a) | FR-DAT-005 | test_digest_equivalence_in_data_new_position: `assert sql == python`; test_chain_rows_verify_in_sql_and_python: `verify_hash_chain()` returns `("ok", None)` |
| vv/tests/OQ/test_oq_fr_dat_006_access_control.py | (a) | FR-DAT-006 | TestSharedAccountRejection.test_shared_account_creation_rejected (10 parametrized cases against `users_username_individual` and the unique keys); test_application_identity_change_is_rejected: `assert "frozen" in str(...)` |
| vv/tests/PQ/test_pq_relay_sessions.py | (a) | NFR-PERF-001, NFR-PERF-002, NFR-PERF-004 | test_g18_relay_sessions: `assert report["concurrency"]["connected_at_start"] == cfg.sessions`, `assert report["audit_parity"]["verdict"] == "PASS"`; report block `latency_ms` carries the p95 verdict against `NFR_PERF_002_P95_MS = 50.0`; `throughput` block records `accepted_points_per_s_send_window` |
| middleware/tests/test_actor_propagation.py | (a) | FR-DAT-004 | test_api_write_records_subject_not_login_role: `assert rows[1]["actor_id"] == username`; TestActorDoesNotLeakThroughPool.test_next_session_on_the_same_connection_has_no_actor |
| middleware/tests/test_fhir_validation.py | (a) | FR-DAT-007 | test_wrong_value_type_is_rejected_by_fhir_resources: `assert outcome["resourceType"] == "OperationOutcome"`; test_operation_outcome_format |
| middleware/tests/test_hash_chain.py | (a) | FR-DAT-005 | test_verify_chain_tampered_data: `assert broken_at == 3`; test_compute_hash_chain_links: `entries[1]["prev_hash"] == entries[0]["current_hash"]` |
| middleware/tests/test_lttb.py | (b) then (a) | NFR-PERF-001 (FR-RTA-005 dropped) | FR-RTA-005 has no assertion support: the file contains no One Euro, EMA, MANO, or jitter case; test_output_size_matches_threshold and test_retains_isolated_spike are LTTB downsampling invariants, and docs/migration-map.md maps both `middleware/engine/lttb.py` and `middleware/tests/test_lttb.py` to NFR-PERF-001 |
| middleware/tests/test_p0_compliance.py | (a) | FR-DAT-007, FR-RTA-005 | test_resolve_channel_from_loinc_code (LOINC coding on a FHIR Observation); test_ema_filter_applies_with_per_channel_alpha: filtered value lies between the raw 200.0 and 140.0 samples (EMA smoothing) |
| middleware/tests/test_relay_offloop_persistence.py | (a) | FR-DAT-001, NFR-PERF-001, NFR-PERF-002 | test_relay_routes_do_not_reference_session_or_commit (`assert token not in source` for `get_db`, `.commit(`); test_successful_batches_feed_the_ingestion_throughput_metric (`ingestion_rate_pps`); test_slow_database_write_does_not_stall_the_event_loop: `assert max(gaps) < 0.15` |
| middleware/tests/test_relay_postgres_integration.py | (a) | FR-DAT-001, FR-DAT-003, FR-DAT-004, FR-DAT-005 | test_telemetry_sessions_rows_cannot_be_updated_deleted_or_truncated: `_rejected(..., "append-only")`; test_relay_session_persists_samples_session_rows_and_hash_chained_audit: `verify_hash_chain()` scalar `"ok"`, audit tuples with actor and reason |
| middleware/tests/test_relay_response_time.py | (a) | NFR-PERF-001, NFR-PERF-002 | test_websocket_relay_sample_is_recorded_by_track_ws_relay: `assert relay["target_p95_ms"] == NFR_P3_WS_P95_MS == 50.0`; test_sample_windows_are_bounded: `assert snapshot["throughput"]["ingestion_rate_pps"]["count"] == SAMPLE_WINDOW` |
| middleware/tests/test_relay_session_records.py | (b) then (a) | FR-DAT-001, FR-DAT-004, NFR-SEC-001 (FR-DAT-003 dropped) | The file has no UPDATE, DELETE, or TRUNCATE rejection assertion; its own docstring defers database behavior to test_relay_postgres_integration.py. Kept: test_session_writes_open_then_finalized_rows_with_points_and_identity (FR-DAT-001), test_sink_writes_one_hash_chained_audit_row_per_session_record (`insert_audit_log` with reason, actor, and `data_new`) (FR-DAT-004), test_missing_and_invalid_tokens_are_refused (close code 4401) (NFR-SEC-001) |
| middleware/tests/test_roles_scope.py | (a) | FR-DAT-006 | test_missing_or_wrong_scope_rejected_with_403 (9 parametrized claim forms); TestScopeClaimParsing.test_parses_each_claim_form |
| middleware/tests/test_scope_enforcement.py | (a) | FR-DAT-006, NFR-SEC-001 | test_substring_or_missing_scope_is_refused_with_4403 (11 parametrized claims); TestWebSocketReadScope.test_exact_read_scope_is_accepted |

Resolution counts: (a) 13 files, (b) 2 files, (c) 0 files. After the edits no register row carries the source "Docstring only, not in VTM", so that key entry was removed from the mapping source key.

The access-control module also contains TestApplicationRoleBoundary (`test_trigger_disable_and_alter_attempts_fail`, `test_truncate_fails_for_application_role`). That class overlaps the G1.1 scope (FR-DAT-003), but DEVELOPMENT_PLAN.md assigns all of task 1.9, including the owner and application role split, to gate G1.4 with requirement FR-DAT-006, and the G1.4 PASS note reads "application role cannot disable triggers or truncate". The register row therefore stays at FR-DAT-006 and is not expanded to FR-DAT-003 or FR-DAT-004.

### 3.2 Task 1.9 overlap (resolution 2)

Approach chosen: merge. The VTM FR-DAT-006 test method cell now reads "existing: `middleware/tests/test_api_auth.py`, `vv/tests/OQ/test_oq_fr_dat_006_access_control.py`, `middleware/tests/test_roles_scope.py`, `middleware/tests/test_scope_enforcement.py`; signatures and lockout planned (tasks 5.2 and 5.3): `vv/tests/OQ/test_oq_fr_dat_006_signatures.py`". The planned citation `vv/tests/OQ/test_oq_fr_dat_006_unique_credentials.py` is removed because task 1.9 is done at f4b9d8f and no VTM cell names that file any more. The register row OQ-FR-DAT-006-UNIQUE-CREDENTIALS is deleted and its scope is carried by OQ-FR-DAT-006-ACCESS-CONTROL, whose mapping source records "VTM; task 1.9 done at f4b9d8f (unique-credential scope merged here)". Merge was chosen over a DONE-BY status because a third status value would fall outside the Existing and Planned columns of the summary table, and because the register lists planned protocols only when a VTM cell names them.

Count effect: PLANNED 27 becomes 26, total rows 67 becomes 66, OQ planned 14 becomes 13. The planned citation reconciliation in SNDEV/docs/impl-2026-10-14-protocol-register.md section 3 changes from 33 citations to 32: 26 planned rows + 2 duplicate-directory citations + 3 task 1.6 locustfile citations + 1 task 1.8 audit-capture citation = 32.

### 3.3 test_uvloop_enabled.py (resolution 3)

Register row UT-UVLOOP-ENABLED: requirement IDs become "FR-DAT-001, NFR-PERF-002"; mapping source becomes "VTM; gate G1.5". The PQ-1 and PQ-8 identifiers are dropped from the row; they are BioSync-Gateway protocol identities and this repository has no PQ-1 or PQ-8 file. NFR-PERF-001 is dropped from the row because gate G1.5 names FR-DAT-001 only and the plan's relay path for this file is NFR-PERF-002 (task 1.5, Gateway R3, gate G1.5). VTM alignment: the FR-DAT-001 cell already cites `middleware/tests/test_uvloop_enabled.py` as existing and needed no change; the NFR-PERF-002 cell did not cite it, so the citation was added there with the descriptor "uvloop policy at startup". The file's own assertions are test_uvloop_pinned_in_requirements and test_configure_uvloop_applies_policy_when_package_present, which is the G1.5 "uvloop policy test green" evidence.

### 3.4 Pending amendment pointer (resolution 4)

The register summary paragraph now reads that the pending SRS amendment is recorded in `docs/srs-v1.1-change-proposal.md` (commit e5b0b14) and tracked under DEVELOPMENT_PLAN.md Section 6 until SRS v1.1 is issued.

### 3.5 Naming convention check (resolution 5)

Every planned register row whose VTM cell gives a file name follows the Section 5.3 patterns: `vv/tests/OQ/test_oq_<req-id-lowercase>_<topic>.py` and `vv/tests/PQ/test_pq_<req-id-lowercase>_<topic>.py`. No planned file name conflicts with the convention, so no rename was proposed. The one register entry whose file name deviates from the convention is the existing `vv/tests/PQ/test_pq_relay_sessions.py`, which has no requirement ID in its name; that deviation is already recorded as an open mapping item in the register and is not renamed here. The rows that cite directories or a CI job (`.github/workflows/ci.yml`, `rta/tests/`, `vv/xil/`) carry no file name to check.

## 4. Verification

Method: PowerShell checks run against the working tree after the edits. No test executions, per the task instruction. No test evidence is claimed by this log.

* ID sweep: `Select-String` over SRS.md with the pattern `(FR-MS-\d{3}|FR-RTA-\d{3}|FR-DAT-\d{3}|FR-VV-\d{3}|NFR-PERF-\d{3}|NFR-SEC-\d{3}|NFR-REL-\d{3})` returns 31 distinct IDs. The VTM first column has 31 rows. Missing 0, dangling 0, set equality in both directions holds. Result: PASS.
* VTM cited paths: 84 backticked paths were extracted from the test method cells of the 31 rows. Each path either resolves under the repository root or its cell carries a planned or exploratory marker. Violations 0. Result: PASS.
* Register requirement IDs: 66 rows were parsed; every requirement ID in every row resolves to an SRS.md definition, with the literal "infrastructure" excluded from that check. Bad IDs 0. Protocol IDs are unique (66 of 66). Result: PASS.
* Register summary reconciliation: recounted rows give IQ 7 existing and 0 planned, OQ 14 existing and 13 planned, PQ 3 existing and 6 planned, unit 16 existing and 4 planned, unspecified 0 existing and 3 planned. EXISTING 40 + PLANNED 26 = 66 rows, which equals the summary table (Total 40, 26, 66) and the status line (EXISTING 40, PLANNED 26). Result: PASS.
* Planned citation reconciliation: the VTM now contains 32 "planned (task" citations after the task 1.9 citation was removed. 26 planned rows + 2 duplicate-directory citations (tasks 3.8 and 3.9) + 3 task 1.6 locustfile citations + 1 task 1.8 audit-capture citation = 32. Result: PASS.
* Docstring-only residue: a scan of `vv/tests/protocol-register.md` for rows carrying "Docstring only, not in VTM" returns 0 rows (the phrase survives only in the open item that records the reconciliation). Result: PASS.
* Table structure: all 31 VTM rows still split into 8 table fields, so no edited test method cell broke a column boundary. Result: PASS.
* Bidirectional spot check: for five requirements in different subsystems, the set of test files in the VTM test method cell was compared with the set of register file paths whose requirement IDs include that ID. FR-MS-006 (Pulse physiology bridge): 4 files versus 4 rows, agree. FR-RTA-001 (RTA C++ safety core): 2 versus 2, agree. FR-DAT-004 (PostgreSQL audit triggers): 8 versus 8, agree. FR-DAT-007 (FHIR mapping): 4 versus 4, agree. NFR-SEC-001 (transport and database isolation): 4 versus 4, agree. Result: PASS, 5 of 5.
* Writing constraints: a scan of the three files found 0 banned words, 0 em or en dashes, 0 curly quotes, and 0 check glyphs. Result: PASS.
* Gate runs: not executed. The next step is the commit of the three files owned by this task.
