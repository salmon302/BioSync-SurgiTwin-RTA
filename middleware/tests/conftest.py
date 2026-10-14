# SPDX-License-Identifier: MIT
"""
Pytest configuration for middleware unit and compliance tests.

Origin: BioSync-Gateway middleware/tests/conftest.py (adapted). Test-only environment defaults
are set with setdefault, so an exported value always wins. The JWT secret default is a test
string and is never a runtime default.
"""

import os
import pathlib
import sys

_TESTS_DIR = pathlib.Path(__file__).resolve().parent
_MIDDLEWARE_DIR = _TESTS_DIR.parent
for _path in (_MIDDLEWARE_DIR, _TESTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://localhost:5432/surgitwin_test")
os.environ.setdefault("DB_SSLMODE", "prefer")

import pytest  # noqa: E402

from database import get_db  # noqa: E402
from dbsupport import db_engine, db_session  # noqa: E402,F401


def pytest_configure(config):
    config.addinivalue_line("markers", "db: requires a PostgreSQL database (BIOSYNC_TEST_DATABASE_URL)")
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "oq: operational qualification (SRS FR/NFR mapping in module docstring)")


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with the database dependency bound to the test session."""
    from fastapi.testclient import TestClient

    from api.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
