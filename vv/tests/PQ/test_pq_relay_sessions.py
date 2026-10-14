# SPDX-License-Identifier: MIT
"""
G1.8 relay session run (SRS NFR-PERF-001, NFR-PERF-002, NFR-PERF-004; DEVELOPMENT_PLAN.md gate G1.8).

Opens PQ_SESSIONS concurrent WebSocket sessions against the migrated relay at /api/telemetry/stream.
PQ_PUBLISHERS of them publish telemetry frames (telemetry_write scope). The others are read-only
subscribers (telemetry_read scope). Every session stays connected for PQ_DURATION_S seconds. After the
window the test waits for the relay writer queue to drain, then compares client-side counts with
PostgreSQL: telemetry_sessions rows, audit_log rows, and surgical_telemetry rows.

Load definition is the same one used by vv/tests/PQ/locustfile.py (RelaySessionUser and
TelemetryIngestUser). The 500-session run is executed here with asyncio because Locust fans out
broadcast frames to every session in one Python process, which is the cost this run measures.

Measurement points:
  * Latency (NFR-PERF-002): client round trip. A publisher sends a frame and times the echo of that
    frame. The relay broadcasts accepted frames to every connected session, including the sender.
  * Throughput (NFR-PERF-001): accepted points per second of the send window, and surgical_telemetry
    rows committed to PostgreSQL per second of the window plus drain.
  * Concurrency (NFR-PERF-004): sessions connected at window start, and /api/telemetry/stream/info
    active_connections sampled at the window midpoint.

Gated: runs only when BIOSYNC_PQ_RELAY_URL and BIOSYNC_PQ_RELAY_DSN are set. JWT_SECRET must equal the
secret the relay process loads (JWT_SECRET or JWT_SECRET_FILE). Environment variables:
    BIOSYNC_PQ_RELAY_URL          http base of the relay, e.g. http://127.0.0.1:8100
    BIOSYNC_PQ_RELAY_DSN          psycopg2 DSN of the migrated scratch database
    PQ_SESSIONS                   concurrent sessions (default 500)
    PQ_PUBLISHERS                 publishing sessions (default 50)
    PQ_FRAMES_PER_SECOND          frames per second per publisher (default 1.0)
    PQ_OBSERVATIONS_PER_FRAME     observations per frame (default 10, maximum 1000)
    PQ_DURATION_S                 sustained window in seconds (default 300)
    PQ_DRAIN_S                    seconds sessions stay open after the window (default 15)
    PQ_RUN_ID                     letters, digits, and hyphens only (default g18-<UTC time>)
Capture: SNDEV/logs/pq-2026-10-14-<run_id>.json

Example:
    BIOSYNC_PQ_RELAY_URL=http://127.0.0.1:8100 BIOSYNC_PQ_RELAY_DSN="host=127.0.0.1 port=5432 dbname=surgitwin_pq_test user=surgitwin password=... sslmode=disable" \
        JWT_SECRET_FILE=... python -m pytest vv/tests/PQ/test_pq_relay_sessions.py -v -s
"""

import asyncio
import json
import math
import os
import pathlib
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
LOG_DIR = REPO_ROOT / "SNDEV" / "logs"

NFR_PERF_002_P95_MS = 50.0
NFR_PERF_004_SESSIONS = 500
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,40}$")

RELAY_URL = os.environ.get("BIOSYNC_PQ_RELAY_URL", "")
RELAY_DSN = os.environ.get("BIOSYNC_PQ_RELAY_DSN", "")

pytestmark = [pytest.mark.pq, pytest.mark.db]

CHANNELS = [
    ("pressure", "mmHg", 80.0, 140.0),
    ("flow", "L/min", -10.0, 10.0),
    ("hr", "beats/min", 60.0, 110.0),
    ("spo2", "%", 92.0, 100.0),
]


@dataclass
class RunConfig:
    relay_url: str
    dsn: str
    secret: str
    sessions: int
    publishers: int
    frames_per_second: float
    observations: int
    duration_s: float
    drain_s: float
    run_id: str

    @property
    def marker(self) -> str:
        return f"pq-{self.run_id}"

    @property
    def identity_prefix(self) -> str:
        return f"pq-{self.run_id}-"


@dataclass
class SessionResult:
    index: int
    publisher: bool
    identity: str
    connected: bool = False
    completed: bool = False
    error: str = ""
    sent: int = 0
    echoed: int = 0
    rejected_backpressure: int = 0
    rejected_other: int = 0
    received: int = 0
    rtt_ms: List[float] = field(default_factory=list)
    open_at: float = 0.0
    close_at: float = 0.0
    sent_at: Dict[int, float] = field(default_factory=dict)


def _percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[rank - 1]


def _mint_token(secret: str, subject: str, scopes: str) -> str:
    from jose import jwt

    now = int(time.time())
    claims = {"sub": subject, "scope": scopes, "iat": now, "exp": now + 3600, "jti": str(uuid.uuid4())}
    return jwt.encode(claims, secret, algorithm="HS256")


def _frame(cfg: RunConfig, index: int, seq: int, rng: random.Random) -> str:
    observations = []
    for k in range(cfg.observations):
        channel, unit, low, high = CHANNELS[k % len(CHANNELS)]
        observations.append({
            "code": {"coding": [{"code": channel}]},
            "valueQuantity": {"value": round(rng.uniform(low, high), 2), "unit": unit},
            "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
        })
    payload = {
        "patientId": cfg.marker,
        "timestamp": f"{index}:{seq}",
        "run_key": f"{cfg.marker}-{index}",
        "observations": observations,
    }
    return json.dumps({"type": "telemetry", "payload": payload})


async def _read_loop(ws, cfg: RunConfig, res: SessionResult) -> None:
    async for raw in ws:
        if cfg.marker in raw:
            res.received += 1
        if not res.publisher:
            continue
        message = json.loads(raw)
        if message.get("type") == "error":
            code = message.get("payload", {}).get("code")
            if code == "backpressure":
                res.rejected_backpressure += 1
            else:
                res.rejected_other += 1
            continue
        payload = message.get("payload") or {}
        if message.get("type") != "telemetry" or payload.get("patientId") != cfg.marker:
            continue
        stamp = str(payload.get("timestamp", ""))
        if not stamp.startswith(f"{res.index}:"):
            continue
        seq = int(stamp.split(":", 1)[1])
        sent = res.sent_at.pop(seq, None)
        if sent is not None:
            res.echoed += 1
            res.rtt_ms.append((time.perf_counter() - sent) * 1000.0)


async def _publish_loop(ws, cfg: RunConfig, res: SessionResult, ctx: "RunContext") -> None:
    rng = random.Random(res.index)
    period = 1.0 / cfg.frames_per_second
    next_at = ctx.start_at
    seq = 0
    while True:
        now = time.perf_counter()
        if now >= ctx.stop_at:
            return
        if now < next_at:
            await asyncio.sleep(next_at - now)
            continue
        if now - next_at > period:
            next_at = now
        res.sent_at[seq] = time.perf_counter()
        await ws.send(_frame(cfg, res.index, seq, rng))
        res.sent += 1
        seq += 1
        next_at += period


@dataclass
class RunContext:
    start_at: float = 0.0
    stop_at: float = 0.0
    end_at: float = 0.0
    connected: int = 0
    failed: int = 0
    start_event: asyncio.Event = field(default_factory=asyncio.Event)


async def _session(index: int, cfg: RunConfig, ctx: RunContext, res: SessionResult) -> None:
    import websockets

    publisher = res.publisher
    scopes = "telemetry_read telemetry_write" if publisher else "telemetry_read"
    token = _mint_token(cfg.secret, res.identity, scopes)
    url = cfg.relay_url.replace("http", "ws", 1) + f"/api/telemetry/stream?token={token}"
    try:
        ws = await websockets.connect(url, open_timeout=60, ping_interval=None, max_size=2**20, max_queue=None)
    except Exception as exc:
        res.error = f"connect: {exc!r}"
        ctx.failed += 1
        return
    res.connected = True
    res.open_at = time.perf_counter()
    ctx.connected += 1
    try:
        await ctx.start_event.wait()
        reader = asyncio.create_task(_read_loop(ws, cfg, res))
        if publisher:
            await _publish_loop(ws, cfg, res, ctx)
        await asyncio.sleep(max(0.0, ctx.end_at - time.perf_counter()))
        await ws.close()
        await reader
        res.completed = True
    except Exception as exc:
        res.error = f"session: {exc!r}"
    finally:
        res.close_at = time.perf_counter()


async def _monitor(cfg: RunConfig, path: str) -> dict:
    import httpx

    token = _mint_token(cfg.secret, f"{cfg.identity_prefix}monitor", "telemetry_read")
    async with httpx.AsyncClient(base_url=cfg.relay_url, timeout=10.0) as client:
        resp = await client.get(path, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp.json()


async def _midpoint_sample(cfg: RunConfig, ctx: RunContext, out: dict) -> None:
    await asyncio.sleep(max(0.0, ctx.start_at + (cfg.duration_s / 2.0) - time.perf_counter()))
    try:
        out["stream_info_midpoint"] = await _monitor(cfg, "/api/telemetry/stream/info")
    except Exception as exc:
        out["stream_info_midpoint_error"] = repr(exc)


async def _wait_for_persistence(cfg: RunConfig, sessions: int, samples: int, timeout_s: float = 180.0) -> dict:
    deadline = time.perf_counter() + timeout_s
    counts = {}
    while time.perf_counter() < deadline:
        counts = await asyncio.to_thread(_database_counts, cfg)
        finalized = counts["telemetry_sessions"].get("finalized", 0)
        if finalized >= sessions and counts["surgical_telemetry_rows"] >= samples:
            break
        await asyncio.sleep(1.0)
    return counts


async def _wait_for_queue_drain(cfg: RunConfig, timeout_s: float = 120.0) -> dict:
    deadline = time.perf_counter() + timeout_s
    stats = {}
    while time.perf_counter() < deadline:
        stats = await _monitor(cfg, "/api/telemetry/ingestion/stats")
        if stats["writer"]["queue_depth"] == 0:
            return stats
        await asyncio.sleep(0.5)
    return stats


def _database_counts(cfg: RunConfig) -> dict:
    import psycopg2

    conn = psycopg2.connect(cfg.dsn, connect_timeout=30)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        like_identity = cfg.identity_prefix + "%"
        like_run_key = cfg.marker + "-%"
        counts = {}
        cur.execute(
            "SELECT record_status, count(*) FROM telemetry_sessions WHERE client_identity LIKE %s GROUP BY 1",
            (like_identity,),
        )
        counts["telemetry_sessions"] = {row[0]: row[1] for row in cur.fetchall()}
        cur.execute(
            "SELECT count(*) FROM audit_log WHERE table_name = 'telemetry_sessions' AND actor_id LIKE %s",
            (like_identity,),
        )
        counts["audit_log_telemetry_sessions"] = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM surgical_telemetry WHERE run_key LIKE %s", (like_run_key,))
        counts["surgical_telemetry_rows"] = cur.fetchone()[0]
        return counts
    finally:
        conn.close()


async def run_load(cfg: RunConfig) -> dict:
    results = [
        SessionResult(index=i, publisher=i < cfg.publishers, identity=f"{cfg.identity_prefix}{i:04d}")
        for i in range(cfg.sessions)
    ]
    ctx = RunContext()
    tasks = [asyncio.create_task(_session(i, cfg, ctx, results[i])) for i in range(cfg.sessions)]

    connect_deadline = time.perf_counter() + 120.0
    while ctx.connected + ctx.failed < cfg.sessions and time.perf_counter() < connect_deadline:
        await asyncio.sleep(0.1)
    connected_at_start = ctx.connected

    writer_before = (await _monitor(cfg, "/api/telemetry/ingestion/stats"))["writer"]
    ctx.start_at = time.perf_counter() + 1.0
    ctx.stop_at = ctx.start_at + cfg.duration_s
    ctx.end_at = ctx.stop_at + cfg.drain_s
    ctx.start_event.set()
    wall_start = datetime.now(timezone.utc).isoformat()

    midpoint: dict = {}
    midpoint_task = asyncio.create_task(_midpoint_sample(cfg, ctx, midpoint))
    await asyncio.gather(*tasks)
    midpoint_task.cancel()
    wall_end = datetime.now(timezone.utc).isoformat()

    ended_expected = sum(1 for r in results if r.connected and r.close_at > 0)
    stats = await _wait_for_queue_drain(cfg)
    accepted_delta = stats["writer"]["accepted_samples"] - writer_before["accepted_samples"]
    counts = await _wait_for_persistence(cfg, ended_expected, accepted_delta)

    publishers = [r for r in results if r.publisher]
    sent = sum(r.sent for r in publishers)
    echoed = sum(r.echoed for r in publishers)
    rejected = sum(r.rejected_backpressure for r in publishers)
    rejected_other = sum(r.rejected_other for r in publishers)
    unacknowledged = sum(len(r.sent_at) for r in publishers)
    server_accepted_samples = stats["writer"]["accepted_samples"] - writer_before["accepted_samples"]
    server_rejected_samples = stats["writer"]["rejected_samples"] - writer_before["rejected_samples"]
    server_accepted = server_accepted_samples // cfg.observations
    server_rejected = server_rejected_samples // cfg.observations
    window_s = cfg.duration_s
    rtts = [v for r in publishers for v in r.rtt_ms]
    subscriber_receipts = [r.received for r in results if not r.publisher]
    completed = sum(1 for r in results if r.completed)
    ended = sum(1 for r in results if r.connected and r.close_at > 0)
    errored = [r.error for r in results if r.error]
    rows = counts["surgical_telemetry_rows"]
    finalized = counts["telemetry_sessions"].get("finalized", 0)
    opened = counts["telemetry_sessions"].get("open", 0)
    audit_rows = counts["audit_log_telemetry_sessions"]

    p95 = _percentile(rtts, 95)
    return {
        "config": {
            "relay_url": cfg.relay_url,
            "sessions": cfg.sessions,
            "publishers": cfg.publishers,
            "subscribers": cfg.sessions - cfg.publishers,
            "frames_per_second_per_publisher": cfg.frames_per_second,
            "observations_per_frame": cfg.observations,
            "duration_s": cfg.duration_s,
            "drain_s": cfg.drain_s,
            "run_id": cfg.run_id,
            "wall_start_utc": wall_start,
            "wall_end_utc": wall_end,
        },
        "concurrency": {
            "connected_at_start": connected_at_start,
            "failed_connects": ctx.failed,
            "server_active_connections_midpoint": (midpoint.get("stream_info_midpoint") or {}).get("active_connections"),
            "completed_sessions": completed,
            "sessions_with_errors": len(errored),
            "first_errors": errored[:5],
        },
        "throughput": {
            "frames_sent": sent,
            "frames_accepted_server": server_accepted,
            "frames_accepted_echoed_to_publishers": echoed,
            "accepted_points_server": server_accepted_samples,
            "accepted_points_per_s_send_window": server_accepted_samples / window_s,
            "committed_rows": rows,
            "committed_rows_per_s_window_plus_drain": rows / (window_s + cfg.drain_s),
        },
        "latency_ms": {
            "samples": len(rtts),
            "p50": _percentile(rtts, 50),
            "p95": p95,
            "p99": _percentile(rtts, 99),
            "max": max(rtts) if rtts else None,
            "proposed_bound_p95_ms": NFR_PERF_002_P95_MS,
            "p95_verdict": None if p95 is None else ("PASS" if p95 < NFR_PERF_002_P95_MS else "FAIL"),
        },
        "drops": {
            "server_backpressure_rejections_frames": server_rejected,
            "publisher_error_frames_backpressure": rejected,
            "publisher_error_frames_other": rejected_other,
            "unacknowledged_publishes_at_publisher": unacknowledged,
            "subscriber_expected_per_session": server_accepted,
            "subscriber_min_received": min(subscriber_receipts) if subscriber_receipts else None,
            "subscriber_max_received": max(subscriber_receipts) if subscriber_receipts else None,
            "subscriber_total_received": sum(subscriber_receipts),
        },
        "audit_parity": {
            "completed_requests_sessions_ended": ended,
            "sessions_ended_cleanly_by_client": completed,
            "telemetry_sessions_open_rows": opened,
            "telemetry_sessions_finalized_rows": finalized,
            "audit_log_telemetry_sessions_rows": audit_rows,
            "expected_audit_rows_two_per_session": 2 * ended,
            "expected_sample_rows_server_accepted": server_accepted_samples,
            "surgical_telemetry_rows": rows,
            "verdict": "PASS" if (finalized == ended and opened == ended and audit_rows == 2 * ended
                                  and rows == server_accepted_samples) else "FAIL",
        },
        "writer_snapshot": stats.get("writer"),
        "stream_info_midpoint": midpoint.get("stream_info_midpoint"),
    }


def _config_from_env() -> RunConfig:
    run_id = os.environ.get("PQ_RUN_ID") or f"g18-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError("PQ_RUN_ID must be letters, digits, and hyphens, at most 40 characters")
    return RunConfig(
        relay_url=RELAY_URL,
        dsn=RELAY_DSN,
        secret=os.environ.get("JWT_SECRET", ""),
        sessions=int(os.environ.get("PQ_SESSIONS", NFR_PERF_004_SESSIONS)),
        publishers=int(os.environ.get("PQ_PUBLISHERS", 50)),
        frames_per_second=float(os.environ.get("PQ_FRAMES_PER_SECOND", 1.0)),
        observations=int(os.environ.get("PQ_OBSERVATIONS_PER_FRAME", 10)),
        duration_s=float(os.environ.get("PQ_DURATION_S", 300)),
        drain_s=float(os.environ.get("PQ_DRAIN_S", 15)),
        run_id=run_id,
    )


@pytest.mark.skipif(
    not (RELAY_URL and RELAY_DSN),
    reason="Set BIOSYNC_PQ_RELAY_URL and BIOSYNC_PQ_RELAY_DSN to run the G1.8 relay session run.",
)
def test_g18_relay_sessions():
    cfg = _config_from_env()
    assert cfg.secret, "JWT_SECRET must match the relay process"
    assert 1 <= cfg.publishers <= cfg.sessions
    report = asyncio.run(run_load(cfg))
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    capture = LOG_DIR / f"pq-2026-10-14-{cfg.run_id}.json"
    capture.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"capture: {capture}")
    print(json.dumps({k: report[k] for k in ("concurrency", "throughput", "latency_ms", "drops", "audit_parity")}, indent=2, default=str))
    assert report["concurrency"]["connected_at_start"] == cfg.sessions, "not all sessions connected"
    assert report["concurrency"]["sessions_with_errors"] == 0, "sessions ended with errors"
    assert report["audit_parity"]["verdict"] == "PASS", "audit parity failed"
