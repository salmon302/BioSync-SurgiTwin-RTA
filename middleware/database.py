"""
Database Configuration Module
Implements SRS FR-DAT-003 (PostgreSQL 15+ compliance tier) and NFR-SEC-001 (TLS and client certificates)

Origin: BioSync-Gateway middleware/database.py (adapted).

Adaptations:
  * DATABASE_URL has no built-in credentials. It is required when ENVIRONMENT is production
    (fail-closed, NFR-SEC-001). Development falls back to a local URL without a password.
  * init_db() and drop_db() are removed. create_all() bypasses the SQL migrations that
    install the append-only triggers and the hash chain, and drop_db() would destroy
    compliance records.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.exc import OperationalError
from typing import Generator
import os
import time
import logging

logger = logging.getLogger(__name__)

# Environment policy shared with api/auth.py (unset means production, fail-closed)
_ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if _ENVIRONMENT == "production":
        raise RuntimeError(
            "DATABASE_URL is not set. Refusing to start in production mode (NFR-SEC-001)."
        )
    DATABASE_URL = "postgresql+psycopg2://localhost:5432/surgitwin"

# TLS/SSL configuration for secure database connections
# Implements SRS NFR-SEC-001 (TLS) and the client-certificate intent of NFR-SEC-001.
#
# Default sslmode is environment-aware:
#   * ENVIRONMENT=production  -> "verify-full" (mutual-TLS intent). Fail-closed.
#   * any other value         -> "prefer" so local and CI stacks without a PKI still connect.
# Server-side enforcement (pg_hba hostssl clientcert=verify-full) is NOT migrated.
# Gateway R2 is carried as open debt (see docs/migration-map.md).
DB_SSLMODE = os.getenv(
    "DB_SSLMODE",
    "verify-full" if _ENVIRONMENT == "production" else "prefer",
)
DB_SSLROOTCERT = os.getenv("DB_SSLROOTCERT")  # Path to CA certificate
DB_SSLCERT = os.getenv("DB_SSLCERT")  # Path to client certificate
DB_SSLKEY = os.getenv("DB_SSLKEY")  # Path to client key

if DB_SSLMODE in ("verify-ca", "verify-full"):
    logger.info(
        "Database TLS enforced: sslmode=%s (client-certificate mutual-TLS requested)",
        DB_SSLMODE,
    )
    if not DB_SSLROOTCERT and DB_SSLMODE == "verify-full":
        logger.warning(
            "DB_SSLMODE=verify-full but DB_SSLROOTCERT is unset; the server certificate "
            "will be verified against the system CA bundle."
        )
elif _ENVIRONMENT == "production":
    logger.warning(
        "ENVIRONMENT=production but DB_SSLMODE=%s (not verify-full). Database connections "
        "are not using mutual-TLS (NFR-SEC-001).", DB_SSLMODE,
    )

# Build connection arguments for SSL/TLS
connect_args = {}
if DB_SSLMODE in ("require", "verify-ca", "verify-full"):
    connect_args["sslmode"] = DB_SSLMODE
    if DB_SSLROOTCERT:
        connect_args["sslrootcert"] = DB_SSLROOTCERT
    if DB_SSLCERT:
        connect_args["sslcert"] = DB_SSLCERT
    if DB_SSLKEY:
        connect_args["sslkey"] = DB_SSLKEY

# Reconnection settings (SRS NFR-R3: exponential backoff)
DB_RECONNECT_MAX_ATTEMPTS = int(os.getenv("DB_RECONNECT_MAX_ATTEMPTS", "5"))
DB_RECONNECT_BASE_DELAY = float(os.getenv("DB_RECONNECT_BASE_DELAY", "0.5"))
DB_RECONNECT_MAX_DELAY = float(os.getenv("DB_RECONNECT_MAX_DELAY", "30.0"))


def _exponential_backoff_delay(attempt: int) -> float:
    """Compute exponential backoff delay with a cap (SRS NFR-R3)."""
    delay = min(DB_RECONNECT_BASE_DELAY * (2 ** attempt), DB_RECONNECT_MAX_DELAY)
    return delay


def connect_with_backoff(engine, max_attempts: int = DB_RECONNECT_MAX_ATTEMPTS) -> bool:
    """
    Attempt to establish a connection to the database with exponential
    backoff (SRS NFR-R3). Returns True on success, False if all attempts
    are exhausted.
    """
    for attempt in range(max_attempts):
        try:
            conn = engine.connect()
            conn.close()
            return True
        except OperationalError as e:
            delay = _exponential_backoff_delay(attempt)
            logger.warning(
                f"Database connection attempt {attempt + 1}/{max_attempts} failed: {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            if attempt < max_attempts - 1:
                time.sleep(delay)
    return False


# Create SQLAlchemy engine with SSL/TLS support
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,  # Recycle connections after 5 minutes (NFR-R3)
    echo=False,
    connect_args=connect_args if connect_args else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()


def warm_up_connection(max_attempts: int = DB_RECONNECT_MAX_ATTEMPTS) -> bool:
    """
    Warm up the connection pool with exponential backoff (NFR-R3).
    Called at application startup to fail fast if the DB is unreachable.
    """
    return connect_with_backoff(engine, max_attempts)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for database sessions.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
