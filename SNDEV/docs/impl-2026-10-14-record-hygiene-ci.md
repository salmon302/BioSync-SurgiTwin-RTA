Title: Record hygiene updates and CI qualification job (task 1.12)
Date: 2026-10-14T16:57:21Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 task 1.12 plus record hygiene after streams F1/F6/1.10
Summary: Pins ruff and mypy, confirms the PostgreSQL 15 qualification job in CI with the relay admin URL, and appends status to the Phase 1 logs and the migration map.

## Task Reference

DEVELOPMENT_PLAN.md Phase 1, task 1.12 (run the qualification job on PostgreSQL 15 in CI, choose and pin the Python lint and type-check tools, and record the first CI run). Record hygiene covers the status of findings F1, F2, F3, F4, F5, and F6 in `SNDEV/docs/impl-2026-10-13-pg15-qualification.md`, the provenance disposition in `SNDEV/docs/impl-2026-10-13-telemetry-relay.md`, and the stale status text in `docs/migration-map.md` and `DEVELOPMENT_PLAN.md`.

## Specification Summary

* Choose and pin an exact version of a Python linter and of a Python type checker in `middleware/requirements-test.txt`. Ruff and mypy are the selected tools.
* Add a qualification job to `.github/workflows/ci.yml` that runs against a PostgreSQL 15 service container with pgcrypto available, and runs `python -m pytest middleware/tests vv/tests -q`. The `python-tests` and `cpp-build` jobs keep working.
* Use only `actions/checkout` and `actions/setup-python` plus the service container.
* Record that the first CI run is PENDING PUSH.
* Close the stale requirement-pin row in `docs/migration-map.md` and the stale relay deferral phrase in `DEVELOPMENT_PLAN.md`.
* Append status sections to the qualification and relay logs, and a superseded marker to the untracked housekeeping draft.

## Implementation Notes

### Files touched

* `middleware/requirements-test.txt`: added `ruff==0.8.4` and `mypy==1.13.0` under a comment that marks them as pinned only. Reason: task 1.12 requires a pinned lint and type-check tool pair. These versions were not installed or executed in this environment, and their presence on PyPI was not re-checked in this session.
* `.github/workflows/ci.yml`: the `qualification` job already existed from commit `0b5b8d2`. This change sets the job to the specified command (`python -m pytest middleware/tests vv/tests -q`, the `-rs` flag removed), adds `BIOSYNC_RELAY_ADMIN_URL` with the same ephemeral CI URL so the five relay PostgreSQL integration tests run instead of skipping, and adds a comment that pgcrypto comes from `database/migrations/001-extensions.sql`. The `python-tests` and `cpp-build` jobs are unchanged. Reason: task 1.12.
* `SNDEV/docs/impl-2026-10-13-pg15-qualification.md`: appended `## Status Update 2026-10-14`. F1, F2, and F6 are CLOSED at `654510b`. F4 and F5 are CLOSED at `4d2a372`. F3 is OPEN. Reason: record the closure of findings in the owning log.
* `SNDEV/docs/impl-2026-10-13-telemetry-relay.md`: appended `## Provenance Resolution`. The Provenance Confirmation section is the operative disposition, and the Provenance Correction section is superseded but retained. No other content changed.
* `SNDEV/docs/impl-2026-10-13-housekeeping.md`: appended `## Status: Superseded`, pointing at `SNDEV/docs/impl-2026-10-14-housekeeping.md`. The file was untracked. It is committed here so the record is retained. It was not deleted.
* `docs/migration-map.md`: the known-debt row "Pins not resolved against PyPI" is marked CLOSED at `ffcf167`, with the suite verified green at `654510b`. Reason: the qualification log records all 15 pins resolved at `ffcf167`.
* `DEVELOPMENT_PLAN.md`: the tier table row for Compliance and Interoperability said the telemetry relay "is deferred into Phase 1 task 1.5". It now reads that the relay landed at `d0ef2c5` and closed at `654510b`. Reason: the relay landed at `d0ef2c5`.
* `SNDEV/docs/impl-2026-10-14-record-hygiene-ci.md`: this log.

### Stale-text review

Checked against `git log` and the cited logs:

* Requirement pins row in `docs/migration-map.md`: stale. Edited.
* Telemetry relay deferral phrase in `DEVELOPMENT_PLAN.md`: stale. Edited.
* Phase 1 status paragraph and the tasks 1.2, 1.3, 1.5, and 1.7 rows in `DEVELOPMENT_PLAN.md`: current. Each says done or closed at the correct commit. No edit.
* Phase 1 estimate line: states 12.5 d complete and 13.0 d remaining. Task 1.10 is complete at `4d2a372` but its row carries no done mark and the estimate does not count it. Not edited, because task 1.10 is outside this task's list. Owner decision.
* `docs/migration-map.md` row "Python and SQL digest equivalence for all JSON values" (FR-DAT-005) reads OPEN. Task 1.10 closed the equivalence at `4d2a372`. Not edited, because task 1.10 is outside this task's list. Owner decision.
* `docs/migration-map.md` Table 4 rows for 006 coverage, the requirement pin provenance, and the relay: current.

### CI job shape

Job `qualification`, `runs-on: ubuntu-latest`.

* Service `postgres:15` with `POSTGRES_DB` and `POSTGRES_USER` set to `surgitwin_test`, an ephemeral password, port `5432:5432`, and a `pg_isready` health check with 10 retries.
* Environment `BIOSYNC_TEST_DATABASE_URL` and `BIOSYNC_RELAY_ADMIN_URL`, both pointing at the service container through `localhost:5432`.
* Steps: `actions/checkout@v4`, `actions/setup-python@v5` with Python 3.11, `pip install -r middleware/requirements-test.txt`, and `python -m pytest middleware/tests vv/tests -q`.
* The PQ-3 suite is not run. It needs `BIOSYNC_PQ3_DATABASE_URL` on a dedicated database.

The `python-tests` job runs the same pytest command without database URLs, so DB-gated tests skip there. The `cpp-build` job is unchanged.

Lint and type-check steps are not in the workflow. The repository has no ruff or mypy configuration, and mypy has not been run against the code. Adding those steps is OPEN.

## Verification

### Commit hash resolution

Method: `git rev-parse --short <hash>` for each hash cited in this log and in the edited files.

| Hash | Cited in | Result |
|:-----|:---------|:-------|
| `654510b` | pg15 log, relay log, migration map, plan | PASS. Resolves to `fix(auth,relay): unblock suite imports and qualify 006 migration on PostgreSQL` |
| `4d2a372` | pg15 log, migration map, this log | PASS. Resolves to `fix(hash-chain): prove Python and SQL digest equivalence across JSON types (1.10)` |
| `ffcf167` | migration map, plan, this log | PASS. Resolves to `test(compliance): qualify baseline on PostgreSQL 15 and fix IQ-5 pins` |
| `d0ef2c5` | migration map, plan, this log | PASS. Resolves to `feat(relay): migrate telemetry relay with off-loop persistence (R3)` |
| `0b5b8d2` | this log (qualification job origin) | PASS. Resolves to `feat(informatics): migrate BioSync-Gateway compliance and telemetry baseline` |

### YAML validity

Command: `python -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml',encoding='utf-8')); print(sorted(d['jobs']))"`, run with PyYAML 6.0.3 on Python 3.14.3.

Result: PASS. The parsed job keys are `cpp-build`, `python-tests`, and `qualification`. The final step of `qualification` parses as `{'run': 'python -m pytest middleware/tests vv/tests -q'}`.

### Test gate

Result: PENDING PUSH. The workflow cannot run on GitHub from this environment. The first CI run is pending the push. The tests it runs are green locally: 492 passed, 8 skipped, 3 xfailed at commit `4d2a372` on `.venv-qual311` (Python 3.11.9), as recorded in `SNDEV/docs/impl-2026-10-14-hash-digest-equivalence.md`. That figure was not re-run in this session. The skip count in CI is expected to fall, because `BIOSYNC_RELAY_ADMIN_URL` is now set in the qualification job.

### Pinned tool check

Result: PENDING. `ruff==0.8.4` and `mypy==1.13.0` were not installed or executed in this environment.
