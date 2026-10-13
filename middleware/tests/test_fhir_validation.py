# SPDX-License-Identifier: MIT
"""
FHIR validation error detail tests (no database).

Origin: BioSync-Gateway tests/unit/test_o14_fhir_validation_errors.py (adapted: import paths,
Pydantic v2 validation, and an assertion that deep fhir.resources validation is active).

Implements SRS FR-DAT-007 (validation) and the OperationOutcome error path.
"""

from fhir_validator import FHIRValidator, ValidationError, validate_resource


def test_deep_validation_is_active():
    assert FHIRValidator().has_fhir_resources is True


def test_wrong_value_type_is_rejected_by_fhir_resources():
    """Deep validation (fhir.resources, Pydantic v2) rejects a non-numeric valueQuantity.value."""
    is_valid, outcome = validate_resource({
        "resourceType": "Observation",
        "status": "final",
        "code": {"text": "test"},
        "valueQuantity": {"value": "not-a-number", "unit": "mmHg"},
    })
    assert is_valid is False
    assert outcome["resourceType"] == "OperationOutcome"
    assert any("fhir.resources validation failed" in i["details"]["text"] for i in outcome["issue"])


def test_missing_valueQuantity_error_detail():
    validator = FHIRValidator()
    is_valid, errors = validator.validate_observation({
        "resourceType": "Observation",
        "status": "final",
        "code": {"text": "test"},
    })
    assert is_valid is False
    assert any("valueQuantity" in e.details.lower() or "valueQuantity" in str(e.location) for e in errors)


def test_missing_code_error_detail():
    validator = FHIRValidator()
    is_valid, errors = validator.validate_observation({
        "resourceType": "Observation",
        "status": "final",
        "valueQuantity": {"value": 1, "unit": "test"},
    })
    assert is_valid is False
    assert any("code" in e.details.lower() or "code" in str(e.location) for e in errors)


def test_wrong_resource_type_error():
    validator = FHIRValidator()
    is_valid, errors = validator.validate_observation({"resourceType": "Patient", "name": "John Doe"})
    assert is_valid is False
    assert any(e.code == "structure" or "Observation" in e.details for e in errors)


def test_empty_valueQuantity_error():
    validator = FHIRValidator()
    is_valid, errors = validator.validate_observation({
        "resourceType": "Observation",
        "code": {"text": "test"},
        "valueQuantity": {},
    })
    assert is_valid is False
    assert any("value" in e.details.lower() or "required" in e.code for e in errors)


def test_valid_observation_no_errors():
    validator = FHIRValidator()
    is_valid, errors = validator.validate_observation({
        "resourceType": "Observation",
        "status": "final",
        "code": {"text": "Body temperature"},
        "valueQuantity": {"value": 98.6, "unit": "Fahrenheit"},
    })
    assert is_valid is True
    assert errors == []


def test_operation_outcome_format():
    error = ValidationError(
        severity="error",
        code="required",
        details="valueQuantity is required",
        location=["Observation", "valueQuantity"],
    )
    outcome = error.to_operation_outcome()
    assert outcome["severity"] == "error"
    assert outcome["code"] == "required"
    assert outcome["details"]["text"] == "valueQuantity is required"
    assert outcome["location"] == ["Observation", "valueQuantity"]


def test_device_metric_missing_operational_status():
    validator = FHIRValidator()
    is_valid, errors = validator.validate_device_metric({
        "resourceType": "DeviceMetric",
        "type": {"coding": [{"code": "temperature"}]},
        "unit": {"coding": [{"code": "Cel"}]},
    })
    assert is_valid is False
    assert any("operationalStatus" in e.details or "operationalStatus" in str(e.location) for e in errors)


def test_multiple_errors_returned():
    validator = FHIRValidator()
    is_valid, errors = validator.validate_observation({"resourceType": "Observation"})
    assert is_valid is False
    assert len(errors) >= 2
