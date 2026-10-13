# SPDX-License-Identifier: MIT
"""
OQ: JWT signing secret handling is fail-closed (SRS NFR-SEC-001)

Acceptance:
  * With ENVIRONMENT=production and no JWT_SECRET or JWT_SECRET_FILE, importing api.auth raises.
  * JWT_SECRET_FILE is read and stripped.
  * The development default is used only when ENVIRONMENT=development.

Each case runs in a fresh interpreter, because api.auth reads the secret at import time.
"""

import os
import pathlib
import subprocess
import sys

import pytest

pytestmark = pytest.mark.oq

MIDDLEWARE_DIR = pathlib.Path(__file__).resolve().parents[3] / "middleware"


def _run(code, env_overrides, drop=()):
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(MIDDLEWARE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


IMPORT_AUTH = "import api.auth as a; print('SECRET_LEN', len(a.JWT_SECRET))"


def test_production_without_secret_refuses_to_import():
    result = _run(
        IMPORT_AUTH,
        {"ENVIRONMENT": "production", "DATABASE_URL": "postgresql+psycopg2://localhost/x"},
        drop=("JWT_SECRET", "JWT_SECRET_FILE"),
    )
    assert result.returncode != 0
    assert "JWT_SECRET is not set" in result.stderr


def test_secret_file_is_read_and_stripped(tmp_path):
    secret_file = tmp_path / "jwt_secret.txt"
    secret_file.write_text("  file-based-secret-value\n", encoding="utf-8")
    result = _run(
        IMPORT_AUTH,
        {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql+psycopg2://localhost/x",
            "JWT_SECRET_FILE": str(secret_file),
        },
        drop=("JWT_SECRET",),
    )
    assert result.returncode == 0, result.stderr
    assert f"SECRET_LEN {len('file-based-secret-value')}" in result.stdout


def test_development_default_secret_is_only_used_in_development():
    result = _run(
        IMPORT_AUTH,
        {"ENVIRONMENT": "development", "DATABASE_URL": "postgresql+psycopg2://localhost/x"},
        drop=("JWT_SECRET", "JWT_SECRET_FILE"),
    )
    assert result.returncode == 0, result.stderr
    assert "SECRET_LEN" in result.stdout
