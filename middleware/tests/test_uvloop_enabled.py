# SPDX-License-Identifier: MIT
"""
R3 — uvloop event-loop verification (NFR-P1/P3, PQ-1/PQ-8).

Confirms uvloop is pinned in requirements.txt and that the loop-policy helper
selects uvloop when the package is available.
"""
import os
import sys

import pytest

_REPO = os.path.dirname(os.path.abspath(__file__))
_REQUIREMENTS = os.path.abspath(os.path.join(_REPO, "..", "requirements.txt"))


def test_uvloop_pinned_in_requirements():
    assert os.path.isfile(_REQUIREMENTS), "middleware/requirements.txt missing"
    with open(_REQUIREMENTS, "r", encoding="utf-8") as f:
        text = f.read()
    assert "uvloop" in text, "uvloop must be pinned in requirements.txt (R3)"


def test_configure_uvloop_sets_policy_when_available():
    from api.loop_policy import configure_uvloop
    import asyncio

    # If uvloop isn't installed in this environment, the helper must decline
    # gracefully rather than raise.
    try:
        import uvloop  # noqa: F401
    except ImportError:
        assert configure_uvloop(force=True) is False
        return

    ok = configure_uvloop(force=True)
    assert ok is True
    policy = asyncio.get_event_loop_policy()
    assert type(policy).__module__.startswith("uvloop"), (
        f"expected uvloop event-loop policy, got {type(policy).__module__}"
    )
