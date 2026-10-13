"""
OQ-16: State Serialization
Implements SRS OQ-16 - Verify state serialization and deserialization
"""

import pytest

# Skip all tests in this module if PyPulse is not available.
# PyPulse is compiled from source in the production Docker image (Dockerfile.pulse).
# See DEVELOPMENT_PLAN §7.1 and SRS §3.6.
pytest.importorskip("pulse")

from engine.pulse import PulseWorker, PatientConfig, run_oq16_test


class TestOQ16StateSerialization:
    """Test suite for OQ-16"""
    
    def test_serialize_state_on_pause(self):
        """State should serialize correctly when paused"""
        config = PatientConfig(
            patient_id="test-patient-3",
            age=55,
            weight_kg=80.0,
            height_cm=180.0,
            sex="male"
        )
        
        worker = PulseWorker(config)
        worker.initialize()
        
        # Step simulation to generate metrics
        metrics = worker.step(100)
        assert metrics is not None
        
        # Pause and serialize
        state = worker.pause()
        
        # Verify serialized state
        assert state.is_valid is True
        assert state.patient_id == "test-patient-3"
        assert state.timestamp > 0
        assert state.engine_state  # Should have serialized data
        assert len(state.metrics) > 0  # Should have metrics
    
    def test_deserialize_state_on_resume(self):
        """State should deserialize correctly when resuming"""
        config = PatientConfig(
            patient_id="test-patient-4",
            age=40,
            weight_kg=65.0,
            height_cm=165.0,
            sex="female"
        )
        
        worker = PulseWorker(config)
        worker.initialize()
        
        # Step and pause
        worker.step(50)
        state = worker.pause()
        
        # Resume
        result = worker.resume()
        assert result is True
        assert worker.state.value == "running"
    
    def test_stop_and_serialize(self):
        """State should serialize correctly when stopped"""
        config = PatientConfig(
            patient_id="test-patient-5",
            age=35,
            weight_kg=70.0,
            height_cm=170.0,
            sex="male"
        )
        
        worker = PulseWorker(config)
        worker.initialize()
        worker.step(200)
        
        state = worker.stop()
        
        assert state.is_valid is True
        assert state.patient_id == "test-patient-5"
        assert worker.state.value == "stopped"
    
    def test_metrics_extracted_correctly(self):
        """Extracted metrics should contain required fields"""
        config = PatientConfig(
            patient_id="test-patient-6",
            age=50,
            weight_kg=75.0,
            height_cm=175.0,
            sex="male"
        )
        
        worker = PulseWorker(config)
        worker.initialize()
        
        metrics = worker.step(10)
        
        # Verify metrics structure
        assert metrics is not None
        assert "heart_rate" in str(metrics)
        assert "blood_pressure_systolic" in str(metrics)
        assert "blood_pressure_diastolic" in str(metrics)
        assert "respiratory_rate" in str(metrics)
        assert "spo2" in str(metrics)
    
    def test_run_oq16_test(self):
        """Run the official OQ-16 test"""
        assert run_oq16_test(), "OQ-16 test failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
