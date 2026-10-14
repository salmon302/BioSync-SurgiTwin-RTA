Title: Closure fixes: TLS test identities, doc URL, migration list single source, service actor
Date: 2026-10-14T17:27:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: Open items from impl-2026-10-14-init-tls-verify.md and impl-2026-10-14-scope-actor-fix.md
Summary: Closes six defects left by the TLS, migration init, and actor work: TLS test identity skip, doc URL, one migration list, service actor identities, em dash cleanup, and shared dev database check.

## Task Reference

* Open items OPEN in SNDEV/docs/impl-2026-10-14-init-tls-verify.md (roles module under TLS, docs/db-client-cert-tls.md line 137, MIGRATION_FILES duplicates, shared 5432 database without 004 and 005).
* Finding F-6 and the relay-writer note in SNDEV/docs/impl-2026-10-14-scope-actor-fix.md (em dashes in middleware/api/auth.py, and background writers recording the login role as actor).

## Specification Summary

1. vv roles module under TLS: zero auth-noise errors in a TLS run of the vv OQ suite. Plaintext run stays at 101 passing.
2. docs/db-client-cert-tls.md: the TLS example for the no-certificate check has no sslcert or sslkey.
3. One migration list in middleware/tests/dbsupport.py, imported by the relay integration test. Order 001, 002, 003, 004, 006, 005.
4. Service identities through set_actor in middleware/database.py: service:relay-writer and service:pulse-engine. Interactive JWT actor behavior stays as in ff0a221.
5. No em dashes in owned middleware files.
6. surgitwin_test on 127.0.0.1:5432 has the 004 and 005 objects, verified with catalog queries. No container drop or recreate.

## Implementation Notes

Plan and decisions, recorded before any edit. Each item below is updated when its change lands.

### Item 1 decision: skip under TLS

The owner decision was a fixed login role with a certificate from database/certs/generate-certs.sh (PG_CLIENT_CN). That tooling writes one client certificate, client.crt, for one CN, and FORCE=1 replaces the CA that the TLS server trusts. A second CN therefore needs a change to generate-certs.sh, which is outside this task's ownership list. The fallback in the checklist applies: the app_engine fixture in vv/tests/OQ/test_oq_fr_dat_006_access_control.py skips under TLS with a reason string. The plaintext run keeps the random role name and its 101 passing cases. The dependent tests are the application-role boundary and permitted-path classes. Shared-account tests run under TLS.

Follow-up (OPEN): either extend generate-certs.sh to issue one client certificate per listed CN, then switch app_engine to a fixed role name, or let the fixture use SET ROLE surgitwin_app from the owner connection. Both options need the owner's choice.

### Item 3 decision: PQ file not edited

vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py is on the do-not-touch list for this task. It lists 001, 002, 003 only, so it also omits 006 (not only 004 and 005). Recorded as OPEN follow-up. The relay integration test is the only duplicate changed here.

### Item 4 decision: relay persistence is in relay_sink.py

middleware/api/relay_writer.py opens no database session. It imports no database code by design. The session is opened in middleware/api/relay_sink.py (SqlAlchemyRelaySink._write_sync, which calls SessionLocal()). relay_sink.py is not on the ownership list, so it is not edited here. The service helper added to middleware/database.py is the call the sink needs. The one-line follow-up for the sink owner is recorded in the Verification section (OPEN).

### Item 6 premise check

The checklist says the shared 5432 database lacks 004 and 005. Catalog check before any change: surgitwin_test already has users_audit_capture, users_identity_guard, users_prevent_truncate (004), roles surgitwin_owner and surgitwin_app (005), and all 13 public tables owned by surgitwin_owner. Migrations 004 and 005 are idempotent (DROP TRIGGER IF EXISTS, CREATE OR REPLACE, IF NOT EXISTS guards). They are re-applied in the documented order with ON_ERROR_STOP to confirm the state, and the catalog queries are recorded in Verification.

### Item 1 result: DONE (skip under TLS)

Change: vv/tests/OQ/test_oq_fr_dat_006_access_control.py. The app_engine fixture reads pg_stat_ssl for the audit connection. Under TLS it skips with TLS_ROLE_SKIP_REASON before it creates the random login role. The module docstring records the rule. The shared-account tests and the plaintext behavior are unchanged.

Before: impl-2026-10-14-init-tls-verify.md recorded 39 errors under TLS, all password authentication failed for surgitwin_app_login_<hex> in app_engine.
After: vv OQ suite under TLS (scratch container on 127.0.0.1:5435): 339 passed, 40 skipped, 0 errors, exit 0. The 39 skips are this module with the reason string. The 40th skip is test_oq16_pulse_state_serialization.py (could not import 'pulse'), which predates this change. Log: SNDEV/logs/closure-vv-oq-tls-2026-10-14.log.
Plaintext: vv OQ application-role and audit modules, 101 passed, exit 0. Log: SNDEV/logs/closure-vv-oq-plaintext-2026-10-14.log.

OPEN: the 39 application-role cases do not run under TLS. Two options need the owner: (a) extend database/certs/generate-certs.sh to issue a client certificate for each listed CN, then use a fixed role such as surgitwin_test_login, or (b) use SET ROLE surgitwin_app from the owner connection in app_engine. generate-certs.sh is outside this task's ownership list, so (a) was not made.

### Item 2 result: DONE

Change: docs/db-client-cert-tls.md. Section 6 is limited to BIOSYNC_TEST_DATABASE_URL and says that URL is not used for BIOSYNC_TLS_TEST_DATABASE_URL. Section 7 gains the TLS URL form with sslmode=verify-full and sslrootcert only.

Before: the section 6 example carried sslcert and sslkey, so the no-certificate check connected and failed (impl-2026-10-14-init-tls-verify.md, one failure).
After: middleware/tests/test_db_ssl_config.py with the section 7 URL against the 5435 TLS server: 17 passed, including test_tls_server_rejects_connection_without_client_certificate. Log: SNDEV/logs/closure-tls-live-doc-url-2026-10-14.log.

### Item 3 result: DONE for the relay test, OPEN for the PQ file

Change: middleware/tests/test_relay_postgres_integration.py. Its own MIGRATION_FILES (001, 002, 003, 006) and MIGRATIONS path are removed. The fixture calls dbsupport.apply_migrations(engine), so the relay database gets the single list in dbsupport.MIGRATION_FILES: 001, 002, 003, 004, 006, 005. The docstring names the shared list. The dbsupport list order is unchanged.

Before: the relay module was skipped in the baseline (BIOSYNC_RELAY_ADMIN_URL unset). Its own list omitted 004 and 005.
After: with BIOSYNC_RELAY_ADMIN_URL set to a plaintext admin URL on 5432, the relay module ran in a three-module run with test_actor_propagation.py and test_scope_enforcement.py: 46 passed, 0 skipped, exit 0. Log: SNDEV/logs/closure-middleware-actor-scope-relay-2026-10-14.log.

OPEN: vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py still has MIGRATION_FILES = [001, 002, 003]. It also omits 006, not only 004 and 005. The file is on this task's do-not-touch list, and a parallel agent works on vv/tests/PQ/*. Follow-up: import MIGRATION_FILES and MIGRATIONS_DIR from middleware/tests/dbsupport.py, or call apply_migrations on a psycopg2 connection, then re-check the file at commit time.

### Item 4 result: DONE for pulse, OPEN for the relay sink

Changes:

* middleware/database.py: SERVICE_ACTOR_PREFIX = "service:" and service_session(identity). The helper validates the prefix, opens SessionLocal(), and calls set_actor. The JWT path (get_current_user, set_actor(db, sub)) is unchanged.
* middleware/engine/pulse.py: PULSE_ENGINE_ACTOR = "service:pulse-engine". _append_state and _finalize_run open their sessions with service_session(PULSE_ENGINE_ACTOR).
* middleware/engine/pulse.py, defect F-7 (pre-existing, found during this check): class SimulationState(Enum) was defined after the import of models.SimulationState, so the model name was shadowed. _append_state raised "EnumType.__call__() got an unexpected keyword argument 'state_uid'", logged "Failed to persist simulation state to DB", and wrote no row. The model import is now aliased to SimulationStateRecord.

Before: pulse _append_state wrote 0 rows and no identity could be observed.
After (scratch database surgitwin_svc_check, created and dropped by dbsupport.scratch_database on 5432): audit_log rows for a users insert and two updates were INSERT service:relay-writer, UPDATE service:pulse-engine, UPDATE surgitwin (a plain SessionLocal session records the login role). service_session("pulse-engine") raised ValueError. The pulse state write produced 1 row in simulation_states. Evidence is recorded here: the check ran from a temp script that is not kept in the repository.

OPEN (relay persistence): middleware/api/relay_writer.py opens no database session. It imports no database code by design. The session is opened in middleware/api/relay_sink.py (SqlAlchemyRelaySink._write_sync, db = self._session_factory()). relay_sink.py is not on this task's ownership list and is unchanged. Follow-up for the sink owner: call set_actor(db, "service:relay-writer") on the batch session, or use database.service_session("service:relay-writer") when the default factory is used. telemetry_sessions rows already record client_identity as actor_id through insert_audit_log, so the JWT-derived identity is kept for them.

### Item 5 result: DONE for owned files

Change: middleware/api/auth.py, three U+2014 em dashes in comments or log messages:

* line 50: "variables - never hard-coded." became "variables, never hard-coded."
* line 71: "JWT_SECRET not set - using" became "JWT_SECRET not set: using"
* line 118: "importable - auth" became "importable, so auth"

The diff is three changed lines, and the CRLF line endings are unchanged.

Other dash locations found by the scan of middleware, vv, database, and docs (not owned, not edited, OPEN):

* middleware/api/routes/auth.py:90 (comment)
* middleware/engine/lttb.py:4, :38, :120, :151 (docstring and comment lines)
* vv/tests/IQ/test_iq2_python_version.py:16 (docstring)

Scan after the change: 0 dashes in each owned file (auth.py, database.py, pulse.py, dbsupport.py, test_relay_postgres_integration.py, the roles module, db-client-cert-tls.md).

### Item 6 result: DONE (premise differed)

Premise check before any change, catalog of surgitwin_test on 127.0.0.1:5432: users_audit_capture, users_identity_guard, and users_prevent_truncate were present (004 objects). Roles surgitwin_owner and surgitwin_app were present, both NOLOGIN (005 objects). All 13 public tables were owned by surgitwin_owner. So the database already had 004 and 005. The checklist premise is stale for this database.

Action: 004-audit-capture.sql, then 005-roles.sql, each applied with psql -v ON_ERROR_STOP=1 -X -1 in one transaction. Both exit 0. 005 printed two NOTICE lines (role already a member, indexes already exist). No container was dropped or recreated.

After: the three 004 triggers are enabled (tgenabled O). surgitwin_owner and surgitwin_app are present. surgitwin_app holds INSERT, SELECT, and UPDATE on users. The users table has 0 rows, so the 005 username CHECK adds no failure.

## Verification

Environment: .venv-qual311 (Python 3.11.9). PostgreSQL 15 on 127.0.0.1:5432 for plaintext runs, all against the database surgitwin_closure_test (own database). A TLS scratch project srta-closure on 127.0.0.1:5435 (container srta-closure-postgres-1, ssl on, server verify path with database/certs/out), removed at the end with down -v, including its volume. The container password was read from the container environment at run time and redacted from every saved log. surgitwin_test was used only for the item 6 migration apply and catalog reads. No full suite ran against surgitwin_test.

| Check | Command or source | Result | Evidence |
|:------|:------------------|:-------|:---------|
| Item 1, vv OQ under TLS | pytest vv\tests\OQ with the verify-full URL and cert paths on 5435 | PASS: 339 passed, 40 skipped (39 roles cases with reason, 1 pulse import), 0 errors | SNDEV/logs/closure-vv-oq-tls-2026-10-14.log |
| Item 1, plaintext regression | pytest test_oq_fr_dat_004 and test_oq_fr_dat_006 on 5432 | PASS: 101 passed | SNDEV/logs/closure-vv-oq-plaintext-2026-10-14.log |
| Item 2, TLS live tests with the section 7 URL | pytest middleware\tests\test_db_ssl_config.py on 5435 | PASS: 17 passed | SNDEV/logs/closure-tls-live-doc-url-2026-10-14.log |
| Items 3, 4, regression targets | pytest test_actor_propagation.py, test_scope_enforcement.py, test_relay_postgres_integration.py on 5432 (relay admin URL set) | PASS: 46 passed, 0 skipped | SNDEV/logs/closure-middleware-actor-scope-relay-2026-10-14.log |
| Item 4, service identity and pulse write | temp scratch script (removed) on surgitwin_svc_check, dropped on exit | PASS: service:relay-writer, service:pulse-engine recorded; invalid prefix rejected; pulse state row count 1 (was 0 before F-7 fix) | output recorded in Item 4 result |
| Item 5, dash scan | Select-String over owned files for U+2013 and U+2014 | PASS: 0 in each owned file | Item 5 result |
| Item 6, catalog after apply | catalog queries on surgitwin_test | PASS: 004 triggers enabled, 005 roles present, surgitwin_app grants present | Item 6 result |
| Full suite, once | pytest middleware\tests vv\tests -q, plaintext, closure database, relay admin and TLS URLs unset | PASS: 659 passed, 13 skipped, 0 failed, exit 0 | SNDEV/logs/closure-full-suite-2026-10-14.log |

Full-suite note: the baseline was 659 passed, 12 skipped. The 13th skip is vv/tests/PQ/test_pq_relay_sessions.py:420 (BIOSYNC_PQ_RELAY_URL not set). That file is untracked work from the parallel agent and is not part of this commit. The other 12 skips match the baseline. The passing count is unchanged, so no test was added or removed by this change.

Open items:

* OPEN: the 39 application-role cases under TLS (Item 1 decision).
* OPEN: vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py migration list (Item 3).
* OPEN: middleware/api/relay_sink.py service identity for relay writes (Item 4).
* OPEN: em or en dashes outside owned files (Item 5 list).
* OPEN: the test database surgitwin_closure_test remains on 5432 as this task's own database.
