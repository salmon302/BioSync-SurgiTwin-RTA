# SPDX-License-Identifier: MIT
"""
Exact scope membership on the WebSocket and HTTP scope checks (finding F-3; SRS FR-DAT-006, NFR-SEC-001).

A scope check asks whether the required scope name is one of the names in the JWT scope claim. A substring
test is an RBAC bypass: telemetry_read_only satisfied telemetry_read, and superadmin satisfied admin. The
claim is parsed by api.auth._scopes_from_claim in the space-delimited string form and in the list form.
These tests need no database. The relay sink is a fake that accepts every batch.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.auth import create_access_token
from api.main import create_app


class NullSink:
    """Relay sink fake. Accepts every batch and persists nothing."""

    async def write_batch(self, batch):
        return None


def _token(claims: dict) -> str:
    return create_access_token({"sub": "scope-tester", "role": "clinician", **claims}, expires_delta=1)


@pytest.fixture
def client():
    with TestClient(create_app(relay_sink=NullSink())) as test_client:
        yield test_client


def _connect_close_code(client: TestClient, claims: dict):
    """Return the close code when the WebSocket is refused, or None when it is accepted and answers a ping."""
    try:
        with client.websocket_connect(f"/api/telemetry/stream?token={_token(claims)}") as ws:
            ws.send_json({"type": "ping"})
            assert ws.receive_json()["type"] == "pong"
    except WebSocketDisconnect as exc:
        return exc.code
    return None


class TestWebSocketReadScope:
    """The stream is readable with telemetry_read or admin, and only as an exact scope name."""

    @pytest.mark.parametrize(
        "claims",
        [
            {"scope": "telemetry_read"},
            {"scope": ["telemetry_read"]},
            {"scope": "telemetry_read telemetry_write"},
            {"scope": "fhir_read\ttelemetry_read"},
            {"scopes": "telemetry_read"},
            {"scope": "admin"},
        ],
        ids=["string", "list", "space-delimited", "tab-delimited", "legacy-scopes-claim", "admin"],
    )
    def test_exact_read_scope_is_accepted(self, client, claims):
        assert _connect_close_code(client, claims) is None

    @pytest.mark.parametrize(
        "claims",
        [
            {"scope": "telemetry_read_only"},
            {"scope": ["telemetry_read_only"]},
            {"scope": "superadmin"},
            {"scope": "telemetry"},
            {"scope": "read_telemetry"},
            {"scope": "telemetry_write"},
            {"scope": "telemetry_write_only"},
            {"scope": "telemetry_read_only telemetry_write_only"},
            {"scope": ""},
            {"scope": 42},
            {},
        ],
        ids=[
            "read-prefix-extension-string",
            "read-prefix-extension-list",
            "admin-substring",
            "stem-only",
            "stem-suffix",
            "write-without-read",
            "write-prefix-extension",
            "both-prefix-extensions",
            "empty-string",
            "non-string-claim",
            "no-scope-claim",
        ],
    )
    def test_substring_or_missing_scope_is_refused_with_4403(self, client, claims):
        assert _connect_close_code(client, claims) == 4403


class TestWebSocketPublishScope:
    """Publishing a telemetry frame requires telemetry_write or admin as an exact scope name."""

    def _publish_reply(self, client, claims):
        with client.websocket_connect(f"/api/telemetry/stream?token={_token(claims)}") as ws:
            ws.send_json({"type": "telemetry", "payload": None})
            return ws.receive_json()

    @pytest.mark.parametrize(
        "claims",
        [
            {"scope": "telemetry_read telemetry_write"},
            {"scope": "telemetry_read admin"},
        ],
        ids=["telemetry_write", "admin"],
    )
    def test_exact_write_scope_reaches_payload_validation(self, client, claims):
        reply = self._publish_reply(client, claims)
        assert reply["payload"]["code"] == "invalid_payload"

    @pytest.mark.parametrize(
        "claims",
        [
            {"scope": "telemetry_read telemetry_write_only"},
            {"scope": "telemetry_read superadmin"},
        ],
        ids=["write-prefix-extension", "admin-substring"],
    )
    def test_substring_write_scope_is_refused_with_forbidden(self, client, claims):
        reply = self._publish_reply(client, claims)
        assert reply["type"] == "error"
        assert reply["payload"]["code"] == "forbidden"


class TestHttpTelemetryScope:
    """The HTTP telemetry routes use require_scope, which is exact list membership."""

    def test_stream_info_with_exact_read_scope_is_accepted(self, client):
        response = client.get("/api/telemetry/stream/info", headers={"Authorization": f"Bearer {_token({'scope': 'telemetry_read'})}"})
        assert response.status_code == 200

    @pytest.mark.parametrize("scope", ["telemetry_read_only", "superadmin", "telemetry_write"])
    def test_stream_info_with_substring_scope_is_refused(self, client, scope):
        response = client.get("/api/telemetry/stream/info", headers={"Authorization": f"Bearer {_token({'scope': scope})}"})
        assert response.status_code == 403

    def test_ingest_with_write_prefix_extension_is_refused(self, client):
        response = client.post(
            "/api/telemetry/ingest",
            json={"patientId": "SYN-SCOPE-001"},
            headers={"Authorization": f"Bearer {_token({'scope': 'telemetry_write_only'})}"},
        )
        assert response.status_code == 403
