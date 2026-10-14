# SPDX-License-Identifier: MIT
"""
Database TLS configuration tests (SRS NFR-SEC-001, Gateway R2).

Origin: BioSync-Gateway tests/test_db_ssl_config.py (adapted).

The client-side tests verify that database.py assembles TLS connect_args from the environment
and that the default is verify-full. They run without a database.

The artifact tests check database/postgres/pg_hba.conf, docker-compose.yml, and
database/certs/generate-certs.sh. They run without a database.

The live tests connect to a TLS-enabled PostgreSQL that is set by BIOSYNC_TLS_TEST_DATABASE_URL.
Set BIOSYNC_TLS_TEST_CERT_DIR when the certificates are not in database/certs/out/. They skip
with a reason when the URL is unset. The live tests need a scratch server that uses the
database/postgres/pg_hba.conf file and the certificates from database/certs/out/.
"""

import importlib
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


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


def test_explicit_prefer_passes_sslmode_without_cert_arguments(monkeypatch, reload_database):
    """An explicit DB_SSLMODE=prefer is passed to libpq. No certificate arguments are added."""
    monkeypatch.setenv("DB_SSLMODE", "prefer")
    monkeypatch.delenv("DB_SSLROOTCERT", raising=False)
    monkeypatch.delenv("DB_SSLCERT", raising=False)
    monkeypatch.delenv("DB_SSLKEY", raising=False)

    database = reload_database()

    assert database.connect_args == {"sslmode": "prefer"}


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


def test_default_verify_full_when_unset_in_development(monkeypatch, reload_database):
    """Verify-full is the default in every environment. Weaker modes need an explicit DB_SSLMODE."""
    monkeypatch.delenv("DB_SSLMODE", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    database = reload_database()

    assert database.DB_SSLMODE == "verify-full"
    assert database.connect_args["sslmode"] == "verify-full"


def test_empty_db_sslmode_fails_closed_to_verify_full(monkeypatch, reload_database):
    """An empty DB_SSLMODE, as produced by an unset value in .env, does not weaken the default."""
    monkeypatch.setenv("DB_SSLMODE", "")
    monkeypatch.setenv("ENVIRONMENT", "development")

    database = reload_database()

    assert database.DB_SSLMODE == "verify-full"


def test_unknown_db_sslmode_is_rejected(monkeypatch, reload_database):
    """A value that is not a libpq sslmode stops the module at import (fail-closed)."""
    monkeypatch.setenv("DB_SSLMODE", "allow-everything")
    monkeypatch.setenv("ENVIRONMENT", "development")

    with pytest.raises(RuntimeError, match="not a libpq sslmode"):
        reload_database()


def test_explicit_db_sslmode_overrides_default(monkeypatch, reload_database):
    """An explicit DB_SSLMODE always wins over the verify-full default."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DB_SSLMODE", "disable")

    database = reload_database()

    assert database.DB_SSLMODE == "disable"
    assert database.connect_args["sslmode"] == "disable"


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


def test_compose_enforces_verify_full():
    with open(os.path.join(REPO_ROOT, "docker-compose.yml"), "r", encoding="utf-8") as f:
        content = f.read()
    assert "DB_SSLMODE: verify-full" in content
    assert "DB_SSLMODE: disable" not in content
    assert "ssl=on" in content
    assert "ssl_ca_file=/var/lib/postgresql/tls/ca.crt" in content
    assert "hba_file=/opt/biosync/pg_hba.conf" in content
    assert "out/ca.key:" not in content


def test_pg_hba_enforces_clientcert():
    pg_hba = os.path.join(REPO_ROOT, "database", "postgres", "pg_hba.conf")
    with open(pg_hba, "r", encoding="utf-8") as f:
        lines = [ln.split() for ln in f if ln.strip() and not ln.strip().startswith("#")]
    assert any(fields[0] == "hostssl" and "clientcert=verify-full" in fields for fields in lines)
    assert not any(fields[0] == "host" for fields in lines)


def test_generate_certs_script_wires_postgres():
    script = os.path.join(REPO_ROOT, "database", "certs", "generate-certs.sh")
    with open(script, "r", encoding="utf-8") as f:
        content = f.read()
    assert "-CA ca.crt" in content
    assert "extendedKeyUsage=serverAuth" in content
    assert "DNS:localhost,DNS:postgres" in content
    assert "extendedKeyUsage=clientAuth" in content
    assert "CN=${DB_USER}" in content


def _tls_url():
    url = os.getenv("BIOSYNC_TLS_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("BIOSYNC_TLS_TEST_DATABASE_URL not set; TLS server tests skipped")
    return url


def _cert_dir():
    return os.getenv("BIOSYNC_TLS_TEST_CERT_DIR", os.path.join(REPO_ROOT, "database", "certs", "out"))


def _verified_connect_args():
    cert_dir = _cert_dir()
    return {
        "sslmode": "verify-full",
        "sslrootcert": os.path.join(cert_dir, "ca.crt"),
        "sslcert": os.path.join(cert_dir, "client.crt"),
        "sslkey": os.path.join(cert_dir, "client.key"),
    }


def _connect_and_report_ssl(connect_args):
    engine = create_engine(_tls_url(), connect_args=connect_args, pool_pre_ping=False)
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            ).scalar()
    finally:
        engine.dispose()


def test_tls_server_accepts_verified_client_certificate():
    """verify-full with the client certificate connects over TLS (pg_stat_ssl.ssl is true)."""
    assert _connect_and_report_ssl(_verified_connect_args()) is True


def test_tls_server_rejects_connection_without_client_certificate():
    """verify-full without a client certificate is rejected by pg_hba clientcert=verify-full."""
    _tls_url()
    connect_args = _verified_connect_args()
    del connect_args["sslcert"]
    del connect_args["sslkey"]
    with pytest.raises(OperationalError, match="client certificate"):
        _connect_and_report_ssl(connect_args)


def test_tls_server_rejects_plaintext_connection():
    """A non-TLS connection matches no pg_hba entry, because only hostssl rows exist."""
    _tls_url()
    with pytest.raises(OperationalError, match="no encryption"):
        _connect_and_report_ssl({"sslmode": "disable"})


def test_database_module_connects_with_verify_full(monkeypatch, reload_database):
    """database.py alone assembles the verify-full settings that the live server accepts."""
    _tls_url()
    cert_dir = _cert_dir()
    monkeypatch.setenv("DATABASE_URL", _tls_url())
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DB_SSLMODE", raising=False)
    monkeypatch.setenv("DB_SSLROOTCERT", os.path.join(cert_dir, "ca.crt"))
    monkeypatch.setenv("DB_SSLCERT", os.path.join(cert_dir, "client.crt"))
    monkeypatch.setenv("DB_SSLKEY", os.path.join(cert_dir, "client.key"))

    database = reload_database()

    with database.engine.connect() as conn:
        ssl_in_use = conn.execute(
            text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
        ).scalar()
    assert database.DB_SSLMODE == "verify-full"
    assert ssl_in_use is True
