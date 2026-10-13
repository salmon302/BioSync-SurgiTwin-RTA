# SPDX-License-Identifier: MIT
"""
IQ-3: pgcrypto extension available and enabled (SRS FR-DAT-005).

Acceptance (IQ-3):
    pg_extension lists pgcrypto, and crypt()/gen_salt() return a non-empty hash.
    The digest() call used by audit_chain_digest() must also succeed.

Requires BIOSYNC_TEST_DATABASE_URL. Skipped with a reason when no database is reachable.
Origin: BioSync-Gateway tests/test_iq3_pgcrypto.py (adapted to the shared db_engine fixture).
"""

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.iq, pytest.mark.db]


def test_pgcrypto_extension_installed(db_engine):
    with db_engine.connect() as conn:
        installed = conn.execute(
            text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'pgcrypto'")
        ).scalar()
    assert installed == 1, "pgcrypto extension is not installed (IQ-3 / FR-DAT-005)"


def test_pgcrypto_crypt_and_digest_callable(db_engine):
    with db_engine.connect() as conn:
        hashed = conn.execute(text("SELECT crypt('test', gen_salt('bf'))")).scalar()
        digest_hex = conn.execute(
            text("SELECT encode(digest('abc', 'sha256'), 'hex')")
        ).scalar()
    assert isinstance(hashed, str) and len(hashed) > 0
    assert digest_hex == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
