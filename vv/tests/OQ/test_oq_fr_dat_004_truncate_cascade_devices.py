# SPDX-License-Identifier: MIT
"""
OQ-8 supplement: TRUNCATE rejection on devices (SRS FR-DAT-004, FR-DAT-003; DB-gated)

The OQ-8 suite in middleware/tests excludes devices from its TRUNCATE case because devices is a
foreign key target. A plain TRUNCATE devices is refused by the foreign key check before any
trigger runs. TRUNCATE devices CASCADE truncates the referencing tables and reaches the
devices BEFORE TRUNCATE rejection trigger. This test covers that path.

Acceptance:
    TRUNCATE devices CASCADE raises the append-only exception, names devices, and leaves the
    device row count unchanged.

Requires BIOSYNC_TEST_DATABASE_URL. Skipped with a reason when no database is reachable.
"""

import uuid

import pytest
from sqlalchemy import text

from dbsupport import execute_expecting_rejection

pytestmark = [pytest.mark.oq, pytest.mark.db]


def test_truncate_cascade_on_devices_rejected(db_session):
    device_identifier = f"oq8-cascade-{uuid.uuid4().hex}"
    db_session.execute(
        text("INSERT INTO devices (device_identifier, device_name) VALUES (:ident, 'oq8 cascade device')"),
        {"ident": device_identifier},
    )
    before = db_session.execute(
        text("SELECT COUNT(*) FROM devices WHERE device_identifier = :ident"), {"ident": device_identifier}
    ).scalar()

    message = execute_expecting_rejection(db_session, text("TRUNCATE devices CASCADE"))

    assert "append-only" in message.lower(), message
    assert "devices" in message, message
    after = db_session.execute(
        text("SELECT COUNT(*) FROM devices WHERE device_identifier = :ident"), {"ident": device_identifier}
    ).scalar()
    assert before == 1
    assert after == before
