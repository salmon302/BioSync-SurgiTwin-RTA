# SPDX-License-Identifier: MIT
"""
PostgreSQL sink for the telemetry relay (SRS FR-DAT-001, FR-DAT-003, FR-DAT-004, FR-DAT-005).

The only module in the relay that writes to the compliance database. The writer task calls
write_batch(), which runs the synchronous SQLAlchemy work in a worker thread through
asyncio.to_thread, so the event loop never executes database I/O.

Each batch is one transaction. Session records are written with an audit_log row through
insert_audit_log(), so the compute_hash_chain trigger in 003-triggers.sql assigns the digest.
"""

from __future__ import annotations

import asyncio
import json
from typing import Callable, Sequence

from sqlalchemy import insert, text
from sqlalchemy.orm import Session

from api.relay_writer import RelayRecord, SampleRecord, SessionRecord
from database import SessionLocal
from models import SurgicalTelemetry, TelemetrySession

SESSION_AUDIT_TABLE = "telemetry_sessions"


class SqlAlchemyRelaySink:
    """Batch writer for surgical_telemetry and telemetry_sessions."""

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory

    async def write_batch(self, batch: Sequence[RelayRecord]) -> None:
        await asyncio.to_thread(self._write_sync, list(batch))

    def _write_sync(self, batch: list) -> None:
        samples = [_sample_row(r) for r in batch if isinstance(r, SampleRecord)]
        sessions = [r for r in batch if isinstance(r, SessionRecord)]
        db = self._session_factory()
        try:
            if samples:
                db.execute(insert(SurgicalTelemetry), samples)
            for record in sessions:
                row = TelemetrySession(
                    session_uid=record.session_uid,
                    record_status=record.record_status,
                    client_identity=record.client_identity,
                    connected_at=record.connected_at,
                    disconnected_at=record.disconnected_at,
                    points_relayed=record.points_relayed,
                )
                db.add(row)
                db.flush()
                db.execute(
                    text(
                        "SELECT insert_audit_log(:table_name, 'INSERT', :record_id, :actor_id, "
                        "CAST(:data_new AS JSONB), NULL, :reason)"
                    ),
                    {
                        "table_name": SESSION_AUDIT_TABLE,
                        "record_id": row.id,
                        "actor_id": record.client_identity,
                        "data_new": json.dumps(_session_audit_state(record)),
                        "reason": f"telemetry session {record.record_status}",
                    },
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def _sample_row(record: SampleRecord) -> dict:
    return {
        "run_key": record.run_key,
        "channel": record.channel,
        "source_timestamp": record.source_timestamp,
        "raw_value": record.raw_value,
        "filtered_value": record.filtered_value,
        "filter_name": record.filter_name,
        "filter_alpha": record.filter_alpha,
        "unit": record.unit,
    }


def _session_audit_state(record: SessionRecord) -> dict:
    return {
        "session_uid": record.session_uid,
        "record_status": record.record_status,
        "client_identity": record.client_identity,
        "connected_at": record.connected_at.isoformat(),
        "disconnected_at": record.disconnected_at.isoformat() if record.disconnected_at else None,
        "points_relayed": record.points_relayed,
    }
