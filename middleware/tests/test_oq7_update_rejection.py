# SPDX-License-Identifier: MIT
"""
OQ-7: UPDATE Rejection Test (DB-gated)
Verifies that append-only triggers reject UPDATE statements on WORM record tables.

Test Criteria:
- Direct SQL UPDATE raises an append-only exception
- Zero-row UPDATE statements are also rejected (statement-level trigger)
- The stored row is unchanged after a rejected UPDATE

SRS Reference: FR-DAT-004 (rejection triggers), FR-DAT-003 (WORM tables)
Origin: BioSync-Gateway tests/test_oq7 (adapted: plates removed, SurgiTwin tables, bound parameters)
"""

import json
import uuid

import pytest
from sqlalchemy import text

from dbsupport import execute_expecting_rejection

APPEND_ONLY_TABLES = [
    "audit_log",
    "patients",
    "devices",
    "device_metrics",
    "observations",
    "simulation_runs",
    "simulation_states",
    "rta_switch_events",
    "sila2_rpc_log",
    "surgical_telemetry",
]

pytestmark = pytest.mark.db


def _insert_audit_row(session):
    row = session.execute(
        text(
            "INSERT INTO audit_log (table_name, action, record_id, actor_id, data_new) "
            "VALUES ('test_table', 'INSERT', 999, 'oq7', CAST(:data AS JSONB)) RETURNING id"
        ),
        {"data": json.dumps({"test": "data"})},
    )
    return row.scalar()


def _insert_observation(session):
    row = session.execute(
        text(
            "INSERT INTO observations (observation_code, value_quantity, fhir_resource) "
            "VALUES ('test-code', CAST(:vq AS JSONB), CAST(:fhir AS JSONB)) RETURNING id"
        ),
        {
            "vq": json.dumps({"value": 100, "unit": "mmHg"}),
            "fhir": json.dumps({"resourceType": "Observation"}),
        },
    )
    return row.scalar()


def _insert_device(session):
    row = session.execute(
        text(
            "INSERT INTO devices (device_identifier, device_name) "
            "VALUES (:ident, 'oq7 device') RETURNING id"
        ),
        {"ident": f"oq7-{uuid.uuid4().hex}"},
    )
    return row.scalar()


def _insert_patient(session):
    row = session.execute(
        text(
            "INSERT INTO patients (synthetic_id) VALUES (:sid) RETURNING id"
        ),
        {"sid": f"SYN-oq7-{uuid.uuid4().hex}"},
    )
    return row.scalar()


class TestOQ7UpdateRejection:
    """OQ-7: UPDATE rejection on append-only tables."""

    def test_update_audit_log_rejected(self, db_session):
        record_id = _insert_audit_row(db_session)
        message = execute_expecting_rejection(
            db_session,
            text("UPDATE audit_log SET reason = 'modified' WHERE id = :id").bindparams(id=record_id),
        )
        assert "append-only" in message.lower(), message

    def test_update_observations_rejected(self, db_session):
        record_id = _insert_observation(db_session)
        message = execute_expecting_rejection(
            db_session,
            text("UPDATE observations SET unit = 'changed' WHERE id = :id").bindparams(id=record_id),
        )
        assert "append-only" in message.lower(), message

    def test_update_devices_rejected(self, db_session):
        record_id = _insert_device(db_session)
        message = execute_expecting_rejection(
            db_session,
            text("UPDATE devices SET device_name = 'changed' WHERE id = :id").bindparams(id=record_id),
        )
        assert "append-only" in message.lower(), message

    @pytest.mark.parametrize("table_name", APPEND_ONLY_TABLES)
    def test_zero_row_update_rejected_on_every_table(self, db_session, table_name):
        """A statement-level trigger rejects UPDATE even when no rows match."""
        message = execute_expecting_rejection(
            db_session,
            text(f"UPDATE {table_name} SET id = id WHERE false"),
        )
        assert "append-only" in message.lower(), f"{table_name}: {message}"

    def test_row_unchanged_after_rejected_update(self, db_session):
        record_id = _insert_patient(db_session)
        original = db_session.execute(
            text("SELECT synthetic_id FROM patients WHERE id = :id").bindparams(id=record_id)
        ).scalar()

        execute_expecting_rejection(
            db_session,
            text("UPDATE patients SET demographics = CAST(:d AS JSONB) WHERE id = :id").bindparams(
                d=json.dumps({"age": 1}), id=record_id
            ),
        )

        current = db_session.execute(
            text("SELECT synthetic_id FROM patients WHERE id = :id").bindparams(id=record_id)
        ).scalar()
        assert current == original
