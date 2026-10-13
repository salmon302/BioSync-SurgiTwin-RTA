# SPDX-License-Identifier: MIT
"""
OQ: Hash chain digest cross-check, Python engine versus pgcrypto (SRS FR-DAT-005)

Acceptance:
  * The Python digest for a fixed input matches the recorded test vector (runs without a database).
  * The SQL audit_chain_digest() for the same input returns the same digest (requires
    BIOSYNC_TEST_DATABASE_URL). A mismatch means the Python verifier cannot be used to
    re-check rows written by the trigger.

Gateway open item (carried as known debt): the Gateway Python hash_chain.py used
json.dumps(sort_keys=True), which did not match the SQL digest. This test is the evidence that
the SurgiTwin rendering matches for the vector inputs. It is not evidence for every JSON value.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from engine.hash_chain import GENESIS_HASH, compute_hash, compute_test_vector

pytestmark = pytest.mark.oq

PINNED_VECTOR_DIGEST = "609c640ee61ad85a8a522dc383127ca16458821b26563def228b2f70e6a73b21"


def test_python_digest_matches_recorded_vector():
    vector = compute_test_vector()
    assert vector["expected_hash"] == PINNED_VECTOR_DIGEST


def test_python_digest_is_stable_across_calls():
    vector = compute_test_vector()
    again = compute_test_vector()
    assert vector["expected_hash"] == again["expected_hash"]


@pytest.mark.db
def test_sql_digest_matches_python_digest(db_engine):
    occurred_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    python_digest = compute_hash(
        previous_hash=GENESIS_HASH,
        occurred_at=occurred_at,
        actor_id="test_user",
        data_new={"field": "value"},
        data_prev=None,
        reason="initial creation",
    )
    with db_engine.connect() as conn:
        conn.execute(text("SET TIME ZONE 'America/New_York'"))
        sql_digest = conn.execute(
            text(
                "SELECT audit_chain_digest(:prev, :ts, :actor, NULL, CAST(:new AS JSONB), :reason)"
            ).bindparams(
                prev=GENESIS_HASH,
                ts=occurred_at,
                actor="test_user",
                new='{"field": "value"}',
                reason="initial creation",
            )
        ).scalar()
    assert sql_digest == python_digest
    assert sql_digest == PINNED_VECTOR_DIGEST
