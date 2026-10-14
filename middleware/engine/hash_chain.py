"""
Hash Chain Engine
Implements SRS FR-DAT-005 - Cryptographic hash chain for audit integrity

Origin: BioSync-Gateway middleware/engine/hash_chain.py (adapted).

Provides:
- compute_hash(): SHA-256 digest for an audit entry, byte-compatible with
  audit_chain_digest() in database/migrations/003-triggers.sql
- verify_chain(): Verifies linkage and digests for a chronological list of entries
- get_genesis_hash(): Returns the genesis block hash

Canonical input rendering (must match the SQL function):
- T_i is rendered as UTC with microseconds, e.g. 2026-10-13T22:34:45.123456Z.
- D_prev and D_new are rendered as PostgreSQL jsonb::text. Object keys are ordered
  by length and then by bytes, with ", " and ": " separators. A missing D_prev is "{}".
  D_new is NOT NULL in audit_log, so a JSON null in D_new is rendered as null.
- Floats are rendered in plain decimal notation from their shortest repr, which matches
  jsonb numeric output for values written in plain notation.
- A missing actor_id or reason is the empty string.
"""

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Genesis block hash (first block in empty chain)
GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def _utc_text(ts: datetime) -> str:
    """Render a timestamp as UTC text with microseconds (matches to_char in SQL)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts = ts.astimezone(timezone.utc)
    return ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond:06d}Z"


def _jsonb_text(value: Any) -> str:
    """Render a JSON value the way PostgreSQL renders jsonb::text."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(Decimal(repr(value)), "f")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        keys = sorted(value.keys(), key=lambda k: (len(k.encode("utf-8")), k.encode("utf-8")))
        parts = [f"{json.dumps(k, ensure_ascii=False)}: {_jsonb_text(value[k])}" for k in keys]
        return "{" + ", ".join(parts) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_jsonb_text(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False, default=str)


def compute_hash(
    previous_hash: str,
    occurred_at: datetime,
    actor_id: Optional[str],
    data_new: Any,
    data_prev: Any = None,
    reason: Optional[str] = None,
) -> str:
    """
    Compute the SHA-256 hash for an audit log entry.

    Implements SRS FR-DAT-005:
        H_i = SHA256(H_{i-1} || T_i || U_i || D_prev || D_new || R_i)

    Args:
        previous_hash: Hash of the previous entry in the chain (H_{i-1})
        occurred_at: Database-generated timestamp (T_i)
        actor_id: Authenticated user or API token identity (U_i)
        data_new: New row state (D_new)
        data_prev: Previous row state (D_prev), None for inserts
        reason: Human-readable change justification (R_i)

    Returns:
        SHA-256 hash as a lowercase hexadecimal string
    """
    concat_data = (
        previous_hash
        + _utc_text(occurred_at)
        + (actor_id or "")
        + ("{}" if data_prev is None else _jsonb_text(data_prev))
        + _jsonb_text(data_new)
        + (reason or "")
    )
    return hashlib.sha256(concat_data.encode("utf-8")).hexdigest()


def verify_chain(audit_entries: List[dict]) -> Tuple[bool, Optional[int]]:
    """
    Verify the integrity of a hash chain.

    Recomputes each digest with the FR-DAT-005 formula and checks prev_hash linkage.

    Args:
        audit_entries: Audit log entries in chronological (id ascending) order. Each entry
            has keys: id, prev_hash, current_hash, occurred_at, actor_id, data_prev,
            data_new, reason.

    Returns:
        Tuple of (is_valid, broken_at_id). broken_at_id is None when the chain is valid.
    """
    if not audit_entries:
        return True, None

    expected_prev = GENESIS_HASH
    for entry in audit_entries:
        if entry.get("prev_hash") != expected_prev:
            logger.warning("Hash chain linkage broken at entry ID %s", entry.get("id"))
            return False, entry.get("id", 0)

        expected_hash = compute_hash(
            previous_hash=entry["prev_hash"],
            occurred_at=entry["occurred_at"],
            actor_id=entry.get("actor_id"),
            data_new=entry.get("data_new"),
            data_prev=entry.get("data_prev"),
            reason=entry.get("reason"),
        )
        if expected_hash != entry.get("current_hash"):
            logger.warning(
                "Hash chain digest mismatch at entry ID %s. Expected %s, got %s",
                entry.get("id"), expected_hash, entry.get("current_hash"),
            )
            return False, entry.get("id", 0)

        expected_prev = entry["current_hash"]

    return True, None


def get_genesis_hash() -> str:
    """Return the genesis block hash."""
    return GENESIS_HASH


def compute_test_vector() -> dict:
    """
    Compute a fixed test vector for hash chain verification (OQ tamper detection).

    Returns:
        Dict with the input row and its expected digest.
    """
    test_data = {
        "occurred_at": datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "actor_id": "test_user",
        "data_new": {"field": "value"},
        "data_prev": None,
        "reason": "initial creation",
    }
    test_hash = compute_hash(previous_hash=GENESIS_HASH, **test_data)
    return {"input": test_data, "expected_hash": test_hash}


if __name__ == "__main__":
    print("Hash Chain Engine Self-Test")
    print("=" * 50)
    print(f"Genesis Hash: {GENESIS_HASH}")
    vector = compute_test_vector()
    print(f"\nTest Vector Hash: {vector['expected_hash']}")
    entry = {
        "id": 1,
        "prev_hash": GENESIS_HASH,
        "current_hash": vector["expected_hash"],
        **vector["input"],
    }
    is_valid, broken_id = verify_chain([entry])
    print(f"\nChain Verification: {'PASS' if is_valid else 'FAIL'}")
    if not is_valid:
        print(f"Broken at ID: {broken_id}")
