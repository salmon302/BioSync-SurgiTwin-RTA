# SPDX-License-Identifier: MIT
"""
IQ-2: Python runtime version check (SRS §7.1).

Acceptance: the active interpreter is Python >= 3.11 (SRS IQ-2 / NFR runtime).

This test is environment-only (no database required) so it can run anywhere,
including local dev and CI, independent of a PostgreSQL service.
"""
import sys

import pytest


def test_python_version_at_least_3_11():
    """SRS IQ-2 — Python 3.11+ is the active runtime."""
    assert sys.version_info >= (3, 11), (
        f"SRS IQ-2 requires Python >= 3.11; "
        f"active interpreter is {sys.version.split()[0]}"
    )
