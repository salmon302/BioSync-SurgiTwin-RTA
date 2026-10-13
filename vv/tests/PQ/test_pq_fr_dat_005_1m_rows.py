# SPDX-License-Identifier: MIT
"""
PQ-3: 1,000,000-row hash chain verification on PostgreSQL (SRS FR-DAT-005 verification performance)

Origin: BioSync-Gateway tests/performance/test_pq3_1m_rows.py (adapted).

Adaptations:
  * The Gateway reset the table with TRUNCATE. The SurgiTwin rejection triggers forbid TRUNCATE
    on audit_log by design, so this test requires an empty audit_log on a dedicated database
    and skips otherwise.
  * psycopg2 has no cursor.nextset(). The Gateway loop that called it would raise. This version
    executes the verification script and reads the last result set.
  * Column names follow the SurgiTwin audit_log (action, data_new, actor_id).

Gated: runs only when BIOSYNC_PQ3_DATABASE_URL is set. Point it at a throwaway database only.
Example:
    BIOSYNC_PQ3_DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/surgitwin_pq3 \
        python -m pytest vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py -v -s
"""

import os
import pathlib
import time

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPO_ROOT / "database" / "migrations"
MIGRATION_FILES = ["001-extensions.sql", "002-schema.sql", "003-triggers.sql"]
HASH_CHECK_SQL = MIGRATIONS_DIR / "hash-chain-check.sql"

ROWS = 1_000_000
VERIFY_LIMIT_SECONDS = 60.0
PQ3_DATABASE_URL = os.environ.get("BIOSYNC_PQ3_DATABASE_URL", "")

pytestmark = [pytest.mark.pq, pytest.mark.pq3, pytest.mark.db]

INSERT_LOOP_SQL = """
DO $$
DECLARE
    i INT;
    v_data JSONB;
BEGIN
    FOR i IN 1..1000000 LOOP
        v_data := jsonb_build_object('row', i, 'table', 'pq3_stress', 'record_id', i, 'action', 'insert');
        INSERT INTO audit_log (table_name, action, record_id, actor_id, data_new, data_prev, reason)
        VALUES ('pq3_stress', 'INSERT', i, 'pq3-loader', v_data, NULL, 'PQ-3 1M-row load generation');
    END LOOP;
END $$;
"""


@pytest.mark.skipif(
    not PQ3_DATABASE_URL,
    reason="Set BIOSYNC_PQ3_DATABASE_URL to a dedicated PostgreSQL database to run PQ-3 (1M rows).",
)
def test_1m_rows_hash_chain_under_60s():
    import psycopg2

    conn = psycopg2.connect(PQ3_DATABASE_URL, connect_timeout=30)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        for name in MIGRATION_FILES:
            cur.execute((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))

        cur.execute("SELECT count(*) FROM audit_log")
        existing = cur.fetchone()[0]
        if existing != 0:
            pytest.skip(
                f"audit_log holds {existing} rows. PQ-3 requires an empty audit_log on a fresh "
                "database, because TRUNCATE is rejected by design."
            )

        insert_start = time.perf_counter()
        cur.execute(INSERT_LOOP_SQL)
        insert_elapsed = time.perf_counter() - insert_start

        cur.execute("SELECT count(*) FROM audit_log")
        rows = cur.fetchone()[0]
        assert rows == ROWS, f"audit_log holds {rows:,} rows, expected {ROWS:,} (NFR-P4 requires a real 1M-row table)"
        print(f"PQ-3: inserted {ROWS:,} rows in {insert_elapsed:.2f} s")

        verify_start = time.perf_counter()
        cur.execute(HASH_CHECK_SQL.read_text(encoding="utf-8"))
        cur.fetchall()
        verify_elapsed = time.perf_counter() - verify_start
        print(f"PQ-3: hash-chain-check.sql completed in {verify_elapsed:.2f} s (limit {VERIFY_LIMIT_SECONDS:.0f} s)")
        assert verify_elapsed < VERIFY_LIMIT_SECONDS, (
            f"Hash chain verification took {verify_elapsed:.2f} s, exceeds {VERIFY_LIMIT_SECONDS:.0f} s"
        )

        cur.execute("SELECT integrity_status, broken_at_row_id FROM verify_hash_chain()")
        status, broken_at = cur.fetchone()
        assert status == "ok", f"Hash chain integrity = {status}; broken at row {broken_at}"
    finally:
        conn.close()
