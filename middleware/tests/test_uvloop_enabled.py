# SPDX-License-Identifier: MIT
"""
R3 - uvloop event-loop policy (NFR-PERF-002 relay latency, NFR-PERF-001 ingestion; PQ-1, PQ-8).

Gate G1.5 requires this module to PASS. uvloop is not available on Windows, so the module
checks both paths:
  * Applied path: a stand-in `uvloop` module is injected, and configure_uvloop() must install
    its event-loop policy. This does not depend on uvloop being installed.
  * Degradation path: `uvloop` is made unimportable, and configure_uvloop() must return False
    and leave the default policy in place.
The real uvloop policy is checked only when the package is importable. Otherwise the module
verifies the degradation path for the real environment.
"""
import asyncio
import os
import sys
import types
import warnings

import pytest

_REPO = os.path.dirname(os.path.abspath(__file__))
_REQUIREMENTS = os.path.abspath(os.path.join(_REPO, "..", "requirements.txt"))


@pytest.fixture
def restore_policy():
    """Restore the global event-loop policy after a test that changes it."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        original = asyncio.get_event_loop_policy()
        yield
        asyncio.set_event_loop_policy(original)


def _current_policy():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return asyncio.get_event_loop_policy()


def test_uvloop_pinned_in_requirements():
    assert os.path.isfile(_REQUIREMENTS), "middleware/requirements.txt missing"
    with open(_REQUIREMENTS, "r", encoding="utf-8") as f:
        text = f.read()
    assert "uvloop" in text, "uvloop must be pinned in requirements.txt (R3)"


def test_configure_uvloop_is_skipped_under_pytest_without_force(restore_policy):
    from api.loop_policy import configure_uvloop

    before = _current_policy()
    assert configure_uvloop() is False
    assert _current_policy() is before


def test_configure_uvloop_applies_policy_when_package_present(restore_policy, monkeypatch):
    from api.loop_policy import configure_uvloop

    class _StandInPolicy(asyncio.DefaultEventLoopPolicy):
        pass

    fake = types.ModuleType("uvloop")
    fake.EventLoopPolicy = _StandInPolicy
    monkeypatch.setitem(sys.modules, "uvloop", fake)

    assert configure_uvloop(force=True) is True
    assert isinstance(_current_policy(), _StandInPolicy)


def test_configure_uvloop_degrades_when_package_missing(restore_policy, monkeypatch):
    from api.loop_policy import configure_uvloop

    monkeypatch.setitem(sys.modules, "uvloop", None)
    before = _current_policy()

    assert configure_uvloop(force=True) is False
    assert _current_policy() is before


def test_real_uvloop_environment_is_handled(restore_policy):
    from api.loop_policy import configure_uvloop

    try:
        import uvloop  # noqa: F401
    except ImportError:
        # Windows and any host without uvloop: the helper declines without raising.
        assert configure_uvloop(force=True) is False
        return

    assert configure_uvloop(force=True) is True
    assert type(_current_policy()).__module__.startswith("uvloop"), (
        "expected uvloop event-loop policy when uvloop is installed"
    )
