# Validation Protocol Register

Protocol register for SurgiTwin-RTA (finding VAL-002, DEVELOPMENT_PLAN.md Section 5.3 and task 6.1). Requirement mappings use the interim VTM at `vv/traceability/vtm.md` as the authority.

## Summary

The register lists every test module under `vv/tests/IQ`, `vv/tests/OQ`, `vv/tests/PQ`, `middleware/tests`, and `rta/tests` that exists in the repository, plus the planned protocols named by a VTM test method cell with "planned (task N.N)".

| Phase | Existing | Planned | Total |
| :--- | ---: | ---: | ---: |
| IQ | 7 | 0 | 7 |
| OQ | 14 | 14 | 28 |
| PQ | 3 | 6 | 9 |
| unit | 16 | 4 | 20 |
| unspecified | 0 | 3 | 3 |
| Total | 40 | 27 | 67 |

Status totals: EXISTING 40, PLANNED 27. Of the existing rows, 3 are infrastructure (IQ-2, IQ-5, UT-SMOKE) and cite no SRS requirement. The "unspecified" phase marks planned rows whose VTM cell names a CI job, a directory, or a `vv/xil/` script set without giving a phase.

This register replaces the undefined "19 protocols" count in SRS NFR-REL-001 and FR-MS-006 (VAL-002). Protocols are counted here by their rows. The SRS amendment is open under DEVELOPMENT_PLAN.md Section 6 until SRS v1.1 is issued.

Support modules are not counted as protocols: `vv/tests/conftest.py`, `middleware/tests/conftest.py`, `middleware/tests/dbsupport.py`, and `vv/tests/PQ/locustfile.py`. The last file is the Locust load definition that the VTM marks as planned (task 1.6) for NFR-PERF-001, NFR-PERF-002, and NFR-PERF-004. The file is present.

## Protocol ID Derivation

* IQ IDs use the number in the file name (`test_iq<N>_<topic>.py`). The repository has no IQ-1 file.
* Gateway-numbered OQ files keep their number as the ID: OQ-6, OQ-7, OQ-8, OQ-9, and OQ-16.
* New-named OQ and PQ files use the requirement ID and topic from the file name, in uppercase with hyphens. For example, `test_oq_fr_dat_005_hash_crosscheck.py` is OQ-FR-DAT-005-HASH-CROSSCHECK.
* Unit modules use the prefix UT- followed by the file name without the `test_` prefix, in uppercase with hyphens.
* Planned rows follow the same pattern from the file name in the VTM. Rows without a file name use the topic.

## Mapping Source Key

* VTM: the VTM test method cell cites this file for the listed IDs.
* VTM planned: the VTM names the file for a planned row, and the task number follows.
* Docstring only, not in VTM: the VTM does not cite this file. The IDs come from the file docstring and are not confirmed by the VTM.
* Infrastructure: the file cites no SRS requirement.

## Protocol Register

| Protocol ID | Phase | Status | File path | Requirement IDs | Mapping source |
| :--- | :--- | :--- | :--- | :--- | :--- |
| IQ-0 | IQ | EXISTING | vv/tests/IQ/test_iq0_repo_layout.py | FR-VV-005 | VTM |
| IQ-2 | IQ | EXISTING | vv/tests/IQ/test_iq2_python_version.py | infrastructure | Infrastructure |
| IQ-3 | IQ | EXISTING | vv/tests/IQ/test_iq3_pgcrypto.py | FR-DAT-005 | VTM |
| IQ-4 | IQ | EXISTING | vv/tests/IQ/test_iq4_pulse_engine_init.py | FR-MS-006 | VTM |
| IQ-5 | IQ | EXISTING | vv/tests/IQ/test_iq5_pip_check.py | infrastructure | Infrastructure |
| IQ-6 | IQ | EXISTING | vv/tests/IQ/test_iq6_triggers_installed.py | FR-DAT-004 | VTM; docstring adds FR-DAT-003 |
| IQ-7 | IQ | EXISTING | vv/tests/IQ/test_iq7_alembic_upgrade.py | FR-DAT-003 | VTM |
| OQ-16 | OQ | EXISTING | vv/tests/OQ/test_oq16_pulse_state_serialization.py | FR-MS-006 | VTM |
| OQ-6 | OQ | EXISTING | vv/tests/OQ/test_oq6_ema_convergence.py | FR-RTA-005 | VTM |
| OQ-7 | OQ | EXISTING | middleware/tests/test_oq7_update_rejection.py | FR-DAT-003, FR-DAT-004 | VTM |
| OQ-8 | OQ | EXISTING | middleware/tests/test_oq8_delete_rejection.py | FR-DAT-003, FR-DAT-004 | VTM |
| OQ-9 | OQ | EXISTING | middleware/tests/test_oq9_tamper_detection.py | FR-DAT-005 | VTM |
| OQ-FR-DAT-001-RELAY-TIERS | OQ | PLANNED | vv/tests/OQ/test_oq_fr_dat_001_relay_tiers.py | FR-DAT-001 | VTM planned, task 1.5 |
| OQ-FR-DAT-002-SILA-RPC | OQ | PLANNED | vv/tests/OQ/test_oq_fr_dat_002_sila_rpc.py | FR-DAT-002 | VTM planned, task 5.1 |
| OQ-FR-DAT-004-AUDIT-CAPTURE | OQ | EXISTING | vv/tests/OQ/test_oq_fr_dat_004_audit_capture.py | FR-DAT-004 | VTM planned, task 1.8 (file present); docstring adds FR-DAT-003 |
| OQ-FR-DAT-004-TRUNCATE-CASCADE-DEVICES | OQ | EXISTING | vv/tests/OQ/test_oq_fr_dat_004_truncate_cascade_devices.py | FR-DAT-003, FR-DAT-004 | Docstring only, not in VTM |
| OQ-FR-DAT-005-HASH-CROSSCHECK | OQ | EXISTING | vv/tests/OQ/test_oq_fr_dat_005_hash_crosscheck.py | FR-DAT-005 | VTM |
| OQ-FR-DAT-005-JSON-TYPES | OQ | EXISTING | vv/tests/OQ/test_oq_fr_dat_005_json_types.py | FR-DAT-005 | Docstring only, not in VTM |
| OQ-FR-DAT-006-ACCESS-CONTROL | OQ | EXISTING | vv/tests/OQ/test_oq_fr_dat_006_access_control.py | FR-DAT-006 | Docstring only, not in VTM |
| OQ-FR-DAT-006-SIGNATURES | OQ | PLANNED | vv/tests/OQ/test_oq_fr_dat_006_signatures.py | FR-DAT-006 | VTM planned, tasks 5.2 and 5.3 |
| OQ-FR-DAT-006-UNIQUE-CREDENTIALS | OQ | PLANNED | vv/tests/OQ/test_oq_fr_dat_006_unique_credentials.py | FR-DAT-006 | VTM planned, task 1.9 |
| OQ-FR-DAT-007-FHIR-HTTP | OQ | EXISTING | vv/tests/OQ/test_oq_fr_dat_007_fhir_http.py | FR-DAT-007 | VTM |
| OQ-FR-DAT-007-VALUE-SETS | OQ | PLANNED | vv/tests/OQ/test_oq_fr_dat_007_value_sets.py | FR-DAT-007 | VTM planned, task 5.5 |
| OQ-FR-MS-001-SEGMENTATION-DICE | OQ | PLANNED | vv/tests/OQ/test_oq_fr_ms_001_segmentation_dice.py | FR-MS-001 | VTM planned, task 2.1 |
| OQ-FR-MS-002-SOLVER-DIVERGENCE | OQ | PLANNED | vv/tests/OQ/test_oq_fr_ms_002_solver_divergence.py | FR-MS-002 | VTM planned, task 2.2 |
| OQ-FR-MS-003-CONTACT-MECHANICS | OQ | PLANNED | vv/tests/OQ/test_oq_fr_ms_003_contact_mechanics.py | FR-MS-003 | VTM planned, task 2.3 |
| OQ-FR-MS-004-WRENCH-PUBLISH | OQ | PLANNED | vv/tests/OQ/test_oq_fr_ms_004_wrench_publish.py | FR-MS-004 | VTM planned, task 2.4 |
| OQ-FR-MS-005-USD-PIPELINE | OQ | PLANNED | vv/tests/OQ/test_oq_fr_ms_005_usd_pipeline.py | FR-MS-005 | VTM planned, task 7.1 |
| OQ-FR-MS-006-PULSE-FAIL-CLOSED | OQ | EXISTING | vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py | FR-MS-006 | VTM |
| OQ-FR-MS-007-CLOCK-SKEW | OQ | PLANNED | vv/tests/OQ/test_oq_fr_ms_007_clock_skew.py | FR-MS-007 | VTM planned, task 2.8 |
| OQ-FR-RTA-005-ONE-EURO | OQ | EXISTING | vv/tests/OQ/test_oq_fr_rta_005_one_euro.py | FR-RTA-005 | VTM |
| OQ-FR-VV-002-XIL-PORTS | OQ | PLANNED | vv/tests/OQ/test_oq_fr_vv_002_xil_ports.py | FR-VV-002 | VTM planned, task 6.3 |
| OQ-FR-VV-003-SIL-HIL-PORTABILITY | OQ | PLANNED | vv/tests/OQ/test_oq_fr_vv_003_sil_hil_portability.py | FR-VV-003 | VTM planned, task 6.4 |
| OQ-FR-VV-005-TRACE-LINKS | OQ | PLANNED | vv/tests/OQ/test_oq_fr_vv_005_trace_links.py | FR-VV-005 | VTM planned, task 6.6 |
| OQ-NFR-SEC-001-JWT-SECRET | OQ | EXISTING | vv/tests/OQ/test_oq_nfr_sec_001_jwt_secret.py | NFR-SEC-001 | VTM |
| PQ-FR-DAT-005-1M-ROWS | PQ | EXISTING | vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py | FR-DAT-005 | VTM |
| PQ-FR-DAT-005-CHAIN-PERF | PQ | EXISTING | vv/tests/PQ/test_pq_fr_dat_005_chain_perf.py | FR-DAT-005 | VTM |
| PQ-FR-MS-006-HEARTBEAT-GAP | PQ | PLANNED | vv/tests/PQ/test_pq_fr_ms_006_heartbeat_gap.py | FR-MS-006 | VTM planned, task 2.5 |
| PQ-FR-RTA-006-HIL-FAIL-SAFE | PQ | PLANNED | vv/tests/PQ/test_pq_fr_rta_006_hil_fail_safe.py | FR-RTA-006 | VTM planned, task 4.5 |
| PQ-NFR-PERF-001-INGEST | PQ | PLANNED | vv/tests/PQ/test_pq_nfr_perf_001_ingest.py | NFR-PERF-001 | VTM planned, task 5.6 |
| PQ-NFR-PERF-002-EDGE | PQ | PLANNED | vv/tests/PQ/test_pq_nfr_perf_002_edge.py | NFR-PERF-002 | VTM planned, task 4.6 |
| PQ-NFR-PERF-003-FPS | PQ | PLANNED | vv/tests/PQ/test_pq_nfr_perf_003_fps.py | NFR-PERF-003 | VTM planned, task 7.5 |
| PQ-NFR-REL-001-SOAK | PQ | PLANNED | vv/tests/PQ/test_pq_nfr_rel_001_soak.py | NFR-REL-001 | VTM planned, task 6.7 |
| PQ-RELAY-SESSIONS | PQ | EXISTING | vv/tests/PQ/test_pq_relay_sessions.py | NFR-PERF-001, NFR-PERF-002, NFR-PERF-004 | Docstring only, not in VTM |
| UT-ACTOR-PROPAGATION | unit | EXISTING | middleware/tests/test_actor_propagation.py | FR-DAT-004 | Docstring only, not in VTM |
| UT-API-AUTH | unit | EXISTING | middleware/tests/test_api_auth.py | FR-DAT-006 | VTM; docstring adds NFR-SEC-001 |
| UT-DB-SSL-CONFIG | unit | EXISTING | middleware/tests/test_db_ssl_config.py | NFR-SEC-001 | VTM |
| UT-FHIR-VALIDATION | unit | EXISTING | middleware/tests/test_fhir_validation.py | FR-DAT-007 | Docstring only, not in VTM |
| UT-HASH-CHAIN | unit | EXISTING | middleware/tests/test_hash_chain.py | FR-DAT-005 | Docstring only, not in VTM |
| UT-LTTB | unit | EXISTING | middleware/tests/test_lttb.py | FR-RTA-005, NFR-PERF-001 | Docstring only, not in VTM |
| UT-P0-COMPLIANCE | unit | EXISTING | middleware/tests/test_p0_compliance.py | FR-DAT-007, FR-RTA-005 | Docstring only, not in VTM |
| UT-RELAY-OFFLOOP-PERSISTENCE | unit | EXISTING | middleware/tests/test_relay_offloop_persistence.py | FR-DAT-001, NFR-PERF-001, NFR-PERF-002 | Docstring only, not in VTM |
| UT-RELAY-POSTGRES-INTEGRATION | unit | EXISTING | middleware/tests/test_relay_postgres_integration.py | FR-DAT-001, FR-DAT-003, FR-DAT-004, FR-DAT-005 | Docstring only, not in VTM |
| UT-RELAY-RESPONSE-TIME | unit | EXISTING | middleware/tests/test_relay_response_time.py | NFR-PERF-001, NFR-PERF-002 | Docstring only, not in VTM |
| UT-RELAY-SESSION-RECORDS | unit | EXISTING | middleware/tests/test_relay_session_records.py | FR-DAT-001, FR-DAT-003, FR-DAT-004, NFR-SEC-001 | Docstring only, not in VTM |
| UT-ROLES-SCOPE | unit | EXISTING | middleware/tests/test_roles_scope.py | FR-DAT-006 | Docstring only, not in VTM |
| UT-RTA-COVERAGE-WCET-SUITES | unit | PLANNED | rta/tests/ (directory; file names not stated in VTM) | FR-RTA-001, FR-VV-004 | VTM planned, task 3.8 |
| UT-RTA-FALLBACK-CONTROLLER | unit | PLANNED | rta/tests/test_fallback_controller.cpp | FR-RTA-004 | VTM planned, task 3.5 |
| UT-RTA-SAFETY-ENVELOPE | unit | PLANNED | rta/tests/test_safety_envelope.cpp | FR-RTA-003 | VTM planned, task 3.4 |
| UT-RTA-SMOKE | unit | EXISTING | rta/tests/test_smoke.cpp | FR-RTA-001 | VTM |
| UT-RTA-TIMED-AUTOMATA | unit | PLANNED | rta/tests/test_timed_automata.cpp | FR-RTA-002 | VTM planned, task 3.3 |
| UT-SCOPE-ENFORCEMENT | unit | EXISTING | middleware/tests/test_scope_enforcement.py | FR-DAT-006, NFR-SEC-001 | Docstring only, not in VTM |
| UT-SMOKE | unit | EXISTING | middleware/tests/test_smoke.py | infrastructure | Infrastructure |
| UT-UVLOOP-ENABLED | unit | EXISTING | middleware/tests/test_uvloop_enabled.py | FR-DAT-001 | VTM; docstring also cites NFR-PERF-001, NFR-PERF-002, PQ-1, and PQ-8 |
| CI-COVERAGE-WCET | unspecified | PLANNED | .github/workflows/ci.yml (coverage and WCET jobs) | FR-VV-004 | VTM planned, task 6.5 |
| CI-MISRA-STATIC-ANALYSIS | unspecified | PLANNED | .github/workflows/ci.yml (MISRA job) | FR-VV-001 | VTM planned, task 3.7, extended by task 6.2 |
| XIL-EES-FAULT-INJECTION | unspecified | PLANNED | vv/xil/ (EES scripts; directory, not under vv/tests) | FR-RTA-002, FR-RTA-004 | VTM planned, task 3.9 |

## Support Modules

| File path | Role |
| :--- | :--- |
| vv/tests/conftest.py | pytest fixtures for vv tests |
| middleware/tests/conftest.py | pytest fixtures for middleware tests |
| middleware/tests/dbsupport.py | shared database fixtures for DB-dependent tests |
| vv/tests/PQ/locustfile.py | Locust load definition for NFR-PERF-001, NFR-PERF-002, and NFR-PERF-004; VTM marks it planned (task 1.6), the file is present |

## Open Mapping Items

* Fifteen rows have the mapping source "Docstring only, not in VTM". The VTM does not cite these files, so their requirement IDs are not confirmed by the VTM.
* The VTM row for FR-DAT-006 names `vv/tests/OQ/test_oq_fr_dat_006_unique_credentials.py` for task 1.9. The plan records task 1.9 as done (commit b111a68). The existing file `test_oq_fr_dat_006_access_control.py` may cover the same scope. Both rows are kept, and no mapping is merged.
* The VTM row for FR-DAT-004 names `test_oq_fr_dat_004_audit_capture.py` as planned. The file exists, so the row is EXISTING.
* `middleware/tests/test_uvloop_enabled.py` cites PQ-1 and PQ-8 in its docstring. Neither identifier has a file in this repository.
* `vv/tests/OQ/test_oq_fr_dat_004_truncate_cascade_devices.py` calls itself "OQ-8 supplement". `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py` calls itself PQ-3. Both keep their new-convention IDs and the self-labels are cross references.
* `vv/tests/PQ/test_pq_relay_sessions.py` and `vv/tests/PQ/locustfile.py` are untracked in git at the time of writing. `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py` has uncommitted changes. The register reflects the files on disk.
* `vv/tests/PQ/test_pq_relay_sessions.py` does not follow the PQ naming pattern, because its name has no requirement ID. Its docstring cites the G1.8 gate.
* The planned VTM row for FR-RTA-001 and FR-VV-004 names the `rta/tests/` directory without file names. The register keeps one row for that directory.
