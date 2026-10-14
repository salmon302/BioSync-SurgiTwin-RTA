# SPDX-License-Identifier: MIT
# Metadata
# Title: PostgreSQL TLS connection matrix (R2 verification)
# Date: 2026-10-14T17:05:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: DEVELOPMENT_PLAN.md Phase 1 task 1.4 (Gateway R2, NFR-SEC-001)
# Summary: Runs three connection attempts against a TLS PostgreSQL server and prints PASS or FAIL per case.
#
# Usage (from the repository root, with the scratch server running):
#   set BIOSYNC_TLS_TEST_PASSWORD=<role password>
#   .venv-qual311\Scripts\python.exe SNDEV\scripts\tls-connection-matrix.py
#
# Environment:
#   BIOSYNC_TLS_TEST_PASSWORD   Role password. Never printed.
#   BIOSYNC_TLS_TEST_HOST       Default 127.0.0.1.
#   BIOSYNC_TLS_TEST_PORT       Default 5433.
#   BIOSYNC_TLS_TEST_DB         Default surgitwin_tls_test.
#   BIOSYNC_TLS_TEST_USER       Default surgitwin.
#   BIOSYNC_TLS_TEST_CERT_DIR   Default database/certs/out.

import os
import pathlib

import psycopg2

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CERT_DIR = pathlib.Path(os.getenv("BIOSYNC_TLS_TEST_CERT_DIR", REPO_ROOT / "database" / "certs" / "out"))

BASE = {
    "host": os.getenv("BIOSYNC_TLS_TEST_HOST", "127.0.0.1"),
    "port": int(os.getenv("BIOSYNC_TLS_TEST_PORT", "5433")),
    "dbname": os.getenv("BIOSYNC_TLS_TEST_DB", "surgitwin_tls_test"),
    "user": os.getenv("BIOSYNC_TLS_TEST_USER", "surgitwin"),
    "password": os.getenv("BIOSYNC_TLS_TEST_PASSWORD", ""),
    "connect_timeout": 5,
}

CASES = [
    (
        "cert ok (verify-full with client certificate)",
        {
            "sslmode": "verify-full",
            "sslrootcert": str(CERT_DIR / "ca.crt"),
            "sslcert": str(CERT_DIR / "client.crt"),
            "sslkey": str(CERT_DIR / "client.key"),
        },
        "accept",
    ),
    (
        "no cert (verify-full without client certificate)",
        {"sslmode": "verify-full", "sslrootcert": str(CERT_DIR / "ca.crt")},
        "reject",
    ),
    (
        "plaintext (sslmode=disable)",
        {"sslmode": "disable"},
        "reject",
    ),
]


def run_case(label, extra, expectation):
    try:
        conn = psycopg2.connect(**BASE, **extra)
    except psycopg2.OperationalError as exc:
        message = " ".join(str(exc).split())
        outcome = "reject"
    else:
        with conn.cursor() as cur:
            cur.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            ssl_in_use = cur.fetchone()[0]
        conn.close()
        message = f"connected, pg_stat_ssl.ssl={ssl_in_use}"
        outcome = "accept"
    status = "PASS" if outcome == expectation else "FAIL"
    print(f"{status} | {label} | expected {expectation}, got {outcome} | {message}")
    return status == "PASS"


def main():
    results = [run_case(label, extra, expectation) for label, extra, expectation in CASES]
    print(f"SUMMARY | {sum(results)}/{len(results)} cases PASS")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
