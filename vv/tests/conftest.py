# SPDX-License-Identifier: MIT
"""
Pytest configuration for the IQ, OQ, and PQ qualification suites.

Test-only environment defaults use setdefault, so an exported value always wins. Database
fixtures are shared with middleware/tests/dbsupport.py. DB-dependent protocols skip with a
reason when BIOSYNC_TEST_DATABASE_URL is not set or not reachable.
"""

import os
import pathlib
import sys

_VV_TESTS = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = _VV_TESTS.parents[1]
_MIDDLEWARE_DIR = _REPO_ROOT / "middleware"
_MIDDLEWARE_TESTS = _MIDDLEWARE_DIR / "tests"
for _path in (_MIDDLEWARE_DIR, _MIDDLEWARE_TESTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://localhost:5432/surgitwin_test")
os.environ.setdefault("DB_SSLMODE", "prefer")

import pytest  # noqa: E402

from dbsupport import db_engine, db_session  # noqa: E402,F401


def pytest_configure(config):
    config.addinivalue_line("markers", "iq: installation qualification")
    config.addinivalue_line("markers", "oq: operational qualification")
    config.addinivalue_line("markers", "pq: performance qualification")
    config.addinivalue_line("markers", "db: requires a PostgreSQL database (BIOSYNC_TEST_DATABASE_URL)")
    config.addinivalue_line("markers", "pq3: 1,000,000-row verification on a dedicated database (BIOSYNC_PQ3_DATABASE_URL)")
