Title: WebSocket telemetry relay migration with off-loop persistence (R3)
Date: 2026-10-14T00:34:40Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 task 1.5 (Gateway R3 closure)
Summary: Migrates the Gateway WebSocket and HTTP telemetry relay with database writes moved to a bounded queue and a writer task, adds telemetry_sessions as an append-only table, and adds the response-time middleware.

## Task Reference

DEVELOPMENT_PLAN.md Phase 1 task 1.5 and gate G1.5 (relay routes perform no synchronous database writes, and `middleware/tests/test_uvloop_enabled.py` PASSES). Requirements: SRS.md FR-DAT-001, FR-DAT-003, FR-DAT-004, FR-DAT-005, FR-RTA-005, NFR-PERF-001, NFR-PERF-002, NFR-SEC-001. Carried item: Gateway R3 in `docs/migration-map.md` Table 3. Source material: BioSync-Gateway `middleware/api/routes/telemetry.py`, `telemetry_generator.py`, `middleware/api/middleware/response_time.py`, `middleware/api/loop_policy.py`, and the `telemetry_sessions` table in `database/migrations/002-schema.sql`.

## Specification Summary

* The WebSocket relay and the HTTP ingest route accept telemetry frames, apply the per-channel EMA filter, and relay the filtered frame to subscribers.
* Each telemetry sample is persisted in `surgical_telemetry` with the raw value (source of truth) and the EMA value (FR-3.5.3 pattern).
* Relay code performs no synchronous database write on the event loop (G1.5). Persistence runs in a writer task, and the synchronous driver runs in a worker thread.
* Session tracking uses `telemetry_sessions` (session id, connected time, disconnected time, points relayed, client identity from the JWT `sub` claim). The table is append-only with a finalization row pattern.
* Session lifecycle events are written to the hash-chained `audit_log` through `insert_audit_log()`.
* The uvloop policy is applied at startup and degrades to the default loop on Windows (G1.5).
* The response-time middleware records per-request and WebSocket relay latency (NFR-PERF-002 measurement point).

## Implementation Notes

### Files

Created:

* `middleware/api/relay_writer.py`: bounded queue, writer task, retry policy, record types. Imports no database module.
* `middleware/api/relay_sink.py`: `SqlAlchemyRelaySink`, the only code that writes to PostgreSQL in the relay. Runs synchronous SQLAlchemy work through `asyncio.to_thread`.
* `middleware/api/routes/telemetry.py`: WebSocket `/stream`, HTTP `/ingest`, `/stream/info`, `/ingestion/stats`, the relay service, and the optional simulator.
* `middleware/api/routes/telemetry_generator.py`: adapted from the Gateway unchanged except for timezone-aware timestamps and the removal of the module-level singleton.
* `middleware/api/middleware/__init__.py`, `middleware/api/middleware/response_time.py`: adapted from the Gateway. Pulse engine imports `record_pulse_step` from this module, so the full registry is kept.
* `database/migrations/006-telemetry-sessions.sql`: DDL for `telemetry_sessions`, a finalization guard, WORM triggers, and comments.
* `middleware/tests/test_relay_offloop_persistence.py`, `middleware/tests/test_relay_session_records.py`, and `middleware/tests/test_relay_postgres_integration.py`.

Adapted:

* `middleware/api/main.py`: `create_app()` factory wiring the routers, the response-time middleware, the lifespan that starts and stops the writer, and the uvloop policy. The module-level `app` and `health` names are kept.
* `middleware/models.py`: `TelemetrySession` mapping only.
* `middleware/tests/test_uvloop_enabled.py`: graceful-degradation and applied-policy checks that run without uvloop installed.

### Design of the off-loop write path

The relay path is a chain of three steps. The handler validates and filters a frame and places its records in a bounded queue (no `await` between the capacity check and the enqueue, so the check is exact on a single loop). The writer task drains the queue in batches. The sink hands each batch to a worker thread through `asyncio.to_thread`, where the synchronous psycopg2 session commits one transaction for the batch.

### Design decision table

| Decision | Choice | Rationale |
|:---------|:-------|:----------|
| Queue type | `asyncio.Queue` with `maxsize` (default 10000) | All producers and the consumer run on one loop, so no thread lock is needed |
| Batch size | Up to 500 records per transaction, no linger time | Batches form under load. An idle system writes each record without added delay. |
| Telemetry sample backpressure | A frame is accepted only if the queue has room for every record in it. Otherwise the whole frame is rejected and not relayed. WebSocket clients receive an error frame with code `backpressure`. HTTP clients receive 503 with `Retry-After`. | Nothing is relayed that is not queued for persistence. The sender sees the rejection, so no loss is silent. The check runs before any filter state changes. |
| Lifecycle record backpressure | `await queue.put()`, which suspends only the one session coroutine | A session open or finalize record must not be dropped |
| Writer lifecycle | Task named `relay-writer`, started in the lifespan. Shutdown closes intake, waits up to 10 s for the queue to drain, then cancels. | Records queued before shutdown are written when the database is reachable |
| Sink execution | Async `write_batch` in the writer task. Synchronous SQLAlchemy work runs in `asyncio.to_thread`. | Database I/O never runs on the loop thread |
| Retry policy | 3 attempts with 0.5 s exponential backoff. After the last attempt, the batch is counted in `failed_batches` and logged at ERROR. | Bounded retry. Durable spooling is outside this task (see findings). |
| EMA state | One `MultiChannelEMAFilter` per application instance | Test isolation. Filter state is shared across sessions, as in the Gateway. |
| Frame limits | Maximum 1000 observations per frame. Each observation needs a finite numeric `valueQuantity.value` and a non-empty unit. | Bounds memory per frame. Invalid frames are rejected before any state changes. |
| Run key | Frame `run_key` when present, else `relay:<session_uid>` (WebSocket) or `relay:<request uuid>` (HTTP) | `surgical_telemetry.run_key` is NOT NULL and the frame format does not define one |

### Audit and tier separation (FR-DAT-001, FR-DAT-004, FR-DAT-005)

The relay module (`routes/telemetry.py`) imports neither `database` nor `models`, and a test checks this. Only `relay_sink.py` writes to the database. Each `telemetry_sessions` record is written with an `audit_log` row through `insert_audit_log()`, so the compute_hash_chain trigger in `003-triggers.sql` assigns the chain digest. Per-sample audit rows are not written, because that would add one advisory-locked insert per sample at the NFR-PERF-001 rate.

### telemetry_sessions (append-only with finalization rows)

Each session writes two rows that share `session_uid`. The `open` row is written at connect with `points_relayed = 0` and `disconnected_at` NULL. The `finalized` row is written at disconnect with the final count and `disconnected_at`. The table is WORM: prevent_update, prevent_delete, and prevent_truncate triggers from `003-triggers.sql` are attached, so no row changes after insert. A BEFORE INSERT guard rejects a `finalized` row when no `open` row exists for the session. A unique constraint on `(session_uid, record_status)` allows one row of each kind. The current state of a session is the newest row for its `session_uid`. Finalized records are immutable (FR-DAT-003).

### Gateway items not migrated

* `GET /api/telemetry/history` reads the Gateway `observations` table with synchronous queries on the event loop. It is outside the relay and belongs to the visualization read path, so it is not migrated here.
* Gateway `PerformanceMiddleware` (a `BaseHTTPMiddleware` that adds `X-Response-Time-ms`) is replaced by `ResponseTimeMiddleware`, which is pure ASGI and does not wrap WebSocket connections.

## Verification

Environment: Windows, Python 3.14.3, FastAPI 0.139.0, Starlette 1.3.1, SQLAlchemy 2.0.51, numpy 2.4.4, pytest 9.0.3. uvloop and pandas are not installed on this host. No package was installed, and the `middleware/requirements.txt` pins were not applied to this interpreter.

Full output: `SNDEV/logs/relay-2026-10-13-pytest-middleware.txt` (gitignored).

| Check | Command | Result |
|:------|:--------|:-------|
| Full middleware suite | `python -m pytest middleware/tests -q -rs` | 97 passed, 45 skipped, 3 xfailed. The skips are database-gated tests (`BIOSYNC_TEST_DATABASE_URL` unset), relay PostgreSQL tests (`BIOSYNC_RELAY_ADMIN_URL` unset), and Pulse binding tests. The 3 xfailed tests are the existing R2 strict checks in `test_db_ssl_config.py`. |
| G1.5 uvloop | `python -m pytest middleware/tests/test_uvloop_enabled.py -v` | PASS, 5 of 5. The applied path is checked with a stand-in `uvloop` module. The degradation path is checked with `uvloop` made unimportable. The real-uvloop branch declines on this host. |
| Relay, off-loop | `test_relay_offloop_persistence.py` | PASS, 15 of 15. Writes run on the task named `relay-writer`. A 300 ms database write leaves the loop ticking with no gap of 150 ms or more. Database work runs on a worker thread. A full queue rejects the whole frame, and rejected records are never written. Retry and drain paths are covered. |
| Relay, session records | `test_relay_session_records.py` | PASS, 12 of 12. Open and finalized rows, scope and identity checks, close codes, refusal when the writer is not running, and one audit call per session record. |
| Response-time middleware | `test_relay_response_time.py` | PASS, 6 of 6. HTTP and WebSocket samples, bounded windows, endpoint key cap, and WebSocket scope pass-through. |
| Timing stability | The four non-database relay modules, run four times in a row | 38 of 38 PASS on each run. |
| Static check | `python -m pyflakes` on the owned files | Clean for the new files. Unused imports in `middleware/api/routes/auth.py` predate this task and were not changed. The `import uvloop` availability probe is flagged on purpose and carries a `noqa` marker. |
| PostgreSQL integration | `test_relay_postgres_integration.py` | NOT RUN. `localhost:5432` accepts TCP connections, but `BIOSYNC_RELAY_ADMIN_URL` is unset and no credentials were supplied, so the module skips (4 tests). The `006-telemetry-sessions.sql` DDL and the WORM and finalization triggers have not been executed on PostgreSQL. |

Gate status:

* G1.5 (relay routes perform no synchronous database writes; `test_uvloop_enabled.py` PASSES): PASS on Windows for the uvloop test and the off-loop tests. The guard tests check that the route module has no database import and no session call.
* G1.8 (500-session run with audit rows equal to completed requests and p95 relay latency reported): not run. Load measurement is in tasks 1.6 and 1.11.
* NFR-PERF-001 and NFR-PERF-002 are not measured by this change. The writer records a batch throughput sample at each commit, but no load run has been made.

## Findings

These items are outside the ownership of this task, or need a decision from the parent session.

1. `docs/migration-map.md` is not updated. The relay, `telemetry_sessions`, and response-time rows still sit in the deferred table. They belong in Table 1, and the Gateway R3 row in Table 3 stays OPEN until the PostgreSQL integration test has run. The `docs\*` path was outside this task's ownership.
2. The compose init mounts and `middleware/alembic/versions/0001_initial_schema.py` run only 001 to 003. A deployment built from those paths has no `telemetry_sessions` table. Every batch that contains session records then fails three attempts, is logged, and is counted in `failed_records`.
3. `middleware/tests/dbsupport.py` `MIGRATION_FILES` lists 001 to 003. Fixtures built on it do not create `telemetry_sessions`. The relay integration test applies 006 itself.
4. The writer keeps no durable spool. After three failed attempts, a batch is dropped after logging. Samples that were already relayed to clients are then missing from the compliance tier. A decision is needed: spool to disk, or refuse frames while the writer has failed batches.
5. Session finalize records queued after `writer.stop()` are logged as errors and not written. A client still connected at shutdown then has an `open` row and no `finalized` row. The effect on shutdown ordering is not measured.
6. The EMA filter is shared by every session of one application instance, as in the Gateway. Concurrent publishers interleave their filter state.
7. The Gateway `GET /api/telemetry/history` route is not migrated. It runs synchronous reads on the event loop, so it needs its own read-path task.
8. Per-sample audit rows are not written. FR-DAT-004 per-row audit capture (task 1.8) is the place for that.
9. Broadcast sends to each subscriber in turn, so a slow subscriber delays the others. This is the Gateway behavior and has not been measured.
10. The environment has FastAPI 0.139.0 and the pins require 0.115.5. The relay tests ran on 0.139.0. The pins are not verified (task 1.3).
11. The real uvloop policy path has not run on this host, because uvloop is not installed.
12. `DEVELOPMENT_PLAN.md` task 5.2 names `database/migrations/006-signatures.sql`. That number is taken by this migration. The plan owner must renumber one of them.
13. `middleware/api/auth.py` calls `datetime.utcnow()`, which emits deprecation warnings in the token tests. It was not changed here.
14. The header uses "Claude Haiku 5.5" as the model name. The parent instruction gave "MiMo-V2.6-Pro", which is the name in the earlier log. The AGENTS.md template calls for the model name, so the parent should confirm which one applies.

## Provenance Correction

The Author line in the metadata header should read `Author: Seth Nenninger (MiMo-V2.6-Pro Agent)`. The header was written in error by the producing agent, which named its model "Claude Haiku 5.5". The header is not rewritten here, per the log overwrite policy. The header timestamp (`2026-10-14T00:34:40Z`) is the real UTC time of the work and needs no correction.

## Provenance Confirmation

The Author line in the metadata header records the producing agent model, Claude Haiku 5.5, and is kept as written. Two later agents self-reported the same model, so the line is accurate. The header timestamp `2026-10-14T00:34:40Z` is the real UTC time of authorship. This section confirms the header only. The "Provenance Correction" section above is kept as written.
