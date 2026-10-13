# SPDX-License-Identifier: MIT
"""
JWT authentication tests (no database).

Origin: BioSync-Gateway tests/integration/test_api_auth.py (adapted). Route tests that depend on
the Gateway plates and Observation endpoints are replaced by scope checks on the audit route.
The login round trip uses a stubbed authenticate_user, so no database is required.

Implements SRS NFR-SEC-001 (JWT authentication) and FR-DAT-006 (scope-based access control).
"""

import base64
import json
import time

import pytest
from jose import jwt as jose_jwt

from api.auth import JWT_ALGORITHM, JWT_SECRET, User, create_access_token, create_refresh_token


@pytest.fixture
def plain_client():
    from fastapi.testclient import TestClient

    from api.main import app

    return TestClient(app)


def _token(scopes, expires_delta=1):
    return create_access_token(
        {"sub": "tester", "role": "clinician", "scopes": scopes}, expires_delta=expires_delta
    )


def _payload(token):
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part))


class TestTokenLifecycle:
    """Token creation and validation (NFR-SEC-001)."""

    def test_token_has_three_segments(self):
        assert len(_token(["read"]).split(".")) == 3

    def test_token_contains_subject_and_scope(self):
        payload = _payload(_token(["audit_read"]))
        assert payload["sub"] == "tester"
        assert payload["scope"] == ["audit_read"]

    def test_token_has_expiration_after_issue(self):
        payload = _payload(_token(["read"]))
        assert "exp" in payload and "iat" in payload
        assert payload["exp"] > payload["iat"]

    def test_valid_token_grants_access(self, plain_client):
        response = plain_client.get(
            "/api/protected", headers={"Authorization": f"Bearer {_token(['read'])}"}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Access granted"

    def test_expired_token_rejected(self, plain_client):
        expired = create_access_token({"sub": "tester", "role": "clinician", "scopes": []}, expires_delta=-1)
        response = plain_client.get("/api/protected", headers={"Authorization": f"Bearer {expired}"})
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_invalid_token_rejected(self, plain_client):
        response = plain_client.get(
            "/api/protected", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert response.status_code == 401

    def test_token_signed_with_other_secret_rejected(self, plain_client):
        forged = jose_jwt.encode(
            {"sub": "attacker", "exp": int(time.time()) + 600, "scope": ["audit_read"]},
            "some-other-secret",
            algorithm=JWT_ALGORITHM,
        )
        response = plain_client.get("/api/protected", headers={"Authorization": f"Bearer {forged}"})
        assert response.status_code == 401

    def test_missing_authorization_header_rejected(self, plain_client):
        response = plain_client.get("/api/protected")
        assert response.status_code == 401


class TestScopeEnforcement:
    """Scope-based access control (FR-DAT-006)."""

    def test_missing_scope_returns_403(self, plain_client):
        response = plain_client.get("/api/audit/", headers={"Authorization": f"Bearer {_token(['read'])}"})
        assert response.status_code == 403

    def test_unauthenticated_audit_access_returns_401(self, plain_client):
        response = plain_client.get("/api/audit/verify")
        assert response.status_code == 401


class TestAuthRoutes:
    """Login and refresh routes (stubbed authentication, no database)."""

    def test_login_returns_access_and_refresh_tokens(self, plain_client, monkeypatch):
        import api.routes.auth as auth_routes

        monkeypatch.setattr(
            auth_routes,
            "authenticate_user",
            lambda username, password: User(
                username=username, email=f"{username}@example.invalid", role="clinician", scopes=["audit_read"]
            ),
        )
        response = plain_client.post("/api/auth/login", json={"username": "clinician1", "password": "x"})

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 3600
        access_payload = jose_jwt.decode(body["access_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        refresh_payload = jose_jwt.decode(body["refresh_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert access_payload["sub"] == "clinician1"
        assert refresh_payload["type"] == "refresh"

    def test_login_rejects_unknown_user(self, plain_client, monkeypatch):
        import api.routes.auth as auth_routes

        monkeypatch.setattr(auth_routes, "authenticate_user", lambda username, password: None)
        response = plain_client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
        assert response.status_code == 401

    def test_refresh_rotates_tokens(self, plain_client):
        refresh_token = create_refresh_token({"sub": "tester", "role": "clinician", "scopes": ["read"]})
        response = plain_client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        body = response.json()
        assert body["refresh_token"] != refresh_token

    def test_refresh_rejects_access_token(self, plain_client):
        response = plain_client.post("/api/auth/refresh", json={"refresh_token": _token(["read"])})
        assert response.status_code == 401
