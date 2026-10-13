# SPDX-License-Identifier: MIT
"""
FHIR Validation Routes
Implements SRS FR-DAT-007 - HL7 FHIR R4 schema validation with OperationOutcome error responses

Derived from the validation path of BioSync-Gateway middleware/api/routes/fhir.py. The
Gateway persistence endpoints (POST Observation and DeviceMetric writes) are not migrated.
Unsupported resource types are rejected with HTTP 422 instead of being accepted with a warning.
"""

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from api.auth import require_scope
from fhir_validator import ValidationError, to_operation_outcome, validate_resource

router = APIRouter()

SUPPORTED_RESOURCE_TYPES = ("Observation", "DeviceMetric", "Bundle")


@router.post("/validate")
async def validate_fhir_resource(
    resource: dict = Body(...),
    current_user=Depends(require_scope("fhir_read")),
):
    """
    Validate a FHIR R4 resource.

    Returns HTTP 200 with an informational OperationOutcome when the resource is valid.
    Returns HTTP 422 with an OperationOutcome listing each validation error otherwise.
    """
    resource_type = resource.get("resourceType")
    if resource_type not in SUPPORTED_RESOURCE_TYPES:
        outcome = to_operation_outcome([ValidationError(
            severity="error",
            code="not-supported",
            details=f"Resource type '{resource_type}' is not supported by this endpoint",
            location=["resourceType"],
        )])
        return JSONResponse(status_code=422, content=outcome, media_type="application/fhir+json")

    is_valid, outcome = validate_resource(resource)
    if not is_valid:
        return JSONResponse(status_code=422, content=outcome, media_type="application/fhir+json")

    return JSONResponse(
        status_code=200,
        content={
            "resourceType": "OperationOutcome",
            "id": "validation-success",
            "issue": [{
                "severity": "information",
                "code": "informational",
                "details": {"text": "Resource is valid"},
            }],
        },
        media_type="application/fhir+json",
    )
