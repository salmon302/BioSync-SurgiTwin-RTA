# SPDX-License-Identifier: MIT
"""
NFR performance test configuration and Locust load definition (SRS NFR-PERF-001, NFR-PERF-002,
NFR-PERF-004; DEVELOPMENT_PLAN.md task 1.6). The configuration record is
SNDEV/docs/impl-2026-10-14-pq-config.md.

Deployment target
    One Windows 11 workstation (AMD Ryzen 9 3900X, 12 cores, 24 logical processors, 48 GB RAM).
    One uvicorn process with one worker, the default asyncio event loop (uvloop is not available on
    Windows, see api/loop_policy.py), and PostgreSQL 15.19 in the local container
    biosync-surgitwin-rta-postgres-1 on 127.0.0.1:5432 over plaintext TCP.
    The workstation is not the reference hardware. Results label as measured on this host only.

Topology
    Load generator (Locust workers in .venv-pq-load, or the asyncio harness in
    test_pq_relay_sessions.py) on the same host, connecting to the relay over loopback.
    Relay (uvicorn, 127.0.0.1:8100 in the runs, mounted at /api/telemetry).
    Database (scratch database surgitwin_pq_test for relay runs, surgitwin_pq_1m for the 1,000,000-row
    check). The relay writer task and sink write to the database; the load generator does not.

Authentication
    Every request carries a JWT (HS256) signed with the secret the relay loads (JWT_SECRET or
    JWT_SECRET_FILE). Claims: sub (client identity, one per session), scope (space-delimited, see
    below), iat, exp, jti. Tokens are minted by this file, not by the login route, because the
    login route needs a users row per simulated client.
    Scope telemetry_read is required for the WebSocket stream. Scope telemetry_write is required
    to publish frames over the WebSocket or on POST /api/telemetry/ingest.

Paths (mounted under the /api/telemetry prefix in middleware/api/main.py)
    WebSocket stream: /api/telemetry/stream?token=...
    HTTP ingest:      POST /api/telemetry/ingest
    Stream info:      GET /api/telemetry/stream/info
    Ingestion stats:  GET /api/telemetry/ingestion/stats

Load definition
    NFR-PERF-001 ingestion (TelemetryIngestUser): HTTP POST /api/telemetry/ingest, one frame per
    request with PQ_INGEST_OBSERVATIONS observations (default 200), constant pacing of
    PQ_INGEST_FRAMES_PER_SECOND per user (default 5), PQ_INGEST_USERS users (default 20), run for
    PQ_INGEST_DURATION_S seconds (default 300). No WebSocket subscribers are connected during this
    load, so the figure is the persistence path without broadcast fan-out.
    NFR-PERF-002 and NFR-PERF-004 sessions (RelaySessionUser): PQ_SESSIONS concurrent WebSocket
    sessions (default 500). PQ_PUBLISHERS of them publish frames of PQ_OBSERVATIONS_PER_FRAME
    observations at PQ_FRAMES_PER_SECOND each. The rest are read-only subscribers. All sessions stay
    connected for PQ_DURATION_S seconds (default 300). The asyncio harness connects every session
    first and starts the window one second after the last connect. In Locust, sessions are spawned at
    the -r rate and each user holds its connection until the run ends. Each accepted frame is
    broadcast to every connected session, so each subscriber receives every accepted frame.
    Payload shape: JSON observations with valueQuantity.value (finite number), valueQuantity.unit,
    a channel code (pressure, flow, hr, spo2), and effectiveDateTime. The frame carries a run_key
    so the rows can be counted per run in surgical_telemetry.

Measurement points
    NFR-PERF-002 latency: client round trip. A publisher times the echo of its own frame, which
    the relay sends to all sessions including the sender. The timer starts before the send and
    stops when the echo is parsed.
    NFR-PERF-001 throughput: rows committed to surgical_telemetry (database commit, read from SQL
    after the writer queue drains) and accepted points at the relay (writer.accepted_samples).
    NFR-PERF-004 concurrency: sessions connected at window start (client) and
    active_connections from GET /api/telemetry/stream/info at the window midpoint (server).

Statistics and proposed acceptance thresholds
    NFR-PERF-002: p95 client round trip under 50 ms (proposed, gate G1.8).
    NFR-PERF-001: sustained rate of committed points of 100,000 per second (SRS and gate G5.6
    value). Rate is the committed row count over the window and drain. Not met here is recorded
    as "measured, below NFR target", not as a pass.
    NFR-PERF-004: 500 concurrent WebSocket sessions with zero dropped frames over a 5-minute run
    (proposed, mirroring the Gateway PQ-1 wording). A dropped frame is a backpressure rejection, an
    unacknowledged publish, or a broadcast a subscriber did not receive.

Usage (headless, from the repository root)
    .venv-pq-load\Scripts\locust -f vv\tests\PQ\locustfile.py --headless -u 20 -r 5 -t 5m ^
        --host http://127.0.0.1:8100 --only-summary --csv SNDEV\logs\pq-2026-10-14-ingest
    The 500-session G1.8 run uses test_pq_relay_sessions.py because a single Locust process would
    have to receive 500 times the accepted frame rate, and that receive cost is what the run measures.
"""

import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

from locust import HttpUser, User, between, constant_pacing, events, task

NFR_PERF_002_P95_MS = 50.0
NFR_PERF_001_POINTS_PER_SECOND = 100_000
NFR_PERF_004_SESSIONS = 500

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_SECRET_FILE = os.environ.get("JWT_SECRET_FILE", "")
RELAY_WS_PREFIX = "/api/telemetry/stream"
INGEST_PATH = "/api/telemetry/ingest"

INGEST_OBSERVATIONS = int(os.environ.get("PQ_INGEST_OBSERVATIONS", 200))
INGEST_FRAMES_PER_SECOND = float(os.environ.get("PQ_INGEST_FRAMES_PER_SECOND", 5))
SESSION_OBSERVATIONS = int(os.environ.get("PQ_OBSERVATIONS_PER_FRAME", 10))
SESSION_FRAMES_PER_SECOND = float(os.environ.get("PQ_FRAMES_PER_SECOND", 1.0))
SESSION_PUBLISHERS = int(os.environ.get("PQ_PUBLISHERS", 50))
SESSION_COUNTER = {"next": 0}

CHANNELS = [
    ("pressure", "mmHg", 80.0, 140.0),
    ("flow", "L/min", -10.0, 10.0),
    ("hr", "beats/min", 60.0, 110.0),
    ("spo2", "%", 92.0, 100.0),
]


def _secret() -> str:
    if JWT_SECRET:
        return JWT_SECRET
    if JWT_SECRET_FILE:
        with open(JWT_SECRET_FILE, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    raise RuntimeError("Set JWT_SECRET or JWT_SECRET_FILE to the secret the relay process loads.")


def mint_token(subject: str, scopes: str) -> str:
    from jose import jwt

    now = int(time.time())
    claims = {"sub": subject, "scope": scopes, "iat": now, "exp": now + 3600, "jti": str(uuid.uuid4())}
    return jwt.encode(claims, _secret(), algorithm="HS256")


def build_frame(observations: int, run_key: str, patient_id: str, stamp: str, rng: random.Random) -> dict:
    items = []
    for k in range(observations):
        channel, unit, low, high = CHANNELS[k % len(CHANNELS)]
        items.append({
            "code": {"coding": [{"code": channel}]},
            "valueQuantity": {"value": round(rng.uniform(low, high), 2), "unit": unit},
            "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
        })
    return {"patientId": patient_id, "timestamp": stamp, "run_key": run_key, "observations": items}


class TelemetryIngestUser(HttpUser):
    """NFR-PERF-001: HTTP ingest, one frame per request, no WebSocket subscribers in the run."""

    wait_time = constant_pacing(1.0 / max(INGEST_FRAMES_PER_SECOND, 1e-6))

    def on_start(self):
        self.token = mint_token(f"pq-ingest-{uuid.uuid4().hex[:8]}", "telemetry_write")
        self.rng = random.Random()
        self.run_key = f"pq-ingest-{uuid.uuid4().hex[:8]}"
        self.seq = 0

    @task
    def ingest(self):
        frame = build_frame(INGEST_OBSERVATIONS, self.run_key, self.run_key, f"{self.seq}", self.rng)
        self.seq += 1
        with self.client.post(
            INGEST_PATH,
            json=frame,
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
            name=INGEST_PATH,
        ) as resp:
            if resp.status_code == 202:
                resp.success()
            elif resp.status_code == 503:
                resp.failure("backpressure: relay queue full (Retry-After)")
            else:
                resp.failure(f"unexpected status {resp.status_code}")


class RelaySessionUser(User):
    """NFR-PERF-002 and NFR-PERF-004: one WebSocket session per simulated user."""

    wait_time = between(0, 0)

    def on_start(self):
        from websockets.sync.client import connect

        SESSION_COUNTER["next"] += 1
        index = SESSION_COUNTER["next"]
        self.index = index
        self.publisher = index <= SESSION_PUBLISHERS
        scopes = "telemetry_read telemetry_write" if self.publisher else "telemetry_read"
        self.identity = f"pq-locust-{index:04d}"
        token = mint_token(self.identity, scopes)
        host = self.host.replace("http", "ws", 1)
        self.ws = connect(f"{host}{RELAY_WS_PREFIX}?token={token}", open_timeout=60, ping_interval=None, max_size=2**20)
        self.seq = 0
        self.sent_at = {}
        self.rng = random.Random(index)

    def on_stop(self):
        self.ws.close()

    @task
    def hold_session(self):
        if not self.publisher:
            self._pump(1.0)
            return
        self.seq += 1
        stamp = f"{self.index}:{self.seq}"
        frame = {"type": "telemetry", "payload": build_frame(
            SESSION_OBSERVATIONS, f"pq-locust-run-{self.index}", "pq-locust", stamp, self.rng)}
        self.sent_at[self.seq] = time.perf_counter()
        self.ws.send(json.dumps(frame))
        self._pump(max(0.0, 1.0 / SESSION_FRAMES_PER_SECOND))

    def _pump(self, seconds: float):
        deadline = time.perf_counter() + seconds
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return
            try:
                raw = self.ws.recv(timeout=remaining)
            except TimeoutError:
                return
            self._record_echo(raw)

    def _record_echo(self, raw: str):
        if not self.publisher:
            return
        message = json.loads(raw)
        payload = message.get("payload") or {}
        stamp = str(payload.get("timestamp", ""))
        if message.get("type") != "telemetry" or not stamp.startswith(f"{self.index}:"):
            return
        seq = int(stamp.split(":", 1)[1])
        start = self.sent_at.pop(seq, None)
        if start is not None:
            events.request.fire(
                request_type="WS",
                name=f"{RELAY_WS_PREFIX} echo round trip",
                response_time=(time.perf_counter() - start) * 1000.0,
                response_length=len(raw),
                exception=None,
                context={},
            )
