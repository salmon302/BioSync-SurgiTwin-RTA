# SPDX-License-Identifier: MIT
"""
PQ: Hash chain verification performance, in-process (SRS FR-DAT-005 verification performance)

Origin: BioSync-Gateway tests/performance/test_pq2_hash_chain_perf.py (adapted to the SurgiTwin
hash interface). The SurgiTwin SRS has no exact analogue of the Gateway NFR-P4 1M-row target.
The 1M-row database check is in test_pq_fr_dat_005_1m_rows.py. The Gateway extrapolation test
that projected 1M-row timing from a 10k sample is not carried over, because a projection is not
a measurement.
"""

import time
from datetime import datetime, timedelta, timezone

import pytest

from engine.hash_chain import GENESIS_HASH, compute_hash, verify_chain

pytestmark = pytest.mark.pq

T0 = datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)


def _build_chain(count):
    entries = []
    prev_hash = GENESIS_HASH
    for i in range(count):
        occurred_at = T0 + timedelta(milliseconds=i)
        data_new = {"table": "surgical_telemetry", "record_id": i, "action": "insert"}
        current_hash = compute_hash(
            previous_hash=prev_hash,
            occurred_at=occurred_at,
            actor_id="pq-user",
            data_new=data_new,
        )
        entries.append({
            "id": i + 1,
            "prev_hash": prev_hash,
            "current_hash": current_hash,
            "occurred_at": occurred_at,
            "actor_id": "pq-user",
            "data_prev": None,
            "data_new": data_new,
            "reason": None,
        })
        prev_hash = current_hash
    return entries


def test_hash_computation_speed():
    """Average digest cost stays under 1 ms."""
    timestamp = T0
    data = {"table": "surgical_telemetry", "record_id": 1, "action": "insert"}
    samples = []
    for _ in range(1000):
        start = time.perf_counter()
        compute_hash(previous_hash=GENESIS_HASH, occurred_at=timestamp, actor_id="u", data_new=data)
        samples.append((time.perf_counter() - start) * 1000)
    avg_ms = sum(samples) / len(samples)
    assert avg_ms < 1.0, f"Average hash computation {avg_ms:.3f} ms exceeds 1 ms"


def test_chain_verification_10k_rows():
    entries = _build_chain(10_000)
    start = time.perf_counter()
    is_valid, broken_at = verify_chain(entries)
    elapsed = time.perf_counter() - start
    assert is_valid is True and broken_at is None
    assert elapsed < 10.0, f"10k-row verification took {elapsed:.2f} s (target < 10 s)"


def test_chain_verification_rate_exceeds_10k_rows_per_second():
    entries = _build_chain(5_000)
    start = time.perf_counter()
    is_valid, _ = verify_chain(entries)
    elapsed = time.perf_counter() - start
    assert is_valid is True
    rate = len(entries) / elapsed if elapsed > 0 else float("inf")
    assert rate > 10_000, f"Verification rate {rate:.0f} rows/s is below 10k rows/s"


def test_tampered_chain_detected_quickly():
    entries = _build_chain(1_000)
    entries[500]["data_new"] = {"table": "surgical_telemetry", "record_id": 500, "action": "tampered"}
    start = time.perf_counter()
    is_valid, broken_at = verify_chain(entries)
    elapsed = time.perf_counter() - start
    assert is_valid is False
    assert broken_at == 501
    assert elapsed < 5.0, f"Tampered detection took {elapsed:.2f} s (target < 5 s)"


def test_empty_chain_verifies_instantly():
    start = time.perf_counter()
    assert verify_chain([]) == (True, None)
    assert time.perf_counter() - start < 0.01
