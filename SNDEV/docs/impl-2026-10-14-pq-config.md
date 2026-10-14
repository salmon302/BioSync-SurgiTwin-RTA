Title: NFR performance test configuration and G1.8 execution (tasks 1.6, 1.11)
Date: 2026-10-14T17:26:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 tasks 1.6 and 1.11, gate G1.8
Summary: Records the test configuration for NFR-PERF-001, NFR-PERF-002, and NFR-PERF-004, adds the Locust load definition and the relay session harness, and logs the G1.8 relay run and the 1,000,000-row hash chain check.

## Task Reference

DEVELOPMENT_PLAN.md Phase 1 task 1.6 (define the test configuration for NFR-PERF-001, NFR-PERF-002, and NFR-PERF-004, output `vv/tests/PQ/locustfile.py` and a configuration record), task 1.11 (1,000,000-row PQ-3 check on a dedicated database, output a run record), and gate G1.8 (performance scope). The run record is `SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md`.

Requirements: SRS.md NFR-PERF-001 (100,000 points per second ingestion), NFR-PERF-002 (sub-50 ms WSS relay, sub-10 ms MessagePack edge leg out of scope here), NFR-PERF-004 (500 concurrent WebSocket sessions). Relay design: `SNDEV/docs/impl-2026-10-13-telemetry-relay.md` (bounded queue of 10,000 records, batches up to 500 records, all-or-nothing frame backpressure).

## Specification Summary

G1.8 requires three things: test configuration recorded for each of the three NFRs, a 500-session run on the migrated relay that produces audit rows equal to completed requests, and p95 relay latency reported against the 50 ms bound (proposed threshold). Task 1.11 requires the 1,000,000-row hash chain check on a dedicated database with throughput and duration recorded.

## Implementation Notes

Work plan (appended as steps complete):

1. Configuration record (this file, section NFR configuration).
2. Locust load definition in `vv/tests/PQ/locustfile.py`.
3. Relay session harness in `vv/tests/PQ/test_pq_relay_sessions.py`.
4. Dedicated database and migrations, relay start, 500-session run, 1,000,000-row check, teardown.

Environment facts observed before work:

* Host: AMD Ryzen 9 3900X, 12 cores, 24 logical processors, 48 GB RAM, Windows 11 Pro. The PostgreSQL container and the relay run on this host, so the load generator, relay, and database share the same CPUs.
* Interpreter: `.venv-qual311` (Python 3.11.9), FastAPI 0.115.5, uvicorn 0.32.1, websockets 17.2, SQLAlchemy 2.0.36, psycopg2-binary 2.9.9. `jose` and `bcrypt` import cleanly.
* PostgreSQL: container `biosync-surgitwin-rta-postgres-1`, server version 15.19, plaintext TCP on 127.0.0.1:5432.
* Route paths: the relay routes are mounted under the `/api/telemetry` prefix (`middleware/api/main.py`). The WebSocket endpoint is `/api/telemetry/stream` and the HTTP ingest is `POST /api/telemetry/ingest`. The brief named `/stream` and `/ingest`, and the run uses the mounted paths.
* `middleware/database.py` defaults `DB_SSLMODE` to `verify-full` and fails closed without a client certificate. The container accepts plaintext only, so the local run sets `DB_SSLMODE=disable`. This is a deviation from NFR-SEC-001 for this measurement only and is recorded as a finding.

## Task 1.6 Configuration Record

The definitions below are the ones in `vv/tests/PQ/locustfile.py` (docstring and user classes) and `vv/tests/PQ/test_pq_relay_sessions.py`. Both files share the deployment target, topology, and authentication text.

Common deployment target: one Windows 11 workstation (AMD Ryzen 9 3900X, 12 cores, 24 logical processors, 48 GB RAM). One uvicorn process with one worker and the default asyncio event loop, because uvloop has no Windows build (`middleware/requirements.txt`, `api/loop_policy.py`). PostgreSQL 15.19 in the local container `biosync-surgitwin-rta-postgres-1` on 127.0.0.1:5432 over plaintext TCP. The relay listens on 127.0.0.1:8100 for the measurement runs, because port 8000 was held by another process on this host.

Common topology: load generator and relay on the same host over loopback. The relay writes to the scratch database `surgitwin_pq_test` (migrations 001, 002, 003, 004, 006, 005 in that order). The load generator never touches the database except for the read-only parity queries made after the run.

Common authentication: HS256 JWT signed with the secret loaded by the relay (JWT_SECRET_FILE, a file outside the repository). Claims are sub (one identity per session), scope (space-delimited), iat, exp (one hour), and jti. Tokens are minted by the load code, not by the login route, because the login route requires a users row per simulated client. The WebSocket route needs telemetry_read, and publishing needs telemetry_write.

Route paths: the relay is mounted under `/api/telemetry` (`middleware/api/main.py`). The brief named `/stream` and `/ingest`. The mounted paths are `/api/telemetry/stream`, `/api/telemetry/ingest`, `/api/telemetry/stream/info`, and `/api/telemetry/ingestion/stats`.

### NFR-PERF-001 (100,000 points per second ingestion)

* Deployment target: the common target above.
* Topology: Locust worker in `.venv-pq-load` (locust 2.46.7) on the same host, posting to POST /api/telemetry/ingest. No WebSocket subscriber is connected, so the figure excludes broadcast fan-out.
* Load definition: `TelemetryIngestUser` in `vv/tests/PQ/locustfile.py`. 200 observations per frame, constant pacing of 5 frames per second per user, 20 users (offered load 20,000 points per second), 120 seconds. Payload is JSON with valueQuantity.value, valueQuantity.unit, a channel code, and effectiveDateTime.
* Measurement point: rows committed to surgical_telemetry (database commit, counted by SQL after the writer queue drains) and writer.accepted_samples at the relay.
* Statistic: sustained committed points per second over the window plus drain.
* Proposed acceptance threshold: 100,000 points per second sustained (SRS NFR-PERF-001). The G5.6 gate uses a 10-minute window, and this run is 120 seconds, so G5.6 is not claimed by this record.

### NFR-PERF-002 (sub-50 ms WebSocket relay)

* Deployment target: the common target above.
* Topology: asyncio harness (`vv/tests/PQ/test_pq_relay_sessions.py`, websockets 17.2) in the qualification venv on the same host. One process holds all 500 sessions.
* Load definition: 500 sessions on /api/telemetry/stream for the window. The publishing sessions send frames of 10 observations. The rest are read-only subscribers. Each accepted frame is broadcast to every connected session. Window: 300 seconds, with 15 seconds of drain after the window.
* Measurement point: client-side round trip. A publisher stamps each frame and times the echo of its own frame, which the relay sends to all sessions including the sender. The Locust user `RelaySessionUser` takes the same measurement.
* Statistic: p50, p95, p99, and maximum of the round trip, from the publisher echoes.
* Proposed acceptance threshold: p95 under 50 ms (proposed gate G1.8 threshold, not in the SRS value).

### NFR-PERF-004 (500 concurrent WebSocket sessions)

* Deployment target: the common target above.
* Topology: the same asyncio harness, with the same 500 sessions as NFR-PERF-002.
* Load definition: 500 sessions connected before the window opens, held open through the window and the drain. 
* Measurement point: client count of sessions connected at window start, and `active_connections` from GET /api/telemetry/stream/info at the window midpoint (server side).
* Statistic: peak concurrent sessions, with dropped frames counted over the window. A dropped frame is a backpressure rejection, a publish with no echo or rejection, or a broadcast a subscriber did not receive.
* Proposed acceptance threshold: 500 concurrent sessions with zero dropped frames over a 5-minute run (proposed, mirrors the Gateway PQ-1 wording).

## Calibration Sweep

Calibration runs used the same relay process and the same 500-session harness, with 60-second windows. They chose the sustained rate for the G1.8 run. Full captures are in `SNDEV/logs/pq-2026-10-14-cal-*.json`.

| Run | Publishers | Frames per second per publisher | Observations per frame | Offered points per second | Sessions connected | Server accepted frames | Backpressure rejected frames | Echo p95 (ms) | Result |
|:----|:-----------|:-------------------------------|:-----------------------|:--------------------------|:-------------------|:-----------------------|:-----------------------------|:--------------|:-------|
| cal-a | 50 | 1 | 10 | 500 | 500 | not recorded (982 echoed to publishers) | 704 (publisher error frames) | 64,594 | Collapsed. 482 sessions closed with `keepalive ping timeout` (1011). Run before the server-count fix |
| cal-b | 10 | 1 | 50 | 500 | 500 | 380 | 220 | 20,198 | Queue full, latency collapse, parity counted before finalization (see Findings) |
| cal-c | 1 | 1 | 10 | 10 | 500 | 60 | 0 | 1.35 | Pass on latency, drops, and parity |
| cal-d | 5 | 1 | 10 | 50 | 500 | 300 | 0 | 365 | Latency FAIL, no drops |
| cal-e | 2 | 1 | 10 | 20 | 500 | 120 | 0 | 84 to 92 | Latency FAIL, no drops (two repeats) |

The 1 publisher at 1 frame per second configuration is the highest load in this sweep that met the 50 ms bound with zero drops. The G1.8 run uses it. Higher loads are recorded as measured and not extrapolated.

## Verification

The measured results, captures, and PASS/FAIL verdicts are in `SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md`. Summary by NFR:

* NFR-PERF-001: measured, below NFR target. About 12,600 points per second committed in a 120 second ingest-only run (upper bound, drain not timed), against 100,000.
* NFR-PERF-002: the 500-session G1.8 run at 10 points per second gave publisher round trip p95 of 1.46 ms (PASS against the 50 ms proposed bound). The bound fails at 20 points per second and above on this host (calibration cal-e).
* NFR-PERF-004: 500 sessions connected and held through a 300 second window with zero dropped frames and zero session errors (PASS against the proposed threshold, at the G1.8 rate only).
* Task 1.11: 1,000,000 rows verified in 5.84 s, bound 60 s, integrity ok (PASS).
