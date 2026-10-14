Title: FR-DAT-006 role matrix execution under TLS via SET ROLE
Date: 2026-10-14T17:49:18Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: Follow-up to SNDEV/docs/impl-2026-10-14-closure-fixes.md item 1 (gate G1.4 under TLS)
Summary: The FR-DAT-006 role matrix module runs under client-certificate TLS by switching the certified login to scratch roles with SET ROLE, and fixes the em dashes in four comment and docstring locations.

## Task Reference

* Follow-up to SNDEV/docs/impl-2026-10-14-closure-fixes.md, item 1. The FR-DAT-006 access-control module (vv/tests/OQ/test_oq_fr_dat_006_access_control.py) skipped 39 cases under TLS because each run created a random login role whose name did not match the client certificate CN.
* Gate G1.4 (FR-DAT-006 unique individual credentials and role separation) under TLS.
* Matrix source: SNDEV/docs/impl-2026-10-14-audit-capture-roles.md, section "G1.4 (role boundary)".
* Scratch TLS server pattern: SNDEV/docs/impl-2026-10-14-r2-tls.md.

## Specification Summary

* Under client-certificate TLS (pg_hba.conf hostssl clientcert=verify-full), the CN of the client certificate must equal the login role. database/certs/generate-certs.sh issues one client CN (surgitwin), so the module cannot log in as a random role.
* The privilege matrix executes under TLS through SET ROLE from the certified connection. The module creates scratch roles from the owner path and does not change certificates.
* The module no longer skips under TLS. The target is zero blanket skips and zero errors.
* Comment cleanup, behavior-neutral: em dashes (U+2014) in middleware/engine/lttb.py (lines 4, 38, 120, 151), middleware/api/routes/auth.py (line 90, comment only), and vv/tests/IQ/test_iq2_python_version.py (line 16) are replaced with commas, colons, or parentheses.
* Not changed: database/certs/generate-certs.sh, middleware/api (except the routes/auth.py comment), middleware/engine (except the lttb.py comments), database/migrations, docker-compose.yml, vv/tests/PQ, vv/traceability, docs, DEVELOPMENT_PLAN.md.

## Implementation Notes

### Plan (recorded before edits)

Fixture design, planned:

* The certified login (the user in the TLS URL, CN surgitwin) is the connection for the owner path. It is the server superuser in the postgres:15 image, so it can create roles and the scratch database.
* A module-scoped fixture creates one scratch role per run: NOLOGIN, granted membership in surgitwin_app. Its name is random, as before.
* Each application-role case opens a connection from the owner engine, runs SET ROLE to the scratch role, runs the statement, and runs RESET ROLE before the connection returns to the pool. The role is changed with plain SET ROLE after a commit, so it survives the commit and is removed by RESET ROLE in a finally block.
* The member check now asserts current_user equals the scratch role and session_user equals the certified login.
* The plaintext path uses the same SET ROLE code. The password login for the application role is no longer exercised by this module. The check that a login role is a member of surgitwin_app is replaced by the membership check on the scratch role.

Scratch database name: BIOSYNC_TEST_DATABASE_URL points at the surgitwin_roles_tls_test database on the scratch server at 127.0.0.1:5436. scratch_database() uses that URL only for its admin connection and creates surgitwin_audit_test on the same server, as the module already does.

### Files changed

* vv/tests/OQ/test_oq_fr_dat_006_access_control.py. Fixture and class changes described below. The 53 test functions and their parameter sets are unchanged, so the case set is the same under both modes.
* middleware/engine/lttb.py. Four comment lines (4, 38, 120, 151). Em dashes replaced with colons. Comment-only change.
* middleware/api/routes/auth.py. One comment line (90). The em dash is replaced with a colon. Comment-only change. No logic change in this file.
* vv/tests/IQ/test_iq2_python_version.py. One docstring line (16). The em dash is replaced with a colon. Docstring-only change.

The diff of the three runtime and IQ files shows six changed lines, all comments or docstrings. The line endings are preserved.

### Fixture design

* audit_db (module): unchanged. It creates surgitwin_audit_test on the server named by BIOSYNC_TEST_DATABASE_URL and drops it on exit.
* app_role (module, replaces app_engine): creates a NOLOGIN role surgitwin_app_scratch_<hex> with GRANT surgitwin_app. It drops the role on exit. No password is generated, and the role cannot log in.
* app_connection (context manager): opens a connection from the audit_db engine, runs SET ROLE to the scratch role, and commits. The connection then holds no open transaction, so each case can begin its own. On exit it rolls back, runs RESET ROLE, and commits before the connection returns to the pool.
* _app_error(audit_db, role, statement): the same behavior as before, run through app_connection.
* The application-role tests use app_connection in place of the old login engine. The member check asserts that current_user is the scratch role, that session_user is the certified login from the URL, and that the scratch role is a member of surgitwin_app.
* TLS_ROLE_SKIP_REASON and the pg_stat_ssl check are removed. Nothing in the module skips for a TLS reason.

### SET ROLE semantics used

* SET ROLE is session scoped. The statement runs after a commit, so it is not undone by the rollback of a later failed transaction. RESET ROLE runs in a finally block, so a failed case cannot leave the pooled connection in the scratch role.
* The certified login is a server superuser (the postgres:15 image creates POSTGRES_USER as superuser). A superuser can SET ROLE to any role. After SET ROLE, the checks use the scratch role's privileges, and the superuser bypass does not apply. The "must be owner", "permission denied", and session_replication_role checks therefore see the application role's rights.
* The scratch role inherits surgitwin_app (INHERIT is the default), so it has the grants of that role and no others.

### Residual skips

None. The TLS run has zero skipped cases.

### Scope changes against the brief

* The plaintext run was not made against the 5432 container. Its configured POSTGRES_PASSWORD (from docker inspect) does not authenticate: pg_hba line 100 rejects the connection with password authentication failed for user surgitwin. The data volume was initialized with a different password. The credential was not changed. The 5432 run skipped all 101 cases as unreachable (SNDEV/logs/roles-plaintext-5432-2026-10-14.log). The plaintext regression was run on a second scratch container, srta-roles-plain-5437 (postgres:15, default pg_hba.conf, 127.0.0.1:5437).
* The plaintext path uses SET ROLE too. The previous plaintext path logged in as a random role with a password. The password login of the application role is no longer exercised by this module. This was not checked against the rest of the repository.
* The TLS URL uses the database surgitwin_roles_tls_test on 127.0.0.1:5436. scratch_database() connects to the postgres database for admin work, and the module creates surgitwin_audit_test on the same scratch server.

### Findings in files this task does not own

* F-A: middleware/tests/dbsupport.py line 16 still says the application-role module "skips under TLS with a reason". The owner of dbsupport.py should replace that sentence with a pointer to SET ROLE. No change was made here.
* F-B: the 5432 container's configured POSTGRES_PASSWORD does not match the password of its data volume. Plaintext runs against 5432 with the container configuration fail. The owner of the shared database needs to restore the credential or rotate it through an operator step.
No runtime change is needed for this task. The runtime middleware files were not changed except for the comment lines listed above.

## Verification

### Scratch servers

| Name | Image | Address | Mode | Database | Role |
|------|-------|---------|------|----------|------|
| srta-roles-tls-5436 | postgres:15 | 127.0.0.1:5436 | TLS, hostssl clientcert=verify-full, database/postgres/pg_hba.conf, database/certs/postgres-entrypoint.sh, certificates from database/certs/out | surgitwin_roles_tls_test | Owner and superuser surgitwin, CN surgitwin (openssl subject check: CN = surgitwin) |
| srta-roles-plain-5437 | postgres:15 | 127.0.0.1:5437 | Plaintext, default pg_hba.conf (ssl off) | surgitwin_roles_plain_test | Owner and superuser surgitwin |

The passwords were generated in process memory and read back from the container configuration in the same command. They are not stored in any file.

### TLS run (command: python -m pytest vv/tests/OQ/test_oq_fr_dat_006_access_control.py -q -rs, .venv-qual311, Python 3.11.9)

Result: 53 passed, 0 skipped, 0 failed, 0 errors. The module had 39 blanket skips under TLS before this change.

Capture: SNDEV/logs/roles-tls-run1-2026-10-14.log.

An earlier attempt in this session ran with an empty password variable (the shell did not keep a variable between calls), and all 53 cases skipped as unreachable. That run is not a result. The log file was overwritten by the passing run.

### Plaintext run, two modules

Command: python -m pytest vv/tests/OQ/test_oq_fr_dat_004_audit_capture.py vv/tests/OQ/test_oq_fr_dat_006_access_control.py -q -rs, against srta-roles-plain-5437.

Result: 101 passed, 0 skipped, 0 failed. This matches the plaintext baseline of 101 (48 from the audit module and 53 from the roles module).

Capture: SNDEV/logs/roles-plaintext-5437-2026-10-14.log.

The same two-module command against the 5432 container: 101 skipped as unreachable, because of finding F-B. Capture: SNDEV/logs/roles-plaintext-5432-2026-10-14.log. This is not a regression result.

### Comment cleanup

* middleware/engine/lttb.py: lines 4, 38, 120, 151 changed. Dash count after the edit: 0.
* middleware/api/routes/auth.py: line 90 changed. Dash count after the edit: 0. No logic change.
* vv/tests/IQ/test_iq2_python_version.py: line 16 changed. Dash count after the edit: 0.
* vv/tests/OQ/test_oq_fr_dat_006_access_control.py: dash count 0 (en and em).
* The three edited files parse with ast.

The IQ-2 module was not run. The change is in a docstring only.

### Teardown

Scratch containers srta-roles-tls-5436 and srta-roles-plain-5437 were removed with `docker rm -f` after the runs, which removed their databases (surgitwin_roles_tls_test, surgitwin_roles_plain_test, and the module-created surgitwin_audit_test on each). The 5432 container biosync-surgitwin-rta-postgres-1 was not stopped, recreated, or altered. Two read-only checks ran against it: current_setting('ssl') and a docker inspect of its environment.

Result: DONE for the TLS module (53 of 53, zero skips, zero errors). DONE for the plaintext regression on the scratch server (101 of 101). OPEN for a plaintext run on the 5432 container (finding F-B).
