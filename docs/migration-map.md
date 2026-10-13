# BioSync-Gateway to SurgiTwin-RTA Migration Map

Migration log: `SNDEV/docs/impl-2026-10-13-gateway-migration.md`

## Provenance

Both repositories are MIT licensed (Copyright 2026 Seth Nenninger). Origin paths are relative to the
BioSync-Gateway repository root at commit `babc632`, which had a clean working tree when the copies
were made. Target paths are relative to this repository root. Files copied unchanged keep the same
content. Adapted files list the changes in the adaptation column.

## Table 1: Migrated artifacts

| SurgiTwin requirement | Target path | Gateway origin path | Adaptation notes |
|:----------------------|:------------|:--------------------|:-----------------|
| FR-DAT-005 | `database/migrations/001-extensions.sql` | `database/migrations/001-extensions.sql` | uuid-ossp and btree_gin dropped. UUID defaults use `gen_random_uuid()`. |
| FR-DAT-003, FR-DAT-004, FR-DAT-005, FR-DAT-006, FR-DAT-007, FR-MS-006 | `database/migrations/002-schema.sql` | `database/migrations/002-schema.sql` | Lab and LLM tables removed. `audit_log` columns renamed to the FR-DAT-005 terms (`prev_hash`, `occurred_at`, `actor_id`, `action`, `data_prev`, `data_new`, `reason`). Added `simulation_runs`, `simulation_states` (replaces the Gateway `simulations` table), `rta_switch_events`, `sila2_rpc_log`, `surgical_telemetry`. `patients.synthetic_id` requires an `SYN-` prefix. DDL is idempotent. Trigger DDL moved to 003. |
| FR-DAT-003, FR-DAT-004 | `database/migrations/003-triggers.sql` | `database/migrations/003-triggers.sql` (and the trigger section of `002-schema.sql`) | Rejection triggers are `FOR EACH STATEMENT` and add `prevent_truncate`, because row-level triggers miss zero-row statements and TRUNCATE. Applied to 10 WORM tables through a DO loop. `users` excluded. Chain append takes an advisory lock and assigns `id` under it. `audit_chain_digest()` is shared by the trigger, verifier, and nightly script. `COMMENT ON FUNCTION insert_audit_log` uses the full signature (the Gateway signature did not match). |
| FR-DAT-005 | `database/migrations/hash-chain-check.sql` | `database/migrations/hash-chain-check.sql` | Uses `audit_chain_digest()` and `LAG()`. The Gateway inline `timestamp::TEXT` digest depended on the session TimeZone. Not applied at initialization. |
| FR-DAT-005 | `middleware/engine/hash_chain.py` | `middleware/engine/hash_chain.py` | Parameters renamed to the SurgiTwin columns. `_utc_text()` and `_jsonb_text()` render inputs the way PostgreSQL does. `verify_chain()` checks prev_hash linkage. |
| FR-DAT-004, FR-DAT-005 | `middleware/api/routes/audit.py` | `middleware/api/routes/audit.py` | `POST /test-trigger` removed. It built an `UPDATE` from a caller-supplied table name. Column renames applied. Verify and statistics routes kept. |
| FR-DAT-006, NFR-SEC-001 | `middleware/api/auth.py` | `middleware/api/auth.py` | Password hashing calls `bcrypt` directly. passlib 1.7.4 fails with bcrypt 5.x. Fail-closed JWT secret loading kept. python-jose kept at 3.5.0. |
| NFR-SEC-001 | `middleware/api/routes/auth.py` | `middleware/api/routes/auth.py` | Copied unchanged. Login uses the DB-backed `users` table. |
| FR-DAT-007 | `middleware/fhir_validator.py` | `middleware/fhir_validator.py` | `parse_obj` changed to `model_validate` (Pydantic v2). Module imports changed to `devicemetric` and `operationoutcome`. The Gateway names did not exist in fhir.resources 8.x, so deep validation was silently skipped. A missing fhir.resources now raises. |
| FR-DAT-007 | `middleware/api/routes/fhir.py` | `middleware/api/routes/fhir.py` (validation path only) | New `POST /api/fhir/validate` endpoint. Returns 422 with an OperationOutcome for invalid input and rejects unsupported types. Gateway persistence endpoints not migrated. |
| FR-RTA-005 | `middleware/engine/signal.py` | `middleware/engine/signal.py` | Copied. Only the deviation record reference changed, because the Gateway SNDEV record is not in this repository. |
| FR-RTA-005 | `middleware/engine/one_euro.py` | none (new) | One Euro filter (Casiez et al., CHI 2012). Scalar implementation. 6-DOF and MANO integration not implemented. |
| NFR-PERF-001 | `middleware/engine/lttb.py` | `middleware/engine/lttb.py` | Copied unchanged. Visualization downsampling. |
| FR-MS-006 | `middleware/engine/pulse.py` | `middleware/engine/pulse.py` | Imports changed to `SimulationRun` and `SimulationState`. Persistence is append-only: each transition inserts a `simulation_states` row, and stop writes one `simulation_runs` row. The Gateway updated a `simulations` row, which the Gateway trigger forbids. Those updates raised and were logged. |
| FR-MS-006 | `middleware/engine/pulse_bridge.py` | `middleware/engine/pulse_bridge.py` | Copied unchanged. |
| FR-MS-006 | `middleware/Pulse/__init__.py`, `middleware/Pulse/CDM.py` | `middleware/Pulse/__init__.py`, `middleware/Pulse/CDM.py` | Copied unchanged. Compatibility shim over the `pulse` and `PyPulse` bindings. |
| FR-MS-006 | `middleware/Dockerfile.pulse` | `middleware/Dockerfile.pulse` | Healthcheck changed to `/health`. Documentation references updated. External prerequisite: the engine source at `./.pulse/` (not copied). |
| FR-DAT-003, NFR-SEC-001 | `middleware/database.py` | `middleware/database.py` | No built-in password. `DATABASE_URL` required in production (fail-closed). `init_db()` and `drop_db()` removed, because `create_all()` bypasses the triggers and `drop_db()` destroys records. Environment-aware `DB_SSLMODE` default kept. |
| FR-DAT-003 to FR-DAT-007 | `middleware/models.py` | `middleware/models.py` | Rewritten to the new schema. Lab, LLM, and plate models removed. `JSONB` and `TIMESTAMPTZ` used directly. The Gateway had no SQLAlchemy compatibility shim, so none was carried over. |
| Test and runtime | `middleware/api/main.py` | `middleware/api/main.py` (not copied) | Scaffold `/health` kept. Routers added for auth, audit, and fhir. Gateway lifespan, telemetry task, and route set not migrated. |
| Test and runtime | `middleware/api/loop_policy.py` | `middleware/api/loop_policy.py` | Copied unchanged. Gateway R3 helper. |
| Test and runtime | `middleware/api/routes/__init__.py`, `middleware/engine/__init__.py` | `middleware/api/routes/__init__.py`, `middleware/engine/__init__.py` | Routes package init added. Engine init rewritten to load signal, one_euro, lttb, and pulse. Barcode and dilution removed. |
| Alembic | `middleware/alembic.ini`, `middleware/alembic/env.py`, `middleware/alembic/script.py.mako`, `middleware/alembic/README` | same paths | `alembic.ini` URL holds no credentials. `env.py` copied unchanged. |
| Alembic | `middleware/alembic/versions/0001_initial_schema.py` | none (Gateway 0001 to 0007 not migrated) | Single baseline revision. Executes the three SQL files. Downgrade refused. Gateway revision chain not carried over. |
| Requirements | `middleware/requirements.txt`, `middleware/requirements-test.txt` | `middleware/requirements.txt`, `middleware/requirements-test.txt` | Scaffold pins kept where newer. Gateway python-jose 3.3.0 replaced by 3.5.0 (3.4.0 fixed the JWE and JWT-bomb issues). passlib, asyncpg, locust, openai, and flake8 dropped. `uvloop`, `pandas`, and `psycopg2-binary` kept from the Gateway. |
| Docker | `middleware/Dockerfile`, `middleware/.dockerignore`, `.dockerignore` | `middleware/Dockerfile` (scaffold base), none for ignore files | Non-root user and `/health` healthcheck added. Ignore files keep `.env` out of images. |
| FR-DAT-001 to FR-DAT-007 | `docker-compose.yml` | none (scaffold extended) | Init mounts for 001 to 003. `JWT_SECRET` and `POSTGRES_PASSWORD` required. `DB_SSLMODE` defaults to `disable` (R2 debt). |
| NFR-SEC-001 | `.env.example` | none (scaffold extended) | Variable names with dummy values. |
| Qualification | `.github/workflows/ci.yml` | none (scaffold extended) | `qualification` job with an ephemeral PostgreSQL 15 service. |
| Qualification | `middleware/tests/conftest.py`, `middleware/tests/dbsupport.py`, `vv/tests/conftest.py` | `middleware/tests/conftest.py`, `tests/conftest.py` | Gateway conftest had a hard-coded test database credential and `create_all()`. Replaced by env-driven fixtures and idempotent migrations. DB tests skip with a reason. |
| FR-DAT-004 | `middleware/tests/test_oq7_update_rejection.py` | `middleware/tests/test_oq7_update_rejection.py` | Rewritten. Bound parameters, 10 WORM tables, zero-row UPDATE cases. `plates` removed. |
| FR-DAT-004 | `middleware/tests/test_oq8_delete_rejection.py` | `middleware/tests/test_oq8_delete_rejection.py` | Rewritten. Adds TRUNCATE cases (`devices` excluded: foreign keys block TRUNCATE before the trigger runs). |
| FR-DAT-005 | `middleware/tests/test_oq9_tamper_detection.py` | `middleware/tests/test_oq9_tamper_detection.py` | Rewritten to the new columns. Route tests use a scoped JWT. |
| FR-RTA-005, FR-DAT-007 | `middleware/tests/test_p0_compliance.py` | `middleware/tests/test_p0_compliance.py` | Only the EMA channel tests kept. Alarm and ingest tests belong to the telemetry routes, which are not migrated. |
| NFR-SEC-001 | `middleware/tests/test_db_ssl_config.py` | `middleware/tests/test_db_ssl_config.py` | Environment tests kept. Added fail-closed `DATABASE_URL` test. Three deployment checks are `xfail(strict=True)` for R2. |
| FR-DAT-005 | `middleware/tests/test_hash_chain.py` | `tests/unit/test_o13_hash_chain_api.py` | Rewritten for the new signature. Adds UTC and JSONB rendering tests. |
| FR-DAT-007 | `middleware/tests/test_fhir_validation.py` | `tests/unit/test_o14_fhir_validation_errors.py` | Import paths corrected. Adds a check that deep validation is active and a wrong-type case. |
| NFR-SEC-001, FR-DAT-006 | `middleware/tests/test_api_auth.py` | `tests/integration/test_api_auth.py` | Rewritten. Route tests for plates and Observation removed. Login tested with a stubbed `authenticate_user`. Scope tests added. |
| NFR-PERF-001 | `middleware/tests/test_lttb.py` | none (new) | Invariant tests for the copied LTTB module. |
| NFR-SEC-001 (R3) | `middleware/tests/test_uvloop_enabled.py` | `middleware/tests/test_uvloop_enabled.py` | Copied unchanged. |
| FR-DAT-003 | `vv/tests/IQ/test_iq3_pgcrypto.py` | `tests/test_iq3_pgcrypto.py` | Rewritten to the shared DB fixture. |
| FR-DAT-004 | `vv/tests/IQ/test_iq6_triggers_installed.py` | `tests/test_iq6_triggers_installed.py` | Rewritten. Checks all 10 WORM tables (the Gateway checked `audit_log` only). |
| FR-DAT-003 | `vv/tests/IQ/test_iq7_alembic_upgrade.py` | `tests/test_iq7_alembic_upgrade.py` | Rewritten. Uses `BIOSYNC_TEST_DATABASE_URL`. Asserts the revision id. |
| FR-MS-006 | `vv/tests/IQ/test_iq4_pulse_engine_init.py` | `tests/test_iq4_pulse_engine_init.py` | Import path changed. Skips without the bindings. |
| IQ-2, IQ-5 | `vv/tests/IQ/test_iq2_python_version.py`, `vv/tests/IQ/test_iq5_pip_check.py` | `tests/test_iq2_python_version.py`, `tests/test_iq5_pip_check.py` | IQ-5 repository path corrected (the Gateway resolved one level too shallow). |
| FR-RTA-005 | `vv/tests/OQ/test_oq6_ema_convergence.py` | `tests/test_oq6_ema_convergence.py` | Import path changed. Deviation reference changed. |
| FR-MS-006 | `vv/tests/OQ/test_oq16_pulse_state_serialization.py` | `tests/test_oq16_state_serialization.py` | Import path changed. Skips without the bindings. |
| FR-DAT-005 | `vv/tests/OQ/test_oq_fr_dat_005_hash_crosscheck.py` | none (new) | Pinned digest vector. SQL digest cross-check (database-gated). |
| NFR-SEC-001 | `vv/tests/OQ/test_oq_nfr_sec_001_jwt_secret.py` | none (new) | Fail-closed secret, secret file, and development default, each in a fresh interpreter. |
| FR-DAT-007 | `vv/tests/OQ/test_oq_fr_dat_007_fhir_http.py` | none (new) | HTTP 200 and 422 paths, scopes, and 401. |
| FR-RTA-005 | `vv/tests/OQ/test_oq_fr_rta_005_one_euro.py` | none (new) | One Euro behaviour and parameter checks. |
| FR-MS-006 | `vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py` | none (new) | Fail-closed without bindings. Synthetic opt-in. |
| FR-DAT-005 (verification performance) | `vv/tests/PQ/test_pq_fr_dat_005_chain_perf.py` | `tests/performance/test_pq2_hash_chain_perf.py` | Rewritten to the new interface. The 10k-row projection to 1M rows was removed. |
| FR-DAT-005 (verification performance) | `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py` | `tests/performance/test_pq3_1m_rows.py` | Gated by `BIOSYNC_PQ3_DATABASE_URL`. TRUNCATE removed (triggers forbid it). `nextset()` removed (psycopg2 has no such method). Requires an empty `audit_log`. |

## Table 2: Deliberately not migrated

| Item | Origin path | Reason |
|:-----|:------------|:-------|
| Plates, plate wells, barcode indices, dilution worklists | `database/migrations/002-schema.sql`, `database/migrations/004-seed-barcodes.sql`, `database/seeds/*.json` | Laboratory automation. Not part of the surgical digital twin. |
| Human factors metrics | `database/migrations/002-schema.sql`, `middleware/api/routes/human_factors.py`, `middleware/models.py` | Gateway FR-3.9 uFMEA instrumentation. Not in the SurgiTwin table scope. |
| Simulation scenarios, scenario runs, synthetic cohorts, chemistry profiles, PK/PD worklists, cfDNA sandbox runs | `database/migrations/002-schema.sql`, `middleware/models.py`, `middleware/simulation/*.py`, `middleware/api/routes/{scenarios,digital_twin,chemistry,pkpd,mrd}.py` | Clinical chemistry, pharmacokinetics, cfDNA, and cohort generation. Laboratory-domain analytics. |
| Clinical text outputs, LLM runs, RAG templates | `database/migrations/002-schema.sql`, `middleware/ai/*`, `middleware/api/routes/ai.py`, `middleware/scripts/seed_rag_templates.py` | LLM and RAG gateway (SRS-excluded domain). |
| Barcode engine | `middleware/engine/barcode.py` | Illumina UDI multiplexing. Laboratory automation. |
| Dilution engine | `middleware/engine/dilution.py` | Laboratory dilution solver. |
| External API clients and cache | `middleware/external/*`, `database/migrations/002-schema.sql` (`external_cache`) | AccessGUDID and ClinVar clients. Not part of the SurgiTwin scope. |
| Performance benchmark module | `middleware/performance_benchmarks.py` | Benchmarks tied to the removed engines. |
| Gateway Alembic revisions 0002 to 0007 | `middleware/alembic/versions/0002_*.py` to `0007_*.py` | Replaced by the single baseline revision 0001. The Gateway chain targets the lab schema. |
| Gateway environment file | `middleware/.env` | Contains secret-named keys with values set (`DB_PASSWORD`, `JWT_SECRET`). Not copied, not quoted, not tracked by Git. Credential rotation status is unknown and is an operator action item. |
| Gateway hard-coded credential literals | `middleware/database.py`, `middleware/alembic.ini`, `middleware/tests/conftest.py` | Replaced by environment-driven values. The literals are not carried over. |
| Gateway SNDEV logs, scripts, and build artifacts | `SNDEV/*`, `middleware/.pytest_cache/`, `**/__pycache__/`, `middleware/.venv-1` | Not part of the baseline. Local caches and the virtual environment are not source. |
| Gateway documentation | `docs/*`, `REMAINING_WORK*.md`, `DEVELOPMENT_PLAN.md`, `README.md`, `run-server.bat` | Gateway-specific. SurgiTwin documentation is authored in this repository. |
| Gateway nginx certificate tooling | `nginx/*` | Not carried in this phase. The certificate script is an R2 dependency and is listed in Table 3. |
| Gateway frontend (chart provider, `useWebSocket`, `TelemetryDashboard`, `MicroplateEditor`, `ScenarioDesigner`, analytics viewers) | `frontend/*` | Deferred. See the deferred row below. The frontend is outside this migration's scope. |
| Gateway `.dockerignore` (root) | `.dockerignore` | Replaced by the SurgiTwin root and middleware ignore files. |

Deferred to the telemetry phase (not dropped):

| Item | Origin path | Reason |
|:-----|:------------|:-------|
| Frontend telemetry visualization path (NFR-PERF-003) | `frontend/src/components/*Telemetry*`, `frontend/src/hooks/useWebSocket.ts`, chart-provider modules | NFR-PERF-003 requires a waveform frontend. Deferred so the migration stays in the informatics tier. |
| WebSocket telemetry relay and session tracking | `middleware/api/routes/telemetry.py`, `middleware/api/routes/telemetry_generator.py`, `database/migrations/002-schema.sql` (`telemetry_sessions`) | Belongs to the NFR-PERF-001 and NFR-PERF-002 work. The Gateway R3 target lives here. |
| Response-time instrumentation middleware | `middleware/api/middleware/response_time.py` | NFR-PERF-002 instrumentation. Its absence leaves `record_pulse_step` unused, and `engine/pulse.py` handles that. |
| Gateway load and soak tests | `tests/performance/test_pq1_*.py`, `tests/performance/test_pq4_*.py`, `tests/performance/locustfile.py`, `tests/performance/k6/*` | Depend on the telemetry relay that is not migrated. |

## Table 3: New development and carried open items

| Item | Requirement | Status | Notes |
|:-----|:------------|:-------|:------|
| SiLA 2 FDL servers over gRPC and Protobuf | FR-DAT-002 | OPEN | `sila2_rpc_log` exists. No server, no FDL definitions, no Protobuf schema. |
| Electronic signatures: printed name, timestamp, and meaning | FR-DAT-006 | OPEN | Not implemented. A signature table and a signing workflow are needed. |
| Inactivity lockout and unique credential enforcement | FR-DAT-006 | OPEN | Login and scope checks exist. No lockout counter, no inactivity timer, and no shared-account detection. |
| WORM semantics on runs and RTA events (finalization guard) | FR-DAT-003 | OPEN | Triggers are installed. A finalization state machine and signature-gated finalization are not implemented. |
| Automatic per-row audit capture (old and new values) | FR-DAT-004 | OPEN | Audit columns and the `insert_audit_log()` helper exist. No generic AFTER trigger writes audit rows for the WORM tables. Rejected UPDATE and DELETE attempts are not recorded, because their transaction rolls back. |
| Role separation against superuser trigger disablement | FR-DAT-004 | OPEN | Triggers do not stop the table owner from running `DISABLE TRIGGER`. An owner role separate from the application role is needed. |
| One Euro filter in the 6-DOF teleoperation pipeline with MANO constraints | FR-RTA-005 | OPEN | Scalar One Euro filter implemented and tested. Per-axis integration and MANO are not. |
| ProcessPoolExecutor delegation for Pulse steps | FR-MS-006 | OPEN | `SimulationManager.step_simulation` is synchronous. The native engine object cannot be pickled, so a process pool needs one long-lived worker per engine. |
| Surgical telemetry ingestion path and throughput | FR-DAT-001, NFR-PERF-001 | OPEN | Table exists. No ingestion route writes to it. The 100,000 points per second target is not measured. |
| Terminology binding validation (for example Observation.status value set) | FR-DAT-007 | OPEN | fhir.resources checks structure and types. The local version accepted `status` set to `bogus-status`. |
| Python and SQL digest equivalence for all JSON values | FR-DAT-005 | OPEN | The Gateway Python and SQL digests did not match for the same input. Equivalence is shown only for the pinned vector, and only after the database cross-check runs with `BIOSYNC_TEST_DATABASE_URL`. |
| Gateway R2: client-certificate TLS to the compliance database | NFR-SEC-001 | OPEN (carried) | Client-side environment-aware default is migrated. Server-side `pg_hba` hostssl clientcert=verify-full and certificate tooling are not. Compose defaults to `disable`. Three xfail tests track this item. |
| Gateway R3: uvloop policy and no synchronous DB writes on the WebSocket relay path | NFR-PERF-001, NFR-PERF-002 | OPEN (carried) | The uvloop helper and dependency are migrated. The relay is not migrated. The database driver is synchronous psycopg2. |
| Gateway defect: passlib with bcrypt 5.x | NFR-SEC-001 | DONE | Replaced by direct bcrypt calls. |
| Gateway defect: silent loss of deep FHIR validation | FR-DAT-007 | DONE | Module names corrected. Missing dependency now raises. |
| Gateway defect: SQL injection in test-trigger endpoint | FR-DAT-004 | DONE | Endpoint not migrated. |
| Gateway defect: zero-row UPDATE and DELETE and TRUNCATE not rejected | FR-DAT-004 | DONE | Statement-level and TRUNCATE triggers. |
| Gateway defect: hash digest formulas diverged across trigger, verifier, and nightly script | FR-DAT-005 | DONE | One shared function. |
| Gateway defect: `insert_audit_log` COMMENT signature mismatch | FR-DAT-004 | DONE | Full signature used. |
| Gateway defect: in-place updates to an append-only `simulations` table | FR-MS-006 | DONE | Append-only state rows. |
| Gateway load and soak CI workflow (`pq.yml`) | NFR-PERF-001, NFR-REL-001 | OPEN | Not migrated. The SurgiTwin qualification job runs the IQ, OQ, and PQ suites against PostgreSQL. The 1,000,000-row check needs `BIOSYNC_PQ3_DATABASE_URL` and is not run in CI. |
| Pins not resolved against PyPI | Requirements | OPEN | `middleware/requirements.txt` pins were not resolved from a network index in this environment. The local interpreter did not match the pins (fastapi 0.139.0, pydantic 2.13.4, fhir.resources 8.3.0, and others), and `uvloop` and `pandas` are absent. |
| Pulse engine source provenance and build | FR-MS-006 | OPEN | `.pulse/` is an external prerequisite. The Pulse image was not built in this migration. |
| Docker image for `Dockerfile.pulse` runs as root | NFR-SEC-001 | OPEN | Gateway image had no non-root user. Not changed in this phase. |
| Data retention periods for surgical telemetry and simulation runs | SRS Section 6 (Gateway section 6.3 analogue) | OPEN | The Gateway retention periods are not restated in this repository. No purge job exists, and the WORM triggers block row deletion. |
