"""
FHIR Validation Layer
Implements SRS FR-DAT-007 - HL7 FHIR R4 Observation and DeviceMetric validation

Origin: BioSync-Gateway middleware/fhir_validator.py (adapted). Deep validation uses the
fhir.resources Pydantic v2 models (model_validate). Failures are returned as OperationOutcome.
"""

from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
import json


class ResourceType(Enum):
    """Supported FHIR resource types"""
    OBSERVATION = "Observation"
    DEVICE_METRIC = "DeviceMetric"
    DEVICE = "Device"
    BUNDLE = "Bundle"
    OPERATION_OUTCOME = "OperationOutcome"


class ValidationError:
    """Represents a FHIR validation error"""
    
    def __init__(
        self,
        severity: str,
        code: str,
        details: str,
        location: Optional[List[str]] = None
    ):
        """
        Initialize validation error.
        
        Args:
            severity: "fatal" | "error" | "warning" | "information"
            code: Error code (e.g., "required", "structure", "value")
            details: Human-readable error description
            location: List of FHIRPath expressions pointing to error location
        """
        self.severity = severity
        self.code = code
        self.details = details
        self.location = location or []
    
    def to_operation_outcome(self) -> Dict:
        """
        Convert to FHIR OperationOutcome issue format.
        
        Returns:
            Dict matching FHIR OperationOutcome.issue structure
            
        Implements:
            SRS FR-3.7.4 - OperationOutcome error responses
        """
        return {
            "severity": self.severity,
            "code": self.code,
            "details": {
                "text": self.details
            },
            "location": self.location
        }


class FHIRValidator:
    """
    FHIR resource validator using fhir.resources Pydantic models.
    
    Implements:
        SRS FR-3.7.1 - FHIR validation using fhir.resources
        SRS FR-3.7.2 - DeviceMetric CRUD validation
        SRS FR-3.7.3 - Observation CRUD validation
        SRS FR-3.7.4 - OperationOutcome error responses
        SRS FR-3.7.5 - Bundle (transaction/batch) support
    """
    
    def __init__(self):
        """Initialize validator"""
        # fhir.resources is a required dependency (SRS FR-DAT-007). Module names are the
        # lowercase R4 class names (fhir.resources 7.x and 8.x). A missing module fails loudly
        # instead of silently skipping deep validation.
        try:
            from fhir.resources.observation import Observation
            from fhir.resources.devicemetric import DeviceMetric
            from fhir.resources.device import Device
            from fhir.resources.bundle import Bundle
            from fhir.resources.operationoutcome import OperationOutcome
        except ImportError as exc:
            raise RuntimeError(
                "fhir.resources is required for FHIR R4 validation (SRS FR-DAT-007)"
            ) from exc

        self.Observation = Observation
        self.DeviceMetric = DeviceMetric
        self.Device = Device
        self.Bundle = Bundle
        self.OperationOutcome = OperationOutcome
        self.has_fhir_resources = True
    
    def validate_observation(self, resource: Dict) -> Tuple[bool, List[ValidationError]]:
        """
        Validate FHIR Observation resource.
        
        Args:
            resource: Observation resource as dict
        
        Returns:
            Tuple of (is_valid, list_of_errors)
            
        Implements:
            SRS FR-3.7.3 - Observation validation
            SRS OQ-10 - Valid Observation accepted
            SRS OQ-11 - Missing valueQuantity rejected
        """
        errors = []
        
        # Check resource type
        if resource.get("resourceType") != "Observation":
            errors.append(ValidationError(
                severity="fatal",
                code="structure",
                details="Resource must be of type 'Observation'",
                location=["resourceType"]
            ))
            return False, errors
        
        # Check required fields (OQ-11)
        if "valueQuantity" not in resource:
            errors.append(ValidationError(
                severity="error",
                code="required",
                details="Observation must have 'valueQuantity' field",
                location=["valueQuantity"]
            ))
        
        if "code" not in resource:
            errors.append(ValidationError(
                severity="error",
                code="required",
                details="Observation must have 'code' field",
                location=["code"]
            ))
        
        # Validate valueQuantity structure if present
        if "valueQuantity" in resource:
            vq = resource["valueQuantity"]
            if "value" not in vq:
                errors.append(ValidationError(
                    severity="error",
                    code="required",
                    details="valueQuantity must have 'value' field",
                    location=["valueQuantity", "value"]
                ))
            if "unit" not in vq and "code" not in vq:
                errors.append(ValidationError(
                    severity="warning",
                    code="required",
                    details="valueQuantity should have 'unit' or 'code' field",
                    location=["valueQuantity", "unit"]
                ))
        
        # Use fhir.resources for deep validation if available
        if self.has_fhir_resources:
            try:
                obs = self.Observation.model_validate(resource)
                # Additional validation passed
            except Exception as e:
                errors.append(ValidationError(
                    severity="error",
                    code="structure",
                    details=f"fhir.resources validation failed: {str(e)}",
                    location=[""]
                ))
        
        return len(errors) == 0, errors
    
    def validate_device_metric(self, resource: Dict) -> Tuple[bool, List[ValidationError]]:
        """
        Validate FHIR DeviceMetric resource.
        
        Args:
            resource: DeviceMetric resource as dict
        
        Returns:
            Tuple of (is_valid, list_of_errors)
            
        Implements:
            SRS FR-3.7.2 - DeviceMetric validation
            SRS OQ-12 - Missing operationalStatus rejected
        """
        errors = []
        
        # Check resource type
        if resource.get("resourceType") != "DeviceMetric":
            errors.append(ValidationError(
                severity="fatal",
                code="structure",
                details="Resource must be of type 'DeviceMetric'",
                location=["resourceType"]
            ))
            return False, errors
        
        # Check required fields (OQ-12)
        if "operationalStatus" not in resource:
            errors.append(ValidationError(
                severity="error",
                code="required",
                details="DeviceMetric must have 'operationalStatus' field",
                location=["operationalStatus"]
            ))
        
        if "type" not in resource:
            errors.append(ValidationError(
                severity="error",
                code="required",
                details="DeviceMetric must have 'type' field",
                location=["type"]
            ))
        
        if "unit" not in resource:
            errors.append(ValidationError(
                severity="error",
                code="required",
                details="DeviceMetric must have 'unit' field",
                location=["unit"]
            ))
        
        # Use fhir.resources for deep validation if available
        if self.has_fhir_resources:
            try:
                dm = self.DeviceMetric.model_validate(resource)
                # Additional validation passed
            except Exception as e:
                errors.append(ValidationError(
                    severity="error",
                    code="structure",
                    details=f"fhir.resources validation failed: {str(e)}",
                    location=[""]
                ))
        
        return len(errors) == 0, errors
    
    def validate_bundle(self, resource: Dict) -> Tuple[bool, List[ValidationError]]:
        """
        Validate FHIR Bundle resource.
        
        Args:
            resource: Bundle resource as dict
        
        Returns:
            Tuple of (is_valid, list_of_errors)
            
        Implements:
            SRS FR-3.7.5 - Bundle validation
        """
        errors = []
        
        # Check resource type
        if resource.get("resourceType") != "Bundle":
            errors.append(ValidationError(
                severity="fatal",
                code="structure",
                details="Resource must be of type 'Bundle'",
                location=["resourceType"]
            ))
            return False, errors
        
        # Check bundle type
        if "type" not in resource:
            errors.append(ValidationError(
                severity="error",
                code="required",
                details="Bundle must have 'type' field",
                location=["type"]
            ))
        
        # Validate each entry
        if "entry" in resource:
            for i, entry in enumerate(resource["entry"]):
                if "resource" not in entry:
                    errors.append(ValidationError(
                        severity="error",
                        code="required",
                        details=f"Bundle.entry[{i}] must have 'resource' field",
                        location=["entry", str(i), "resource"]
                    ))
                    continue
                
                # Validate nested resource
                nested_resource = entry["resource"]
                resource_type = nested_resource.get("resourceType")
                
                if resource_type == "Observation":
                    is_valid, resource_errors = self.validate_observation(nested_resource)
                    for err in resource_errors:
                        err.location = [f"entry[{i}]", "resource"] + err.location
                        errors.append(err)
                elif resource_type == "DeviceMetric":
                    is_valid, resource_errors = self.validate_device_metric(nested_resource)
                    for err in resource_errors:
                        err.location = [f"entry[{i}]", "resource"] + err.location
                        errors.append(err)
        
        return len(errors) == 0, errors
    
    def create_operation_outcome(self, errors: List[ValidationError]) -> Dict:
        """
        Create OperationOutcome resource from validation errors.
        
        Args:
            errors: List of ValidationError objects
        
        Returns:
            FHIR OperationOutcome resource
            
        Implements:
            SRS FR-3.7.4 - OperationOutcome error responses
        """
        issues = [err.to_operation_outcome() for err in errors]
        
        outcome = {
            "resourceType": "OperationOutcome",
            "id": "validation-result",
            "issue": issues
        }
        
        return outcome


def to_operation_outcome(errors: List[ValidationError]) -> Dict:
    """
    Create OperationOutcome resource from validation errors.
    
    Args:
        errors: List of ValidationError objects
    
    Returns:
        FHIR OperationOutcome resource with application/fhir+json content type
        
    Implements:
        SRS FR-3.7.4 - OperationOutcome error responses
    """
    issues = [err.to_operation_outcome() for err in errors]
    
    outcome = {
        "resourceType": "OperationOutcome",
        "id": "validation-result",
        "issue": issues
    }
    
    return outcome


# Convenience functions for API endpoints
def validate_resource(resource: Dict) -> Tuple[bool, Optional[Dict]]:
    """
    Validate any FHIR resource.
    
    Args:
        resource: FHIR resource as dict
    
    Returns:
        Tuple of (is_valid, operation_outcome_or_none)
    """
    validator = FHIRValidator()
    resource_type = resource.get("resourceType")
    
    if resource_type == "Observation":
        is_valid, errors = validator.validate_observation(resource)
    elif resource_type == "DeviceMetric":
        is_valid, errors = validator.validate_device_metric(resource)
    elif resource_type == "Bundle":
        is_valid, errors = validator.validate_bundle(resource)
    else:
        # Unknown resource type - accept but warn
        errors = [ValidationError(
            severity="warning",
            code="not-supported",
            details=f"Resource type '{resource_type}' validation not implemented"
        )]
        is_valid = True
    
    if not is_valid:
        return False, validator.create_operation_outcome(errors)
    else:
        return True, None


# Test functions for OQ-10, OQ-11, OQ-12
def run_oq10_test() -> bool:
    """
    OQ-10: Valid Observation accepted
    
    Returns:
        True if valid Observation passes validation
    """
    valid_observation = {
        "resourceType": "Observation",
        "id": "example-obs",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "8310-5",
                "display": "Body temperature"
            }]
        },
        "valueQuantity": {
            "value": 36.5,
            "unit": "Celsius",
            "system": "http://unitsofmeasure.org",
            "code": "Cel"
        }
    }
    
    is_valid, _ = validate_resource(valid_observation)
    return is_valid


def run_oq11_test() -> bool:
    """
    OQ-11: Missing valueQuantity rejected
    
    Returns:
        True if Observation without valueQuantity is rejected
    """
    invalid_observation = {
        "resourceType": "Observation",
        "id": "example-obs-no-value",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "8310-5"
            }]
        }
        # Missing valueQuantity
    }
    
    is_valid, outcome = validate_resource(invalid_observation)
    return not is_valid and outcome is not None


def run_oq12_test() -> bool:
    """
    OQ-12: Missing operationalStatus rejected
    
    Returns:
        True if DeviceMetric without operationalStatus is rejected
    """
    invalid_device_metric = {
        "resourceType": "DeviceMetric",
        "id": "example-dm-no-status",
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/metric-type",
                "code": "temperature"
            }]
        },
        "unit": {
            "coding": [{
                "system": "http://unitsofmeasure.org",
                "code": "Cel"
            }]
        }
        # Missing operationalStatus
    }
    
    is_valid, outcome = validate_resource(invalid_device_metric)
    return not is_valid and outcome is not None


if __name__ == "__main__":
    # Self-test
    print("Running OQ-10, OQ-11, OQ-12 tests...")
    
    print(f"OQ-10 (valid Observation): {'PASS' if run_oq10_test() else 'FAIL'}")
    print(f"OQ-11 (missing valueQuantity): {'PASS' if run_oq11_test() else 'FAIL'}")
    print(f"OQ-12 (missing operationalStatus): {'PASS' if run_oq12_test() else 'FAIL'}")
    
    # Example validation
    print("\nExample: Validating Observation...")
    test_obs = {
        "resourceType": "Observation",
        "valueQuantity": {"value": 98.6, "unit": "Fahrenheit"}
    }
    is_valid, outcome = validate_resource(test_obs)
    print(f"Valid: {is_valid}")
    if not is_valid:
        print(f"Errors: {json.dumps(outcome, indent=2)}")
