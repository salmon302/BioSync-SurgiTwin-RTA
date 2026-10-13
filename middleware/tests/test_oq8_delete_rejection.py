# SPDX-License-Identifier: MIT
"""
OQ-8: DELETE Rejection Test (DB-gated)
Verifies that append-only triggers reject DELETE statements on WORM record tables.

Test Criteria:
- Direct SQL DELETE raises an append-only exception
- Zero-row DELETE statements are also rejected (statement-level trigger)
- The stored row is intact after a rejected DELETE
- TRUNCATE is rejected (row-level triggers do not fire on TRUNCATE)

SRS Reference: FR-DAT-004 (rejection triggers), FR-DAT-003 (WORM tables)
Origin: BioSync-Gateway tests/test_oq8 (adapted: plates removed, SurgiTwin tables, bound parameters)
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
    return session.execute(
        text(
            "INSERT INTO audit_log (table_name, action, record_id, actor_id, data_new) "
            "VALUES ('test_table', 'INSERT', 998, 'oq8', CAST(:data AS JSONB)) RETURNING id"
        ),
        {"data": json.dumps({"test": "delete"})},
    ).scalar()


def _insert_observation(session):
    return session.execute(
        text(
            "INSERT INTO observations (observation_code, value_quantity, fhir_resource) "
            "VALUES ('test-code', CAST(:vq AS JSONB), CAST(:fhir AS JSONB)) RETURNING id"
        ),
        {
            "vq": json.dumps({"value": 100, "unit": "mmHg"}),
            "fhir": json.dumps({"resourceType": "Observation"}),
        },
    ).scalar()


class TestOQ8DeleteRejection:
    """OQ-8: DELETE rejection on append-only tables."""

    def test_delete_audit_log_rejected(self, db_session):
        record_id = _insert_audit_row(db_session)
        message = execute_expecting_rejection(
            db_session,
            text("DELETE FROM audit_log WHERE id = :id").bindparams(id=record_id),
        )
        assert "append-only" in message.lower(), message

        count = db_session.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE id = :id").bindparams(id=record_id)
        ).scalar()
        assert count == 1, "audit_log row was deleted despite the trigger"

    def test_delete_observations_rejected(self, db_session):
        record_id = _insert_observation(db_session)
        message = execute_expecting_rejection(
            db_session,
            text("DELETE FROM observations WHERE id = :id").bindparams(id=record_id),
        )
        assert "append-only" in message.lower(), message

        count = db_session.execute(
            text("SELECT COUNT(*) FROM observations WHERE id = :id").bindparams(id=record_id)
        ).scalar()
        assert count == 1

    @pytest.mark.parametrize("table_name", APPEND_ONLY_TABLES)
    def test_zero_row_delete_rejected_on_every_table(self, db_session, table_name):
        """A statement-level trigger rejects DELETE even when no rows match."""
        message = execute_expecting_rejection(
            db_session,
            text(f"DELETE FROM {table_name} WHERE false"),
        )
        assert "append-only" in message.lower(), f"{table_name}: {message}"

    # devices is referenced by foreign keys. PostgreSQL rejects TRUNCATE on a referenced table
    # before the BEFORE TRUNCATE trigger runs, so that case is not a trigger test.
    @pytest.mark.parametrize("table_name", [t for t in APPEND_ONLY_TABLES if t != "devices"])
    def test_truncate_rejected_on_every_table(self, db_session, table_name):
        """TRUNCATE bypasses row-level triggers, so a statement-level trigger must reject it."""
        message = execute_expecting_rejection(
            db_session,
            text(f"TRUNCATE {table_name}"),
        )
        assert "append-only" in message.lower(), f"{table_name}: {message}"
