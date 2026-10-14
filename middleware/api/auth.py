"""
JWT Authentication Module
Implements SRS NFR-SEC-001 - JWT authentication for all external API interactions
Implements SRS FR-DAT-006 - Role-based access control with unique credentials

Origin: BioSync-Gateway middleware/api/auth.py (BioSync-Gateway FR-3.8.5, NFR-S2/S3/S7 mapping).
Secrets are injected via JWT_SECRET or JWT_SECRET_FILE and are never hard-coded.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
import bcrypt
from typing import Optional, List
import logging
import os
from uuid import uuid4

logger = logging.getLogger(__name__)

# JWT Configuration (SRS NFR-S7: secrets injected via env/Docker secrets, never hard-coded)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 1
JWT_REFRESH_EXPIRATION_DAYS = 7


def _load_jwt_secret() -> str:
    """
    Load the JWT signing secret from the environment.

    SRS NFR-S7: Secrets shall be injected via Docker secrets or environment
    variables — never hard-coded. In production this MUST be set; we fail
    closed (raise) when missing so a misconfigured deploy cannot silently
    fall back to an insecure default.
    """
    secret = os.getenv("JWT_SECRET")
    if secret:
        return secret

    # Docker secrets file (preferred in production)
    secret_file = os.getenv("JWT_SECRET_FILE")
    if secret_file:
        try:
            with open(secret_file, "r") as f:
                return f.read().strip()
        except OSError as e:
            logger.error(f"JWT_SECRET_FILE configured but unreadable: {e}")

    # Development fallback ONLY when ENVIRONMENT=development
    env = os.getenv("ENVIRONMENT", "production")
    if env == "development":
        logger.warning(
            "JWT_SECRET not set — using insecure development default. "
            "This MUST NOT be used in production (NFR-S7)."
        )
        return "dev-only-insecure-secret-change-me"

    raise RuntimeError(
        "JWT_SECRET is not set. Refusing to start in production mode (NFR-S7). "
        "Set the JWT_SECRET environment variable or JWT_SECRET_FILE."
    )


JWT_SECRET = _load_jwt_secret()

security = HTTPBearer(auto_error=False)

# Password hashing (SRS NFR-SEC-001: credentials never stored in plaintext).
# bcrypt is called directly. passlib 1.7.4 cannot read the bcrypt 4.1+ and 5.x backend, so it is not used.
def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def hash_password(plain: str) -> str:
    """Hash a plaintext password for storage with bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def authenticate_user(username: str, password: str) -> Optional["User"]:
    """
    Authenticate a user against the database (SRS FR-3.8.5).

    Looks up the ``users`` table by username, verifies the bcrypt password
    hash, and returns a :class:`User` with scopes sourced from the DB row
    (not hardcoded). Returns ``None`` on any failure.

    Falls back to a development-only path when no database is configured
    (ENVIRONMENT=development), preserving local-dev ergonomics without
    weakening production security.
    """
    # Production path: query the users table
    try:
        from database import SessionLocal
        from models import User as UserModel
    except ImportError:
        logger.warning("Database models not importable — auth will use dev fallback")
        return _dev_authenticate(username, password)

    try:
        db = SessionLocal()
        row = db.query(UserModel).filter(UserModel.username == username).first()
        if row is None:
            return None
        if not verify_password(password, row.password_hash):
            return None
        return User(
            username=row.username,
            email=row.email,
            role=row.role,
            scopes=list(row.scopes) if row.scopes else [],
        )
    except Exception as e:
        logger.error(f"Database auth error for user '{username}': {e}")
        # Fall back to dev auth if DB is unavailable and we're in dev mode
        return _dev_authenticate(username, password)
    finally:
        try:
            db.close()
        except Exception:
            pass


def _dev_authenticate(username: str, password: str) -> Optional["User"]:
    """
    Development-only authentication fallback.

    Only active when ENVIRONMENT=development. Accepts any non-empty
    credentials and assigns scopes based on username, mirroring the
    previous behavior so local dev and tests are not broken.
    """
    env = os.getenv("ENVIRONMENT", "production")
    if env != "development":
        return None
    logger.warning(
        f"Development auth fallback active for user '{username}' "
        "(ENVIRONMENT=development). This MUST NOT be used in production."
    )
    # Dev-only scopes: broad enough to exercise all feature areas locally.
    # Production relies on DB-backed user scopes, never this fallback.
    scopes = [
        "read", "write",
        "plate_read", "plate_write",
        "fhir_read", "fhir_write",
        "simulation_read", "simulation_write",
        "human_factors_read", "human_factors_write",
        "audit_read", "audit_write",
        "ai_read", "ai_write",
        "scenario_read", "scenario_write",
    ]
    if username == "admin":
        scopes.append("admin")
    return User(
        username=username,
        email=f"{username}@biosync.local",
        role="admin" if username == "admin" else "user",
        scopes=scopes,
    )


class User(BaseModel):
    """Authenticated user model"""
    username: str
    email: str
    role: str
    scopes: List[str]


class TokenData(BaseModel):
    """JWT token payload"""
    username: Optional[str] = None
    role: Optional[str] = None
    scopes: Optional[List[str]] = None
    scope: Optional[List[str]] = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Dependency to extract and validate JWT token from Authorization header.
    Returns authenticated User object or raises 401 Unauthorized.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        
        username: str = payload.get("sub")
        role: str = payload.get("role")
        scopes: List[str] = payload.get("scope") or payload.get("scopes") or []
        
        if username is None:
            raise credentials_exception
            
        token_data = TokenData(
            username=username,
            role=role,
            scopes=scopes,
            scope=scopes,
        )
        
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception
    
    # In production, you would validate against database
    # For now, return user from token
    return User(
        username=token_data.username,
        email=f"{token_data.username}@biosync.local",
        role=token_data.role or "user",
        scopes=token_data.scopes or []
    )


def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Payload to encode in token
        expires_delta: Expiration time in hours (default: JWT_EXPIRATION_HOURS)
    
    Returns:
        Encoded JWT token string
    """
    from datetime import datetime, timedelta, timezone

    issued_at = datetime.now(timezone.utc)
    to_encode = data.copy()
    to_encode["jti"] = str(uuid4())

    if expires_delta is not None:
        expire = issued_at + timedelta(hours=expires_delta)
    else:
        expire = issued_at + timedelta(hours=JWT_EXPIRATION_HOURS)

    to_encode.update({"iat": issued_at, "exp": expire})
    # FR-3.8.5: canonical JWT claim is `scope` (singular). Retain
    # `scopes` as a backward-compatible alias for existing clients.
    _scope = data.get("scope") or data.get("scopes")
    if _scope is not None:
        to_encode["scope"] = _scope

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token with extended expiration.
    
    Args:
        data: Payload to encode in token
    
    Returns:
        Encoded JWT refresh token string
    """
    from datetime import datetime, timedelta, timezone
    
    to_encode = data.copy()
    issued_at = datetime.now(timezone.utc)
    to_encode.update({
        "iat": issued_at,
        "exp": issued_at + timedelta(days=JWT_REFRESH_EXPIRATION_DAYS),
        "jti": str(uuid4()),
        "type": "refresh",
    })
    _scope = data.get("scope") or data.get("scopes")
    if _scope is not None:
        to_encode["scope"] = _scope

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_refresh_token(token: str) -> Optional[User]:
    """
    Verify a refresh token and return the associated User.
    
    Args:
        token: JWT refresh token string
    
    Returns:
        User object if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        if payload.get("type") != "refresh":
            return None
        
        username: str = payload.get("sub")
        role: str = payload.get("role")
        scopes: List[str] = payload.get("scope") or payload.get("scopes") or []
        
        if username is None:
            return None
            
    except JWTError:
        return None
    
    return User(
        username=username,
        email=f"{username}@biosync.local",
        role=role or "user",
        scopes=scopes or [],
    )


def require_scope(required_scope: str):
    """
    Dependency factory for scope-based authorization.
    
    Usage:
        @app.get("/api/audit")
        async def read_audit(user: User = Depends(require_scope("audit_read"))):
            ...
    """
    async def scope_checker(user: User = Depends(get_current_user)) -> User:
        if required_scope not in user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required scope: {required_scope}"
            )
        return user
    return scope_checker


def verify_token(token: str) -> Optional[dict]:
    """
    Verify a JWT token and return its payload.
    Used for WebSocket authentication where Depends() is not available.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload dict if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        return None
