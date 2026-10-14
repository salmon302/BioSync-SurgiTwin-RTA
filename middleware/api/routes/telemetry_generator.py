# SPDX-License-Identifier: MIT
"""
Telemetry Data Generator
Generates synthetic physiological signals for WebSocket streaming (visualization and demos).
Implements SRS FR-3.1.4 (telemetry channels with realistic waveforms, Gateway lineage).

Origin: BioSync-Gateway middleware/api/routes/telemetry_generator.py (adapted).
Adaptations: timestamps are timezone-aware UTC (datetime.utcnow is deprecated), and the
module-level singleton is removed. The simulator is opt-in (see routes/telemetry.py). Its
output is synthetic and is broadcast only. It is not persisted to the compliance tier.
"""

import math
import random
from datetime import datetime, timezone
from typing import Dict, List


class TelemetryGenerator:
    """
    Generates synthetic physiological telemetry data.

    Simulates:
        - Heart Rate (HR): 60-100 bpm with respiratory variation
        - Blood Pressure (Systolic/Diastolic): 120/80 mmHg with pulse wave
        - SpO2: 95-100% with slight variation
        - Flow Rate: Respiratory flow pattern

    Uses sinusoidal models with noise to simulate realistic physiological signs.
    """

    # Baseline values
    BASELINE_HR = 72.0
    BASELINE_BP_SYS = 120.0
    BASELINE_BP_DIA = 80.0
    BASELINE_SPO2 = 98.0
    BASELINE_FLOW = 0.0

    # Noise levels
    NOISE_HR = 2.0
    NOISE_BP = 3.0
    NOISE_SPO2 = 0.5
    NOISE_FLOW = 0.2

    # Alarm thresholds (SRS FR-3.1.5)
    ALARM_THRESHOLDS = {
        "hr": {"low": 40, "high": 160},
        "pressure": {"low": 60, "high": 140},
        "flow": {"low": 1, "high": 80},
        "spo2": {"low": 88, "high": 100}
    }

    def __init__(self, patient_id: str = "demo"):
        self.patient_id = patient_id
        self._time = 0.0
        self._hr_phase = 0.0  # Respiratory phase for HR variation

    def generate_timestep(self, dt: float = 0.1) -> Dict:
        """
        Generate one timestep of telemetry data.

        Args:
            dt: Time step in seconds (default 0.1s = 10Hz)

        Returns:
            Dict with telemetry data points
        """
        self._time += dt

        hr = self._generate_hr()
        bp_sys = self._generate_bp_systolic()
        self._generate_bp_diastolic()
        spo2 = self._generate_spo2()
        flow = self._generate_flow()

        alarms = self._check_alarms(hr, bp_sys, flow, spo2)

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        observations = [
            self._build_observation("hr", hr, timestamp),
            self._build_observation("pressure", bp_sys, timestamp),
            self._build_observation("flow", flow, timestamp),
            self._build_observation("spo2", spo2, timestamp)
        ]

        return {
            "patientId": self.patient_id,
            "timestamp": timestamp,
            "observations": observations,
            "alarms": alarms
        }

    def _generate_hr(self) -> float:
        """
        Generate heart rate with respiratory sinus arrhythmia.
        HR varies with breathing cycle (~0.2Hz).
        """
        respiratory_variation = 3.0 * math.sin(2 * math.pi * 0.2 * self._time)
        drift = 2.0 * math.sin(2 * math.pi * 0.01 * self._time)
        noise = random.gauss(0, self.NOISE_HR)
        hr = self.BASELINE_HR + respiratory_variation + drift + noise
        return round(hr, 1)

    def _generate_bp_systolic(self) -> float:
        """
        Generate systolic blood pressure with pulse wave.
        """
        pulse_wave = 5.0 * math.sin(2 * math.pi * 1.2 * self._time)
        variation = 4.0 * math.sin(2 * math.pi * 0.005 * self._time)
        noise = random.gauss(0, self.NOISE_BP)
        bp_sys = self.BASELINE_BP_SYS + pulse_wave + variation + noise
        return round(bp_sys, 1)

    def _generate_bp_diastolic(self) -> float:
        """
        Generate diastolic blood pressure (less variation than systolic).
        """
        variation = 2.0 * math.sin(2 * math.pi * 0.005 * self._time)
        noise = random.gauss(0, self.NOISE_BP * 0.5)
        bp_dia = self.BASELINE_BP_DIA + variation + noise
        return round(bp_dia, 1)

    def _generate_spo2(self) -> float:
        """
        Generate SpO2 with slight respiratory variation.
        """
        variation = 0.5 * math.sin(2 * math.pi * 0.2 * self._time)
        drift = 0.3 * math.sin(2 * math.pi * 0.002 * self._time)
        noise = random.gauss(0, self.NOISE_SPO2)
        spo2 = self.BASELINE_SPO2 + variation + drift + noise
        return round(max(85.0, min(100.0, spo2)), 1)  # Clamp to realistic range

    def _generate_flow(self) -> float:
        """
        Generate respiratory flow rate (sinusoidal pattern).
        Positive = inspiration, Negative = expiration.
        """
        flow = 2.0 * math.sin(2 * math.pi * 0.25 * self._time)
        noise = random.gauss(0, self.NOISE_FLOW)
        return round(flow + noise, 2)

    def _check_alarms(self, hr: float, bp_sys: float, flow: float, spo2: float) -> List[str]:
        """
        Check if any values are outside alarm thresholds.
        Implements SRS FR-3.1.5 - Alarm visualization.
        """
        alarms = []

        if hr < self.ALARM_THRESHOLDS["hr"]["low"] or hr > self.ALARM_THRESHOLDS["hr"]["high"]:
            alarms.append("hr")

        if bp_sys < self.ALARM_THRESHOLDS["pressure"]["low"] or bp_sys > self.ALARM_THRESHOLDS["pressure"]["high"]:
            alarms.append("pressure")

        if flow < self.ALARM_THRESHOLDS["flow"]["low"] or flow > self.ALARM_THRESHOLDS["flow"]["high"]:
            alarms.append("flow")

        if spo2 < self.ALARM_THRESHOLDS["spo2"]["low"] or spo2 > self.ALARM_THRESHOLDS["spo2"]["high"]:
            alarms.append("spo2")

        return alarms

    def _build_observation(self, channel: str, value: float, timestamp: str) -> Dict:
        """
        Build FHIR Observation resource for a single channel.
        """
        code_map = {
            "hr": {"code": "8867-4", "display": "Heart rate", "unit": "beats/min"},
            "pressure": {"code": "8310-5", "display": "Systolic blood pressure", "unit": "mmHg"},
            "flow": {"code": "85354-9", "display": "Respiratory flow", "unit": "L/min"},
            "spo2": {"code": "59408-5", "display": "Oxygen saturation", "unit": "%"}
        }

        code_info = code_map[channel]

        return {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": code_info["code"],
                        "display": code_info["display"]
                    }
                ]
            },
            "subject": {"reference": f"Patient/{self.patient_id}"},
            "effectiveDateTime": timestamp,
            "valueQuantity": {
                "value": value,
                "unit": code_info["unit"]
            }
        }
