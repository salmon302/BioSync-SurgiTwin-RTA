Title: Phase 1 task completion marks and finding dispositions
Date: 2026-10-14T17:30:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 tracking (coordinator decision on 1.4, 1.8, 1.9, 1.12)
Summary: Marks Phase 1 tasks 1.4, 1.8, 1.9, 1.10, and 1.12 DONE in the plan, recomputes the Phase 1 estimate, and records the audit-capture findings F-1 to F-5 in the migration map.

## Task Reference

Coordinator decision recorded in the session that spawned this task. Plan: `DEVELOPMENT_PLAN.md`, Phase 1 task table and status paragraph. Migration map: `docs/migration-map.md`, Tables 1, 3, and 4.

## Specification Summary

Mark the landed Phase 1 rows as done with their commit hashes. Leave tasks 1.6 and 1.11 in progress. Recompute the Phase 1 estimate from the row estimates without changing any row estimate. Update the status paragraph. Record the dispositions of audit-capture findings F-1 to F-5 in the migration map, and update rows that are stale because of the landed commits. Close the Gateway R2 open item in the risk register and the plan text.

## Implementation Notes

Rows changed in `DEVELOPMENT_PLAN.md`:

* Task 1.4 (3.0d): DONE, commit `a44c163`, gate G1.7 PASS.
* Task 1.8 (3.0d): DONE, commit `f4b9d8f`, gate G1.2 PASS.
* Task 1.9 (2.0d): DONE, commit `f4b9d8f`, gate G1.4 PASS.
* Task 1.10 (1.5d): already DONE, commit `4d2a372`. No change.
* Task 1.12 (0.5d): DONE, commit `94fc8d1`. First CI run pending push.
* Tasks 1.6 (2.0d) and 1.11 (1.0d): remain open.
* Status paragraph: replaced the commit sentence with one sentence naming the done tasks and the remaining Phase 1 work.
* Phase 1 estimate line, recomputed from the row estimates:
  * Complete: 1.1 (4.0) + 1.2 (1.5) + 1.3 (1.0) + 1.4 (3.0) + 1.5 (4.0) + 1.7 (2.0) + 1.8 (3.0) + 1.9 (2.0) + 1.10 (1.5) + 1.12 (0.5) = 22.5 d.
  * Remaining: 1.6 (2.0) + 1.11 (1.0) = 3.0 d.
  * Total: 22.5 + 3.0 = 25.5 d, unchanged.
* The gate-status log (`SNDEV/docs/impl-2026-10-14-gate-status.md`) gave 22.0 d complete and 3.5 d remaining. That figure left out task 1.12 (0.5 d). Task 1.12 is DONE under this decision, so it is counted, and the figures are 22.5 d and 3.0 d.
* Risk register (Section 7): the Gateway R2 and R3 row now names R3 as the open item and records R2 as closed at `a44c163`. The Section 1 database row now states that verify-full TLS is configured at `a44c163`.

Rows changed in `docs/migration-map.md`:

* Table 1, docker-compose row: init mounts now list 001 to 006 in apply order, and `DB_SSLMODE` default is `verify-full` (R2 closed).
* Table 3, automatic per-row audit capture: OPEN changed to CLOSED (`f4b9d8f`).
* Table 3, role separation: OPEN changed to CLOSED (`f4b9d8f`).
* Table 3, finalization guard: stays OPEN. The freeze guard landed at `f4b9d8f`, and signature-gated finalization remains open.
* Table 3, inactivity lockout and unique credential: stays OPEN. The unique-credential constraint and shared-account rejection landed at `f4b9d8f`. Lockout and inactivity timer remain open.
* Table 4, new rows for findings F-1 to F-5 of `SNDEV/docs/impl-2026-10-14-audit-capture-roles.md`:
  * F-1 CLOSED (`45087af`).
  * F-2 CLOSED (`45087af`).
  * F-3 CLOSED (`ff0a221`).
  * F-4 IN PROGRESS. The request-scoped actor is closed at `ff0a221`, and the background-writer service identity belongs to a parallel closure stream.
  * F-5 OPEN as a test-discipline rule. Parallel streams isolate by database name, and full-suite runs are serialized.
* Table 4, shared 5432 container with ssl=off and the client-key wrapper row: kept OPEN as R2 residue (operator action and live-container checks).

## Verification

Commit hashes cited in the edited files, checked with `git log --oneline`: `a44c163`, `f4b9d8f`, `4d2a372`, `94fc8d1`, `45087af`, and `ff0a221` all resolve.

Evidence paths cited in the edited files, checked with `Test-Path`: `SNDEV/docs/impl-2026-10-14-r2-tls.md`, `SNDEV/docs/impl-2026-10-14-audit-capture-roles.md`, `SNDEV/docs/impl-2026-10-14-record-hygiene-ci.md`, and `SNDEV/docs/impl-2026-10-14-gate-status.md` exist.

Source checks: `middleware/api/routes/telemetry.py` line 333 uses `_scopes_from_claim()`, and `database/migrations/005-roles.sql` and `middleware/alembic/versions/0001_initial_schema.py` list 004 and 005 in the stated order. Gates G1.2, G1.4, and G1.7 are PASS per the coordinator decision and the gate-status log. No tests were run, because this change is documentation only.
