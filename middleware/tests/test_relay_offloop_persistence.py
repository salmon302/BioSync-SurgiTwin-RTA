# SPDX-License-Identifier: MIT
"""
Off-loop persistence for the telemetry relay (SRS FR-DAT-001, NFR-PERF-001, NFR-PERF-002; gate G1.5).

Covers:
  * The relay handler never calls the sink. Every write runs on the writer task.
  * The synchronous database work runs in a worker thread, so a slow write does not stall
    the event loop.
  * Backpressure: a full queue rejects the whole frame, and rejected records are never written.
  * The HTTP route returns 503 when the queue is full, and the WebSocket returns a backpressure error.
  * Raw and EMA-filtered values are both persisted (FR-3.5.3 pattern).
  * The relay modules do not import the database layer.

No PostgreSQL is needed. The sinks here are in-process fakes.
"""

import ast
import asyncio
import pathlib
import threading
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.auth import create_access_token
from api.main import create_app
from api.relay_sink import SqlAlchemyRelaySink
from api.relay_writer import (
    OFFER_ACCEPTED,
    OFFER_REJECTED_FULL,
    WRITER_TASK_NAME,
    RelayWriter,
    SampleRecord,
    SessionRecord,
)
from engine.signal import MultiChannelEMAFilter

_MIDDLEWARE = pathlib.Path(__file__).resolve().parents[1]

LOINC = {
    "hr": ("8867-4", "beats/min"),
    "pressure": ("8310-5", "mmHg"),
    "spo2": ("59408-5", "%"),
    "flow": ("85354-9", "L/min"),
}


def _token(scopes, sub="relay-tester"):
    return create_access_token({"sub": sub, "role": "clinician", "scopes": scopes}, expires_delta=1)


def _frame(values, channel="hr", run_key=None):
    code, unit = LOINC[channel]
    payload = {
        "patientId": "SYN-RELAY-001",
        "observations": [
            {
                "resourceType": "Observation",
                "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
                "effectiveDateTime": "2026-10-13T12:00:00Z",
                "valueQuantity": {"value": value, "unit": unit},
            }
            for value in values
        ],
    }
    if run_key is not None:
        payload["run_key"] = run_key
    return {"type": "telemetry", "payload": payload}


def _sample(value, channel="hr"):
    return SampleRecord(
        run_key="unit", channel=channel, unit="beats/min", raw_value=float(value),
        filtered_value=None, filter_name=None, filter_alpha=None, source_timestamp=None,
    )


class RecordingSink:
    """Async fake sink. Records the task that executes each write and the records it received."""

    def __init__(self, gate: threading.Event | None = None) -> None:
        self.gate = gate
        self.calls = []
        self.records = []

    async def write_batch(self, batch):
        task = asyncio.current_task()
        self.calls.append(task.get_name() if task else None)
        if self.gate is not None:
            await asyncio.to_thread(self.gate.wait, 10)
        self.records.extend(batch)


class FakeSession:
    """Stand-in for a SQLAlchemy Session. Records the thread of each call. Performs no I/O."""

    def __init__(self, log, delay_s=0.0):
        self._log = log
        self._delay_s = delay_s
        self._pending = []
        self._next_id = 0

    def execute(self, statement, params=None):
        self._log.append(("execute", threading.get_ident(), type(statement).__name__))
        if self._delay_s:
            time.sleep(self._delay_s)

    def add(self, obj):
        self._pending.append(obj)

    def flush(self):
        for obj in self._pending:
            self._next_id += 1
            obj.id = self._next_id
        self._pending = []

    def commit(self):
        self._log.append(("commit", threading.get_ident(), None))

    def rollback(self):
        self._log.append(("rollback", threading.get_ident(), None))

    def close(self):
        self._log.append(("close", threading.get_ident(), None))


def test_relay_frames_are_written_only_by_the_writer_task():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)

    with TestClient(app) as client:
        token = _token(["telemetry_read", "telemetry_write"])
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            ws.send_json(_frame([70.0]))
            echoed = ws.receive_json()
            assert echoed["type"] == "telemetry"
            ws.send_json(_frame([71.0, 72.0]))
            assert ws.receive_json()["type"] == "telemetry"

    assert sink.calls, "writer never reached the sink"
    assert set(sink.calls) == {WRITER_TASK_NAME}, f"sink ran on tasks {set(sink.calls)}"
    sample_values = sorted(r.raw_value for r in sink.records if isinstance(r, SampleRecord))
    assert sample_values == [70.0, 71.0, 72.0]


def test_slow_database_write_does_not_stall_the_event_loop():
    log = []
    sink = SqlAlchemyRelaySink(session_factory=lambda: FakeSession(log, delay_s=0.3))
    writer = RelayWriter(sink)

    async def ticker(stop, gaps):
        last = time.perf_counter()
        while not stop.is_set():
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    async def scenario():
        writer.start()
        stop = asyncio.Event()
        gaps = []
        tick = asyncio.create_task(ticker(stop, gaps))
        await asyncio.sleep(0.02)
        assert writer.offer_samples([_sample(1.0), _sample(2.0)]) == OFFER_ACCEPTED
        await writer.stop()
        stop.set()
        await tick
        return gaps

    gaps = asyncio.run(scenario())
    assert log, "sink did not run"
    assert max(gaps) < 0.15, f"event loop stalled for {max(gaps) * 1000:.0f} ms during a 300 ms write"


def test_database_work_runs_in_a_worker_thread_not_the_loop_thread():
    log = []
    loop_threads = []

    async def scenario():
        loop_threads.append(threading.get_ident())
        writer = RelayWriter(SqlAlchemyRelaySink(session_factory=lambda: FakeSession(log)))
        writer.start()
        writer.offer_samples([_sample(3.0)])
        await writer.put_lifecycle(SessionRecord(
            session_uid="11111111-1111-1111-1111-111111111111", record_status="open",
            client_identity="unit", connected_at=datetime.now(timezone.utc),
            disconnected_at=None, points_relayed=0,
        ))
        await writer.stop()

    asyncio.run(scenario())
    assert log, "no database work was recorded"
    touched = {thread for _, thread, _ in log}
    assert loop_threads[0] not in touched
    assert any(kind == "commit" for kind, _, _ in log)


def test_full_queue_rejects_the_whole_frame_and_never_writes_rejected_records():
    async def scenario():
        gate = asyncio.Event()

        class BlockingSink:
            def __init__(self):
                self.written = []

            async def write_batch(self, batch):
                await gate.wait()
                self.written.extend(r.raw_value for r in batch)

        blocking = BlockingSink()
        writer = RelayWriter(blocking, maxsize=3, batch_size=1)
        writer.start()

        assert writer.offer_samples([_sample(1), _sample(2)]) == OFFER_ACCEPTED
        await asyncio.sleep(0)  # writer takes record 1 and blocks in the sink
        assert writer.queue_depth == 1

        assert writer.offer_samples([_sample(3), _sample(4), _sample(5)]) == OFFER_REJECTED_FULL
        assert writer.offer_samples([_sample(6)]) == OFFER_ACCEPTED
        assert writer.offer_samples([_sample(7), _sample(8)]) == OFFER_REJECTED_FULL
        assert writer.rejected_samples == 5
        assert writer.accepted_samples == 3

        gate.set()
        await writer.stop()
        return blocking.written, writer

    written, writer = asyncio.run(scenario())
    assert written == [1.0, 2.0, 6.0]
    assert writer.persisted_records == 3
    assert writer.failed_batches == 0


def test_failed_batch_is_retried_then_counted_and_the_writer_keeps_running():
    class FlakySink:
        def __init__(self):
            self.attempts = 0
            self.persisted = []

        async def write_batch(self, batch):
            self.attempts += 1
            if self.attempts <= 2:
                raise ConnectionError("simulated outage")
            self.persisted.extend(batch)

    class AlwaysFailingSink:
        async def write_batch(self, batch):
            raise ConnectionError("database down")

    async def scenario():
        flaky = FlakySink()
        writer = RelayWriter(flaky, retry_base_delay_s=0.001, max_attempts=3)
        writer.start()
        writer.offer_samples([_sample(1.0), _sample(2.0)])
        await writer.stop()
        assert [r.raw_value for r in flaky.persisted] == [1.0, 2.0]
        assert flaky.attempts == 3
        assert writer.persisted_records == 2
        assert writer.failed_batches == 0

        failing = RelayWriter(AlwaysFailingSink(), retry_base_delay_s=0.001, max_attempts=2)
        failing.start()
        failing.offer_samples([_sample(3.0)])
        await failing.put_lifecycle(SessionRecord(
            session_uid="33333333-3333-3333-3333-333333333333", record_status="open",
            client_identity="unit", connected_at=datetime.now(timezone.utc),
            disconnected_at=None, points_relayed=0,
        ))
        await failing.stop()
        return failing

    failing = asyncio.run(scenario())
    assert failing.failed_batches >= 1
    assert failing.failed_records >= 1
    assert failing.persisted_records == 0


def test_stop_abandons_records_when_the_drain_times_out_and_refuses_later_records():
    async def scenario():
        never = asyncio.Event()

        class StuckSink:
            async def write_batch(self, batch):
                await never.wait()

        writer = RelayWriter(StuckSink(), maxsize=5, batch_size=1, drain_timeout_s=0.05)
        writer.start()
        writer.offer_samples([_sample(1.0), _sample(2.0), _sample(3.0)])
        await asyncio.sleep(0)
        await writer.stop()
        assert writer.abandoned_records == 2
        assert writer.running is False
        assert writer.offer_samples([_sample(4.0)]) != OFFER_ACCEPTED
        assert await writer.put_lifecycle(SessionRecord(
            session_uid="44444444-4444-4444-4444-444444444444", record_status="open",
            client_identity="unit", connected_at=datetime.now(timezone.utc),
            disconnected_at=None, points_relayed=0,
        )) is False

    asyncio.run(scenario())


def test_successful_batches_feed_the_ingestion_throughput_metric():
    from api.middleware.response_time import get_metrics, reset_metrics

    reset_metrics()

    async def scenario():
        writer = RelayWriter(RecordingSink())
        writer.start()
        writer.offer_samples([_sample(float(i)) for i in range(50)])
        await writer.stop()

    asyncio.run(scenario())
    stats = get_metrics().snapshot()["throughput"]["ingestion_rate_pps"]
    assert stats["count"] >= 1
    assert stats["max"] > 0
    reset_metrics()


def test_http_ingest_returns_503_when_queue_is_full_and_relays_nothing_rejected():
    gate = threading.Event()
    sink = RecordingSink(gate=gate)
    app = create_app(relay_sink=sink, relay_queue_maxsize=2)
    token = _token(["telemetry_write", "telemetry_read"])
    headers = {"Authorization": f"Bearer {token}"}
    statuses = []
    accepted_values = []

    with TestClient(app) as client:
        for i in range(10):
            value = 100.0 + i
            response = client.post("/api/telemetry/ingest", json=_frame([value])["payload"], headers=headers)
            statuses.append(response.status_code)
            if response.status_code == 202:
                accepted_values.append(value)
            else:
                assert response.status_code == 503
                assert response.headers.get("Retry-After") == "1"
        gate.set()

    assert 2 <= len(accepted_values) <= 3
    assert statuses.count(202) == len(accepted_values)
    assert statuses.count(503) == 10 - len(accepted_values)
    persisted = sorted(r.raw_value for r in sink.records if isinstance(r, SampleRecord))
    assert persisted == sorted(accepted_values)


def test_websocket_backpressure_error_frame_and_no_relay_of_rejected_frame():
    gate = threading.Event()
    sink = RecordingSink(gate=gate)
    app = create_app(relay_sink=sink, relay_queue_maxsize=1)
    token = _token(["telemetry_read", "telemetry_write"])

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            codes = []
            relayed = []
            for value in (10.0, 11.0, 12.0, 13.0):
                ws.send_json(_frame([value]))
                reply = ws.receive_json()
                if reply["type"] == "error":
                    codes.append(reply["payload"]["code"])
                else:
                    relayed.append(reply["payload"]["observations"][0]["valueQuantity"]["value"])
            gate.set()

    assert "backpressure" in codes
    assert len(relayed) + len(codes) == 4
    persisted = sorted(r.raw_value for r in sink.records if isinstance(r, SampleRecord))
    assert persisted == sorted(relayed)


def test_raw_and_filtered_values_are_both_persisted_and_relayed():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)
    token = _token(["telemetry_read", "telemetry_write"])

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            ws.send_json(_frame([70.0, 100.0]))
            reply = ws.receive_json()

    samples = sorted(
        (r for r in sink.records if isinstance(r, SampleRecord)), key=lambda r: r.raw_value
    )
    assert [s.raw_value for s in samples] == [70.0, 100.0]
    alpha = MultiChannelEMAFilter.DEFAULT_ALPHAS["hr"]
    assert samples[0].filtered_value == pytest.approx(70.0)
    assert samples[1].filtered_value == pytest.approx(alpha * 100.0 + (1 - alpha) * 70.0)
    assert {s.filter_name for s in samples} == {"EMA"}
    assert {s.filter_alpha for s in samples} == {alpha}
    assert {s.channel for s in samples} == {"hr"}

    relayed = reply["payload"]["observations"]
    assert [o["raw_data"]["value"] for o in relayed] == [70.0, 100.0]
    assert relayed[1]["filtered_data"]["value"] == pytest.approx(samples[1].filtered_value)


def test_high_pressure_alarm_is_evaluated_on_the_filtered_value():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)
    token = _token(["telemetry_read", "telemetry_write"])

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            ws.send_json(_frame([160.0], channel="pressure"))
            reply = ws.receive_json()

    alarms = reply["payload"]["alarms"]
    assert alarms == [{"channel": "pressure", "active": True, "direction": "high", "threshold": 150.0}]


def test_invalid_frames_are_rejected_before_any_record_is_queued():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)
    token = _token(["telemetry_read", "telemetry_write"])
    bad_frames = [
        {"type": "telemetry", "payload": {"observations": []}},
        {"type": "telemetry", "payload": {"observations": [{"valueQuantity": {"value": True, "unit": "x"}}]}},
        {"type": "telemetry", "payload": {"observations": [{"valueQuantity": {"value": float("nan"), "unit": "x"}}]}},
        {"type": "telemetry", "payload": {"observations": [{"valueQuantity": {"value": 1.0, "unit": ""}}]}},
        {"type": "telemetry", "payload": {"observations": [{"valueQuantity": {"value": 1.0, "unit": "x"}}], "run_key": 7}},
    ]

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            for frame in bad_frames:
                ws.send_json(frame)
                reply = ws.receive_json()
                assert reply["type"] == "error"
                assert reply["payload"]["code"] == "invalid_payload"

    assert not [r for r in sink.records if isinstance(r, SampleRecord)]


def test_opt_in_simulator_broadcasts_without_persisting(monkeypatch):
    monkeypatch.setenv("TELEMETRY_SIMULATOR", "1")
    sink = RecordingSink()
    app = create_app(relay_sink=sink)

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={_token(['telemetry_read'])}") as ws:
            message = ws.receive_json()

    assert message["type"] == "telemetry"
    assert message["payload"]["patientId"] == "demo"
    assert len(message["payload"]["observations"]) == 4
    assert not [r for r in sink.records if isinstance(r, SampleRecord)]


def test_relay_modules_do_not_import_the_database_layer():
    forbidden = {"database", "models", "sqlalchemy", "api.relay_sink"}
    for relative in ("api/routes/telemetry.py", "api/relay_writer.py", "api/routes/telemetry_generator.py"):
        tree = ast.parse((_MIDDLEWARE / relative).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        hits = {name for name in imported if name.split(".")[0] in forbidden or name in forbidden}
        assert not hits, f"{relative} imports the database layer: {sorted(hits)}"


def test_relay_routes_do_not_reference_session_or_commit():
    source = (_MIDDLEWARE / "api/routes/telemetry.py").read_text(encoding="utf-8")
    for token in ("get_db", "SessionLocal", ".commit(", ".rollback(", "db.add("):
        assert token not in source, f"relay route module references {token}"
