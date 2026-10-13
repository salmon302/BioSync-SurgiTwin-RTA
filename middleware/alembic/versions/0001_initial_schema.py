# SPDX-License-Identifier: MIT
"""Initial compliance schema (SRS FR-DAT-003 to FR-DAT-007).

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-13

Applies the SQL migrations in database/migrations in order. Each file is idempotent, so the
same files can also be mounted into the PostgreSQL container init directory. The Gateway
revisions 0002 to 0007 are not carried over. This single revision is the SurgiTwin baseline.
"""

import os

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

MIGRATIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "database", "migrations")
)
SQL_FILES = [
    "001-extensions.sql",
    "002-schema.sql",
    "003-triggers.sql",
]


def upgrade() -> None:
    for name in SQL_FILES:
        path = os.path.join(MIGRATIONS_DIR, name)
        with open(path, "r", encoding="utf-8") as fh:
            op.get_bind().exec_driver_sql(fh.read())


def downgrade() -> None:
    raise NotImplementedError(
        "The compliance schema is append-only and is not downgradable (SRS FR-DAT-003)."
    )
