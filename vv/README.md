# Continuous Verification Tier (V&V)

Status: qualification harness migrated from BioSync-Gateway. ASAM XIL adapters and the
traceability engine are not implemented yet.

This tier holds the ASAM XIL test abstraction, the bidirectional traceability engine, and the IQ/OQ/PQ protocol tests.

* `xil/`: ASAM XIL v3.0.0 port adapters (SRS FR-VV-002, FR-VV-003). Not implemented.
* `traceability/`: requirements trace engine (SRS FR-VV-005). Not implemented.
* `tests/IQ/`: installation qualification (repo layout, Python version, pgcrypto, triggers, Alembic, pip check, Pulse import)
* `tests/OQ/`: operational qualification (FHIR over HTTP, JWT secret, One Euro and EMA filters, hash chain digest cross-check, Pulse fail-closed)
* `tests/PQ/`: performance qualification (hash chain verification in process, 1,000,000-row database check)

Run from the repository root:

* `python -m pytest middleware/tests vv/tests -q`: DB-dependent tests skip with a reason when no database is set.
* Set `BIOSYNC_TEST_DATABASE_URL` to a disposable PostgreSQL 15+ database to run the DB-dependent tests.
* Set `BIOSYNC_PQ3_DATABASE_URL` to a dedicated empty database to run the 1,000,000-row check.

A skipped test is not a pass. Record skip counts with each qualification run.
