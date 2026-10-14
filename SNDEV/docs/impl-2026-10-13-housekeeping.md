Title: Post-migration housekeeping: map closure, plan status, provenance correction
Date: 2026-10-14T00:55:21Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc (Phase 1 hygiene after relay, VTM, and qualification streams)
Summary: Moves the landed relay rows out of the migration map deferred table, records the known-debt items from the relay and qualification logs, updates the Phase 1 plan status, renumbers the task 5.2 migration to 007, and appends a provenance correction to the relay log.

## Task Reference

Ad-hoc request from the parent session after commits `d0ef2c5` (telemetry relay, response-time middleware, `telemetry_sessions`), `12147f6` (interim VTM), and `ffcf167` (PostgreSQL 15 qualification and IQ-5 pins). Source logs: `SNDEV/docs/impl-2026-10-13-telemetry-relay.md`, `SNDEV/docs/impl-2026-10-13-interim-vtm.md`, and `SNDEV/docs/impl-2026-10-13-pg15-qualification.md`. Plan reference: `DEVELOPMENT_PLAN.md` Phase 1, tasks 1.2, 1.3, 1.5, and 1.7.

## Specification Summary

* `docs/migration-map.md`: move the WebSocket telemetry relay, `telemetry_sessions`, and the response-time middleware from the deferred table to the migrated table, with commit hashes and the current target paths. Keep the Gateway load and soak tests deferred, pointing at Phase 1 task 1.6. Add a known-debt table with four entries.
* `DEVELOPMENT_PLAN.md`, Phase 1 only: update the status paragraph and the estimate line for the completed tasks. Rename the task 5.2 migration reference from `006-signatures.sql` to `007-signatures.sql` and note the renumbering.
* `SNDEV/docs/impl-2026-10-13-telemetry-relay.md`: append a provenance correction for the Author line. The existing content is not rewritten.

## Implementation Notes

### Files changed

`docs/migration-map.md`

* Table 1 gains six rows for the relay work: `middleware/api/routes/telemetry.py`, `telemetry_generator.py`, `middleware/api/relay_writer.py`, `middleware/api/relay_sink.py`, `middleware/api/middleware/response_time.py`, and `database/migrations/006-telemetry-sessions.sql`. Each row names the landing commit `d0ef2c5`.
* The Table 1 row for `middleware/api/main.py` is updated. The routers now include telemetry, and the lifespan starts and stops the relay writer.
* The deferred table loses three rows (relay and session tracking, response-time middleware, and the frontend-independent relay entries). The Gateway load and soak test row stays deferred and now points at task 1.6 and task 1.11.
* Table 4 is added with four known-debt entries:
  * Durable spool for relay batches that exhaust 3 retries: DEFERRED (decision). Recorded as a decision, not a defect. Owner is the Phase 1 task 1.6 area.
  * Compose init and Alembic baseline coverage of migration 006: IN PROGRESS, with the unblock-integration stream in this commit series.
  * Requirement pin provenance for the relay suite: IN PROGRESS. The relay tests ran on FastAPI 0.139.0, and `.venv-qual` is the authoritative environment.
  * Hash-chain tail deletion: OPEN, referenced to finding F3 in the qualification log.

`DEVELOPMENT_PLAN.md`, Phase 1 only

* Status paragraph: tasks 1.2 and 1.3 are complete at `ffcf167`. Task 1.5 is complete at `d0ef2c5`. Task 1.7 is complete at `12147f6`. Gate G1.3 was reopened by the auth import defect F1 and is being closed in the same commit series. The relay PostgreSQL integration test has not run.
* Estimate line: 25.5 d total, 12.5 d complete (tasks 1.1, 1.2, 1.3, 1.5, and 1.7), 13.0 d remaining. The arithmetic uses only the existing task estimates.
* Task rows 1.2, 1.3, 1.5, and 1.7 are marked "(done)" in the estimate column, following the convention of task 1.1.
* No rows were added. The durable spool and the hash-chain anchor are carried by the known-debt table in `docs/migration-map.md`.

`DEVELOPMENT_PLAN.md`, Phase 5 (task 5.2 only)

* The output reference `database/migrations/006-signatures.sql` is now `database/migrations/007-signatures.sql`. Migration 006 is taken by `006-telemetry-sessions.sql` from commit `d0ef2c5`. The row notes the renumbering once.

`SNDEV/docs/impl-2026-10-13-telemetry-relay.md`

* A `## Provenance Correction` section is appended after the last line. The header and body are unchanged. The section states that the Author line should read `Seth Nenninger (MiMo-V2.6-Pro Agent)`, that the header was written in error by the producing agent, and that the header timestamp `2026-10-14T00:34:40Z` is the real UTC time and needs no correction.

### Renumbering decision

Migration 006 is taken by the relay's `telemetry_sessions` DDL, so the signatures migration moves to 007. The number 007 is unused in `database/migrations/`. The Alembic baseline covers 001 to 003 only, so no Alembic revision is affected by the renumbering.

## Verification

Commit hash resolution, method: `git log --oneline -1 <hash>` for each hash cited in the four files.

| Hash | Cited in | Result |
|:-----|:---------|:-------|
| `d0ef2c5` | migration map, plan, this log | PASS. Resolves to `feat(relay): migrate telemetry relay with off-loop persistence (R3)` |
| `12147f6` | plan, this log | PASS. Resolves to `docs(vtm): publish interim complete verification traceability matrix` |
| `ffcf167` | plan, this log | PASS. Resolves to `test(compliance): qualify baseline on PostgreSQL 15 and fix IQ-5 pins` |
| `0b5b8d2` | plan (Phase 1 status, unchanged text) | PASS. Resolves to `feat(informatics): migrate BioSync-Gateway compliance and telemetry baseline` |
| `2026-10-14T00:34:40Z` | telemetry log header (timestamp, not a hash) | Not a hash. Recorded as the real UTC time per the correction. |

Path check, method: `Test-Path` for each path cited in the migration map rows added or changed.

| Path | Result |
|:-----|:-------|
| `middleware/api/routes/telemetry.py` | PASS, exists |
| `middleware/api/routes/telemetry_generator.py` | PASS, exists |
| `middleware/api/relay_writer.py` | PASS, exists |
| `middleware/api/relay_sink.py` | PASS, exists |
| `middleware/api/middleware/response_time.py` | PASS, exists |
| `database/migrations/006-telemetry-sessions.sql` | PASS, exists |
| `database/migrations/002-schema.sql`, `003-triggers.sql` | PASS, exist |
| `middleware/alembic/versions/0001_initial_schema.py` | PASS, exists (in-progress item, Table 4) |
| `.venv-qual` | PASS, exists (in-progress item, Table 4) |
| `vv/traceability/vtm.md` | PASS, exists |
| `database/migrations/007-signatures.sql` | PLANNED, does not exist. The plan marks it "(created)" for task 5.2. |

Writing-constraint check, method: a case-insensitive word search over the four files for the banned vocabulary, plus a search for em and en dashes and curly quotes. Result is recorded in the commit step.

Gate status: no build or test gate applies to this documentation-only change. The relay and qualification gates are unchanged by this log. G1.3 remains OPEN until the unblock-integration commit lands.

## Status: Superseded

This draft is superseded by `SNDEV/docs/impl-2026-10-14-housekeeping.md`. The draft was produced by a dispatch that failed mid-run, so its content is not the final record of the housekeeping work. The later log is the operative record. The draft is retained unchanged above this section because log content is append-only.
