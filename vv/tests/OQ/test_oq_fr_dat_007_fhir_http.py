# SPDX-License-Identifier: MIT
"""
OQ: FHIR R4 validation over HTTP, including OperationOutcome 422 paths (SRS FR-DAT-007)

Acceptance:
  * A valid Observation returns 200 with an informational OperationOutcome.
  * A structurally invalid Observation returns 422 with an OperationOutcome that names the field.
  * An unsupported resource type returns 422.
  * A caller without the fhir_read scope receives 403, and a caller without a token receives 401.

No database is required. The validation endpoint does not persist resources.
"""

import pytest
from fastapi.testclient import TestClient

from api.auth import create_access_token
from api.main import app

pytestmark = pytest.mark.oq

client = TestClient(app)


def _auth(scopes):
    token = create_access_token({"sub": "qa", "role": "qa_officer", "scopes": scopes}, expires_delta=1)
    return {"Authorization": f"Bearer {token}"}


VALID_OBSERVATION = {
    "resourceType": "Observation",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5"}]},
    "valueQuantity": {"value": 36.5, "unit": "Celsius", "system": "http://unitsofmeasure.org", "code": "Cel"},
}


def test_valid_observation_returns_200():
    response = client.post("/api/fhir/validate", json=VALID_OBSERVATION, headers=_auth(["fhir_read"]))
    assert response.status_code == 200
    body = response.json()
    assert body["resourceType"] == "OperationOutcome"
    assert body["issue"][0]["severity"] == "information"


def test_missing_value_quantity_returns_422_outcome():
    resource = {"resourceType": "Observation", "status": "final", "code": {"text": "x"}}
    response = client.post("/api/fhir/validate", json=resource, headers=_auth(["fhir_read"]))
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/fhir+json")
    body = response.json()
    assert body["resourceType"] == "OperationOutcome"
    assert any("valueQuantity" in issue["details"]["text"] for issue in body["issue"])


def test_wrong_value_type_returns_422_outcome():
    resource = {
        "resourceType": "Observation",
        "status": "final",
        "code": {"text": "x"},
        "valueQuantity": {"value": "not-a-number", "unit": "mmHg"},
    }
    response = client.post("/api/fhir/validate", json=resource, headers=_auth(["fhir_read"]))
    assert response.status_code == 422
    assert any("fhir.resources validation failed" in i["details"]["text"] for i in response.json()["issue"])


def test_unsupported_resource_type_returns_422():
    response = client.post(
        "/api/fhir/validate", json={"resourceType": "Patient", "name": "x"}, headers=_auth(["fhir_read"])
    )
    assert response.status_code == 422
    assert response.json()["issue"][0]["code"] == "not-supported"


def test_device_metric_without_operational_status_returns_422():
    resource = {
        "resourceType": "DeviceMetric",
        "type": {"coding": [{"code": "temperature"}]},
        "unit": {"coding": [{"code": "Cel"}]},
    }
    response = client.post("/api/fhir/validate", json=resource, headers=_auth(["fhir_read"]))
    assert response.status_code == 422


def test_missing_fhir_read_scope_returns_403():
    response = client.post("/api/fhir/validate", json=VALID_OBSERVATION, headers=_auth(["audit_read"]))
    assert response.status_code == 403


def test_missing_token_returns_401():
    response = client.post("/api/fhir/validate", json=VALID_OBSERVATION)
    assert response.status_code == 401
