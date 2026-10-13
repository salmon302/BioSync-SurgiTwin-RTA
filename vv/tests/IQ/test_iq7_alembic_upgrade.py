# SPDX-License-Identifier: MIT
"""
IQ-7: Alembic migrations apply cleanly and are idempotent (SRS FR-DAT-003).

Acceptance (IQ-7):
    `alembic upgrade head` completes without error against a PostgreSQL database, and
    `alembic_version` records 0001_initial_schema.

The db_engine fixture applies the raw SQL migrations first. Alembic then re-applies them,
which confirms that the revision is idempotent. This test runs only against the disposable
BIOSYNC_TEST_DATABASE_URL database.

Origin: BioSync-Gateway tests/test_iq7_alembic_upgrade.py (adapted: environment variable
BIOSYNC_TEST_DATABASE_URL, revision assertion added).
"""

import pathlib

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.iq, pytest.mark.db]

MIDDLEWARE_DIR = pathlib.Path(__file__).resolve().parents[3] / "middleware"


def test_alembic_upgrade_head(db_engine, monkeypatch):
    from alembic import command
    from alembic.config import Config

    from dbsupport import TEST_DATABASE_URL

    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    cfg = Config(str(MIDDLEWARE_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")

    with db_engine.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert revision == "0001_initial_schema"
