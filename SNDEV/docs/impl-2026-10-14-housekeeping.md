Title: Post-migration housekeeping: map closure, plan status, provenance confirmation
Date: 2026-10-14T16:45:32Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc (Phase 1 hygiene after relay, VTM, qualification, and unblock streams)
Summary: Closes the relay deferral rows in docs/migration-map.md, records Phase 1 status and gate G1.3 in DEVELOPMENT_PLAN.md, and confirms the Author line of the telemetry relay log.

## Task Reference

Coordinator request for Phase 1 housekeeping. Documents: `docs/migration-map.md`, `DEVELOPMENT_PLAN.md` (Phase 1 section only), and `SNDEV/docs/impl-2026-10-13-telemetry-relay.md`. Source logs: `SNDEV/docs/impl-2026-10-13-telemetry-relay.md` (commit `d0ef2c5`), `SNDEV/docs/impl-2026-10-13-interim-vtm.md` (commit `12147f6`), `SNDEV/docs/impl-2026-10-13-pg15-qualification.md` (commit `ffcf167`), and `SNDEV/docs/impl-2026-10-14-unblock-integration.md` (commit `654510b`).

## Specification Summary

* Move the telemetry relay, `telemetry_sessions`, and response-time middleware rows into the migrated table, with the commit hash and the target paths.
* Keep the Gateway load and soak tests deferred, pointing at Phase 1 task 1.6.
* Add the known-debt entries from the relay and unblock logs, and mark the pin provenance and migration 006 coverage items CLOSED.
* Record Phase 1 status: tasks 1.2, 1.3, and 1.5 CLOSED, task 1.7 complete, and gate G1.3 status after commit `654510b`.
* Renumber the future signature migration in task 5.2 from 006 to 007.
* Append a provenance confirmation to the telemetry relay log without changing its existing content.

## Implementation Notes

### docs/migration-map.md

The working tree already held the relay rows moved from the deferred table into Table 1, and the deferred table kept only the frontend row and the load and soak row. This task reviewed those edits, kept them, and made these changes:

* Table 1, `database/migrations/006-telemetry-sessions.sql` row: the coverage sentence now lists the compose init, the Alembic baseline, the `dbsupport.py` fixture list, and the relay integration test, as of commit `654510b`.
* Table 1, `docker-compose.yml` row: init mounts cover 001 to 003 and 006.
* Table 1, Alembic `0001_initial_schema.py` row: the baseline executes 001, 002, 003, and 006.
* Table 2, load and soak row: stays deferred, now stated to point at Phase 1 task 1.6.
* Table 3, Gateway R3 row: the relay is migrated at `d0ef2c5`, and its PostgreSQL integration tests passed at `654510b`. The status stays OPEN until gate G1.8 is recorded.
* Table 3, surgical telemetry ingestion row: the relay writes to the table through the writer task. The throughput target is still not measured.
* Table 4, compose and Alembic coverage of migration 006: CLOSED at `654510b`.
* Table 4, pin provenance for the relay suite: CLOSED at `654510b`.
* Table 4, retained rows: the durable spool (DEFERRED, decision) and hash-chain tail deletion (OPEN, finding F3).
* Table 4, new rows: shutdown queue-full race (OPEN), `test_db_ssl_config.py` module reload (OPEN), OQ-9 `DATABASE_URL` requirement (OPEN), and Alembic upgrade from a database stamped 0001 (OPEN, noted).

### DEVELOPMENT_PLAN.md

The Phase 1 Status paragraph names tasks 1.2, 1.3, and 1.5 as CLOSED, with the evidence commits. It records gate G1.3 as OPEN after `654510b`. The OQ-9 tamper tests collect and pass, and the injection suite detects 54 of 54 cases. The digest cross-check covers 19 vectors with two known-limit strict xfails, and tail deletion needs an external anchor.

The Estimate line is unchanged in total. The arithmetic on the task table:

* Complete: 1.1 (4.0 d), 1.2 (1.5 d), 1.3 (1.0 d), 1.5 (4.0 d), and 1.7 (2.0 d), for a total of 12.5 d.
* Remaining: 1.4 (3.0 d), 1.6 (2.0 d), 1.8 (3.0 d), 1.9 (2.0 d), 1.10 (1.5 d), 1.11 (1.0 d), and 1.12 (0.5 d), for a total of 13.0 d.
* Sum: 25.5 d, which matches the phase total in the table.

Tasks 1.2, 1.3, and 1.5 were already in the 12.5 d complete figure, so the total does not change.

### 006 and 007 renumbering

Task 5.2 names `database/migrations/007-signatures.sql`. Migration 006 is taken by `006-telemetry-sessions.sql` (commit `d0ef2c5`). Migrations 004 and 005 are reserved for planned tasks 1.8 and 1.9, so 007 is the next number not in use. The task 5.2 row carries one note about the renumbering. The file does not exist yet, and it is a planned output of task 5.2.

### Telemetry relay log

`SNDEV/docs/impl-2026-10-13-telemetry-relay.md` received an appended section, "Provenance Confirmation". Its text confirms that the Author line records the producing agent model and is kept as written, and that the header timestamp is the real UTC time of authorship. The existing content is unchanged. The earlier "Provenance Correction" section asks for a different Author line. Both sections now coexist in the file, and this log does not resolve that difference.

### Author convention

SNDEV log headers name the producing model. Where a header names MiMo-V2.6-Pro, that line records coordinator attribution of the work. This log was written by a Claude Haiku 5.5 subagent under that coordinator, and its Author line follows the coordinator instruction.

## Verification

Commit hashes cited in this log, checked with `git log --oneline --no-walk`:

```
654510b fix(auth,relay): unblock suite imports and qualify 006 migration on PostgreSQL
ffcf167 test(compliance): qualify baseline on PostgreSQL 15 and fix IQ-5 pins
12147f6 docs(vtm): publish interim complete verification traceability matrix
d0ef2c5 feat(relay): migrate telemetry relay with off-loop persistence (R3)
0b5b8d2 feat(informatics): migrate BioSync-Gateway compliance and telemetry baseline
```

Result: PASS. All five hashes resolve.

Paths cited in this log:

* Exist: `docs/migration-map.md`, `DEVELOPMENT_PLAN.md`, `SNDEV/docs/impl-2026-10-13-telemetry-relay.md`, `SNDEV/docs/impl-2026-10-13-interim-vtm.md`, `SNDEV/docs/impl-2026-10-13-pg15-qualification.md`, `SNDEV/docs/impl-2026-10-14-unblock-integration.md`, `SNDEV/docs/impl-2026-10-13-gateway-migration.md`, `middleware/api/routes/telemetry.py`, `middleware/api/routes/telemetry_generator.py`, `middleware/api/relay_writer.py`, `middleware/api/relay_sink.py`, `middleware/api/middleware/response_time.py`, `database/migrations/006-telemetry-sessions.sql`, `middleware/alembic/versions/0001_initial_schema.py`, `middleware/tests/test_oq9_tamper_detection.py`, `middleware/tests/test_db_ssl_config.py`, `middleware/tests/conftest.py`, and `middleware/tests/dbsupport.py`.
* Planned, not yet created: `database/migrations/007-signatures.sql` and `middleware/api/routes/signatures.py` (task 5.2), and `vv/tests/PQ/locustfile.py` (task 1.6).

Result: PASS. Each cited path exists or carries a planned marker.

Writing checks on the new and edited text: banned vocabulary, em and en dashes, curly quotes, and emojis were searched in the added lines. Result recorded at commit time in the final report.

Gate results: this change is documentation only. No build, test, or static analysis gate applies.
