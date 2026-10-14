Title: Auth import fix, 006 migration repair, relay PostgreSQL integration
Date: 2026-10-14T16:26:11Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 tasks 1.2 and 1.5 closure work (F1, F6, session finalization)
Summary: Fixes the auth.py forward-reference import error (F1), the 006 migration psycopg2 message hazard (F6), wires 006 into every migration path, finalizes open relay sessions at shutdown, and qualifies the relay on PostgreSQL 15 under Python 3.11.

## Task Reference

Parent session instruction for the SurgiTwin-RTA qualification suite. Blockers F1, F2, F6 and the relay session lifecycle gap. Related plan items: DEVELOPMENT_PLAN.md Phase 1 tasks 1.2 (relay persistence) and 1.5 (qualification). The plan file is not edited here.

## Specification Summary

1. F1: middleware/api/auth.py annotated Optional[User] before User was defined, which raised NameError at import and blocked eight test modules from collecting. Fix: quoted forward references on the two functions defined above the User class. Replace the deprecated datetime.utcnow() calls in auth.py with datetime.now(timezone.utc).
2. F6: database/migrations/006-telemetry-sessions.sql passed a % placeholder to RAISE EXCEPTION. Fix: the USING MESSAGE concatenation form used by 003-triggers.sql.
3. Migration coverage: the test fixture list, the docker-compose init mount, and the Alembic baseline each apply 001, 002, 003, and 006. hash-chain-check.sql is a read-only verification query and is excluded.
4. Finalize-on-shutdown: every telemetry_sessions row left open at shutdown gets its finalized row, with points_relayed as of shutdown.
5. Python 3.11 provisioning for IQ-2 (finding F2), with a .venv-qual311 environment.
6. Prove the relay PostgreSQL integration tests pass and run the full suite with zero collection errors.

## Implementation Notes

### Files changed

* middleware/api/auth.py: F1 fix (two annotations changed to "User"), utcnow replaced in create_access_token and create_refresh_token.
* database/migrations/006-telemetry-sessions.sql: finalize guard RAISE changed from "... % ..." format to USING MESSAGE concatenation with NEW.session_uid::text.
* middleware/api/relay_writer.py: session tracking and finalize-on-shutdown. New SessionTracker dataclass, track_session(), open_session(), close_session(), finalize_open_sessions(). stop() calls finalize_open_sessions() before it closes intake. The timeout branch of stop() now catches asyncio.TimeoutError (see Findings, Python 3.10 difference).
* middleware/api/routes/telemetry.py: the WebSocket handler registers a tracker, queues the open row through open_session(), adds accepted points to tracker.points, and calls close_session() in its finally block. See Cross-ownership edits below.
* middleware/tests/dbsupport.py: MIGRATION_FILES now lists 001, 002, 003, and 006.
* docker-compose.yml: postgres init mount for 006-telemetry-sessions.sql added. Mounts are applied in lexical order by the postgres entrypoint.
* middleware/alembic/versions/0001_initial_schema.py: SQL_FILES now includes 006-telemetry-sessions.sql.
* middleware/tests/test_relay_session_records.py: three tests added (shutdown with a connected session, writer stop with tracked sessions, open row still queueing when finalize is requested).
* middleware/tests/test_relay_postgres_integration.py: one PostgreSQL test added (shutdown finalizes a connected session), for five relay PostgreSQL tests in total.
* SNDEV/docs/impl-2026-10-14-unblock-integration.md: this log.

main.py is unchanged. Its lifespan already calls writer.stop(), which now finalizes open sessions first.

### Cross-ownership edits

Two files outside the ownership list were changed. Both edits are small and are listed here so they can be reverted or reviewed.

* middleware/api/routes/telemetry.py. The finalize-on-shutdown requirement needs the session point count, and the point count lives in the WebSocket handler. Without this change the writer would not know how many points each session relayed.
* middleware/tests/conftest.py. The client fixture imported get_db inside the fixture. middleware/tests/test_db_ssl_config.py calls importlib.reload(database), which replaces database.get_db with a new function object. routes/audit.py keeps the original object, so after the reload the dependency override missed the route and the OQ-9 API tests read committed data instead of the test transaction. The fix imports get_db once at conftest import time, before any test reloads the module. Diff: the import moved to module scope and the in-fixture import was removed.

### Session finalization design

* A session is registered with track_session() before its open row is queued.
* open_session() queues the open row. If close was requested while the open row was waiting for queue space, the finalized row is queued right after the open row, so the open row always precedes the finalized row.
* close_session() queues the finalized row with tracker.points, and is idempotent through the closed flag.
* finalize_open_sessions() closes every tracked session that is not closed. stop() runs it before intake stops, so the finalized rows are written during the drain.
* The WebSocket loop exits after a frame is read if the tracker is closed, so no frame is counted after shutdown.

Before this change, a WebSocket still connected at shutdown had its finalized row refused, because stop() set intake to closed before the handler's finally block ran. That produced the open-only row described in the parent instruction.

### Python 3.11 provisioning (F2)

Python 3.11.9 was already installed per-user at C:\Users\salmo\AppData\Local\Programs\Python\Python311\python.exe and is listed by the py launcher. No admin rights, winget install, or download was needed. .venv-qual311 was created from it and the pinned middleware/requirements.txt and middleware/requirements-test.txt were installed. The install capture is SNDEV/logs/pip-install-qual-py311-2026-10-14.txt. pip check reports no broken requirements. vv/tests/IQ/test_iq2_python_version.py was not changed.

### Migration coverage checks

* Alembic: a scratch database was created, alembic upgrade head ran against it, and it reported revision 0001_initial_schema. telemetry_sessions exists with 4 non-internal triggers (finalize guard, prevent update, prevent delete, prevent truncate). The scratch database was dropped.
* Fresh container init: a throwaway postgres:15 container was started with the same four init mounts as docker-compose.yml, with no published port. Initialization completed with no error, telemetry_sessions exists, and it has 4 triggers. The container was removed.

## Verification

Environment: PostgreSQL 15 container biosync-surgitwin-rta-postgres-1 (healthy). Test database surgitwin_test. DATABASE_URL, BIOSYNC_TEST_DATABASE_URL, and BIOSYNC_RELAY_ADMIN_URL were set for the run, with credentials read from the running container and not written to any file.

### Suite counts

* Before, .venv-qual (Python 3.10.11), capture SNDEV/logs/unblock-baseline-run.txt: 260 passed, 3 failed, 3 skipped, 5 xfailed, 8 collection errors. The 3 failures were IQ-2 and two NFR-SEC-001 JWT secret tests. The 8 collection errors were the NameError in auth.py.
* After, .venv-qual311 (Python 3.11.9), capture SNDEV/logs/unblock-integration-run.txt, command "python -m pytest middleware/tests vv/tests -v -rfEs": 333 passed, 0 failed, 0 errors, 3 skipped, 5 xfailed. Result: PASS for the target of zero collection errors and zero failures on 3.11. IQ-2 PASS.
* After, .venv-qual (Python 3.10.11), capture SNDEV/logs/unblock-py310-run.txt: 332 passed, 1 failed, 3 skipped, 5 xfailed. The one failure is IQ-2, which requires 3.11 and is expected on 3.10.

The 3 skipped tests are the existing gates: IQ-4 and OQ-16 need a pulse package that is not importable from the test environment, and PQ-3 needs BIOSYNC_PQ3_DATABASE_URL pointing at a dedicated 1M-row database.

The 32 previously blocked tests now collect and pass. This includes the OQ-9 tamper tests (6 in test_oq9_tamper_detection.py) and the OQ-NFR-SEC-001 tests (test_oq_nfr_sec_001_jwt_secret.py) and the other modules listed in the baseline errors.

### PostgreSQL relay integration

Command: python -m pytest middleware/tests/test_relay_postgres_integration.py -v. Result: PASS, 5 passed, 0 skipped. The database surgitwin_relay_test was created, 001, 002, 003, and 006 were applied, and the database was dropped at teardown.

* test_relay_session_persists_samples_session_rows_and_hash_chained_audit: PASS. Sample rows, open and finalized rows with 3 points, two audit rows, and verify_hash_chain() returns ok.
* test_telemetry_sessions_rows_cannot_be_updated_deleted_or_truncated: PASS. UPDATE, DELETE, and TRUNCATE are rejected.
* test_finalized_row_without_open_row_is_rejected: PASS. The message "no open record" matches the fixed 006 RAISE.
* test_second_open_row_for_one_session_is_rejected: PASS. The unique constraint rejects the second open row.
* test_shutdown_finalizes_a_connected_session_in_postgresql (new): PASS. Open row with 0 points, then finalized row with 2 points, written during shutdown while the WebSocket was still connected.

### Relay and auth unit tests

Command: python -m pytest middleware/tests/test_relay_session_records.py middleware/tests/test_relay_offloop_persistence.py middleware/tests/test_relay_response_time.py middleware/tests/test_api_auth.py. Result: PASS, 50 passed.

### Findings and fixes during verification

* test_relay_offloop_persistence.py::test_stop_abandons_records_when_the_drain_times_out_and_refuses_later_records failed on Python 3.10. stop() caught the builtin TimeoutError, but asyncio.wait_for raises asyncio.TimeoutError, which is a separate class on 3.10 and the same class on 3.11. Fixed by catching asyncio.TimeoutError in relay_writer.py.
* The first WebSocket harness exposed a NameError (session_uid) in routes/telemetry.py left over from the lifecycle refactor. Fixed by using tracker.session_uid.
* Full-suite OQ-9 API failure caused by the reload in test_db_ssl_config.py. Fixed as described under Cross-ownership edits.
* OQ-9 API tests need DATABASE_URL to name a reachable test database. The conftest default has no password, so the runs above set DATABASE_URL to surgitwin_test in the environment.

### Findings in files not owned by this task

* middleware/tests/test_db_ssl_config.py reloads the database module at test time. Any test that depends on the get_db identity can break after it runs. The conftest change in this commit removes the observed failure. The test file should use monkeypatch.setenv with a fresh import in a subprocess, or avoid reloading the module.
* DEVELOPMENT_PLAN.md and docs/migration-map.md carry uncommitted edits from another agent. This task did not stage them. The plan should record 006 as the telemetry migration and 007-signatures.sql as the future signature migration, as the parent instruction states.
* SNDEV/docs/impl-2026-10-13-telemetry-relay.md has uncommitted edits from another agent. Not staged here.
* The Alembic change edits the 0001 baseline. A database already stamped at 0001_initial_schema would not receive 006 from alembic upgrade. No such database exists in this repository today. A later migration revision would be needed if one is created.
* Residual race during shutdown: a handler waiting for queue space to enqueue its open row, when the drain has already started, can enqueue the open row after the writer stops accepting. That session then has an open row and no finalized row. This needs a queue-full condition during shutdown and is not covered by a test.

## Result

DONE for F1, F6, the migration coverage, finalize-on-shutdown, the PostgreSQL relay qualification, and the 3.11 suite. Commit hash is recorded in the commit message and in the final report.
