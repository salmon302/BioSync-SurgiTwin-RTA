# SPDX-License-Identifier: MIT
"""
Audit actor propagation from the JWT subject to biosync.actor (finding F-4; SRS FR-DAT-004).

The audit-capture trigger (database/migrations/004-audit-capture.sql) records biosync.actor on each audit_log
row. The application sets that setting from the verified JWT subject through set_actor() in
middleware/database.py, with set_config(..., true). The value ends with each transaction, so a pooled
connection never carries an actor into a later transaction. A session without set_actor() records the
database session user, which is the documented default for writes that carry no JWT.

The tests use the scratch database surgitwin_sec_actor_test. Audit rows are append-only and cannot be deleted,
so committed test data requires a database that is dropped on exit. Set BIOSYNC_TEST_DATABASE_URL to enable them.
"""

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from api.auth import create_access_token, require_scope
from database import ACTOR_MAX_LENGTH, get_db, set_actor
from dbsupport import scratch_database

SCRATCH_DATABASE = "surgitwin_sec_actor_test"


@pytest.fixture(scope="module")
def actor_engine():
    with scratch_database(SCRATCH_DATABASE) as engine:
        yield engine


@pytest.fixture(scope="module")
def session_factory(actor_engine):
    return sessionmaker(bind=actor_engine, autoflush=False)


@pytest.fixture(scope="module")
def single_connection_engine(actor_engine):
    """One pooled connection, so a later session is guaranteed to reuse the connection an actor was set on."""
    engine = create_engine(actor_engine.url, poolclass=QueuePool, pool_size=1, max_overflow=0)
    yield engine
    engine.dispose()


def _insert_user(factory, username: str, actor: str) -> int:
    db = factory()
    try:
        set_actor(db, actor)
        user_id = db.execute(
            text(
                "INSERT INTO users (username, email, password_hash, role, scopes) "
                "VALUES (:u, :e, 'hash-initial', 'clinician', ARRAY['read']) RETURNING id"
            ),
            {"u": username, "e": f"{username}@example.test"},
        ).scalar()
        db.commit()
        return user_id
    finally:
        db.close()


def _user_audit(factory, user_id: int) -> list:
    db = factory()
    try:
        rows = db.execute(
            text(
                "SELECT action, actor_id FROM audit_log "
                "WHERE table_name = 'users' AND record_id = :r ORDER BY id"
            ),
            {"r": user_id},
        ).mappings()
        return [dict(row) for row in rows]
    finally:
        db.close()


def _login_role(factory) -> str:
    db = factory()
    try:
        return db.execute(text("SELECT session_user")).scalar()
    finally:
        db.close()


def _bearer(sub: str, scope: str = "admin") -> dict:
    token = create_access_token({"sub": sub, "role": "clinician", "scope": scope}, expires_delta=1)
    return {"Authorization": f"Bearer {token}"}


def _build_app(factory) -> FastAPI:
    app = FastAPI()

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    @app.post("/users/{user_id}/touch")
    def touch_user(user_id: int, db: Session = Depends(get_db), user=Depends(require_scope("admin"))):
        db.execute(text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id})
        db.commit()
        return {"actor": user.username}

    @app.post("/anonymous/{user_id}/touch")
    def touch_anonymously(user_id: int, db: Session = Depends(get_db)):
        db.execute(text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id})
        db.commit()
        return {"ok": True}

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def client(session_factory):
    return TestClient(_build_app(session_factory))


class TestSetActorValidation:
    """set_actor accepts only a non-empty string that fits audit_log.actor_id."""

    @pytest.mark.parametrize("actor", ["", None, 7, ["alice"], "x" * (ACTOR_MAX_LENGTH + 1)])
    def test_rejects_unusable_actor(self, actor):
        with pytest.raises(ValueError):
            set_actor(Session(), actor)

    def test_accepts_maximum_length_actor(self):
        db = Session()
        set_actor(db, "x" * ACTOR_MAX_LENGTH)
        assert db.info["actor"] == "x" * ACTOR_MAX_LENGTH


class TestJwtSubjectIsTheAuditActor:
    """A permitted change through an authenticated request is attributed to the JWT subject."""

    def test_api_write_records_subject_not_login_role(self, client, session_factory):
        username = f"clinician-{uuid.uuid4().hex[:8]}"
        user_id = _insert_user(session_factory, username, actor="registrar-1")

        response = client.post(f"/users/{user_id}/touch", headers=_bearer(username))

        assert response.status_code == 200, response.text
        rows = _user_audit(session_factory, user_id)
        assert [r["action"] for r in rows] == ["INSERT", "UPDATE"]
        assert rows[0]["actor_id"] == "registrar-1"
        assert rows[1]["actor_id"] == username
        assert rows[1]["actor_id"] != _login_role(session_factory)

    def test_actor_is_reapplied_in_each_transaction_of_one_session(self, session_factory):
        username = f"reapply-{uuid.uuid4().hex[:8]}"
        user_id = _insert_user(session_factory, username, actor="registrar-2")

        db = session_factory()
        try:
            set_actor(db, username)
            db.execute(text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id})
            db.commit()
            db.execute(text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id})
            db.commit()
        finally:
            db.close()

        rows = _user_audit(session_factory, user_id)
        assert [r["actor_id"] for r in rows] == ["registrar-2", username, username]

    def test_actor_set_inside_open_transaction_applies_to_that_transaction(self, session_factory):
        db = session_factory()
        try:
            db.execute(text("SELECT 1"))
            assert db.in_transaction()
            set_actor(db, "open-transaction-user")
            current = db.execute(text("SELECT current_setting('biosync.actor', true)")).scalar()
            assert current == "open-transaction-user"
            db.rollback()
        finally:
            db.close()


class TestActorDoesNotLeakThroughPool:
    """set_config(..., true) ends with the transaction, so the next checkout starts with no actor."""

    def test_next_session_on_the_same_connection_has_no_actor(self, single_connection_engine):
        factory = sessionmaker(bind=single_connection_engine, autoflush=False)
        username = f"pooled-{uuid.uuid4().hex[:8]}"
        user_id = _insert_user(factory, username, actor="registrar-3")
        login_role = _login_role(factory)

        db = factory()
        try:
            set_actor(db, username)
            db.execute(text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id})
            db.commit()
        finally:
            db.close()

        db = factory()
        try:
            leftover = db.execute(text("SELECT current_setting('biosync.actor', true)")).scalar()
            assert not leftover
            db.execute(text("UPDATE users SET last_login = now() WHERE id = :id"), {"id": user_id})
            db.commit()
        finally:
            db.close()

        rows = _user_audit(factory, user_id)
        assert rows[1]["actor_id"] == username
        assert rows[2]["actor_id"] == login_role


class TestNoJwtDefault:
    """Without a JWT, authenticated routes return 401, and unauthenticated writes record the login role."""

    def test_authenticated_route_without_token_is_refused_and_writes_nothing(self, client, session_factory):
        username = f"nojwt-{uuid.uuid4().hex[:8]}"
        user_id = _insert_user(session_factory, username, actor="registrar-4")

        response = client.post(f"/users/{user_id}/touch")

        assert response.status_code == 401
        assert [r["action"] for r in _user_audit(session_factory, user_id)] == ["INSERT"]

    def test_unauthenticated_write_records_database_session_user(self, client, session_factory):
        username = f"anon-{uuid.uuid4().hex[:8]}"
        user_id = _insert_user(session_factory, username, actor="registrar-5")

        response = client.post(f"/anonymous/{user_id}/touch")

        assert response.status_code == 200
        rows = _user_audit(session_factory, user_id)
        assert rows[-1]["action"] == "UPDATE"
        assert rows[-1]["actor_id"] == _login_role(session_factory)

    @pytest.mark.parametrize("sub", ["", 5, "x" * (ACTOR_MAX_LENGTH + 1)], ids=["empty", "non-string", "too-long"])
    def test_unusable_subject_is_refused_with_401(self, client, session_factory, sub):
        username = f"subject-{uuid.uuid4().hex[:8]}"
        user_id = _insert_user(session_factory, username, actor="registrar-6")

        response = client.post(f"/users/{user_id}/touch", headers=_bearer(sub))

        assert response.status_code == 401
        assert [r["action"] for r in _user_audit(session_factory, user_id)] == ["INSERT"]
