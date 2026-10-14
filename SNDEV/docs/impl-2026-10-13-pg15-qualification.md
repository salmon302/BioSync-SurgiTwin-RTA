Title: PostgreSQL 15 qualification of migrated compliance baseline
Date: 2026-10-13T00:00:00Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 tasks 1.2 and 1.3
Summary: Runs the migrated SQL and the DB-gated IQ/OQ tests on PostgreSQL 15.19, fixes the migration and pin defects in owned files, and makes IQ-5 pass. IQ-2 (Python 3.11 gate) and the api/auth.py import defect remain OPEN.

## Task Reference

DEVELOPMENT_PLAN.md Phase 1, task 1.2 (execute the SQL migrations and DB-gated tests on PostgreSQL 15, add the VAL-015 injection suite) and task 1.3 (resolve the IQ-5 failure, check pins against PyPI, verify on Python 3.11). Gates G1.1 (append-only store) and G1.3 (hash chain). Predecessor ledger: `SNDEV/docs/impl-2026-10-13-gateway-migration.md`.

## Specification Summary

* Start PostgreSQL 15 with pgcrypto through `docker-compose.yml`, then apply `database/migrations/001-extensions.sql`, `002-schema.sql`, and `003-triggers.sql` in order.
* Run IQ-3 (pgcrypto), IQ-6 (triggers installed), IQ-7 (Alembic upgrade head), OQ-7 (UPDATE rejection), OQ-8 (DELETE and TRUNCATE rejection), OQ-9 (tamper detection), and the FR-DAT-005 SQL cross-check against the database.
* VAL-015 injection suite: several tamper types on chains of 5 and 200 rows, with 100% detection and the exact broken row ID reported.
* IQ-5: check every pin against PyPI, correct pins that do not resolve, make uvloop platform-conditional, install into an isolated venv, run `pip check` and the full suite.

## Implementation Notes

### Environment

* Host: Windows (win32), PowerShell. Docker Desktop with Docker Engine 25.0.3.
* Database: `postgres:15` image. Server version PostgreSQL 15.19 (Debian, pgdg). pgcrypto 1.3.
* Test database: `surgitwin_test`, owned by the compose role `surgitwin`, created with `CREATE DATABASE` after the init run. The compose container publishes 5432 on `127.0.0.1` only.
* Python: 3.10.11 in `.venv-qual` (gitignored by `.venv-*/`). Python 3.11 is not installed. Python 3.14.3 and 3.9.13 are also installed. 3.14 cannot install the pins (Findings F2). 3.10 is the nearest available interpreter and is used for the qualification run.
* Network use: PyPI (pin checks and pip installs) and the `postgres:15` image pull. No other fetches.
* Credentials: the local test password was set in the process environment only. It is redacted to `<REDACTED>` in every capture under `SNDEV/logs/`.

### Defects found and fixed (owned files)

1. `database/migrations/003-triggers.sql`: three `RAISE EXCEPTION` statements used a `%` placeholder in the message text. SQLAlchemy `exec_driver_sql` with psycopg2 passes the statement through `%` formatting, and the call failed with `TypeError: sqlalchemy.cyextension.immutabledict.immutabledict is not a sequence`. This blocked every DB fixture (IQ-3, IQ-6, IQ-7, OQ-7, OQ-8, and the cross-check). Before: `RAISE EXCEPTION 'Table % is append-only. ...', TG_TABLE_NAME;`. After: `RAISE EXCEPTION USING MESSAGE = 'Table ' || TG_TABLE_NAME || ' is append-only. ...';`. The messages keep the "append-only" wording the tests match. The docker init path (psql) applied the file before and after the change.
2. `middleware/engine/hash_chain.py`: `compute_hash` rendered a top-level JSON null in `data_new` as `{}`. SQL renders the same value as `null`. `data_new` is NOT NULL in `audit_log`, so a Python `None` can only mean JSON null. Before: probe digest mismatch for `null`. After: `_jsonb_text(data_new)` and the `json_null` vector matches. The `data_prev` path is unchanged (see Findings F4).
3. `middleware/engine/hash_chain.py`: `_jsonb_text` rendered floats through `json.dumps`, which uses exponent notation for small and large values. PostgreSQL uses plain notation. Before: `1e-05` gave `1e-05` (Python) against `0.00001` (SQL), and `1.5e-7` gave `1.5e-07` against `0.00000015`. After: `format(Decimal(repr(value)), "f")`. Plain-notation inputs now match (vectors `float_small_plain` and `float_small_plain_long`).
4. `middleware/requirements.txt`: `fhir.resources==7.1.0` lacks `model_validate`, which `middleware/fhir_validator.py` calls. Every `validate_observation` deep validation returned "type object 'Observation' has no attribute 'model_validate'". Changed to `fhir.resources==8.3.0`. `fhir-core==1.1.11` is pinned because fhir.resources declares it as a floating dependency. Result: `test_valid_observation_no_errors` PASS, `pip check` clean.
5. `middleware/requirements.txt`: `uvloop==0.19.0` has no Windows build. Changed to `uvloop==0.19.0; sys_platform != "win32"`. `middleware/api/loop_policy.py` already falls back to the default event loop when uvloop is absent, so no runtime code changed.
6. `vv/tests/IQ/test_iq5_pip_check.py`: the requirement parser ignored environment markers, and the installed-package check used substring matching. The parser now evaluates markers with `packaging.requirements.Requirement`. The check compares PEP 503 canonical names (`packaging.utils.canonicalize_name`), so `fhir-core` matches the installed `fhir_core`. The substring match is stricter now and no longer accepts a near-name.
7. `docker-compose.yml`: the postgres service had no healthcheck and published no port. Added `pg_isready` healthcheck and `127.0.0.1:5432:5432` for host-side tests.
8. `.gitignore`: added `.venv-*/` so `.venv-qual` is ignored.
9. `.env.example`: the test URL named role `surgitwin_test`, which the compose stack does not create. Changed to role `surgitwin` on database `surgitwin_test`, with the `CREATE DATABASE` command documented.

### Test additions (owned directories)

* `vv/tests/OQ/test_oq_fr_dat_005_hash_crosscheck.py` existed from the migration as a single-vector file. It was extended, not replaced. It now holds the JSON vector set, the known-limit xfail cases, the VAL-015 injection suite (54 cases), the tail deletion boundary, the nightly report check, and a summary test that prints the tamper-detection table to the run output.
* `vv/tests/OQ/test_oq_fr_dat_004_truncate_cascade_devices.py` is new. OQ-8 in `middleware/tests` skips `devices` because a plain TRUNCATE is refused by the foreign key check before any trigger runs. `TRUNCATE devices CASCADE` reaches the `devices` rejection trigger. The new test covers that path. The check was run in a rolled-back transaction before the test was written: plain TRUNCATE returned "cannot truncate a table referenced in a foreign key constraint", and CASCADE returned "Table devices is append-only. TRUNCATE operations are not permitted."

### Interpreter decision (task 1.3)

Python 3.11 is not installed (`py -0` lists 3.14, 3.10, and 3.9). Python 3.14 cannot install the pins: a binary-only dry run (`SNDEV/logs/pip-dryrun-py314-2026-10-13.txt`) fails on `psycopg2-binary==2.9.9`, and a per-pin check shows `numpy==2.1.3` and `pandas==2.2.2` also have no 3.14 wheel. The venv uses 3.10.11 because every pin has a 3.10 wheel or an abi3 wheel. This is a stand-in for the 3.11 target. IQ-2 fails on 3.10 by design, and it is the only test that depends on the minor version. The 3.11 run is recorded as OPEN.

### Pin verification against PyPI (task 1.3)

All 15 runtime and test pins in the migrated requirements resolved on PyPI on 2026-10-13 (JSON API, not yanked): fastapi 0.115.5, uvicorn 0.32.1, uvloop 0.19.0, sqlalchemy 2.0.36, psycopg2-binary 2.9.9, alembic 1.14.0, python-jose 3.5.0, cryptography 49.0.0, bcrypt 5.0.0, fhir.resources 7.1.0 (replaced, see defect 4), pydantic 2.10.3, numpy 2.1.3, pandas 2.2.2, pytest 8.3.4, httpx 0.28.1. The IQ-5 failure came from a missing install (no venv was provisioned from the pins), uvloop having no Windows build, and the FHIR pin defect. No pin failed to resolve.

### Run history

| Run | Capture | Result | Cause addressed next |
|:----|:--------|:-------|:---------------------|
| 1 | `pg15-qualification-run-1.log` | Collection stopped on 4 errors | `api/auth.py` NameError (Finding F1) |
| 2 | `pg15-qualification-run-2.log` | 121 passed, 4 failed, 54 errors | `%` in migration SQL (defect 1) |
| 3 | `pg15-qualification-run-3.log` | 171 passed, 4 failed, 4 errors | FHIR pin (defect 4), hash rendering (defects 2 and 3), IQ-5 naming (defect 6) |
| 4 | `pg15-qualification-run-4.log` | 250 passed, 3 failed, 3 skipped, 5 xfailed, 8 errors | IQ-5 `fhir-core` vs `fhir_core` (defect 6) |
| Final | `pg15-qualification-run.log` | 260 passed, 3 failed, 3 skipped, 5 xfailed, 8 errors | Remaining items are findings below |

## Verification

### Final suite run

Command, from the repository root with the venv `.venv-qual`:

    python -m pytest middleware/tests vv/tests -v -rsxfE -p no:cacheprovider --continue-on-collection-errors

Environment: `BIOSYNC_TEST_DATABASE_URL` points at `surgitwin_test` on the compose container. The database was dropped and recreated before the run, so the migrations and the Alembic upgrade ran against an empty schema. The flag `--continue-on-collection-errors` lets the eight blocked modules report instead of halting the run. Without it, collection stops at the first import error.

Result: 260 passed, 3 failed, 3 skipped, 5 xfailed, 8 collection errors, in 20.75 seconds. Capture: `SNDEV/logs/pg15-qualification-run.log`. `pip check` before the run: "No broken requirements found."

| Protocol or module | Result | Notes |
|:-------------------|:-------|:------|
| IQ-2 Python version | FAIL (1) | Interpreter is 3.10.11, requirement is 3.11 (Finding F2) |
| IQ-3 pgcrypto | PASS (2 of 2) | `crypt()` and `gen_salt('bf')` return a value on PostgreSQL 15.19 |
| IQ-4 Pulse engine init | SKIP | No Pulse bindings on this host |
| IQ-5 pip check | PASS (4 of 4) | Requirements, critical imports, pip list match, pip check |
| IQ-6 triggers installed | PASS (11 of 11) | Chain trigger and three rejection triggers on each of 10 WORM tables |
| IQ-7 Alembic upgrade head | PASS (1 of 1) | `alembic_version` is `0001_initial_schema` |
| OQ-7 UPDATE rejection | PASS (14 of 14) | Named UPDATEs, zero-row UPDATEs on all 10 tables, row unchanged |
| OQ-8 DELETE and TRUNCATE rejection | PASS (21 of 21) | Named DELETEs, zero-row DELETEs on 10 tables, TRUNCATE on 9 tables |
| OQ-8 supplement, TRUNCATE CASCADE on devices | PASS (1 of 1) | New file, see above |
| OQ-9 tamper detection (middleware) | ERROR (6 tests not run) | Blocked by Finding F1 |
| FR-DAT-005 cross-check and injection | PASS (87), XFAIL (2) | See tables below |
| PQ-3 one million rows | SKIP | Needs `BIOSYNC_PQ3_DATABASE_URL`, task 1.11 |
| OQ-16 Pulse state serialization | SKIP | No Pulse bindings on this host |
| OQ-NFR-SEC-001 JWT secret (2 tests) | FAIL (2) | Subprocess import of `api.auth` (Finding F1) |
| OQ-FR-DAT-007 FHIR HTTP | ERROR (collection) | Finding F1 |
| API auth and smoke (middleware) | ERROR (collection) | Finding F1 |
| Telemetry relay tests (commit d0ef2c5) | ERROR (collection, 4 modules) | Finding F1 |
| Gateway R2 checks | XFAIL (3) | Strict known-debt xfail, unchanged |
| PQ hash chain performance (`test_pq_fr_dat_005_chain_perf.py`) | PASS (5 of 5) | Existing PQ suite, run only as part of the command |
| Hash chain unit tests | PASS (17 of 17) | Includes the change to `data_new` rendering |
| FHIR validation unit tests | PASS (10 of 10) | Includes deep validation after the pin change |

### Tamper-detection table (VAL-015)

Source: summary block printed by `test_injection_suite_summary` in the capture. Each row aggregates three positions (first, middle, last). The table is generated from `_RESULTS` in the test module. "Reported row correct" means `verify_hash_chain()` returned the injected row ID. "Python agrees" means `verify_chain()` returned the same ID.

| Tamper type | Rows | Cases | Detected | Reported row correct | Python agrees |
|:------------|-----:|------:|---------:|---------------------:|--------------:|
| data_new | 5 | 3 | 3 | 3 | 3 |
| data_new | 200 | 3 | 3 | 3 | 3 |
| data_prev | 5 | 3 | 3 | 3 | 3 |
| data_prev | 200 | 3 | 3 | 3 | 3 |
| actor_id | 5 | 3 | 3 | 3 | 3 |
| actor_id | 200 | 3 | 3 | 3 | 3 |
| occurred_at (1 microsecond) | 5 | 3 | 3 | 3 | 3 |
| occurred_at (1 microsecond) | 200 | 3 | 3 | 3 | 3 |
| reason | 5 | 3 | 3 | 3 | 3 |
| reason | 200 | 3 | 3 | 3 | 3 |
| prev_hash | 5 | 3 | 3 | 3 | 3 |
| prev_hash | 200 | 3 | 3 | 3 | 3 |
| current_hash | 5 | 3 | 3 | 3 | 3 |
| current_hash | 200 | 3 | 3 | 3 | 3 |
| reorder adjacent rows (id swap) | 5 | 3 | 3 | 3 | 3 |
| reorder adjacent rows (id swap) | 200 | 3 | 3 | 3 | 3 |
| delete interior row | 5 | 3 | 3 | 3 | 3 |
| delete interior row | 200 | 3 | 3 | 3 | 3 |
| TOTAL | | 54 | 54 | 54 | 54 |

Detection rate: 54 of 54 in-scope cases (100%). Each tamper is applied with the append-only trigger disabled for the statement, the way a table owner would apply it. Each test first asserts that the untampered chain verifies as "ok".

Documented boundary, outside the injection total:

| Tamper type | Rows | Chain status after deletion | Python valid |
|:------------|-----:|:----------------------------|:-------------|
| delete last row (tail) | 5 | ok | True |
| delete last row (tail) | 200 | ok | True |

A tail deletion leaves a valid prefix, so the chain cannot detect it without an external anchor (Finding F3).

### Digest cross-check (FR-DAT-005)

Nineteen JSON value vectors match between the Python engine and `audit_chain_digest()` on PostgreSQL 15.19. The vectors cover: JSON null, true, false, integers (including 9007199254740993), negative integers, decimals in plain notation (98.6, -0.5, 1.0, 0.0, 0.00001, 0.00000015), strings with escapes and non-ASCII characters, empty object and array, nested objects with mixed value types, and object key ordering by length and then by bytes. A vector set is not a proof for every JSON document. The two forms in `KNOWN_LIMIT_VECTORS` are strict xfail (Finding F5).

The nightly report in `database/migrations/hash-chain-check.sql` was run through the test harness on valid and tampered chains of 5 and 200 rows. It reported OK on valid chains (total entries matched the row count), and it reported BROKEN with the expected first broken ID for data_new, reorder, and delete injections. All 8 cases pass.

### Gate status

| Gate | Status | Evidence |
|:-----|:-------|:---------|
| G1.1 Append-only store | PASS on PostgreSQL 15.19 for the 10 WORM tables | OQ-7 (14 cases), OQ-8 (21 cases plus the devices CASCADE case). Row counts are asserted unchanged. Plain TRUNCATE devices is refused by the foreign key check, not by the trigger. The trigger case is covered by CASCADE. The OQ-7 and OQ-8 files in `middleware/tests` are not owned by this task and were not edited. |
| G1.3 Hash chain | OPEN | The SQL verifier passes 54 of 54 injection cases (100%) with the exact row ID, the Python verifier agrees, the nightly report agrees, and 19 of 19 JSON vectors match. The middleware OQ-9 file cannot be collected until Finding F1 is fixed, so its six tests have not run in this tree. |
| IQ-3 pgcrypto | PASS | 2 of 2 |
| IQ-5 pip check | PASS | 4 of 4, on Python 3.10.11 |
| IQ-6 triggers | PASS | 11 of 11 |
| IQ-7 Alembic upgrade | PASS | 1 of 1 |
| Task 1.3 interpreter 3.11 | OPEN | Python 3.11 is not installed (Finding F2) |

### Verification of the OQ-9 blocker

A temporary copy of `middleware/`, `vv/`, and `database/` (outside the repository) received one change: the return annotation of `authenticate_user` changed from `Optional[User]` to `Optional["User"]`. The copy was run against the same database. The five suites that import `api.auth` (`test_oq9_tamper_detection.py`, `test_api_auth.py`, `test_smoke.py`, `test_oq_fr_dat_007_fhir_http.py`, and `test_oq_nfr_sec_001_jwt_secret.py`) reported 32 passed. The repository file was not edited, and the copy was removed afterwards.

## Findings

Findings are not fixed in this task. Each one names the owner or the next step.

F1 (OPEN, blocker, file not owned): `middleware/api/auth.py` line 84 annotates `authenticate_user` as returning `Optional[User]`, but `User` is defined later in the module. Python evaluates annotations when the `def` runs, so the import raises `NameError: name 'User' is not defined`. This happens on every Python version. Eight modules fail collection: `middleware/tests/test_api_auth.py`, `middleware/tests/test_oq9_tamper_detection.py`, `middleware/tests/test_smoke.py`, `vv/tests/OQ/test_oq_fr_dat_007_fhir_http.py`, and four telemetry relay modules (`test_relay_offloop_persistence.py`, `test_relay_postgres_integration.py`, `test_relay_response_time.py`, `test_relay_session_records.py`, committed in d0ef2c5). Two OQ-NFR-SEC-001 tests fail because they spawn a subprocess that imports the same module. Owner action: quote the annotation or add `from __future__ import annotations`. Verified in a copy (see above).

F2 (OPEN, interpreter): Python 3.11 is not installed, so IQ-2 fails on 3.10.11 by design. Python 3.14 cannot install the pinned `psycopg2-binary==2.9.9`, `numpy==2.1.3`, and `pandas==2.2.2`, because those versions have no 3.14 wheel. Owner action: install Python 3.11 and rerun this log, or decide on a pin set for 3.14.

F3 (OPEN, design limit): deleting the last row of a chain is not detected by `verify_hash_chain()` or by `verify_chain()`. The two boundary tests pass and document this. Owner action: add an external anchor (for example, a nightly export of the head hash), and state the limit in the FR-DAT-005 verification.

F4 (OPEN, Python verifier): a row whose `data_prev` is stored as JSON null (`'null'::jsonb`) verifies as "ok" in SQL and fails in `verify_chain()`, which reports `(False, 22970)` for a one-row probe. psycopg2 decodes both SQL NULL and JSON null to Python `None`, and `compute_hash` renders `None` as `{}`. The API layer that writes `data_prev` was not reviewed (not owned). Owner action: reject JSON null in `data_prev` at write time, or pass raw JSON text to the Python verifier.

F5 (OPEN, Python verifier, known limit): JSON numbers written in exponent notation (`1e3`) and decimals with more than 17 significant digits cannot be reproduced from the psycopg2 float. Both cases are strict xfail in the cross-check file. The SQL verifier stays authoritative for these values.

F6 (OPEN, static, not executed): `database/migrations/006-telemetry-sessions.sql` (commit d0ef2c5, another task) contains `RAISE EXCEPTION 'Telemetry session % has no open record; ...'`, the same `%` pattern fixed in 003 (defect 1). The file is not applied by `dbsupport.py` or by the compose init, so this run did not execute it. Applying it through `exec_driver_sql` with psycopg2 will fail the same way. Owner action: use the `USING MESSAGE` form.

F7 (OPEN, record accuracy): the ledger `SNDEV/docs/impl-2026-10-13-gateway-migration.md` reports 147 passed and 1 failed (V1). That result was recorded before the SQL ran and before the FHIR pin and the `api/auth.py` import defect were found. It is not reproduced on this tree. The DB-gated suites in that run were skipped, so no DB result from that run is evidence.

## Operational notes

* The compose init scripts run only on an empty `pgdata` volume. An existing volume keeps its schema and does not rerun 001 to 003.
* The `postgres` container from this task is left running on `127.0.0.1:5432`. Its password is the local value set in the process environment and is not stored in any file.
* `SNDEV/logs/` is gitignored by repository policy, so the run captures are referenced by path and are not committed.
