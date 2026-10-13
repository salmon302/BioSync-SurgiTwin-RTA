# SPDX-License-Identifier: MIT
"""
Database TLS configuration tests (NFR-SEC-001).

Origin: BioSync-Gateway tests/test_db_ssl_config.py (adapted).

The client-side tests verify that database.py assembles TLS connect_args from the environment
and that the default is environment-aware. They run without a database.

The server-side and deployment tests (pg_hba.conf hostssl clientcert=verify-full, the
docker-compose TLS settings, and the nginx certificate script) are strict expected failures.
Those artifacts are not part of this migration, and Gateway open item R2 is carried as debt.
A strict xfail turns into a visible failure as soon as the artifact is added, which forces the
test to be updated.
"""

import importlib
import os

import pytest


@pytest.fixture
def reload_database(monkeypatch, request):
    """Reload database.py with the current monkeypatched environment and restore it afterward."""

    def _reload():
        import database
        return importlib.reload(database)

    def _restore():
        monkeypatch.undo()
        _reload()

    request.addfinalizer(_restore)
    return _reload


def test_ssl_connect_args_assembled_when_verify_full(monkeypatch, reload_database):
    """When DB_SSLMODE=verify-full and cert paths are set, connect_args must contain all four."""
    monkeypatch.setenv("DB_SSLMODE", "verify-full")
    monkeypatch.setenv("DB_SSLROOTCERT", "/etc/ssl/certs/ca.crt")
    monkeypatch.setenv("DB_SSLCERT", "/etc/ssl/certs/client.crt")
    monkeypatch.setenv("DB_SSLKEY", "/etc/ssl/certs/client.key")

    database = reload_database()

    assert database.connect_args["sslmode"] == "verify-full"
    assert database.connect_args["sslrootcert"] == "/etc/ssl/certs/ca.crt"
    assert database.connect_args["sslcert"] == "/etc/ssl/certs/client.crt"
    assert database.connect_args["sslkey"] == "/etc/ssl/certs/client.key"
    assert database.engine.url.database is not None


def test_ssl_connect_args_empty_when_prefer(monkeypatch, reload_database):
    """DB_SSLMODE=prefer forces no sslmode or key arguments."""
    monkeypatch.setenv("DB_SSLMODE", "prefer")
    monkeypatch.delenv("DB_SSLROOTCERT", raising=False)
    monkeypatch.delenv("DB_SSLCERT", raising=False)
    monkeypatch.delenv("DB_SSLKEY", raising=False)

    database = reload_database()

    assert "sslmode" not in database.connect_args
    assert "sslrootcert" not in database.connect_args
    assert "sslcert" not in database.connect_args
    assert "sslkey" not in database.connect_args


def test_ssl_connect_args_partial_when_root_cert_only(monkeypatch, reload_database):
    """verify-full with only a root certificate sets sslrootcert and omits the client pair."""
    monkeypatch.setenv("DB_SSLMODE", "verify-full")
    monkeypatch.setenv("DB_SSLROOTCERT", "/etc/ssl/certs/ca.crt")
    monkeypatch.delenv("DB_SSLCERT", raising=False)
    monkeypatch.delenv("DB_SSLKEY", raising=False)

    database = reload_database()

    assert database.connect_args["sslmode"] == "verify-full"
    assert database.connect_args["sslrootcert"] == "/etc/ssl/certs/ca.crt"
    assert "sslcert" not in database.connect_args
    assert "sslkey" not in database.connect_args


def test_default_verify_full_in_production(monkeypatch, reload_database):
    """The default enforces verify-full when ENVIRONMENT=production."""
    monkeypatch.delenv("DB_SSLMODE", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")

    database = reload_database()

    assert database.DB_SSLMODE == "verify-full"


def test_default_prefer_in_development(monkeypatch, reload_database):
    """Non-production environments default to prefer so local and CI stacks still connect."""
    monkeypatch.delenv("DB_SSLMODE", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    database = reload_database()

    assert database.DB_SSLMODE == "prefer"


def test_explicit_db_sslmode_overrides_default(monkeypatch, reload_database):
    """An explicit DB_SSLMODE always wins over the environment-aware default."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DB_SSLMODE", "disable")

    database = reload_database()

    assert database.DB_SSLMODE == "disable"


def test_production_requires_database_url(monkeypatch, reload_database):
    """Fail-closed (NFR-SEC-001): production refuses to start without DATABASE_URL."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        reload_database()


def test_development_database_url_has_no_password(monkeypatch, reload_database):
    """The development fallback URL carries no credentials."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    database = reload_database()

    assert "@" not in database.DATABASE_URL
    assert database.DATABASE_URL.startswith("postgresql+psycopg2://")


@pytest.mark.xfail(
    strict=True,
    reason="Gateway R2 OPEN: docker-compose TLS and DB_SSLMODE=verify-full wiring not migrated",
)
def test_compose_enforces_verify_full():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    with open(os.path.join(repo_root, "docker-compose.yml"), "r", encoding="utf-8") as f:
        content = f.read()
    assert "DB_SSLMODE=verify-full" in content
    assert "ssl_ca_file" in content


@pytest.mark.xfail(
    strict=True,
    reason="Gateway R2 OPEN: database/postgres/pg_hba.conf hostssl clientcert=verify-full not migrated",
)
def test_pg_hba_enforces_clientcert():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    pg_hba = os.path.join(repo_root, "database", "postgres", "pg_hba.conf")
    with open(pg_hba, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
    assert any(ln.startswith("hostssl") and "clientcert=verify-full" in ln for ln in lines)


@pytest.mark.xfail(
    strict=True,
    reason="Gateway R2 OPEN: nginx/generate-certs.sh CA-signed PostgreSQL server certificate not migrated",
)
def test_generate_certs_script_wires_postgres():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    script = os.path.join(repo_root, "nginx", "generate-certs.sh")
    with open(script, "r", encoding="utf-8") as f:
        content = f.read()
    assert "${CERTS_DIR}/server.crt" in content
    assert '-CA "${CERTS_DIR}/ca.crt"' in content
