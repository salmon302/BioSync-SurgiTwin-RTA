# SPDX-License-Identifier: MIT
"""
OQ: FR-DAT-004 audit capture and FR-DAT-003 finalization guard (DB-gated, gate G1.2, task 1.8)

Acceptance, under the VAL-010 split (SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md):
  * Every permitted change to users (INSERT, UPDATE, DELETE) writes one audit_log row with the
    action, the record id, the actor, and the prior and new row states. The suite checks 100% of
    the changes it performs.
  * The identity columns of users (id, username, created_at) are frozen. Each change attempt is
    rejected, the row is unchanged, and no audit row is written.
  * TRUNCATE on users is rejected and removes no rows.
  * The generic capture function writes audit rows for a second table shape.
  * The rejection triggers on the WORM tables and on telemetry_sessions still reject UPDATE,
    DELETE, and TRUNCATE (regression against OQ-7 and OQ-8).
  * The hash chain verifies after the capture writes, and a tampered capture row is reported.

Runs on the disposable database surgitwin_audit_test. The module creates and drops it.
Requires BIOSYNC_TEST_DATABASE_URL. Skipped with a reason when no database is reachable.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from dbsupport import execute_expecting_rejection, scratch_database
from engine.hash_chain import JsonText, verify_chain

pytestmark = [pytest.mark.oq, pytest.mark.db]

WORM_TABLES = [
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
    "telemetry_sessions",
]


@pytest.fixture(scope="module")
def audit_db():
    with scratch_database("surgitwin_audit_test") as engine:
        yield engine


@pytest.fixture
def session(audit_db):
    connection = audit_db.connect()
    transaction = connection.begin()
    db = Session(bind=connection)
    yield db
    db.close()
    transaction.rollback()
    connection.close()


def _insert_user(db, username, email=None):
    return db.execute(
        text(
            "INSERT INTO users (username, email, password_hash, role, scopes) "
            "VALUES (:u, :e, 'hash-initial', 'clinician', ARRAY['read']) RETURNING id"
        ),
        {"u": username, "e": email or f"{username}@example.test"},
    ).scalar()


def _user_row(db, user_id):
    return db.execute(text("SELECT to_jsonb(u) FROM users u WHERE id = :id"), {"id": user_id}).scalar()


def _audit_rows(db, table_name, record_id):
    rows = db.execute(
        text(
            "SELECT id, action, actor_id, data_prev, data_new FROM audit_log "
            "WHERE table_name = :t AND record_id = :r ORDER BY id"
        ),
        {"t": table_name, "r": record_id},
    ).mappings()
    return [dict(row) for row in rows]


def _set_actor(db, actor):
    db.execute(text("SELECT set_config('biosync.actor', :a, true)"), {"a": actor})


class TestPermittedChangesAudited:
    """Every permitted change to users writes one audit row with prior and new states (G1.2)."""

    def test_insert_writes_audit_row_with_new_state(self, session):
        _set_actor(session, "registrar-1")
        user_id = _insert_user(session, "alice")

        rows = _audit_rows(session, "users", user_id)
        assert len(rows) == 1
        assert rows[0]["action"] == "INSERT"
        assert rows[0]["actor_id"] == "registrar-1"
        assert rows[0]["data_prev"] is None
        assert rows[0]["data_new"] == _user_row(session, user_id)

    def test_actor_defaults_to_session_user_when_unset(self, session):
        user_id = _insert_user(session, "bob")
        session_user = session.execute(text("SELECT session_user")).scalar()

        rows = _audit_rows(session, "users", user_id)
        assert rows[0]["actor_id"] == session_user

    def test_update_captures_prior_and_new_state(self, session):
        user_id = _insert_user(session, "carol")
        before = _user_row(session, user_id)
        _set_actor(session, "clinician-2")
        session.execute(
            text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id}
        )
        after = _user_row(session, user_id)

        rows = _audit_rows(session, "users", user_id)
        assert [r["action"] for r in rows] == ["INSERT", "UPDATE"]
        update = rows[-1]
        assert update["actor_id"] == "clinician-2"
        assert update["data_prev"] == before
        assert update["data_new"] == after
        assert update["data_prev"]["last_login"] is None
        assert update["data_new"]["last_login"] is not None

    @pytest.mark.parametrize(
        ("column", "new_value"),
        [
            ("password_hash", "hash-rotated"),
            ("role", "admin"),
            ("scopes", ["read", "write"]),
            ("email", "carol.new@example.test"),
        ],
    )
    def test_each_permitted_column_change_is_audited(self, session, column, new_value):
        user_id = _insert_user(session, "dana")
        before = _user_row(session, user_id)
        session.execute(
            text(f"UPDATE users SET {column} = :v WHERE id = :id"), {"v": new_value, "id": user_id}
        )
        after = _user_row(session, user_id)

        rows = _audit_rows(session, "users", user_id)
        assert len(rows) == 2
        assert rows[-1]["action"] == "UPDATE"
        assert rows[-1]["data_prev"] == before
        assert rows[-1]["data_new"] == after
        assert rows[-1]["data_prev"][column] != rows[-1]["data_new"][column]

    def test_delete_captures_prior_state_and_removes_row(self, session):
        user_id = _insert_user(session, "erin")
        before = _user_row(session, user_id)
        session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})

        rows = _audit_rows(session, "users", user_id)
        assert [r["action"] for r in rows] == ["INSERT", "DELETE"]
        assert rows[-1]["data_prev"] == before
        assert rows[-1]["data_new"] is None
        remaining = session.execute(text("SELECT COUNT(*) FROM users WHERE id = :id"), {"id": user_id}).scalar()
        assert remaining == 0

    def test_every_permitted_change_writes_one_row(self, session):
        """Six permitted changes produce six audit rows, in order (100% of changes in this test)."""
        user_id = _insert_user(session, "frank")
        session.execute(text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id})
        session.execute(text("UPDATE users SET role = 'qa_officer' WHERE id = :id"), {"id": user_id})
        session.execute(text("UPDATE users SET password_hash = 'h2' WHERE id = :id"), {"id": user_id})
        session.execute(text("UPDATE users SET email = 'frank2@example.test' WHERE id = :id"), {"id": user_id})
        session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})

        rows = _audit_rows(session, "users", user_id)
        assert [r["action"] for r in rows] == ["INSERT", "UPDATE", "UPDATE", "UPDATE", "UPDATE", "DELETE"]

    def test_capture_applies_to_a_second_table_shape(self, session):
        """audit_row_change() is generic. This test attaches it to a probe table with other columns."""
        session.execute(
            text("CREATE TABLE audit_probe (id BIGSERIAL PRIMARY KEY, label TEXT NOT NULL, payload JSONB)")
        )
        session.execute(
            text(
                "CREATE TRIGGER audit_probe_capture AFTER INSERT OR UPDATE OR DELETE ON audit_probe "
                "FOR EACH ROW EXECUTE FUNCTION audit_row_change()"
            )
        )
        probe_id = session.execute(
            text("INSERT INTO audit_probe (label, payload) VALUES ('a', CAST(:p AS JSONB)) RETURNING id"),
            {"p": '{"k": 1}'},
        ).scalar()
        session.execute(text("UPDATE audit_probe SET label = 'b' WHERE id = :id"), {"id": probe_id})
        session.execute(text("DELETE FROM audit_probe WHERE id = :id"), {"id": probe_id})

        rows = _audit_rows(session, "audit_probe", probe_id)
        assert [r["action"] for r in rows] == ["INSERT", "UPDATE", "DELETE"]
        assert rows[0]["data_new"]["label"] == "a"
        assert rows[1]["data_prev"]["label"] == "a"
        assert rows[1]["data_new"]["label"] == "b"
        assert rows[2]["data_prev"]["label"] == "b"
        assert rows[2]["data_new"] is None


class TestFinalizationGuard:
    """Identity columns are frozen, and TRUNCATE on users is rejected (FR-DAT-003)."""

    @pytest.mark.parametrize(
        "statement",
        [
            "UPDATE users SET username = 'mallory' WHERE id = :id",
            "UPDATE users SET id = id + 1000 WHERE id = :id",
            "UPDATE users SET created_at = now() + INTERVAL '1 day' WHERE id = :id",
        ],
        ids=["username", "id", "created_at"],
    )
    def test_identity_column_change_rejected_and_not_audited(self, session, statement):
        user_id = _insert_user(session, "gina")
        before = _user_row(session, user_id)
        audit_before = len(_audit_rows(session, "users", user_id))

        message = execute_expecting_rejection(session, text(statement).bindparams(id=user_id))

        assert "frozen" in message, message
        assert _user_row(session, user_id) == before
        assert len(_audit_rows(session, "users", user_id)) == audit_before

    def test_truncate_users_rejected_and_rows_kept(self, session):
        _insert_user(session, "hank")
        count_before = session.execute(text("SELECT COUNT(*) FROM users")).scalar()

        message = execute_expecting_rejection(session, text("TRUNCATE users"))

        assert "does not permit TRUNCATE" in message, message
        assert session.execute(text("SELECT COUNT(*) FROM users")).scalar() == count_before


class TestWormRejectionRegression:
    """UPDATE, DELETE, and TRUNCATE on the WORM tables and telemetry_sessions stay rejected."""

    @pytest.mark.parametrize("table_name", WORM_TABLES)
    def test_zero_row_update_rejected(self, session, table_name):
        message = execute_expecting_rejection(session, text(f"UPDATE {table_name} SET id = id WHERE false"))
        assert "append-only" in message.lower(), f"{table_name}: {message}"

    @pytest.mark.parametrize("table_name", WORM_TABLES)
    def test_zero_row_delete_rejected(self, session, table_name):
        message = execute_expecting_rejection(session, text(f"DELETE FROM {table_name} WHERE false"))
        assert "append-only" in message.lower(), f"{table_name}: {message}"

    # devices is referenced by foreign keys, so PostgreSQL refuses a plain TRUNCATE before the trigger.
    @pytest.mark.parametrize("table_name", [t for t in WORM_TABLES if t != "devices"])
    def test_truncate_rejected(self, session, table_name):
        message = execute_expecting_rejection(session, text(f"TRUNCATE {table_name}"))
        assert "append-only" in message.lower(), f"{table_name}: {message}"


class TestHashChainAcrossCaptureWrites:
    """The chain verifies after capture writes, and a tampered capture row is reported."""

    def test_chain_verifies_after_capture_writes(self, session):
        user_id = _insert_user(session, "ivy")
        session.execute(text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id})
        session.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
        session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})

        status = session.execute(text("SELECT integrity_status FROM verify_hash_chain()")).scalar()
        assert status == "ok"

        rows = session.execute(
            text(
                "SELECT id, prev_hash, current_hash, occurred_at, actor_id, "
                "data_prev::text AS data_prev, data_new::text AS data_new, reason "
                "FROM audit_log ORDER BY id"
            )
        ).mappings()
        entries = [
            {
                **dict(row),
                "data_prev": JsonText(row["data_prev"]) if row["data_prev"] is not None else None,
                "data_new": JsonText(row["data_new"]),
            }
            for row in rows
        ]
        assert len(entries) == 4
        assert verify_chain(entries) == (True, None)

    def test_tampered_capture_row_is_reported(self, session):
        user_id = _insert_user(session, "jack")
        session.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
        target_id = _audit_rows(session, "users", user_id)[-1]["id"]

        session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_update"))
        session.execute(
            text("UPDATE audit_log SET data_new = CAST(:d AS JSONB) WHERE id = :id"),
            {"d": '{"role": "clinician"}', "id": target_id},
        )

        status, broken_id, _ = session.execute(
            text("SELECT integrity_status, broken_at_row_id, broken_at_table FROM verify_hash_chain()")
        ).one()
        assert status == "broken"
        assert broken_id == target_id
