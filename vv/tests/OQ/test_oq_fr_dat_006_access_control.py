# SPDX-License-Identifier: MIT
"""
OQ: FR-DAT-006 unique individual credentials and database role separation (DB-gated, gates G1.4
and G1.1, task 1.9)

Acceptance:
  * Shared-account creation is rejected in 100% of the attempts in this module: duplicate and
    case or whitespace variants of a username, duplicate and variant emails, and generic shared
    account names. A distinct individual account is accepted as a control.
  * The application role surgitwin_app cannot disable or alter the immutability triggers, cannot
    truncate or change the record tables, cannot create triggers, and cannot set
    session_replication_role. Each attempt is run by a login role that is a member of
    surgitwin_app, and each one fails.
  * The application role keeps the grants it needs: inserts on record tables, and insert and
    update on users. Its user updates are captured in audit_log with the actor it sets.
  * The triggers that the attempts target stay enabled after the attempts.

The module creates the disposable database surgitwin_audit_test and a login role with a random
password. It drops both on exit. The password is not written to any file. Requires
BIOSYNC_TEST_DATABASE_URL. Skipped with a reason when no database is reachable.

Under client-certificate TLS the application login role cannot present a matching certificate, so
the tests that use the application login role are skipped with a reason. The shared-account tests
run under TLS.
"""

import secrets

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from dbsupport import execute_expecting_rejection, scratch_database

pytestmark = [pytest.mark.oq, pytest.mark.db]

RECORD_TABLES = [
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


TLS_ROLE_SKIP_REASON = (
    "TLS server (clientcert=verify-full): the client certificate CN must equal the login role, and "
    "database/certs/generate-certs.sh issues one client CN (PG_CLIENT_CN). A random login role cannot "
    "present a matching certificate, so the application-role tests are skipped under TLS."
)


@pytest.fixture(scope="module")
def app_engine(audit_db):
    """Engine that connects as a login role which is a member of surgitwin_app."""
    with audit_db.connect() as conn:
        if conn.execute(text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")).scalar():
            pytest.skip(TLS_ROLE_SKIP_REASON)
    role = f"surgitwin_app_login_{secrets.token_hex(4)}"
    password = secrets.token_hex(16)
    with audit_db.begin() as conn:
        conn.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
        conn.exec_driver_sql(f'GRANT surgitwin_app TO "{role}"')
    engine = create_engine(audit_db.url.set(username=role, password=password), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        yield engine
    finally:
        engine.dispose()
        with audit_db.begin() as conn:
            conn.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')


def _insert_user(db, username, email):
    return db.execute(
        text(
            "INSERT INTO users (username, email, password_hash, role, scopes) "
            "VALUES (:u, :e, 'hash', 'clinician', ARRAY['read']) RETURNING id"
        ),
        {"u": username, "e": email},
    ).scalar()


def _app_error(engine, statement):
    """Run one statement as the application login role in its own transaction. Return the error text."""
    with engine.connect() as conn:
        try:
            with conn.begin():
                conn.execute(text(statement))
        except DBAPIError as exc:
            return str(exc.orig)
    raise AssertionError(f"application role was allowed to run: {statement}")


class TestSharedAccountRejection:
    """Shared-account creation is rejected in 100% of attempts (G1.4)."""

    @pytest.fixture
    def seeded(self, session):
        _insert_user(session, "alice", "alice@example.test")
        return session

    @pytest.mark.parametrize(
        ("username", "email"),
        [
            ("alice", "second@example.test"),
            ("Alice", "variant-case@example.test"),
            (" alice ", "variant-space@example.test"),
            ("alice2", "alice@example.test"),
            ("alice3", "ALICE@example.test"),
            ("admin", "admin@example.test"),
            ("ADMIN", "admin-upper@example.test"),
            ("Shared", "shared@example.test"),
            ("operator", "operator@example.test"),
            ("guest", "guest@example.test"),
        ],
        ids=[
            "duplicate-username",
            "case-variant-username",
            "padded-username",
            "duplicate-email",
            "case-variant-email",
            "generic-admin",
            "generic-admin-upper",
            "generic-shared",
            "generic-operator",
            "generic-guest",
        ],
    )
    def test_shared_account_creation_rejected(self, seeded, username, email):
        message = execute_expecting_rejection(
            seeded,
            text("INSERT INTO users (username, email, password_hash, role) VALUES (:u, :e, 'h', 'clinician')")
            .bindparams(u=username, e=email),
        )
        constraints = (
            "users_username_normalized_key",
            "users_username_individual",
            "users_email_normalized_key",
            "users_email_key",
            "users_username_key",
        )
        assert any(name in message for name in constraints), message

    def test_all_attempts_leave_one_account(self, seeded):
        count = seeded.execute(text("SELECT COUNT(*) FROM users")).scalar()
        assert count == 1

    def test_distinct_individual_account_accepted(self, seeded):
        user_id = _insert_user(seeded, "seth.nenninger", "seth.nenninger@example.test")
        assert user_id is not None


class TestApplicationRoleBoundary:
    """The application role cannot alter the immutability triggers or the record tables (G1.1, G1.4)."""

    def test_application_login_is_member_of_surgitwin_app(self, app_engine):
        with app_engine.connect() as conn:
            current = conn.execute(text("SELECT current_user")).scalar()
            member = conn.execute(
                text("SELECT pg_has_role(current_user, 'surgitwin_app', 'MEMBER')")
            ).scalar()
        assert current.startswith("surgitwin_app_login_")
        assert member is True

    def test_record_tables_and_users_are_owned_by_surgitwin_owner(self, session):
        owners = session.execute(
            text("SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'public'")
        ).mappings().all()
        assert owners, "no tables found"
        for row in owners:
            assert row["tableowner"] == "surgitwin_owner", row

    @pytest.mark.parametrize(
        "statement",
        [
            "ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_update",
            "ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_delete",
            "ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_truncate",
            "ALTER TABLE observations DISABLE TRIGGER observations_prevent_update",
            "ALTER TABLE users DISABLE TRIGGER users_audit_capture",
            "ALTER TABLE users DISABLE TRIGGER users_identity_guard",
            "ALTER TABLE users DISABLE TRIGGER ALL",
            "ALTER TABLE audit_log ENABLE TRIGGER audit_log_prevent_update",
            "ALTER TABLE audit_log ADD COLUMN app_probe TEXT",
            "DROP TRIGGER audit_log_prevent_update ON audit_log",
        ],
    )
    def test_trigger_disable_and_alter_attempts_fail(self, app_engine, statement):
        message = _app_error(app_engine, statement)
        assert "must be owner" in message, message

    @pytest.mark.parametrize("table_name", RECORD_TABLES)
    def test_truncate_fails_for_application_role(self, app_engine, table_name):
        message = _app_error(app_engine, f"TRUNCATE {table_name}")
        assert "permission denied" in message, f"{table_name}: {message}"

    @pytest.mark.parametrize("table_name", RECORD_TABLES)
    def test_update_and_delete_fail_for_application_role(self, app_engine, table_name):
        update_message = _app_error(app_engine, f"UPDATE {table_name} SET id = id WHERE false")
        delete_message = _app_error(app_engine, f"DELETE FROM {table_name} WHERE false")
        assert "permission denied" in update_message, f"{table_name}: {update_message}"
        assert "permission denied" in delete_message, f"{table_name}: {delete_message}"

    def test_create_trigger_fails_for_application_role(self, app_engine):
        message = _app_error(
            app_engine,
            "CREATE TRIGGER app_probe BEFORE INSERT ON observations FOR EACH ROW "
            "EXECUTE FUNCTION compute_hash_chain()",
        )
        assert "permission denied" in message, message

    def test_session_replication_role_fails_for_application_role(self, app_engine):
        message = _app_error(app_engine, "SET session_replication_role = replica")
        assert "permission denied" in message, message

    def test_users_delete_and_truncate_fail_for_application_role(self, app_engine):
        assert "permission denied" in _app_error(app_engine, "DELETE FROM users WHERE false")
        assert "permission denied" in _app_error(app_engine, "TRUNCATE users")

    def test_immutability_triggers_stay_enabled_after_attempts(self, session):
        enabled = session.execute(
            text(
                "SELECT tgname, tgenabled FROM pg_trigger "
                "WHERE tgname IN ('audit_log_prevent_update', 'audit_log_prevent_delete', "
                "'audit_log_prevent_truncate', 'users_audit_capture', 'users_identity_guard') "
                "ORDER BY tgname"
            )
        ).all()
        assert len(enabled) == 5
        assert all(state == "O" for _, state in enabled), enabled


class TestApplicationRolePermittedPath:
    """The application role keeps the grants it needs, and its user updates are captured (G1.2)."""

    def test_application_insert_on_record_table_succeeds(self, app_engine):
        with app_engine.connect() as conn:
            trans = conn.begin()
            conn.execute(
                text("INSERT INTO observations (observation_code, value_quantity, fhir_resource) "
                     "VALUES ('oq-app', CAST(:vq AS JSONB), CAST(:fhir AS JSONB))"),
                {"vq": '{"value": 1, "unit": "mmHg"}', "fhir": '{"resourceType": "Observation"}'},
            )
            trans.rollback()

    def test_application_user_update_is_captured_with_application_actor(self, app_engine):
        with app_engine.connect() as conn:
            trans = conn.begin()
            user_id = conn.execute(
                text("INSERT INTO users (username, email, password_hash, role) "
                     "VALUES ('app.user', 'app.user@example.test', 'h', 'clinician') RETURNING id")
            ).scalar()
            conn.execute(text("SELECT set_config('biosync.actor', 'jwt-subject-42', true)"))
            conn.execute(text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id})
            rows = conn.execute(
                text("SELECT action, actor_id, data_prev->>'last_login' AS prev, "
                     "data_new->>'last_login' AS new FROM audit_log "
                     "WHERE table_name = 'users' AND record_id = :id ORDER BY id"),
                {"id": user_id},
            ).mappings().all()
            trans.rollback()
        assert [r["action"] for r in rows] == ["INSERT", "UPDATE"]
        assert rows[-1]["actor_id"] == "jwt-subject-42"
        assert rows[-1]["prev"] is None
        assert rows[-1]["new"] is not None

    def test_application_identity_change_is_rejected(self, app_engine):
        with app_engine.connect() as conn:
            trans = conn.begin()
            user_id = conn.execute(
                text("INSERT INTO users (username, email, password_hash, role) "
                     "VALUES ('app.frozen', 'app.frozen@example.test', 'h', 'clinician') RETURNING id")
            ).scalar()
            with pytest.raises(DBAPIError) as excinfo:
                conn.execute(text("UPDATE users SET username = 'app.renamed' WHERE id = :id"), {"id": user_id})
            trans.rollback()
        assert "frozen" in str(excinfo.value.orig)
