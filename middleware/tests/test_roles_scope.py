# SPDX-License-Identifier: MIT
"""
RBAC scope check tests (no database). SRS FR-DAT-006 (role-based access control), task 1.9.

A route that depends on require_scope accepts a token only when the JWT scope claim names the
required scope. A missing token is rejected with 401. A token whose scope is missing, different,
or only a prefix of the required name is rejected with 403. The scope claim is read in the
space-delimited string form and in the list form.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.auth import _scopes_from_claim, create_access_token, require_scope


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/audit")
    async def audit(user=Depends(require_scope("audit_read"))):
        return {"user": user.username, "scopes": user.scopes}

    return app


@pytest.fixture
def client():
    return TestClient(_build_app())


def _bearer(claims: dict) -> dict:
    token = create_access_token({"sub": "tester", "role": "clinician", **claims}, expires_delta=1)
    return {"Authorization": f"Bearer {token}"}


class TestRequireScopeRoute:
    """A route guarded by require_scope (FR-DAT-006)."""

    def test_missing_token_rejected_with_401(self, client):
        response = client.get("/audit")
        assert response.status_code == 401

    def test_list_scope_claim_with_required_scope_accepted(self, client):
        response = client.get("/audit", headers=_bearer({"scope": ["audit_read"]}))
        assert response.status_code == 200
        assert response.json()["scopes"] == ["audit_read"]

    def test_space_delimited_scope_claim_with_required_scope_accepted(self, client):
        response = client.get("/audit", headers=_bearer({"scope": "fhir_read audit_read"}))
        assert response.status_code == 200
        assert response.json()["scopes"] == ["fhir_read", "audit_read"]

    def test_legacy_scopes_claim_accepted(self, client):
        response = client.get("/audit", headers=_bearer({"scopes": ["audit_read"]}))
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "claims",
        [
            {"scope": ["fhir_read"]},
            {"scope": "fhir_read telemetry_read"},
            {"scope": "audit_read_admin"},
            {"scope": "audit"},
            {"scope": []},
            {"scope": ""},
            {"scope": [1, None]},
            {"scope": 42},
            {},
        ],
        ids=[
            "list-wrong-scope",
            "string-wrong-scopes",
            "string-prefix-extension",
            "string-prefix-stem",
            "empty-list",
            "empty-string",
            "non-string-entries",
            "non-string-claim",
            "no-scope-claim",
        ],
    )
    def test_missing_or_wrong_scope_rejected_with_403(self, client, claims):
        response = client.get("/audit", headers=_bearer(claims))
        assert response.status_code == 403, response.text
        assert "audit_read" in response.json()["detail"]


class TestScopeClaimParsing:
    """_scopes_from_claim reads the scope claim in each supported form."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("audit_read", ["audit_read"]),
            ("fhir_read  audit_read", ["fhir_read", "audit_read"]),
            (["audit_read", 3, None], ["audit_read"]),
            ([], []),
            (None, []),
            (42, []),
            ({"audit_read": True}, []),
        ],
    )
    def test_parses_each_claim_form(self, value, expected):
        assert _scopes_from_claim(value) == expected
