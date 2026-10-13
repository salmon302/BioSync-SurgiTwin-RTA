# SPDX-License-Identifier: MIT
import pathlib
import sys

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from api.main import app, health  # noqa: E402


def test_health_route_registered():
    paths = [getattr(route, "path", None) for route in app.routes]
    assert "/health" in paths


def test_health_payload():
    assert health() == {"status": "ok"}
