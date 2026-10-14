# SPDX-License-Identifier: MIT
"""
Shared database fixtures for DB-dependent compliance tests.

Set BIOSYNC_TEST_DATABASE_URL to a disposable PostgreSQL 15+ database. When it is unset or
unreachable, the fixtures skip the dependent test with a reason. A DB-dependent test is never
reported as passed without database evidence.

Origin: BioSync-Gateway tests/conftest.py fixture pattern (db_engine, db_session), adapted
to the SQL migrations. The Gateway created tables with Base.metadata.create_all(), which
skips the append-only triggers and the hash chain. Migrations are applied here instead.
Credentials are not stored in this file.
"""

import pathlib
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
import os

TEST_DATABASE_URL = os.getenv("BIOSYNC_TEST_DATABASE_URL", "")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"
# 005 runs last because its grants name telemetry_sessions, which 006 creates.
MIGRATION_FILES = [
    "001-extensions.sql",
    "002-schema.sql",
    "003-triggers.sql",
    "004-audit-capture.sql",
    "006-telemetry-sessions.sql",
    "005-roles.sql",
]


def apply_migrations(engine) -> None:
    """Apply the idempotent SQL migrations to the target database."""
    with engine.begin() as conn:
        for name in MIGRATION_FILES:
            conn.exec_driver_sql((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))


@contextmanager
def scratch_database(name: str):
    """
    Create a disposable database on the server named by BIOSYNC_TEST_DATABASE_URL, apply the
    migrations, and yield its engine. The database is dropped on exit. Skips when no database is
    configured or reachable. The name must be a fixed test identifier, never user input.
    """
    if not TEST_DATABASE_URL:
        pytest.skip("BIOSYNC_TEST_DATABASE_URL not set; DB-dependent tests skipped")
    base = make_url(TEST_DATABASE_URL)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
            conn.exec_driver_sql(f"CREATE DATABASE {name}")
    except Exception as exc:
        admin.dispose()
        pytest.skip(f"PostgreSQL not reachable at BIOSYNC_TEST_DATABASE_URL ({exc.__class__.__name__})")
    engine = create_engine(base.set(database=name), pool_pre_ping=True)
    try:
        apply_migrations(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        admin.dispose()


def execute_expecting_rejection(session: Session, statement) -> str:
    """
    Run a statement that the database must reject and return the server error message.

    The statement runs inside a savepoint, so the enclosing transaction stays usable for
    later assertions. Raises AssertionError if the statement is not rejected.
    """
    try:
        with session.begin_nested():
            session.execute(statement)
    except DBAPIError as exc:
        return str(exc.orig)
    raise AssertionError("statement was not rejected by the database")


@pytest.fixture(scope="session")
def db_engine():
    if not TEST_DATABASE_URL:
        pytest.skip("BIOSYNC_TEST_DATABASE_URL not set; DB-dependent tests skipped")
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        with engine.connect():
            pass
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL not reachable at BIOSYNC_TEST_DATABASE_URL ({exc.__class__.__name__})")
    apply_migrations(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Session bound to a connection with an outer transaction, rolled back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
