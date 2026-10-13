# SPDX-License-Identifier: MIT
"""
OQ-9: Tamper Detection Test (DB-gated)
Verifies that the hash chain detects tampering with audit_log rows below the application layer.

Test Criteria:
- Altering data_new breaks the chain at the altered row
- Altering current_hash breaks the chain at the altered row
- Altering prev_hash breaks the chain at the altered row
- A valid chain reports ok
- GET /api/audit/verify reports the same result

Tampering disables the append-only trigger for the duration of the change, which simulates an
attacker with table owner rights. The chain verifier must still report the broken row.

SRS Reference: FR-DAT-005 (hash chain and tamper detection)
Origin: BioSync-Gateway tests/test_oq9 (adapted to audit_log column names)
"""

import json

import pytest
from sqlalchemy import text

from api.auth import create_access_token

pytestmark = pytest.mark.db


def _insert_audit(session, table_name, record_id, data):
    return session.execute(
        text(
            "INSERT INTO audit_log (table_name, action, record_id, actor_id, data_new) "
            "VALUES (:t, 'INSERT', :r, 'oq9', CAST(:d AS JSONB)) RETURNING id"
        ).bindparams(t=table_name, r=record_id, d=json.dumps(data)),
    ).scalar()


def _tamper(session, sql, params):
    session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_update"))
    try:
        session.execute(text(sql).bindparams(**params))
    finally:
        session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_prevent_update"))


def _verify(session):
    return session.execute(text("SELECT * FROM verify_hash_chain()")).first()


class TestOQ9TamperDetection:
    """OQ-9: Tamper detection via the hash chain."""

    def test_tamper_detection_data_modification(self, db_session):
        original_id = _insert_audit(db_session, "test_table", 1, {"original": "data"})
        _tamper(
            db_session,
            "UPDATE audit_log SET data_new = CAST(:d AS JSONB) WHERE id = :id",
            {"d": json.dumps({"tampered": "data"}), "id": original_id},
        )

        status, broken_at, _ = _verify(db_session)
        assert status == "broken", f"Tamper not detected. Status: {status}"
        assert broken_at == original_id, f"Wrong broken row reported. Expected {original_id}, got {broken_at}"

    def test_tamper_detection_hash_modification(self, db_session):
        record_id = _insert_audit(db_session, "test_table", 2, {"test": "hash"})
        _tamper(
            db_session,
            "UPDATE audit_log SET current_hash = :h WHERE id = :id",
            {"h": "0" * 64, "id": record_id},
        )

        status, broken_at, _ = _verify(db_session)
        assert status == "broken", "Hash modification not detected"
        assert broken_at == record_id, "Wrong broken row reported"

    def test_tamper_detection_prev_hash_modification(self, db_session):
        _insert_audit(db_session, "test_table", 3, {"entry": "1"})
        id2 = _insert_audit(db_session, "test_table", 4, {"entry": "2"})
        _tamper(
            db_session,
            "UPDATE audit_log SET prev_hash = :h WHERE id = :id",
            {"h": "f" * 64, "id": id2},
        )

        status, broken_at, _ = _verify(db_session)
        assert status == "broken", "Previous hash tamper not detected"
        assert broken_at == id2, "Wrong broken row reported"

    def test_valid_chain_passes_verification(self, db_session):
        for i in range(5):
            _insert_audit(db_session, "test_table", i + 10, {"entry": str(i)})

        status, broken_at, _ = _verify(db_session)
        assert status == "ok", f"Valid chain marked as broken: status={status}"
        assert broken_at is None

    def test_api_verify_endpoint_reports_ok(self, client, db_session):
        _insert_audit(db_session, "test_table", 99, {"api": "test"})
        token = create_access_token({"sub": "auditor", "role": "qa_officer", "scopes": ["audit_read"]}, expires_delta=1)

        response = client.get("/api/audit/verify", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["integrity"] == "ok", f"API verification failed: {data}"
        assert data["broken_at_row_id"] is None

    def test_api_verify_endpoint_detects_tampering(self, client, db_session):
        record_id = _insert_audit(db_session, "test_table", 100, {"tamper": "test"})
        _tamper(
            db_session,
            "UPDATE audit_log SET data_new = CAST(:d AS JSONB) WHERE id = :id",
            {"d": json.dumps({"tampered": True}), "id": record_id},
        )
        token = create_access_token({"sub": "auditor", "role": "qa_officer", "scopes": ["audit_read"]}, expires_delta=1)

        response = client.get("/api/audit/verify", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["integrity"] == "broken", "Tampering not detected via API"
        assert data["broken_at_row_id"] == record_id
