Title: Migration init ordering, Alembic coverage, TLS fixture rule, compose verification
Date: 2026-10-14T17:17:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: F-1 and F-2 findings (impl-2026-10-14-audit-capture-roles.md) and R2 TLS open items (impl-2026-10-14-r2-tls.md); DEVELOPMENT_PLAN.md Phase 1 tasks 1.4 and 1.2
Summary: Wires migrations 004 and 005 into the compose init and the Alembic baseline in the order 001, 002, 003, 004, 006, 005, records the test TLS identity rule, and verifies the TLS compose stack in an isolated project.

## Task Reference

* F-1: docker-compose.yml init mounts omit 004 and 005. Source: SNDEV/docs/impl-2026-10-14-audit-capture-roles.md, Findings.
* F-2: middleware/alembic/versions/0001_initial_schema.py SQL_FILES omits 004 and 005. Same source.
* R2 open items: the scratch-role fixture conflicts with clientcert=verify-full CN matching (run 8), and the compose stack has not been run live. Source: SNDEV/docs/impl-2026-10-14-r2-tls.md, Open items.
* Phase 1 tasks 1.4 (Gateway R2, NFR-SEC-001) and 1.2 (database initialization).
* Out-of-scope item from the roles stream: the users denylist includes admin (SNDEV/docs/impl-2026-10-14-audit-capture-roles.md, Decisions for the plan owner).

## Specification Summary

* The compose init and the Alembic baseline apply 001, 002, 003, 004, 006, 005 in that order. 005 grants on telemetry_sessions, which 006 creates.
* Plain lexical order of the source names puts 005 before 006, so the order is set explicitly.
* The TLS test identity follows one rule (see Implementation Notes).
* The admin denylist is recorded in the 005 header comment.
* The TLS compose stack runs in the isolated project srta-verify on 127.0.0.1:5434. The shared container biosync-surgitwin-rta-postgres-1 on 127.0.0.1:5432 is not touched.

## Implementation Notes

### Files changed

* docker-compose.yml. Init mounts for 004 and 005 added. The 006 and 005 mount targets are swapped. A comment explains the order.
* docker-compose.verify-override.yml (new). Replaces the postgres publish list with 127.0.0.1:5434:5432 using !override (Compose 2.24.6 supports the tag).
* middleware/alembic/versions/0001_initial_schema.py. SQL_FILES lists 001, 002, 003, 004, 006, 005 with a comment on the order.
* middleware/tests/dbsupport.py. Docstring only: the TLS identity rule. MIGRATION_FILES already had the required order and is unchanged.
* database/migrations/005-roles.sql. Comment-only note on the admin denylist.
* SNDEV/docs/impl-2026-10-14-init-tls-verify.md (this file).

Not changed: middleware/tests/conftest.py (no fixture code needed for the chosen rule), database/certs/generate-certs.sh (not in this task's file list), middleware/api/*, middleware/database.py, migrations 001 to 004 and 006, test_db_ssl_config.py, the parallel agent's test files, vv/*, and docs/*.

### Init ordering mechanism (F-1)

The PostgreSQL image entrypoint runs the files in /docker-entrypoint-initdb.d in glob order, which is lexical order of the target names. docker-compose.yml sets the target names:

* 001-extensions.sql (source 001-extensions.sql)
* 002-schema.sql (source 002-schema.sql)
* 003-triggers.sql (source 003-triggers.sql)
* 004-audit-capture.sql (source 004-audit-capture.sql)
* 005-telemetry-sessions.sql (source 006-telemetry-sessions.sql)
* 006-roles.sql (source 005-roles.sql)

The source files keep their names, and the repository order of the migrations is unchanged. Only the mount targets change, so the mount list is the single place that sets the order. A wrapper script was not used, because database/certs/postgres-entrypoint.sh is outside this task's file list and a second wrapper would add a second order source.

Existing volumes are not re-initialized. The 5432 container was initialized with the old mount list, so Docker init does not apply 004 or 005 there. Its state was not checked in this task. Bringing it up to this schema needs an operator step (OPEN).

### Alembic (F-2)

SQL_FILES is now 001, 002, 003, 004, 006, 005. The same order is used in the compose mounts. The comment in the file names the reason for the last position.

### Admin denylist note

The 005 header has a two-line comment. Behavior verified on a database with a user named admin: the file stops at the CHECK statement with ERROR check constraint "users_username_individual" ... is violated by some row, exit code 3. Statements before the CHECK (role creation, ownership transfer, grants) had already run, so the failure is partial. Re-running after the rename is expected to complete, because each statement is idempotent. The re-run was not executed.

### TLS test identity rule (R2 open item)

Chosen rule: the shared test fixtures use one login identity, the user in BIOSYNC_TEST_DATABASE_URL. Its client certificate is the one that database/certs/generate-certs.sh issues for that CN (PG_CLIENT_CN, default surgitwin). The fixtures in dbsupport.py create no login roles, so they never present a certificate with another CN.

Reasons for this option instead of a dedicated surgitwin_app_login certificate:

* generate-certs.sh writes fixed file names into database/certs/out/ and refuses to run when out/ca.key exists unless FORCE=1. FORCE=1 replaces the CA that the TLS server trusts, and the server and the middleware certificate would both break. The script has no option to issue one extra client certificate, so a per-session certificate would need a script change outside this task's file list.
* The only consumer that needs another identity is vv/tests/OQ/test_oq_fr_dat_006_access_control.py, fixture app_engine. It creates a random role per run (surgitwin_app_login_<8 hex>) and asserts the name prefix in test_application_login_is_member_of_surgitwin_app. A CN check cannot match a random name, and the file is off-limits to this task.

Measured effect (Verification): the roles module errors 39 times under the TLS URL, with password authentication failed for user "surgitwin_app_login_aa691e53". Every error in the full run is in that module. OPEN: to clear these, the owner of the roles module either (1) changes app_engine to a fixed role name (for example surgitwin_app_login), issues the certificate with PG_CLIENT_CN set to that name through generate-certs.sh, and changes the startswith assertion at line 174 to the exact name, or (2) skips the module when BIOSYNC_TEST_DATABASE_URL requires TLS and runs it against the non-TLS flow.

Documentation note for the docs owner (docs/db-client-cert-tls.md line 137, not edited): the example puts sslcert and sslkey into BIOSYNC_TLS_TEST_DATABASE_URL. test_db_ssl_config.py builds its own client certificate arguments, and the URL certificate makes the no-certificate test connect and fail. The bare URL with sslmode and sslrootcert is the correct value.

### Compose verification method

Project name srta-verify, so the container, network, and volume srta-verify_pgdata are separate from the shared stack. The env file with throwaway POSTGRES_PASSWORD and JWT_SECRET values was written under C:\Users\salmo\AppData\Local\Temp\opencode\srta-verify and deleted at teardown. No secret is written to the repository or to SNDEV/logs.

Limit: the middleware image build is not run. The Dockerfile runs pip install -r requirements.txt, which needs network access beyond the image-pull allowance, and the middleware service has a build section, so compose does not start it without a build. The middleware wrapper is checked in a local python:3.11-slim container with --network none instead (check d).

## Verification

### Compose check matrix (project srta-verify, port 5434)

| Check | Result | Evidence |
|:------|:-------|:---------|
| (a) postgres ssl=on, verify-full client certificate accepted | PASS | SNDEV/logs/srta-verify-tls-matrix-2026-10-14.log (case 1: connected, pg_stat_ssl.ssl=True). SHOW ssl returned on. |
| (b) no-certificate connection rejected | PASS | Same log (case 2: connection requires a valid client certificate). Case 3 (plaintext) also rejected: no pg_hba.conf entry, no encryption. |
| (c) fresh database receives all migrations in order, with audit trigger and roles | PASS | Init order: SNDEV/logs/srta-verify-postgres-init-2026-10-14.log (six "running" lines in the order above, ready with no ERROR). pg_trigger: users_audit_capture and users_identity_guard present on users, all triggers enabled (tgenabled O). pg_roles: surgitwin_owner (NOLOGIN) and surgitwin_app (NOLOGIN). 12 of 12 public tables owned by surgitwin_owner. |
| (d) middleware entrypoint installs client key at /tmp/biosync-db-tls/client.key | PASS (limited) | SNDEV/logs/srta-verify-middleware-entrypoint-2026-10-14.log: uid 1000, directory mode drwx------, key mode 600, KEY_MATCH against the mounted key, DB_SSLKEY readable. Run in python:3.11-slim with --network none. Image build not run (see Limit). bash -n exit 0 for both wrappers. |

Additional checks:

* Alembic revision 0001 upgrade() on a fresh database (surgitwin_verify_alembic) through the TLS URL: PASS. users_audit_capture present, telemetry_sessions has 4 triggers, both roles present, surgitwin_app has INSERT on telemetry_sessions. Log: SNDEV/logs/srta-verify-alembic-upgrade-2026-10-14.log.
* Admin denylist (005 on a database with user admin): FAIL as expected, exit 3, CHECK violation. Documented. Log: SNDEV/logs/srta-verify-admin-denylist-2026-10-14.log.

### Test runs (database surgitwin_verify_test on 5434, TLS URL, server-side verify-full)

Full suite, one valid run: `python -m pytest middleware/tests vv/tests -q`. Result: 623 passed, 8 skipped, 1 failed, 39 errors. Log: SNDEV/logs/srta-verify-full-suite-tls-2026-10-14.log.

* The 1 failure was middleware/tests/test_db_ssl_config.py::test_tls_server_rejects_connection_without_client_certificate. Cause: my environment setup put sslcert and sslkey into BIOSYNC_TLS_TEST_DATABASE_URL, so the no-certificate case connected. This is a run configuration fault, not a code fault. Targeted rerun of the module with the bare URL: 17 passed (SNDEV/logs/srta-verify-tls-ssl-config-targeted-2026-10-14.log). The failure is cleared by this rerun, and the full suite is not run again.
* The 39 errors are all in vv/tests/OQ/test_oq_fr_dat_006_access_control.py, the app_engine fixture, with the password authentication failure described under TLS identity rule. OPEN (see above).
* An earlier attempt had a PowerShell interpolation fault that sent only the query string to the test URL. Every test that used the URL failed at engine creation (417 errors, 4 failed, 244 passed). No database connection was made by that attempt. Its log is kept at SNDEV/logs/srta-verify-full-suite-tls-attempt1-env-error-2026-10-14.log. It counts as a configuration fault, not as a full-suite run against the test database. The full-suite count above is the first run that reached the database.
* Interference: the runs used the isolated server on 5434. The shared 5432 database was not used, so no advisory-lock contention with other agents was possible. The shared container was not queried.

Server log for the isolated project: SNDEV/logs/srta-verify-postgres-runtime-2026-10-14.log. It has 7 authentication rejection lines. These include the matrix's intentional rejections, the no-certificate test, and the roles module.

### Teardown

docker compose -p srta-verify down -v removed the container, the network, and the volume srta-verify_pgdata. Log: SNDEV/logs/srta-verify-down-2026-10-14.log. The shared container biosync-surgitwin-rta-postgres-1 is still running and healthy after teardown. The env file in the temp directory was deleted. A search of every srta-verify log for the generated password and JWT value returned no matches.

### Open items

* OPEN: vv/tests/OQ/test_oq_fr_dat_006_access_control.py app_engine uses random role names, which fail the CN rule under TLS (39 errors). Needs the owner change described under TLS test identity rule.
* OPEN: docs/db-client-cert-tls.md line 137 puts client certificate parameters into the TLS test URL. Needs a docs edit.
* OPEN: the 5432 container was initialized before this change. Init does not re-run on it, so 004 and 005 need an operator step. Recreation was out of scope.
* OPEN: the middleware image was not built, because the build needs network access for pip. A full compose run of the middleware service needs an environment that allows the package download.
* OPEN: middleware/tests/test_relay_postgres_integration.py and vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py keep their own MIGRATION_FILES lists without 004 and 005. Both files are outside this task's file list. Their lists should follow the same order.
