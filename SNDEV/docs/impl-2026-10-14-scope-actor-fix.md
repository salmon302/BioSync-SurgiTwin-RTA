Title: RBAC scope-check bypass fix and audit actor propagation
Date: 2026-10-14T17:15:51Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: F-3 and F-4 findings from SNDEV/docs/impl-2026-10-14-audit-capture-roles.md (FR-DAT-004, FR-DAT-006, NFR-SEC-001)
Summary: Replaces substring-based WebSocket scope checks with exact scope-set membership, and sets biosync.actor from the verified JWT subject on each request session so audit_log rows record the user.

## Task Reference

Findings F-3 and F-4 in SNDEV/docs/impl-2026-10-14-audit-capture-roles.md. The audit-capture trigger from task 1.8 (commit f4b9d8f, database/migrations/004-audit-capture.sql) reads biosync.actor and is not modified.

## Specification Summary

* F-3 (FR-DAT-006, NFR-SEC-001): A WebSocket scope check in middleware/api/routes/telemetry.py used a substring test on the raw scope claim. A scope named telemetry_read_only satisfied telemetry_read, and superadmin satisfied admin. Every scope check in middleware/api must use exact membership over the claim parsed by _scopes_from_claim().
* F-4 (FR-DAT-004): No code set biosync.actor, so application writes recorded the database login role as the actor. Each authenticated database transaction must carry the JWT subject as the actor. Behavior without a JWT must be documented.

## Implementation Notes

### F-3 scope checks

Audit of middleware/api and middleware/*.py for scope membership tests:

| Location | Test | Result |
|---|---|---|
| middleware/api/routes/telemetry.py (WebSocket read gate) | substring test on the raw claim | Fixed. The claim now goes through _scopes_from_claim() and exact list membership. |
| middleware/api/routes/telemetry.py (WebSocket publish gate) | substring test on the raw claim | Fixed by the same change. |
| middleware/api/auth.py require_scope | required_scope not in user.scopes, where user.scopes is a parsed list | Already exact. No change. |
| middleware/api/routes/*.py | Depends(require_scope(...)) only | No inline checks. No change. |

The telemetry.py change: scopes = _scopes_from_claim(payload.get("scope") or payload.get("scopes")), and the two membership tests are unchanged in form.

### F-4 actor propagation

Design:

1. middleware/database.py adds set_actor(session, actor). It validates the value (non-empty string, at most 255 characters, matching audit_log.actor_id VARCHAR(255)), stores it in session.info["actor"], and applies it to the open transaction if one exists.
2. middleware/database.py registers an after_begin listener on Session. At the start of every transaction it runs SELECT set_config('biosync.actor', :actor, true) when session.info holds an actor. A session that commits and begins again keeps its actor, and each new transaction receives it.
3. middleware/api/auth.py get_current_user depends on get_db. After the token verifies, it calls set_actor(db, sub). FastAPI caches dependencies per request, so a route that depends on get_db and on require_scope receives the same session that carries the actor. The change needs no route edits.

Pooling: set_config(..., true) has SET LOCAL semantics. The value is cleared at commit or rollback, and the pool rolls back on connection return, so a pooled connection never carries an actor into another transaction. The single-connection test in middleware/tests/test_actor_propagation.py checks this directly.

No JWT: an unauthenticated request to an authenticated route returns 401 before any write. A session with no actor (scripts, migrations, and the relay writer, which uses its own session) leaves biosync.actor unset, and the trigger records session_user, which is the database login role. This is the default that 004-audit-capture.sql documents. Invalid subjects (missing, empty, non-string, or longer than 255 characters) return 401, so no actor is set from them.

Trust base: the actor is the token subject. The subject is not checked against the users table. The signature check in verify_token and get_current_user is the trust base, as it is for scope claims.

Scope limit: the relay writer (middleware/api/relay_writer.py, relay_sink.py) and pulse engine sessions open their own sessions and do not carry request actors. Their writes record the login role. That matches the existing relay design, and no change was made there.

### Files changed

* middleware/api/routes/telemetry.py (scope parsing, 2 lines)
* middleware/api/auth.py (get_current_user dependency and actor set)
* middleware/database.py (set_actor, after_begin listener, constants)
* middleware/tests/test_scope_enforcement.py (new, 41 cases across scope tests, see Verification)
* middleware/tests/test_actor_propagation.py (new, actor tests on a scratch database)
* SNDEV/docs/impl-2026-10-14-scope-actor-fix.md (this log)

Not changed: database/migrations/*, docker-compose.yml, middleware/tests/dbsupport.py, middleware/tests/test_db_ssl_config.py, middleware/models.py, middleware/engine/*, vv/*, docs/*, DEVELOPMENT_PLAN.md.

Pre-existing em dashes in middleware/api/auth.py (lines 50, 71, 118) are outside the changed hunks and were left unedited, as recorded in F-6.

### Test database

The suite ran against surgitwin_sec_test, created on the compose container (127.0.0.1:5432) with OWNER surgitwin. surgitwin_test was not used. The compose container accepts plaintext connections only, so the runs set DB_SSLMODE=prefer, the conftest default. The actor tests use a scratch database, surgitwin_sec_actor_test, created and dropped by dbsupport.scratch_database. Audit rows are append-only, so committed test rows need a database that is dropped on exit. Credentials were read from the container environment at run time and are not recorded here.

## Verification

Checks run in .venv-qual311 (Python 3.11.9) on PostgreSQL 15 with surgitwin_sec_test.

| Step | Command | Result | Capture |
|---|---|---|---|
| Baseline, existing auth, RBAC, and relay modules before the new tests | pytest middleware/tests/test_api_auth.py test_roles_scope.py test_relay_offloop_persistence.py test_relay_response_time.py | 55 passed | terminal output, not saved |
| Regression check: committed telemetry.py against the new scope tests | pytest middleware/tests/test_scope_enforcement.py (HEAD version of telemetry.py swapped in and restored) | 6 failed, 20 passed. The six failures are the substring cases: telemetry_read_only, superadmin, telemetry_write_only, and the prefix-extension and admin-substring publish cases | terminal output, not saved |
| New scope and actor tests | pytest middleware/tests/test_scope_enforcement.py middleware/tests/test_actor_propagation.py | 41 passed, 0 skipped | terminal output, not saved |
| Audit-capture and access-control OQ suites | pytest vv/tests/OQ/test_oq_fr_dat_004_audit_capture.py vv/tests/OQ/test_oq_fr_dat_006_access_control.py | 101 passed | SNDEV/logs/scope-actor-oq-audit-rbac-2026-10-14.log |
| Middleware suite | pytest middleware/tests | 207 passed, 9 skipped (TLS and relay integration URLs unset) | SNDEV/logs/scope-actor-middleware-2026-10-14.log |
| Full suite, once | pytest middleware/tests vv/tests -q | 659 passed, 12 skipped, 0 failed | SNDEV/logs/scope-actor-full-suite-2026-10-14.log |

Baseline comparison: the earlier suite was 618 passed, 12 skipped. The 41 new cases account for the difference (618 + 41 = 659). The skip count is unchanged.

Concurrent runs: no other python or pytest process was running when the full suite started. No advisory-lock deadlocks or hash cross-check failures were seen.

Test coverage of F-3: a WebSocket scope named telemetry_read_only is refused with close code 4403. A scope named superadmin does not satisfy admin. A telemetry_read claim is accepted, and space-delimited, tab-delimited, list-form, and legacy scopes claims parse correctly. The HTTP telemetry routes refuse prefix extensions with 403.

Test coverage of F-4: an API write (POST to a route that uses require_scope and get_db) recorded the JWT subject as the UPDATE actor on the users table, and the login role was not used. The actor is re-applied in each transaction of one session. The pooled single-connection test shows no actor carries into the next checkout. Unauthenticated writes record the login role. Invalid subjects return 401.
