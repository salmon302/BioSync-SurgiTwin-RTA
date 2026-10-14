# SPDX-License-Identifier: MIT
"""
Telemetry relay session tracking (SRS FR-DAT-001, FR-DAT-003, FR-DAT-004, NFR-SEC-001).

Covers the open and finalized row pattern for telemetry_sessions, the scope and identity rules
on the WebSocket, the refusal when the writer is not running, and the audit statement the sink
issues for each session record. No PostgreSQL is needed. The database behavior is covered by
test_relay_postgres_integration.py.
"""

import asyncio
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import TextClause
from starlette.websockets import WebSocketDisconnect

from api.auth import create_access_token
from api.main import create_app
from api.relay_sink import SqlAlchemyRelaySink
from api.relay_writer import RelayWriter, SampleRecord, SessionRecord

HR_CODE = {"system": "http://loinc.org", "code": "8867-4"}


def _telemetry_frame(values):
    return {
        "type": "telemetry",
        "payload": {
            "patientId": "SYN-SESSION-001",
            "observations": [
                {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"coding": [HR_CODE]},
                    "valueQuantity": {"value": value, "unit": "beats/min"},
                }
                for value in values
            ],
        },
    }


class RecordingSink:
    def __init__(self):
        self.records = []

    async def write_batch(self, batch):
        self.records.extend(batch)


def _token(scopes, sub="relay-tester"):
    claims = {"role": "clinician", "scopes": scopes}
    if sub is not None:
        claims["sub"] = sub
    return create_access_token(claims, expires_delta=1)


def _sessions(sink):
    return [r for r in sink.records if isinstance(r, SessionRecord)]


def _samples(sink):
    return [r for r in sink.records if isinstance(r, SampleRecord)]


def test_session_writes_open_then_finalized_rows_with_points_and_identity():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)
    token = _token(["telemetry_read", "telemetry_write"], sub="operator-42")

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            ws.send_json(_telemetry_frame([70.0, 71.0]))
            ws.receive_json()
            ws.send_json(_telemetry_frame([72.0]))
            ws.receive_json()

    sessions = _sessions(sink)
    assert [s.record_status for s in sessions] == ["open", "finalized"]
    opened, finalized = sessions
    assert opened.session_uid == finalized.session_uid
    assert opened.client_identity == finalized.client_identity == "operator-42"
    assert opened.disconnected_at is None
    assert opened.points_relayed == 0
    assert finalized.points_relayed == 3
    assert finalized.disconnected_at is not None
    assert finalized.disconnected_at >= finalized.connected_at


def test_session_without_telemetry_frames_finalizes_with_zero_points():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)
    token = _token(["telemetry_read"])

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            ws.send_json({"type": "ping"})
            assert ws.receive_json()["type"] == "pong"

    sessions = _sessions(sink)
    assert [s.record_status for s in sessions] == ["open", "finalized"]
    assert sessions[1].points_relayed == 0


def test_read_only_client_is_refused_telemetry_frames_and_nothing_is_queued():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)
    token = _token(["telemetry_read"])

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            ws.send_json(_telemetry_frame([80.0]))
            reply = ws.receive_json()

    assert reply["type"] == "error"
    assert reply["payload"]["code"] == "forbidden"
    assert _samples(sink) == []
    assert [s.record_status for s in _sessions(sink)] == ["open", "finalized"]
    assert _sessions(sink)[1].points_relayed == 0


def test_unknown_frame_type_and_malformed_json_return_error_frames():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)
    token = _token(["telemetry_read"])

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            ws.send_json({"type": "bogus"})
            assert ws.receive_json()["payload"]["code"] == "unsupported_type"
            ws.send_text("{not json")
            assert ws.receive_json()["payload"]["code"] == "invalid_json"
            ws.send_json(["not", "an", "object"])
            assert ws.receive_json()["payload"]["code"] == "invalid_frame"


def test_token_without_subject_is_refused():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)
    token = _token(["telemetry_read"], sub=None)

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as refused:
            with client.websocket_connect(f"/api/telemetry/stream?token={token}"):
                pass
    assert refused.value.code == 4401
    assert sink.records == []


def test_token_without_telemetry_read_scope_is_refused():
    sink = RecordingSink()
    app = create_app(relay_sink=sink)
    token = _token(["audit_read"])

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as refused:
            with client.websocket_connect(f"/api/telemetry/stream?token={token}"):
                pass
    assert refused.value.code == 4403
    assert sink.records == []


def test_missing_and_invalid_tokens_are_refused():
    app = create_app(relay_sink=RecordingSink())
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as missing:
            with client.websocket_connect("/api/telemetry/stream"):
                pass
        with pytest.raises(WebSocketDisconnect) as invalid:
            with client.websocket_connect("/api/telemetry/stream?token=not.a.jwt"):
                pass
    assert missing.value.code == 4401
    assert invalid.value.code == 4401


def test_websocket_is_refused_when_the_writer_is_not_running():
    """Without the lifespan the writer never starts. Frames must not be accepted silently."""
    app = create_app(relay_sink=RecordingSink())
    token = _token(["telemetry_read", "telemetry_write"])

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}"):
            pass
    assert refused.value.code == 1013


def test_http_ingest_is_refused_when_the_writer_is_not_running():
    app = create_app(relay_sink=RecordingSink())
    token = _token(["telemetry_write"])
    client = TestClient(app)

    response = client.post(
        "/api/telemetry/ingest",
        json=_telemetry_frame([90.0])["payload"],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503
    assert response.json()["reason"] == "rejected_stopped"


def test_http_ingest_requires_a_bearer_token():
    app = create_app(relay_sink=RecordingSink())
    response = TestClient(app).post("/api/telemetry/ingest", json=_telemetry_frame([90.0])["payload"])
    assert response.status_code == 401


def test_http_ingest_rejects_unscoped_token():
    app = create_app(relay_sink=RecordingSink())
    token = _token(["telemetry_read"])
    response = TestClient(app).post(
        "/api/telemetry/ingest",
        json=_telemetry_frame([90.0])["payload"],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


class _AuditFakeSession:
    def __init__(self, statements):
        self._statements = statements
        self._pending = []
        self._next_id = 100

    def execute(self, statement, params=None):
        self._statements.append((statement, params))

    def add(self, obj):
        self._pending.append(obj)

    def flush(self):
        for obj in self._pending:
            self._next_id += 1
            obj.id = self._next_id
        self._pending = []

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_sink_writes_one_hash_chained_audit_row_per_session_record():
    statements = []
    sink = SqlAlchemyRelaySink(session_factory=lambda: _AuditFakeSession(statements))
    connected = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    disconnected = datetime(2026, 10, 13, 12, 5, tzinfo=timezone.utc)
    session_uid = "22222222-2222-2222-2222-222222222222"

    async def scenario():
        writer = RelayWriter(sink)
        writer.start()
        await writer.put_lifecycle(SessionRecord(
            session_uid=session_uid, record_status="open", client_identity="auditor",
            connected_at=connected, disconnected_at=None, points_relayed=0,
        ))
        await writer.put_lifecycle(SessionRecord(
            session_uid=session_uid, record_status="finalized", client_identity="auditor",
            connected_at=connected, disconnected_at=disconnected, points_relayed=7,
        ))
        await writer.stop()

    asyncio.run(scenario())

    audit_calls = [
        (stmt, params) for stmt, params in statements
        if isinstance(stmt, TextClause) and "insert_audit_log" in stmt.text
    ]
    assert len(audit_calls) == 2
    reasons = [params["reason"] for _, params in audit_calls]
    assert reasons == ["telemetry session open", "telemetry session finalized"]
    assert {params["table_name"] for _, params in audit_calls} == {"telemetry_sessions"}
    assert {params["actor_id"] for _, params in audit_calls} == {"auditor"}
    assert {params["record_id"] for _, params in audit_calls} == {101, 102}
    finalized_state = json.loads(audit_calls[1][1]["data_new"])
    assert finalized_state["points_relayed"] == 7
    assert finalized_state["session_uid"] == session_uid
    assert finalized_state["disconnected_at"] == disconnected.isoformat()
