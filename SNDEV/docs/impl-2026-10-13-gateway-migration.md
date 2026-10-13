Title: BioSync-Gateway baseline migration to SurgiTwin-RTA
Date: 2026-10-13T22:34:45Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc (repo preparation for initial development)
Summary: Copies and adapts the qualified BioSync-Gateway compliance storage, middleware, and IQ/OQ/PQ test baseline into SurgiTwin-RTA for SRS FR-DAT-003 to FR-DAT-007, FR-MS-006, FR-RTA-005, NFR-SEC-001, and NFR-PERF-001/002/004, NFR-REL-001, with Gateway open items R2 and R3 carried as known debt.

## Task Reference

Parent-session instruction to migrate the reusable baseline from `I:\Documents\GitHub\BioSync\BioSync-Gateway` (read-only source, MIT licensed) into `I:\Documents\GitHub\BioSync\BioSync-SurgiTwin-RTA`. Requirement source: `SRS.md` v1.0.0 in the target repository. Gateway open items source: `REMAINING_WORK_v1.1.md` in the Gateway repository (R2 and R3 open as of the 2026-07-28 re-audit).

## Specification Summary

* Compliance storage tier under `database/migrations/` for FR-DAT-003, FR-DAT-004, FR-DAT-005, and FR-DAT-006 (users table only).
* Middleware baseline under `middleware/` for FR-DAT-005 (hash chain engine), FR-DAT-007 (FHIR validation), FR-RTA-005 (EMA plus One Euro filter), FR-MS-006 (Pulse bridge and worker), and NFR-SEC-001 (JWT with fail-closed secret loading).
* Qualification harness under `vv/tests/{IQ,OQ,PQ}` and `middleware/tests/` with DB-gated tests that skip cleanly when no PostgreSQL is reachable.
* Infrastructure: compose init mounts, `.env.example` variable names, and a CI qualification job.
* Migration map in `docs/migration-map.md`.
* Out of scope: `rta/`, `CMakeLists.txt`, `sim/`, `edge/`, `frontend/`, `vv/xil/`, `vv/traceability/`, and the protected documents listed in the parent instruction.

## Implementation Notes

### Ledger summary

* Gateway files migrated: 47 (11 copied with no content change, 36 adapted or rewritten). Covers 4 SQL files, 15 Python modules, 4 Alembic files, 2 Dockerfiles, 2 requirements files, 10 middleware test files, and 10 V&V test files.
* New files written for SurgiTwin: 14 (one_euro.py, routes/fhir.py, routes/__init__.py, dbsupport.py, test_lttb.py, 5 OQ suites, Alembic revision 0001, 2 ignore files, vv/tests/conftest.py). Also `api/main.py` (scaffold kept, routers integrated) and scaffold files extended in place (docker-compose.yml, .env.example, ci.yml, .gitignore, database/README.md, vv/README.md).
* Database tables: 11 in the new schema (audit_log, users, patients, devices, device_metrics, observations, simulation_runs, simulation_states, rta_switch_events, sila2_rpc_log, surgical_telemetry). 10 carry the append-only triggers. users is excluded by design.
* Dropped: 15 tables (14 named in the parent instruction plus external_cache), 2 engine modules, 6 simulation modules, 3 AI modules, 4 external-client modules, 13 API route modules, performance_benchmarks.py, seed_rag_templates.py, middleware/.env (not copied).
* Deferred: telemetry_sessions table, telemetry routes and generator, response-time middleware, Gateway load and soak tests, and the frontend telemetry visualization path.
* Full row-by-row mapping is in `docs/migration-map.md` (Table 1 migrated, Table 2 not migrated, Table 3 new development and open items).

### Migration ledger (condensed)

Origin paths are relative to BioSync-Gateway at commit `babc632`. Full mapping: `docs/migration-map.md`.

| Origin | Target | Adaptation | Requirement |
|:-------|:-------|:-----------|:------------|
| `database/migrations/001-extensions.sql` | `database/migrations/001-extensions.sql` | uuid-ossp and btree_gin dropped | FR-DAT-005 |
| `database/migrations/002-schema.sql` | `database/migrations/002-schema.sql` | Lab tables dropped. audit_log renamed to FR-DAT-005 terms. New runs, states, RTA, SiLA 2, and telemetry tables. Idempotent DDL. | FR-DAT-003, 004, 005, 006, 007, FR-MS-006 |
| `database/migrations/003-triggers.sql` | `database/migrations/003-triggers.sql` | Statement-level rejection and TRUNCATE guard. Advisory lock. Shared digest function. COMMENT signature fixed. | FR-DAT-003, 004, 005 |
| `database/migrations/hash-chain-check.sql` | `database/migrations/hash-chain-check.sql` | Uses shared digest. Session-independent timestamps. | FR-DAT-005 |
| `middleware/engine/hash_chain.py` | `middleware/engine/hash_chain.py` | Renamed parameters. PostgreSQL-compatible UTC and JSONB rendering. Linkage check. | FR-DAT-005 |
| `middleware/api/routes/audit.py` | `middleware/api/routes/audit.py` | test-trigger endpoint removed (SQL injection). Column renames. | FR-DAT-004, 005 |
| `middleware/api/auth.py` | `middleware/api/auth.py` | bcrypt called directly (passlib incompatible with bcrypt 5). | FR-DAT-006, NFR-SEC-001 |
| `middleware/api/routes/auth.py` | `middleware/api/routes/auth.py` | Copied unchanged. | NFR-SEC-001 |
| `middleware/fhir_validator.py` | `middleware/fhir_validator.py` | model_validate. Module names corrected. Missing dependency raises. | FR-DAT-007 |
| `middleware/engine/signal.py` | `middleware/engine/signal.py` | Deviation reference text changed. | FR-RTA-005 |
| (none) | `middleware/engine/one_euro.py` | New scalar One Euro filter. | FR-RTA-005 |
| `middleware/engine/lttb.py` | `middleware/engine/lttb.py` | Copied unchanged. | NFR-PERF-001 |
| `middleware/engine/pulse.py` | `middleware/engine/pulse.py` | Append-only persistence. Imports changed. Docstrings corrected. | FR-MS-006 |
| `middleware/engine/pulse_bridge.py` | `middleware/engine/pulse_bridge.py` | Copied unchanged. | FR-MS-006 |
| `middleware/Pulse/__init__.py`, `Pulse/CDM.py` | `middleware/Pulse/` | Copied unchanged. | FR-MS-006 |
| `middleware/api/loop_policy.py` | `middleware/api/loop_policy.py` | Copied unchanged. | NFR-PERF-001 (R3 helper) |
| `middleware/database.py` | `middleware/database.py` | No built-in password. Fail-closed DATABASE_URL in production. init_db and drop_db removed. | FR-DAT-003, NFR-SEC-001 |
| `middleware/models.py` | `middleware/models.py` | Rewritten to the new schema. | FR-DAT-003 to 007 |
| `middleware/engine/__init__.py` | `middleware/engine/__init__.py` | Barcode and dilution removed. | Integration |
| `middleware/alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/README` | same paths | URL holds no credentials. env.py and templates unchanged. | FR-DAT-003 |
| (Gateway 0001 to 0007 revisions) | `middleware/alembic/versions/0001_initial_schema.py` | Single baseline that executes the SQL migrations. | FR-DAT-003 |
| `middleware/Dockerfile.pulse` | `middleware/Dockerfile.pulse` | Healthcheck to /health. External .pulse prerequisite documented. | FR-MS-006 |
| `middleware/Dockerfile` | `middleware/Dockerfile` | Non-root user and /health healthcheck. | FR-DAT-001 |
| `middleware/requirements.txt`, `requirements-test.txt` | same paths | Exact pins reconciled. python-jose 3.5.0. passlib, asyncpg, locust dropped. | NFR-SEC-001 |
| `middleware/tests/conftest.py` | `middleware/tests/conftest.py` | Environment defaults. Fixtures moved to dbsupport.py. No hard-coded credentials. | Qualification |
| (none) | `middleware/tests/dbsupport.py` | Migration-based DB fixtures. Skip with a reason when unreachable. | Qualification |
| `middleware/tests/test_oq7_update_rejection.py` | same path | Rewritten for 10 WORM tables and zero-row cases. | FR-DAT-004 |
| `middleware/tests/test_oq8_delete_rejection.py` | same path | Rewritten. TRUNCATE cases added. | FR-DAT-004 |
| `middleware/tests/test_oq9_tamper_detection.py` | same path | Rewritten to new columns. | FR-DAT-005 |
| `middleware/tests/test_p0_compliance.py` | same path | EMA channel tests only. | FR-RTA-005, FR-DAT-007 |
| `middleware/tests/test_db_ssl_config.py` | same path | Environment tests kept. Three R2 checks marked strict xfail. | NFR-SEC-001 |
| `tests/unit/test_o13_hash_chain_api.py` | `middleware/tests/test_hash_chain.py` | Rewritten for new signature. | FR-DAT-005 |
| `tests/unit/test_o14_fhir_validation_errors.py` | `middleware/tests/test_fhir_validation.py` | Import paths fixed. Deep-validation check added. | FR-DAT-007 |
| `tests/integration/test_api_auth.py` | `middleware/tests/test_api_auth.py` | Route tests replaced by audit scope checks and stubbed login. | NFR-SEC-001, FR-DAT-006 |
| `middleware/tests/test_uvloop_enabled.py` | same path | Copied unchanged. | NFR-PERF-001 |
| `tests/test_iq2_python_version.py` | `vv/tests/IQ/test_iq2_python_version.py` | Copied unchanged. | IQ-2 |
| `tests/test_iq3_pgcrypto.py` | `vv/tests/IQ/test_iq3_pgcrypto.py` | Rewritten to shared fixture. | FR-DAT-005 |
| `tests/test_iq4_pulse_engine_init.py` | `vv/tests/IQ/test_iq4_pulse_engine_init.py` | Import path changed. | FR-MS-006 |
| `tests/test_iq5_pip_check.py` | `vv/tests/IQ/test_iq5_pip_check.py` | Repository path corrected. | IQ-5 |
| `tests/test_iq6_triggers_installed.py` | `vv/tests/IQ/test_iq6_triggers_installed.py` | All 10 WORM tables. | FR-DAT-004 |
| `tests/test_iq7_alembic_upgrade.py` | `vv/tests/IQ/test_iq7_alembic_upgrade.py` | Env var renamed. Revision asserted. | FR-DAT-003 |
| `tests/test_oq6_ema_convergence.py` | `vv/tests/OQ/test_oq6_ema_convergence.py` | Import path changed. | FR-RTA-005 |
| `tests/test_oq16_state_serialization.py` | `vv/tests/OQ/test_oq16_pulse_state_serialization.py` | Import path changed. | FR-MS-006 |
| `tests/performance/test_pq2_hash_chain_perf.py` | `vv/tests/PQ/test_pq_fr_dat_005_chain_perf.py` | Rewritten. 1M projection removed. | FR-DAT-005 |
| `tests/performance/test_pq3_1m_rows.py` | `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py` | TRUNCATE removed. nextset removed. | FR-DAT-005 |
| (none) | `vv/tests/OQ/test_oq_fr_dat_005_hash_crosscheck.py` | New. Pinned vector and SQL cross-check. | FR-DAT-005 |
| (none) | `vv/tests/OQ/test_oq_nfr_sec_001_jwt_secret.py` | New. Fail-closed secret tests. | NFR-SEC-001 |
| (none) | `vv/tests/OQ/test_oq_fr_dat_007_fhir_http.py` | New. HTTP 200 and 422 paths. | FR-DAT-007 |
| (none) | `vv/tests/OQ/test_oq_fr_rta_005_one_euro.py` | New. One Euro behaviour. | FR-RTA-005 |
| (none) | `vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py` | New. Fail-closed and synthetic opt-in. | FR-MS-006 |
| `database/*` (scaffold), `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, `.gitignore` | same paths | Scaffold extended in place. | Infrastructure |

### Implementation notes

* Scope gate: 47 Gateway files plus 14 new files. This exceeds the 5-file approval threshold in AGENTS.md section 6. The parent session instructed the migration explicitly, so the threshold was not re-gated.
* Design decisions: rejection triggers are statement-level, so zero-row UPDATE and DELETE attempts are also rejected. TRUNCATE is rejected on append-only tables. The chain appends under an advisory lock, and id is assigned under that lock. The Pulse persistence path is append-only. python-jose 3.5.0 replaces 3.3.0. bcrypt is called directly.
* Defects found in the Gateway while migrating are corrected here and recorded in `docs/migration-map.md` Table 3 (rows marked DONE).
* Known debt carried, status OPEN: R2 (client-certificate TLS) and R3 (sync DB driver, WebSocket relay not migrated), plus the new-development items in `docs/migration-map.md` Table 3.

## Verification

### V1: Python test suite (FAIL: one IQ check)

Command: `python -m pytest middleware/tests vv/tests -q -rsx -p no:cacheprovider` from the repository root.
Interpreter: Python 3.14.3 (CPython, Windows). The SRS target is Python 3.11, which was not available.
Output saved to `SNDEV/logs/qual-2026-10-13-gateway-migration.txt` (gitignored runtime capture).

| Result | Count | Notes |
|:-------|------:|:------|
| Passed | 147 | Includes the scaffold IQ-0 and smoke tests, the migrated middleware unit tests, and the new OQ tests |
| Failed | 1 | IQ-5 `test_pip_list_matches_requirements`: `uvloop` and `pandas` are pinned in requirements.txt and are not installed in this interpreter. The environment was not provisioned from the pins, and network installs are not permitted. |
| Skipped | 59 | 56 need `BIOSYNC_TEST_DATABASE_URL` (no PostgreSQL reachable). 2 need the native Pulse bindings (module-level `importorskip` in IQ-4 and OQ-16). 1 needs `BIOSYNC_PQ3_DATABASE_URL` (1,000,000 rows). |
| XFAIL (strict) | 3 | R2 deployment checks: pg_hba, compose TLS, nginx certificate script. They turn into failures when the artifacts are added. |

A skipped test is not counted as evidence. The DB-dependent OQ-7, OQ-8, OQ-9, IQ-3, IQ-6, IQ-7, and the FR-DAT-005 SQL cross-check have not executed against PostgreSQL.

### V2: SQL validation (NOT RUN)

Not run: no local PostgreSQL (no `psql`, `pg_ctl`, or embedded server found on this machine). No SQL parser (pglast, sqlglot, sqlparse) is installed.

Inspection performed on the SQL in `database/migrations/`:

* Every table, index, and trigger statement uses IF NOT EXISTS, DROP IF EXISTS, or CREATE OR REPLACE.
* The DO block in 003 builds trigger names from a constant list and uses no `%` format strings, so it runs safely through psycopg2 and SQLAlchemy.
* The digest function, the chain trigger, the verifier, and the nightly script call the same `audit_chain_digest()`.
* The Python `_utc_text()` and `_jsonb_text()` functions were checked against the SQL format string and the jsonb key-ordering rule. The pinned vector digest is `609c640ee61ad85a8a522dc383127ca16458821b26563def228b2f70e6a73b21` (Python only).
* The trigger and chain SQL is carried over from the Gateway version with the adaptation diff listed in `docs/migration-map.md` Table 1. The Gateway SQL was qualified against PostgreSQL in its own repository. This migration's SQL is unexecuted.

### V3: Compose configuration (PASS)

`docker compose config -q` exits 0 with dummy `POSTGRES_PASSWORD` and `JWT_SECRET` set in the process environment only. With `JWT_SECRET` unset, it exits 15 with "required variable JWT_SECRET is missing", which is the intended guard. No containers were started.

### V4: Image build and CI (NOT RUN)

* `docker build` of `middleware/Dockerfile` and `middleware/Dockerfile.pulse` was not run. Network access is prohibited for this migration, so pip install cannot complete.
* The GitHub Actions workflow was not executed. Its commands were run locally in V1.

### V5: Writing and secret checks

* No banned terms, em dashes, curly quotes, emojis, or checkmark glyphs were found in `docs/migration-map.md`, the new SQL, or the new Python files. Lines flagged in copied Gateway code were left unchanged.
* Gateway `middleware/.env` was not copied. Key names only were inspected, and their values were not read or recorded in this log.
* No secrets, tokens, or credential literals were written into this repository. Test defaults use the placeholder `test-only-jwt-secret-do-not-use-in-production`, and the CI password is labelled as an ephemeral service value.

### Overall

FAIL. Python suite: 147 passed, 1 failed (IQ-5, environment missing `uvloop` and `pandas`), 59 skipped (no PostgreSQL, no Pulse bindings, no dedicated PQ-3 database). SQL: not run. Compose: PASS. Image build and CI: not run.

