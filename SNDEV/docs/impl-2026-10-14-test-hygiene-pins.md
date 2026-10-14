Title: Test hygiene fixes and PQ tooling pins
Date: 2026-10-14T21:29:31Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: follow-ups from SNDEV/docs/impl-2026-10-14-phase2-kickoff.md
Summary: Moves the PQ-3 skipif marker onto the test function, corrects the stale Pulse docstring, and adds exact PQ tooling pins.

## Task Reference

Follow-ups from SNDEV/docs/impl-2026-10-14-phase2-kickoff.md: skipif placement defect, stale FR-MS-006 docstring, and exact pins for the PQ tooling.

## Specification Summary

1. The `skipif` marker for PQ-3 must decorate `test_1m_rows_hash_chain_under_60s`, not the helper `_recreate_database`. Without the marker on the test, the test runs without `BIOSYNC_PQ3_DATABASE_URL` and fails with `OperationalError`.
2. The OQ FR-MS-006 docstring must describe the current worker design from commit 5fb26a3 instead of the open debt.
3. `vv/tests/PQ/requirements.txt` must pin the PQ load and harness tooling with exact versions.

## Implementation Notes

Files changed:

* `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py` (edit). The `skipif` decorator (condition `not PQ3_DATABASE_URL`, same reason text) moved from `_recreate_database` to `test_1m_rows_hash_chain_under_60s`. The helper is unmarked. Verification logic, the 60 s bound, and database handling are unchanged.
* `vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py` (edit). The "Limitation" paragraph stating that ProcessPoolExecutor delegation is not active was replaced with a "Design" paragraph. Old: "Limitation: SimulationManager.step_simulation is synchronous. The ProcessPoolExecutor delegation of FR-MS-006 is not active (docs/migration-map.md, open item)." New: one long-lived spawned worker process per engine instance, native engine created inside the worker, steps awaited off the event loop with a bounded timeout, and fail-closed initialization on import failure or worker crash. No test code or assertions changed.
* `vv/tests/PQ/requirements.txt` (new). Header comment references DEVELOPMENT_PLAN.md Phase 1 task 1.6 and sim/SOUP.md. Contents:
  * `-r ../../../middleware/requirements-test.txt` (supplies psycopg2-binary, python-jose, httpx, pytest, and the runtime pins already exact in middleware)
  * `locust==2.46.7`
  * `websockets==17.2`

Import audit of `vv/tests/PQ/*.py`: third-party imports are locust, websockets, jose, psycopg2, httpx, pytest. Only locust and websockets were absent from the tracked requirements files, so only those two were added.

## Verification

| Check | Command | Result |
|---|---|---|
| PQ-3 without env vars | `python -m pytest vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py -rs -q` | PASS: `1 skipped` (reason: Set BIOSYNC_PQ3_DATABASE_URL ...). No database connection attempted. |
| PQ-3 with unreachable URLs set | `--collect-only -q` with `BIOSYNC_PQ3_DATABASE_URL` and `BIOSYNC_PQ3_ADMIN_URL` set to `postgresql://u:p@127.0.0.1:1/...` | PASS: `1 test collected`. The 1,000,000-row insert was not run. |
| OQ FR-MS-006 | `pytest vv/tests/OQ/test_oq_fr_ms_006_pulse_fail_closed.py -rs -q` | PASS: `3 passed`. Pulse bindings absent on this host; no change from baseline. |
| pyflakes | `pyflakes` on both changed test files | PASS: exit 0, no output. |
| Writing sweep | Banned-word list, em and en dashes, curly quotes, over the three inserted or edited files | PASS: zero matches. |

Tooling note: the verification interpreter was `.venv-qual311` (Python 3.11.9) for pytest and the global Python 3.14 for pyflakes.

## Pinned Versions

| Package | Version | Source |
|---|---|---|
| locust | 2.46.7 | Phase 1 measurement venv `.venv-pq-load` (impl-2026-10-14-pq-config.md) |
| websockets | 17.2 | Phase 1 qualification venv `.venv-qual311` (impl-2026-10-14-pq-config.md) |
