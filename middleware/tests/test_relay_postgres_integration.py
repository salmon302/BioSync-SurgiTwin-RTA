# SPDX-License-Identifier: MIT
"""
Telemetry relay against PostgreSQL (SRS FR-DAT-001, FR-DAT-003, FR-DAT-004, FR-DAT-005).

Skipped unless BIOSYNC_RELAY_ADMIN_URL is set to a PostgreSQL 15+ URL whose role may create
databases, and the server is reachable. The module creates the database surgitwin_relay_test,
applies 001-extensions, 002-schema, 003-triggers, and 006-telemetry-sessions, runs a relay
session end to end, and drops surgitwin_relay_test at teardown. No other database is used.

The admin URL holds credentials, so it is read from the environment and is never stored here.
"""

import asyncio
import json
import os
import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from api.auth import create_access_token
from api.main import create_app
from api.relay_sink import SqlAlchemyRelaySink

RELAY_DB = "surgitwin_relay_test"
ADMIN_URL = os.getenv("BIOSYNC_RELAY_ADMIN_URL", "")
MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "database" / "migrations"
MIGRATION_FILES = [
    "001-extensions.sql",
    "002-schema.sql",
    "003-triggers.sql",
    "006-telemetry-sessions.sql",
]


def _frame(values, channel_code, unit):
    return {
        "type": "telemetry",
        "payload": {
            "patientId": "SYN-PG-001",
            "observations": [
                {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"coding": [{"system": "http://loinc.org", "code": channel_code}]},
                    "effectiveDateTime": "2026-10-13T12:00:00Z",
                    "valueQuantity": {"value": value, "unit": unit},
                }
                for value in values
            ],
        },
    }


@pytest.fixture(scope="module")
def relay_db():
    if not ADMIN_URL:
        pytest.skip("BIOSYNC_RELAY_ADMIN_URL not set; relay PostgreSQL integration not run")

    admin = create_engine(
        ADMIN_URL,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
    try:
        with admin.connect() as conn:
            version = conn.execute(text("SHOW server_version_num")).scalar()
            conn.execute(text(f"DROP DATABASE IF EXISTS {RELAY_DB} WITH (FORCE)"))
            conn.execute(text(f"CREATE DATABASE {RELAY_DB}"))
    except Exception as exc:
        admin.dispose()
        pytest.skip(f"PostgreSQL not reachable or not usable ({exc.__class__.__name__})")
    if int(version) < 150000:
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {RELAY_DB} WITH (FORCE)"))
        admin.dispose()
        pytest.skip("PostgreSQL 15+ required")

    engine = create_engine(make_url(ADMIN_URL).set(database=RELAY_DB), pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            for name in MIGRATION_FILES:
                conn.exec_driver_sql((MIGRATIONS / name).read_text(encoding="utf-8"))
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {RELAY_DB} WITH (FORCE)"))
        admin.dispose()


def _rejected(engine, sql, match):
    with engine.connect() as conn:
        with pytest.raises(DBAPIError, match=match):
            conn.execute(text(sql))
        conn.rollback()


def test_relay_session_persists_samples_session_rows_and_hash_chained_audit(relay_db):
    app = create_app(relay_sink=SqlAlchemyRelaySink(session_factory=sessionmaker(bind=relay_db)))
    token = create_access_token(
        {"sub": "pq-operator", "role": "clinician", "scopes": ["telemetry_read", "telemetry_write"]},
        expires_delta=1,
    )

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/telemetry/stream?token={token}") as ws:
            ws.send_json(_frame([70.0, 100.0], "8867-4", "beats/min"))
            assert ws.receive_json()["type"] == "telemetry"
            ws.send_json(_frame([160.0], "8310-5", "mmHg"))
            assert ws.receive_json()["payload"]["alarms"][0]["channel"] == "pressure"

    with relay_db.connect() as conn:
        samples = conn.execute(text(
            "SELECT channel, raw_value, filtered_value, filter_name FROM surgical_telemetry ORDER BY id"
        )).all()
        assert [row.channel for row in samples] == ["hr", "hr", "pressure"]
        assert [row.raw_value for row in samples] == [70.0, 100.0, 160.0]
        assert all(row.filter_name == "EMA" for row in samples)
        assert samples[1].filtered_value == pytest.approx(0.3 * 100.0 + 0.7 * 70.0)

        sessions = conn.execute(text(
            "SELECT record_status, client_identity, points_relayed FROM telemetry_sessions ORDER BY id"
        )).all()
        assert [tuple(row) for row in sessions] == [
            ("open", "pq-operator", 0),
            ("finalized", "pq-operator", 3),
        ]

        audit = conn.execute(text(
            "SELECT table_name, action, actor_id, reason FROM audit_log ORDER BY id"
        )).all()
        assert [tuple(row) for row in audit] == [
            ("telemetry_sessions", "INSERT", "pq-operator", "telemetry session open"),
            ("telemetry_sessions", "INSERT", "pq-operator", "telemetry session finalized"),
        ]
        assert conn.execute(text("SELECT integrity_status FROM verify_hash_chain()")).scalar() == "ok"


def test_telemetry_sessions_rows_cannot_be_updated_deleted_or_truncated(relay_db):
    _rejected(relay_db, "UPDATE telemetry_sessions SET points_relayed = 99", "append-only")
    _rejected(relay_db, "DELETE FROM telemetry_sessions", "append-only")
    _rejected(relay_db, "TRUNCATE telemetry_sessions", "append-only")


def test_finalized_row_without_open_row_is_rejected(relay_db):
    _rejected(
        relay_db,
        "INSERT INTO telemetry_sessions (session_uid, record_status, client_identity, connected_at, "
        "disconnected_at, points_relayed) VALUES (gen_random_uuid(), 'finalized', 'orphan', now(), now(), 0)",
        "no open record",
    )


def test_shutdown_finalizes_a_connected_session_in_postgresql(relay_db):
    """The lifespan exits while the WebSocket is open. The session gets its finalized row during shutdown."""
    app = create_app(relay_sink=SqlAlchemyRelaySink(session_factory=sessionmaker(bind=relay_db)))
    token = create_access_token(
        {"sub": "pq-shutdown", "role": "clinician", "scopes": ["telemetry_read", "telemetry_write"]},
        expires_delta=1,
    )
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "app": app,
        "scheme": "ws",
        "path": "/api/telemetry/stream",
        "raw_path": b"/api/telemetry/stream",
        "root_path": "",
        "query_string": f"token={token}".encode(),
        "headers": [],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 50000),
        "subprotocols": [],
    }

    async def scenario():
        inbox: asyncio.Queue = asyncio.Queue()
        outbox: asyncio.Queue = asyncio.Queue()

        async def receive():
            return await inbox.get()

        async def send(message):
            await outbox.put(message)

        async with app.router.lifespan_context(app):
            await inbox.put({"type": "websocket.connect"})
            connection = asyncio.create_task(app(scope, receive, send))
            assert (await outbox.get())["type"] == "websocket.accept"
            await inbox.put({
                "type": "websocket.receive",
                "text": json.dumps(_frame([70.0, 71.0], "8867-4", "beats/min")),
            })
            assert (await outbox.get())["type"] == "websocket.send"
        connection.cancel()
        await asyncio.gather(connection, return_exceptions=True)

    asyncio.run(scenario())

    with relay_db.connect() as conn:
        sessions = conn.execute(text(
            "SELECT record_status, client_identity, points_relayed FROM telemetry_sessions "
            "WHERE client_identity = 'pq-shutdown' ORDER BY id"
        )).all()
        assert [tuple(row) for row in sessions] == [
            ("open", "pq-shutdown", 0),
            ("finalized", "pq-shutdown", 2),
        ]
        assert conn.execute(text("SELECT integrity_status FROM verify_hash_chain()")).scalar() == "ok"


def test_second_open_row_for_one_session_is_rejected(relay_db):
    with relay_db.connect() as conn:
        session_uid = conn.execute(text("SELECT gen_random_uuid()")).scalar()
        conn.execute(text(
            "INSERT INTO telemetry_sessions (session_uid, record_status, client_identity, connected_at) "
            "VALUES (:uid, 'open', 'dup', now())"
        ), {"uid": session_uid})
        conn.commit()
    _rejected(
        relay_db,
        "INSERT INTO telemetry_sessions (session_uid, record_status, client_identity, connected_at) "
        f"VALUES ('{session_uid}', 'open', 'dup', now())",
        "telemetry_sessions_one_row_per_status",
    )
