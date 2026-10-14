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

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.exc import OperationalError
from typing import Generator, Optional
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

# TLS/SSL configuration for secure database connections (SRS NFR-SEC-001, Gateway R2).
#
# DB_SSLMODE defaults to "verify-full" in every environment, so an unset or empty value fails
# closed. The server certificate must chain to DB_SSLROOTCERT and carry the host name used in
# DATABASE_URL, and the middleware presents DB_SSLCERT and DB_SSLKEY. A weaker mode is used only
# when it is set explicitly (for example, test runs set DB_SSLMODE=prefer in conftest.py).
# Server-side enforcement is pg_hba.conf hostssl clientcert=verify-full (database/postgres/).
DB_SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")
DB_SSLMODE = os.getenv("DB_SSLMODE") or "verify-full"
if DB_SSLMODE not in DB_SSL_MODES:
    raise RuntimeError(
        f"DB_SSLMODE={DB_SSLMODE!r} is not a libpq sslmode (NFR-SEC-001)."
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

# The sslmode is always passed to libpq. libpq otherwise defaults to "prefer", which would
# silently ignore an explicit "disable".
connect_args = {"sslmode": DB_SSLMODE}
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

# Audit actor propagation (FR-DAT-004). The audit-capture trigger in database/migrations/004-audit-capture.sql
# reads biosync.actor. The application sets it from the authenticated JWT subject with set_config(..., true),
# which is SET LOCAL semantics: the value ends with the transaction, so a pooled connection never carries an
# actor into a later transaction. The value is applied again at the start of every transaction of the session,
# because the session keeps the actor in session.info across commits.
ACTOR_SETTING = "biosync.actor"
ACTOR_MAX_LENGTH = 255  # audit_log.actor_id is VARCHAR(255)


def _apply_actor(session: Session, connection) -> None:
    actor: Optional[str] = session.info.get("actor")
    if actor:
        connection.execute(
            text("SELECT set_config(:setting, :actor, true)"),
            {"setting": ACTOR_SETTING, "actor": actor},
        )


def set_actor(session: Session, actor: str) -> None:
    """
    Attribute the session's audited writes to ``actor`` (the JWT subject).

    Raises ValueError when actor is not a non-empty string of at most ACTOR_MAX_LENGTH characters.
    Without a call to set_actor, the trigger records the database session user instead.
    """
    if not isinstance(actor, str) or not actor or len(actor) > ACTOR_MAX_LENGTH:
        raise ValueError("actor must be a non-empty string of at most 255 characters")
    session.info["actor"] = actor
    if session.in_transaction():
        _apply_actor(session, session.connection())


SERVICE_ACTOR_PREFIX = "service:"


def service_session(identity: str) -> Session:
    """
    Open a session for a background writer whose audited writes carry a service identity.

    The identity names the writer, for example service:pulse-engine. It is set with set_actor, so
    it follows the same per-transaction rule as a JWT subject. The caller closes the session.
    Raises ValueError when identity does not start with SERVICE_ACTOR_PREFIX.
    """
    if not isinstance(identity, str) or not identity.startswith(SERVICE_ACTOR_PREFIX):
        raise ValueError(f"service identity must start with {SERVICE_ACTOR_PREFIX!r}")
    db = SessionLocal()
    try:
        set_actor(db, identity)
    except ValueError:
        db.close()
        raise
    return db


@event.listens_for(Session, "after_begin")
def _set_actor_on_begin(session: Session, transaction, connection) -> None:
    _apply_actor(session, connection)


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
