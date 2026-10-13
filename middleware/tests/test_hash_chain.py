# SPDX-License-Identifier: MIT
"""
Hash chain engine unit tests (no database).

Origin: BioSync-Gateway tests/unit/test_o13_hash_chain_api.py (adapted to the SurgiTwin
audit_log columns and the canonical rendering shared with audit_chain_digest()).

Implements SRS FR-DAT-005: H_i = SHA256(H_{i-1} || T_i || U_i || D_prev || D_new || R_i).
"""

from datetime import datetime, timedelta, timezone

from engine.hash_chain import GENESIS_HASH, _jsonb_text, _utc_text, compute_hash, verify_chain

T0 = datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)


def _build_chain(count=5):
    entries = []
    prev_hash = GENESIS_HASH
    for i in range(count):
        occurred_at = T0 + timedelta(seconds=i)
        data_new = {"table": "devices", "record_id": i, "action": "insert"}
        current_hash = compute_hash(
            previous_hash=prev_hash,
            occurred_at=occurred_at,
            actor_id="test-user",
            data_new=data_new,
            reason="unit",
        )
        entries.append({
            "id": i + 1,
            "prev_hash": prev_hash,
            "current_hash": current_hash,
            "occurred_at": occurred_at,
            "actor_id": "test-user",
            "data_prev": None,
            "data_new": data_new,
            "reason": "unit",
        })
        prev_hash = current_hash
    return entries


def test_compute_hash_deterministic():
    kwargs = dict(previous_hash=GENESIS_HASH, occurred_at=T0, actor_id="u", data_new={"a": 1})
    assert compute_hash(**kwargs) == compute_hash(**kwargs)
    assert len(compute_hash(**kwargs)) == 64


def test_compute_hash_changes_with_data_new():
    base = dict(previous_hash=GENESIS_HASH, occurred_at=T0, actor_id="u", reason="r")
    assert compute_hash(data_new={"action": "insert"}, **base) != compute_hash(data_new={"action": "update"}, **base)


def test_compute_hash_changes_with_data_prev_and_reason():
    base = dict(previous_hash=GENESIS_HASH, occurred_at=T0, actor_id="u", data_new={"a": 1})
    assert compute_hash(data_prev=None, reason="r", **base) != compute_hash(data_prev={"a": 0}, reason="r", **base)
    assert compute_hash(data_prev=None, reason="r1", **base) != compute_hash(data_prev=None, reason="r2", **base)


def test_compute_hash_changes_with_timestamp():
    base = dict(previous_hash=GENESIS_HASH, actor_id="u", data_new={"a": 1})
    assert compute_hash(occurred_at=T0, **base) != compute_hash(occurred_at=T0 + timedelta(microseconds=1), **base)


def test_utc_text_is_session_independent():
    local = datetime(2026, 10, 13, 8, 0, 0, 5, tzinfo=timezone(timedelta(hours=-4)))
    assert _utc_text(local) == "2026-10-13T12:00:00.000005Z"


def test_utc_text_treats_naive_as_utc():
    assert _utc_text(datetime(2026, 10, 13, 12, 0, 0)) == "2026-10-13T12:00:00.000000Z"


def test_jsonb_text_orders_keys_by_length_then_bytes():
    value = {"bb": 1, "a": 2, "aaa": 3, "ab": 4}
    assert _jsonb_text(value) == '{"a": 2, "ab": 4, "bb": 1, "aaa": 3}'


def test_jsonb_text_nested_and_scalars():
    value = {"flag": True, "none": None, "items": [1, "x"]}
    assert _jsonb_text(value) == '{"flag": true, "none": null, "items": [1, "x"]}'


def test_compute_hash_chain_links():
    entries = _build_chain(2)
    assert entries[1]["prev_hash"] == entries[0]["current_hash"]
    assert entries[0]["current_hash"] != GENESIS_HASH


def test_verify_chain_valid():
    is_valid, broken_at = verify_chain(_build_chain(5))
    assert is_valid is True
    assert broken_at is None


def test_verify_chain_tampered_data():
    entries = _build_chain(5)
    entries[2]["data_new"] = {"table": "devices", "record_id": 2, "action": "tampered"}
    is_valid, broken_at = verify_chain(entries)
    assert is_valid is False
    assert broken_at == 3


def test_verify_chain_broken_linkage():
    entries = _build_chain(3)
    entries[1]["prev_hash"] = "f" * 64
    is_valid, broken_at = verify_chain(entries)
    assert is_valid is False
    assert broken_at == 2


def test_verify_chain_empty():
    assert verify_chain([]) == (True, None)


def test_verify_chain_single_entry():
    assert verify_chain(_build_chain(1)) == (True, None)


def test_verify_chain_wrong_genesis():
    entries = _build_chain(1)
    entries[0]["prev_hash"] = "wrong_genesis_hash"
    is_valid, broken_at = verify_chain(entries)
    assert is_valid is False
    assert broken_at is not None


def test_genesis_hash_constant():
    assert GENESIS_HASH == "0" * 64


def test_hash_is_lowercase_hex_sha256():
    value = compute_hash(previous_hash=GENESIS_HASH, occurred_at=T0, actor_id="u", data_new={})
    assert len(value) == 64
    assert all(c in "0123456789abcdef" for c in value)
