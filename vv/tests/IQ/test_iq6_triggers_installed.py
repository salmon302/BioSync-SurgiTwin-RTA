# SPDX-License-Identifier: MIT
"""
IQ-6: Append-only triggers are installed on every WORM record table (SRS FR-DAT-003, FR-DAT-004).

Acceptance (IQ-6):
    pg_trigger lists the UPDATE, DELETE, and TRUNCATE rejection triggers for each table in
    APPEND_ONLY_TABLES, plus the audit_log hash chain trigger.

Requires BIOSYNC_TEST_DATABASE_URL. Skipped with a reason when no database is reachable.
Origin: BioSync-Gateway tests/test_iq6_triggers_installed.py (adapted: the Gateway checked
audit_log only; the SurgiTwin check covers all ten WORM tables).
"""

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.iq, pytest.mark.db]

APPEND_ONLY_TABLES = [
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
]


def _installed_triggers(engine):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT c.relname, t.tgname
                FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                WHERE NOT t.tgisinternal
                """
            )
        ).fetchall()
    return {(relname, tgname) for relname, tgname in rows}


def test_audit_log_hash_chain_trigger_installed(db_engine):
    assert ("audit_log", "audit_log_hash_chain") in _installed_triggers(db_engine)


@pytest.mark.parametrize("table_name", APPEND_ONLY_TABLES)
def test_rejection_triggers_installed(db_engine, table_name):
    installed = _installed_triggers(db_engine)
    for suffix in ("prevent_update", "prevent_delete", "prevent_truncate"):
        assert (table_name, f"{table_name}_{suffix}") in installed, (
            f"Missing {table_name}_{suffix} (IQ-6 / FR-DAT-004)"
        )
