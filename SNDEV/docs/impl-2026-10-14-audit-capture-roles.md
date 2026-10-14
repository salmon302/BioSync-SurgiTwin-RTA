Title: FR-DAT-004 audit capture and FR-DAT-006 role separation seed
Date: 2026-10-14T16:59:24Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 tasks 1.8 and 1.9 (gates G1.2, G1.4)
Summary: Adds the audit capture trigger for permitted changes on users, the identity freeze and TRUNCATE rejection on users, an application role without ownership, and the FR-DAT-006 credential uniqueness seed.

## Task Reference

DEVELOPMENT_PLAN.md Phase 1, task 1.8 (FR-DAT-003 finalization guard and FR-DAT-004 generic AFTER trigger, using the VAL-010 split) and task 1.9 (table owner role separated from the application role, FR-DAT-006 unique-credential constraint and RBAC scope check). Gates G1.2 (audit capture) and G1.4 (credentials). Requirements: SRS.md FR-DAT-003, FR-DAT-004, FR-DAT-006. Split source: SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md, finding VAL-010, and the interim VTM row for FR-DAT-004 in vv/traceability/vtm.md.

## Specification Summary

VAL-010 split, as implemented:

* Prohibited and rejected: UPDATE, DELETE, and TRUNCATE on the 10 WORM tables (003-triggers.sql) and on telemetry_sessions (006-telemetry-sessions.sql). These rejections are unchanged by this work.
* Permitted and audited: changes to users. Every INSERT, UPDATE, and DELETE on users writes one audit_log row through insert_audit_log() with the prior and new row states.

Scope of FR-DAT-004 capture (task 1.8): the trigger is attached to users. The WORM tables are not attached, because every UPDATE and DELETE on them is rejected before a row-level trigger can run, and their INSERTs are the original records.

Scope of FR-DAT-006 seed (task 1.9): unique individual credentials (case and whitespace normalized uniqueness of username and email, a denylist of generic shared account names) and the JWT scope check (require_scope) under test. Session lockout (inactivity lock, failed-login lock) and electronic signature display fields (printed name, timestamp, meaning) are out of scope. They belong to Phase 5 (tasks 5.2 and 5.3).

## Implementation Notes

### Files changed

* database/migrations/004-audit-capture.sql (new): identity guard on users, TRUNCATE rejection on users, the generic audit_row_change() function, and the users_audit_capture trigger.
* database/migrations/005-roles.sql (new): the surgitwin_owner and surgitwin_app roles, table ownership transfer, application grants, and the FR-DAT-006 credential constraints and indexes on users.
* middleware/api/auth.py: _scopes_from_claim() parses the JWT scope claim in the space-delimited string form and the list form. get_current_user() and verify_refresh_token() call it. No other auth behavior changed.
* middleware/tests/dbsupport.py: MIGRATION_FILES in the dependency order below, and scratch_database(), which creates and drops a named test database.
* middleware/tests/test_roles_scope.py (new): 20 RBAC scope cases, no database.
* vv/tests/OQ/test_oq_fr_dat_004_audit_capture.py (new): 48 cases on surgitwin_audit_test.
* vv/tests/OQ/test_oq_fr_dat_006_access_control.py (new): 53 cases on surgitwin_audit_test, including the application login role.

Not changed: middleware/models.py and middleware/engine/hash_chain.py. The users constraints are enforced in SQL, and insert_audit_log() needed no change.

### Design decisions

VAL-010 split as implemented:

* Rejected: UPDATE, DELETE, and TRUNCATE on the 10 WORM tables (003-triggers.sql) and on telemetry_sessions (006-telemetry-sessions.sql). Their rejection triggers are unchanged. Every column of a WORM row is frozen after insert.
* Permitted and audited: INSERT, UPDATE, and DELETE on users. Each change writes one audit_log row through insert_audit_log() with the actor, the action, the prior row state (data_prev, NULL on INSERT), and the new row state (data_new, JSON null on DELETE).
* Frozen on users: id, username, and created_at (users_identity_guard). Other columns may change.
* Rejected on users: TRUNCATE (users_prevent_truncate), because TRUNCATE skips row-level triggers and would remove rows without an audit row.

Finalization guard (task 1.8). The example in the task brief, a status column that moves to finalized on a WORM row, would require an UPDATE on a WORM row, and the VAL-010 split rejects that. The implemented guard therefore freezes every column of the WORM tables. A finalized state is written as a new row, as telemetry_sessions does in 006.

Capture scope. audit_row_change() is generic and reads TG_TABLE_NAME, so it works for any table with an integer or bigint id column. It is attached to users only. The WORM tables are not attached, because their UPDATE and DELETE are rejected before any row trigger runs, and their INSERTs are the original records. The test suite attaches it to a second table (audit_probe, created in the test transaction) to exercise a second table shape.

Actor and reason. The actor is taken from the transaction setting biosync.actor, and falls back to session_user. The reason is taken from biosync.reason when set. No application code sets either setting yet (see findings).

Rejected attempts. A rejected statement raises an exception and the transaction rolls back, so no audit row for the attempt survives. The VAL-010 split does not require logging rejections, so the design limit is recorded here and not worked around. The tests check that rejected attempts write no audit row.

Role separation (task 1.9). The application role is surgitwin_app (NOLOGIN, with membership granted to a login role). Ownership is the boundary. Tables are owned by surgitwin_owner, so ALTER TABLE, ENABLE TRIGGER, and DISABLE TRIGGER fail for the application role with "must be owner". Grants are SELECT on all tables, INSERT on the 11 record and audit tables, and INSERT and UPDATE on users. The role holds no TRUNCATE, UPDATE, or DELETE on record tables, and no TRIGGER privilege. Functions are not transferred, because the pgcrypto functions belong to an extension and cannot be altered.

Migration order: 001, 002, 003, 004, 006, 005. 004 needs only users (002) and the functions in 003. 005 grants privileges on telemetry_sessions, which 006 creates, so 005 runs after 006. dbsupport.py uses this order. The numbering is unchanged.

FR-DAT-006 seed (task 1.9):

* Case- and whitespace-insensitive unique indexes on username and email (users_username_normalized_key, users_email_normalized_key), on top of the existing unique constraints.
* A CHECK constraint (users_username_individual) that rejects an untrimmed or empty username and ten generic shared account names: admin, administrator, root, shared, guest, operator, clinic, team, generic, anonymous. The check is case-insensitive.
* The RBAC scope check (require_scope) is covered by 20 tests that include the missing, wrong, prefix, and empty scope cases, and the string-claim fix.

Out of scope, belongs to Phase 5: session lockout after inactivity and failed logins (task 5.3), and electronic signature display fields (printed name, timestamp, meaning; task 5.2).

### Verification

Fresh database. All six files were applied in the order above to an empty database with psql ON_ERROR_STOP=1. A second pass over the idempotent files completed with no error. Every table in schema public is owned by surgitwin_owner.

Application role probe, before the tests were written, through a login role that is a member of surgitwin_app:

* ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_update: ERROR must be owner of table audit_log
* TRUNCATE audit_log: ERROR permission denied for table audit_log
* UPDATE audit_log SET reason = 'x' WHERE false: ERROR permission denied for table audit_log
* CREATE TRIGGER on observations: ERROR permission denied for table observations

Test runs. Command: python -m pytest middleware/tests vv/tests -q with BIOSYNC_TEST_DATABASE_URL pointing at surgitwin_test on the compose container, Python 3.11.9 in .venv-qual311.

| Run | Result | Capture |
|:----|:-------|:--------|
| New FR-DAT-004 OQ module | 48 passed | SNDEV/logs/audit-capture-roles-oq-verbose-2026-10-14.txt |
| New FR-DAT-006 OQ module | 53 passed | same capture |
| New RBAC scope module | 20 passed | same capture |
| Full suite (final) | 618 passed, 12 skipped, 0 failed, 0 xfailed | SNDEV/logs/audit-capture-roles-pytest-2026-10-14.txt |
| Full suite without the three new modules | 497 passed, 12 skipped, 0 failed (one clean run) | not saved. A second run in the same window hit finding F-5 and is not counted. |

Reconciliation with the 492 baseline. The baseline counted 3 xfailed cases in middleware/tests/test_db_ssl_config.py. Another agent has uncommitted edits to that file that remove all of its xfail markers, so the count moved. The 121 new cases account for the rest: 497 + 121 = 618.

Gate evidence.

* G1.2 (audit capture). The suite performs 14 permitted changes on users across INSERT, UPDATE (last_login, role, scopes, password_hash, email), and DELETE. Each produces exactly one audit row with the correct action and actor. For each UPDATE, data_prev equals the row before and data_new equals the row after. For DELETE, data_prev equals the row before and data_new is JSON null. The probe table also produces three correctly ordered rows. The 100% claim covers the changes the suite performs. The WORM tables have no permitted UPDATE or DELETE, so no change there is expected to write a row.
* G1.2 (chain). verify_hash_chain() returns ok after the capture writes. verify_chain() in Python agrees, using data_prev::text and data_new::text as JsonText. Altering one capture row after disabling its trigger inside the test transaction makes verify_hash_chain() report that row ID.
* G1.4 (shared accounts). Ten rejection attempts are rejected: duplicate username, case-variant and padded username, duplicate email, case-variant email, and five generic names. Rejections are 10 of 10. A distinct individual account is accepted, and the table keeps one account after the attempts.
* G1.4 (role boundary). The login role is a member of surgitwin_app, and it cannot run 10 ALTER TABLE, ENABLE or DISABLE TRIGGER, or DROP TRIGGER statements (each fails with must be owner), 11 TRUNCATE statements (permission denied), 22 zero-row UPDATE and DELETE statements over the 11 tables (permission denied), CREATE TRIGGER, SET session_replication_role, DELETE on users, or TRUNCATE on users. The immutability triggers remain enabled (tgenabled O) after the attempts. The same login role can insert into a record table, and its user updates are captured with the actor it sets.
* G1.1 regression. The OQ-7 and OQ-8 suites still pass. The new module repeats zero-row UPDATE and DELETE on each of the 11 WORM and telemetry tables, and TRUNCATE on each except devices, which the foreign key blocks before the trigger runs (as OQ-8 also excludes). All are rejected.

Scratch databases and roles. The module fixtures created surgitwin_audit_test and a login role, and dropped both at module exit. After the final run, pg_database lists postgres, surgitwin, surgitwin_test, and the template databases, and pg_roles lists only surgitwin, surgitwin_app, and surgitwin_owner among the surgitwin roles.

Lint and type checks. No lint or type-check tool is configured for this repository yet (task 1.12). The new SQL was checked by execution on PostgreSQL 15.19 with ON_ERROR_STOP.

### Findings in files this task does not own

* F-1: docker-compose.yml mounts only 001, 002, 003, and 006 into the container init directory. A database created by compose therefore has no audit capture trigger and no application roles. The owner of docker-compose.yml must add 004 and 005 in the order 001, 002, 003, 004, 006, 005. The compose init sorts by file name, so 005 would run before 006 and fail on the telemetry grant. The owner must mount them in the order above by renaming or by an init script.
* F-2: middleware/alembic/versions/0001_initial_schema.py lists 001, 002, 003, and 006 in SQL_FILES. It needs 004 and 005 in the order above.
* F-3: middleware/api/routes/telemetry.py lines 333 and 334 read the scope claim with the same expression as the old auth.py code and then test membership with the in operator. A string claim such as "telemetry_read_only" passes the telemetry_read check, and "superadmin" passes the admin check, because the test is a substring match. The route should use _scopes_from_claim() from api/auth.py. The telemetry WebSocket path is outside this task.
* F-4: The application does not set biosync.actor. The JWT subject does not reach the database session, so the audit actor for application writes is the database login role. Wiring the subject into each database transaction belongs to the database session layer (middleware/database.py, not in this task's scope).
* F-5: Concurrent full-suite runs on surgitwin_test. During this task another pytest process ran the same full suite against port 5432 at the same time. The overlapping runs produced advisory-lock deadlocks on the chain lock (PostgreSQL log; database oid 17993 is surgitwin_test) and 40 failures in the hash-crosscheck module. Test runs against the shared database must not overlap. A per-run database name is the fix.
* F-6: middleware/api/auth.py has three em dashes in comments that predate this change. They are outside the changed hunks and were not edited.

### Decisions for the plan owner

* DELETE on users is permitted and audited, because the VAL-010 split covers only the WORM tables. If account deletion should also be prohibited, a BEFORE DELETE statement trigger on users, modeled on 003-triggers.sql, is the change.
* The denylist includes admin. A database that already holds a user named admin cannot apply 005 until that account is renamed.
* Rejected attempts are not logged to audit_log (see Design decisions).
