"""
IQ-4: Pulse Engine Initialization
Implements SRS IQ-4 - Verify PyPulse import and engine initialization

NOTE: PyPulse (Kitware Pulse Physiology Engine) is a required dependency for
production. These tests skip when PyPulse is not installed (e.g., local dev
without the multi-stage Docker build). In CI with the production Docker image
(Dockerfile.pulse), PyPulse is compiled from source and these tests run.
"""

import pytest

# Skip all tests in this module if PyPulse is not available.
# PyPulse is compiled from source in the production Docker image (Dockerfile.pulse).
# See DEVELOPMENT_PLAN §7.1 and SRS §3.6.
pytest.importorskip("pulse")

from engine.pulse import PulseWorker, PatientConfig, run_iq4_test


class TestIQ4PulseEngineInit:
    """Test suite for IQ-4"""
    
    def test_engine_initialization(self):
        """Engine should initialize successfully"""
        config = PatientConfig(
            patient_id="test-patient-1",
            age=45,
            weight_kg=70.0,
            height_cm=175.0,
            sex="male"
        )
        
        worker = PulseWorker(config)
        result = worker.initialize()
        
        assert result is True, "Engine initialization should succeed"
        assert worker.state.value == "running", "Engine state should be 'running'"
        assert worker.engine is not None, "Engine should be initialized"
    
    def test_engine_with_different_patient_configs(self):
        """Engine should initialize with various patient configurations"""
        test_configs = [
            PatientConfig(patient_id="p1", age=25, weight_kg=60.0, height_cm=160.0, sex="female"),
            PatientConfig(patient_id="p2", age=65, weight_kg=85.0, height_cm=180.0, sex="male"),
            PatientConfig(patient_id="p3", age=50, weight_kg=70.0, height_cm=170.0, sex="other"),
        ]
        
        for config in test_configs:
            worker = PulseWorker(config)
            assert worker.initialize() is True, f"Failed to init for {config.patient_id}"
            assert worker.state.value == "running"
    
    def test_engine_state_transitions(self):
        """Engine should transition from initializing to running"""
        config = PatientConfig(
            patient_id="test-patient-2",
            age=30,
            weight_kg=75.0,
            height_cm=175.0,
            sex="male"
        )
        
        worker = PulseWorker(config)
        
        # Initial state
        assert worker.state.value == "initializing"
        
        # After initialization
        worker.initialize()
        assert worker.state.value == "running"
    
    def test_run_iq4_test(self):
        """Run the official IQ-4 test"""
        assert run_iq4_test(), "IQ-4 test failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
