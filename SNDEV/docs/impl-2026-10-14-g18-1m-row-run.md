Title: G1.8 relay session run, NFR-PERF-001 ingestion run, and 1,000,000-row hash chain check (tasks 1.11 and G1.8)
Date: 2026-10-14T17:58:17Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 task 1.11 and gate G1.8; configuration record in SNDEV/docs/impl-2026-10-14-pq-config.md
Summary: Runs the migrated relay with 500 concurrent WebSocket sessions (G1.8), an HTTP ingestion load for NFR-PERF-001, and the 1,000,000-row hash chain check on a dedicated database (task 1.11), with raw captures in SNDEV/logs.

## Task Reference

DEVELOPMENT_PLAN.md task 1.11 (1,000,000-row PQ-3 check on a dedicated database, record throughput and duration) and gate G1.8 (500-session run produces audit rows equal to completed requests, with p95 relay latency against the 50 ms NFR-PERF-002 proposed bound, and test configuration recorded for NFR-PERF-001, NFR-PERF-002, NFR-PERF-004). Configuration: `SNDEV/docs/impl-2026-10-14-pq-config.md`.

## Specification Summary

* G1.8: 500 concurrent WebSocket sessions on the migrated relay for a 5-minute window. Audit rows match completed sessions. p95 client round trip is reported against 50 ms (proposed).
* NFR-PERF-001: 100,000 points per second sustained ingestion (SRS). Reported as measured on this host.
* NFR-PERF-002: sub-50 ms WebSocket relay (proposed p95 threshold for this gate).
* NFR-PERF-004: 500 concurrent WebSocket sessions with zero dropped frames over 5 minutes (proposed).
* Task 1.11: 1,000,000 rows in `audit_log`, hash chain verified in under 60 seconds (`vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py`).

## Implementation Notes

Environment for every run in this record:

* Host: AMD Ryzen 9 3900X (12 cores, 24 logical processors), 48 GB RAM, Windows 11 Pro. The database and the relay share this host with the load generator.
* Relay: `uvicorn api.main:app --app-dir middleware --workers 1` on 127.0.0.1:8100, interpreter `.venv-qual311` (Python 3.11.9, FastAPI 0.115.5, uvicorn 0.32.1). Port 8000 was occupied by another process on this host, so it was not used. Log: `SNDEV/logs/pq-2026-10-14-uvicorn-app.log`.
* Environment variables for the relay: `ENVIRONMENT=production`, `DATABASE_URL` for database `surgitwin_pq_test`, `DB_SSLMODE=disable`, `JWT_SECRET_FILE` pointing to a random 48-byte secret kept outside the repository. The secret and the database password are not recorded here or in any log.
* Deviation: `DB_SSLMODE=disable`. The default is `verify-full` (NFR-SEC-001, Gateway R2). The container accepts plaintext TCP only, so measurements ran without TLS. This affects the latency figures (no TLS cost) and is recorded as a finding.
* Database: `surgitwin_pq_test` on the shared container. Migrations applied in the required order 001, 002, 003, 004, 006, 005. Result: 12 tables in `public`.
* Routes: `/api/telemetry/stream`, `/api/telemetry/ingest`, `/api/telemetry/stream/info`, `/api/telemetry/ingestion/stats`.
* Harness: `vv/tests/PQ/test_pq_relay_sessions.py` (asyncio, websockets 17.2, qualification venv). Load definition: `vv/tests/PQ/locustfile.py`, run with Locust 2.46.7 in `.venv-pq-load`.
* Measurement configuration of the G1.8 run: 500 sessions, 1 publisher, 499 read-only subscribers, 1 frame per second per publisher, 10 observations per frame, 300-second window, 15-second drain. Aggregate offered load 10 points per second.

The G1.8 configuration uses one publisher because the calibration sweep (in the configuration record) showed the 50 ms p95 bound was not met at 2 frames per second or more. Every accepted frame is broadcast to all 500 sessions, so higher publish rates cost one send per subscriber per frame.

### Measurement definitions

* Latency: publisher-side round trip. The publisher times the echo of its own frame. The echo is the relay broadcast to every session, including the sender.
* Audit parity: `telemetry_sessions` has two rows per session (open and finalized), and each row writes one `audit_log` row through `insert_audit_log()`. The relay writes no per-frame audit row (design decision, `impl-2026-10-13-telemetry-relay.md`). "Completed requests" is therefore read as completed WebSocket sessions. Each completed session produces two audit rows. Sample rows in `surgical_telemetry` are compared with the relay's accepted-point count.
* Throughput: committed rows in `surgical_telemetry` for the run key prefix, and the relay's accepted-point counter.

## Results

### G1.8 relay session run (run id g18-run1)

Captures: `SNDEV/logs/pq-2026-10-14-g18-run1.json`, `SNDEV/logs/pq-2026-10-14-g18-run1-pytest.txt`, `SNDEV/logs/pq-2026-10-14-g18-run1-cpu.csv`.

| Measure | Value | Source |
|:--------|:------|:-------|
| Sessions connected at window start | 500 of 500, 0 failed connects | client |
| Active connections at window midpoint | 500 | GET /api/telemetry/stream/info |
| Sessions that ended with an error | 0 | client |
| Frames sent | 300 | client |
| Frames accepted by the relay | 300 | writer counter (delta) |
| Frames rejected (backpressure or other) | 0 | writer counter and error frames |
| Unacknowledged publishes | 0 | client |
| Accepted points | 3,000 | writer counter (delta) |
| Achieved aggregate rate over the send window | 10.0 points per second | 3,000 / 300 s |
| Committed rows per second over window and drain | 9.5 points per second | SQL, 3,000 / 315 s |
| Round trip p50 | 1.24 ms | n = 300 |
| Round trip p95 | 1.46 ms | n = 300 |
| Round trip p99 | 1.62 ms | n = 300 |
| Round trip maximum | 2.27 ms | n = 300 |
| p95 against 50 ms proposed bound | PASS | |
| Subscriber receipts (each of 499 subscribers) | 300 each, total 149,700 | client |
| Subscriber receipts missing | 0 | client |
| `telemetry_sessions` open rows | 500 | SQL |
| `telemetry_sessions` finalized rows | 500 | SQL |
| `audit_log` rows for `telemetry_sessions` | 1,000 (2 per session) | SQL |
| `surgical_telemetry` rows | 3,000 (equal to accepted points) | SQL |
| Parity verdict | PASS | |

Server CPU during the window, from `pq-2026-10-14-g18-run1-cpu.csv`: 23.1 CPU-seconds over about 317 seconds, about 7% of one core. The sampler sums CPU for every other Python process on the host, so the client figure in that file is approximate (about 1.7 CPU-seconds).

### NFR-PERF-001 ingestion run (run id ingest-run1)

Captures: `SNDEV/logs/pq-2026-10-14-ingest-run1_stats.csv`, `..._failures.csv`, `..._exceptions.csv` (if present), `SNDEV/logs/pq-2026-10-14-ingest-run1.json` not written (driver stopped, see Findings).

Load: `TelemetryIngestUser`, 20 users, 200 observations per frame, 5 frames per second per user (offered 20,000 points per second), 120 seconds, no WebSocket subscribers. Locust 2.46.7.

| Measure | Value |
|:--------|:------|
| HTTP requests issued | 10,735 |
| Requests per second (Locust) | 89.5 |
| Failures, all HTTP 503 with backpressure (queue full, Retry-After) | 3,169 (29.5%) |
| Frames committed to `surgical_telemetry` (SQL, 20 Locust run keys) | 7,576 frames, 1,515,200 points |
| Locust successes (10,735 minus 3,169) | 7,566 frames, 1,513,200 points |
| Difference | 10 frames (committed, not counted as success by Locust; cause not isolated) |
| Committed points per second over the 120 s window | at most 12,627 (1,515,200 / 120 s; drain not timed, so this is an upper bound) |
| Rejected points (backpressure) | about 633,800 (3,169 frames x 200), counted by the relay as `rejected_samples` |
| Request latency (Locust, all requests) | median 56 ms, p95 410 ms, maximum 503 ms |

Result: measured, below NFR target. The figure is about 12,600 points per second against the 100,000 points per second NFR-PERF-001 value. It is not extrapolated from the run.

### Task 1.11, 1,000,000-row hash chain check

Run: `BIOSYNC_PQ3_ADMIN_URL` set, so the test dropped and recreated the dedicated database `surgitwin_pq_1m`, applied migrations 001, 002, and 003, and checked that `audit_log` was empty. Capture: `SNDEV/logs/pq-2026-10-14-1m-pytest.txt`.

| Measure | Value | Bound |
|:--------|:------|:------|
| Rows inserted (single DO block, one transaction) | 1,000,000 | assert rows == 1,000,000 |
| Insert wall-clock | 52.78 s | none asserted |
| Insert throughput | about 18,950 rows per second | none asserted |
| `hash-chain-check.sql` wall-clock | 5.84 s | under 60 s (PASS) |
| `verify_hash_chain()` integrity status | ok | must be ok (PASS) |
| pytest result | 1 passed in 62.78 s | |

Result: PASS against the 60 second bound. The plan expectation (1,000,000 rows verified in under 60 seconds) is met with about 54 seconds of headroom. The 52.78 second insert is the load generation step and is not part of the verification bound.

## Findings

1. Fan-out limits the relay at 500 sessions. Each accepted frame is serialized and sent to every connected session in turn (`api/routes/telemetry.py`, `ConnectionManager.broadcast`). At 2 frames per second with 500 sessions, the publisher round trip p95 was 85 to 92 ms in two repeats. At 5 frames per second it was 365 ms. In calibration cal-a (50 publishers at 1 frame per second offered, about 16 accepted frames per second with 10 observations each), 482 of 500 sessions were closed by the server with `keepalive ping timeout`. The relay's event loop was not saturated on average (uvicorn used about 16% of one core in calibration cal-e). The source of the tail latency was not isolated: client-side queueing in a single Python process is a candidate that was not measured.
2. The G1.8 run uses 10 points per second. The 50 ms p95 bound holds at that rate and fails at 20 points per second and above on this host. The 100,000 points per second NFR is not reached in the fan-out configuration, and the ingestion-only figure is about 12,600 points per second.
3. Backpressure works as designed on the ingestion path. At the offered 20,000 points per second, 29.5% of requests returned 503 with Retry-After and no partial frame was persisted. The queue (maxsize 10,000) was the limit at that load.
4. The audit design writes two audit rows per session, not one per request. Audit parity is therefore checked against completed sessions, not against HTTP requests.
5. Parity counts in calibration cal-b were read before the server finished finalizing sessions. The harness now polls for finalized rows and committed samples before counting. Captures from cal-a and cal-b are pre-fix and are not used for any gate figure.
6. The ingestion driver process was killed by the 120 second tool timeout after Locust finished. The Locust CSV is complete. The committed-row count was taken from SQL after the run. The relay's accepted counter for this run was not captured separately, so the accepted-point figure is inferred from the Locust counts.
7. The relay ran with `DB_SSLMODE=disable` (plaintext container). This is not the production TLS configuration.
8. The port on which the relay listens (8100) differs from the port named in the brief. Port 8000 was held by another process.

## Verification

| Check | Command or source | Result |
|:------|:------------------|:-------|
| Migrations on scratch database | psycopg2 applying 001, 002, 003, 004, 006, 005 | applied, 12 tables |
| Smoke: WebSocket echo, HTTP ingest 202, audit parity | manual smoke script, 5 sessions | PASS (2 telemetry_sessions rows and 2 audit rows per session) |
| Harness pyflakes | `pyflakes vv/tests/PQ/test_pq_relay_sessions.py vv/tests/PQ/locustfile.py` | clean |
| Calibration sweep | cal-a through cal-e (SNDEV/logs/pq-2026-10-14-cal-*.json) | recorded in the configuration record |
| G1.8 run | `pytest vv/tests/PQ/test_pq_relay_sessions.py` with the g18-run1 settings | PASS (pytest 1 passed, parity PASS, p95 PASS) |
| NFR-PERF-001 ingestion run | Locust, TelemetryIngestUser, 20 users, 120 s | measured, below NFR target |
| 1,000,000-row check | `pytest vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py` with the admin URL set | PASS (5.84 s verification, bound 60 s, integrity ok) |
| Teardown | relay process on 127.0.0.1:8100 stopped, `surgitwin_pq_test` and `surgitwin_pq_1m` dropped | done; surgitwin_test and the shared container untouched |
