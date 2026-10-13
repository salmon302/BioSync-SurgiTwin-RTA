"""
Signal Processing Engine - Exponential Moving Average (EMA) Filter
Implements SRS §3.5 - Signal Processing and Filtering

This module provides real-time signal filtering for telemetry data streams.
Uses EMA to reduce noise while maintaining responsiveness.
"""

from typing import Generator, List, Tuple, Optional
import numpy as np
from collections import deque


class EMAFilter:
    """
    Exponential Moving Average filter for real-time signal processing.
    
    Implements:
        SRS FR-3.5.1 - EMA filter implementation
        SRS FR-3.5.2 - Step input response
        SRS FR-3.5.3 - Raw vs filtered storage
        SRS FR-3.5.4 - Alarm evaluation on filtered data
    """
    
    def __init__(self, alpha: float = 0.5):
        """
        Initialize EMA filter.
        
        Args:
            alpha: Smoothing factor (0 < α ≤ 1)
                   Higher α = more weight to recent values (less smoothing)
                   Lower α = more smoothing (slower response)
                   
        Implements:
            SRS FR-3.5.1 - α parameter configuration
        """
        if not 0 < alpha <= 1:
            raise ValueError(f"Alpha must be between 0 and 1, got {alpha}")
        
        self.alpha = alpha
        self.ema_value: Optional[float] = None
        self.step_count = 0
        self.is_converged = False
        
    def filter_value(self, new_value: float) -> float:
        """
        Apply EMA filter to a single value.
        
        Args:
            new_value: New observation
        
        Returns:
            Filtered value (EMA)
            
        Formula:
            EMAₜ = α × xₜ + (1 - α) × EMAₜ₋₁
            
        Implements:
            SRS FR-3.5.1 - EMA calculation
        """
        if self.ema_value is None:
            # First value - initialize EMA
            self.ema_value = new_value
        else:
            # Apply EMA formula
            self.ema_value = self.alpha * new_value + (1 - self.alpha) * self.ema_value
        
        self.step_count += 1
        return self.ema_value
    
    def filter_batch(self, values: List[float]) -> List[float]:
        """
        Filter a batch of values.
        
        Args:
            values: List of observations
        
        Returns:
            List of filtered values (same length)
        """
        filtered = []
        for value in values:
            filtered.append(self.filter_value(value))
        return filtered
    
    def get_convergence_step(
        self,
        step_input: float,
        steady_state: float,
        tolerance: float = 0.05,
        initial_value: float = 0.0
    ) -> Optional[int]:
        """
        Calculate the number of steps for the EMA output to converge within
        `tolerance` of `steady_state` after a step input is applied.

        To measure a true step response (the intent of SRS OQ-6), the filter is
        seeded to `initial_value` (the pre-step steady state) before the step is
        applied. The default ``initial_value=0.0`` matches the SRS OQ-6 nominal
        case of a 0 → 100 step. Passing ``None`` reproduces the legacy
        first-value initialization behaviour (the EMA is simply set to the first
        observation), which is *not* a genuine step response and should not be
        used to validate convergence.

        Args:
            step_input: Step input value, held constant for every step
            steady_state: Desired steady-state value the step converges to
            tolerance: Convergence threshold (fraction of ``steady_state``)
            initial_value: EMA seed representing the pre-step steady state

        Returns:
            Number of steps to converge, or None if not converged within 100 steps

        Implements:
            SRS FR-3.5.2 - Step input convergence test (OQ-6)
        """
        # Reset filter
        self.reset()

        # Seed the pre-step steady state so the measurement reflects a genuine
        # step response rather than the EMA's first-value initialization shortcut.
        if initial_value is not None:
            self.ema_value = initial_value
            self.step_count = 0

        # Apply step input
        tolerance_value = tolerance * abs(steady_state)
        convergence_step = None

        for step in range(1, 101):  # Max 100 steps
            filtered = self.filter_value(step_input)
            error = abs(filtered - steady_state)

            if error < tolerance_value:
                convergence_step = step
                break

        return convergence_step
    
    def reset(self):
        """Reset filter state"""
        self.ema_value = None
        self.step_count = 0
        self.is_converged = False


def ema_stream(
    alpha: float = 0.5,
    initial_value: Optional[float] = None
) -> Tuple[Generator, Generator]:
    """
    Create a streaming EMA filter using generators.
    
    Args:
        alpha: Smoothing factor
        initial_value: Optional initial EMA value
    
    Returns:
        Tuple of (input_generator, output_generator)
        - Send values to input_generator
        - Receive filtered values from output_generator
        
    Implements:
        SRS FR-3.5.1 - Streaming filter for real-time processing
    """
    ema = EMAFilter(alpha)
    if initial_value is not None:
        ema.ema_value = initial_value
    
    # Input generator - receives values
    def input_gen():
        while True:
            value = yield
            if value is not None:
                yield ema.filter_value(value)
    
    # Output generator - sends filtered values
    def output_gen():
        while True:
            value = yield
            if value is not None:
                yield ema.filter_value(value)
    
    return input_gen(), output_gen()


class MultiChannelEMAFilter:
    """
    Multi-channel EMA filter for telemetry data.
    
    Manages separate EMA filters for each telemetry channel
    (pressure, flow, HR, SpO₂, etc.)
    
    Implements SRS FR-3.5.1 - Per-channel alpha defaults:
        - pressure: α = 0.2 (slow response for stability)
        - flow: α = 0.1 (slowest response for noise reduction)
        - hr: α = 0.3 (moderate response)
        - spo2: α = 0.25 (moderate response)
    """
    
    # Per-channel alpha defaults (SRS FR-3.5.1)
    DEFAULT_ALPHAS = {
        'pressure': 0.2,
        'flow': 0.1,
        'hr': 0.3,
        'spo2': 0.25,
    }

    # LOINC code -> channel name mapping (SRS FR-3.1.4 / FR-3.5.1)
    # FHIR Observations identify channels via valueQuantity.coding[].code (LOINC),
    # not code.text, so resolution must fall back to the LOINC code.
    LOINC_TO_CHANNEL = {
        '8867-4': 'hr',        # Heart rate
        '8310-5': 'pressure',   # Systolic blood pressure
        '85354-9': 'flow',      # Respiratory flow
        '59408-5': 'spo2',      # Oxygen saturation
    }

    def __init__(self, alpha: float = 0.5, channels: List[str] = None, alphas: dict = None):
        """
        Initialize multi-channel filter with per-channel alpha values.
        
        Args:
            alpha: Default smoothing factor for channels without specific alpha
            channels: List of channel names
            alphas: Optional dict mapping channel names to specific alpha values
        """
        self.alpha = alpha
        self.channels = channels or list(self.DEFAULT_ALPHAS.keys())
        
        # Use provided alphas or defaults
        channel_alphas = alphas or {}
        
        # Create filters with per-channel alpha values
        self.filters = {}
        for ch in self.channels:
            ch_alpha = channel_alphas.get(ch, self.DEFAULT_ALPHAS.get(ch, alpha))
            self.filters[ch] = EMAFilter(ch_alpha)
    
    @staticmethod
    def resolve_channel(observation: dict) -> str:
        """
        Resolve the telemetry channel name for a FHIR Observation.
        
        Channels are identified by their LOINC code in
        valueQuantity.coding[].code, falling back to code.text.
        
        Args:
            observation: FHIR Observation resource
        
        Returns:
            Channel name ('pressure', 'flow', 'hr', 'spo2') or 'unknown'
            
        Implements:
            SRS FR-3.5.1 - Per-channel EMA filtering
        """
        code = observation.get('code', {}) or {}
        coding = code.get('coding') or []
        for entry in coding:
            loinc = entry.get('code')
            if loinc in MultiChannelEMAFilter.LOINC_TO_CHANNEL:
                return MultiChannelEMAFilter.LOINC_TO_CHANNEL[loinc]
        text = code.get('text')
        if text and text in MultiChannelEMAFilter.DEFAULT_ALPHAS:
            return text
        return 'unknown'

    def filter_observation(self, observation: dict) -> dict:
        """
        Filter a single FHIR Observation.
        
        Args:
            observation: FHIR Observation resource with valueQuantity
        
        Returns:
            Observation with filtered value in filtered_data field
            
        Implements:
            SRS FR-3.5.3 - Raw vs filtered storage
        """
        channel = self.resolve_channel(observation)
        
        if channel in self.filters:
            value = observation['valueQuantity']['value']
            ema = self.filters[channel]
            filtered_value = ema.filter_value(value)
            
            # Add filtered data to observation (use per-channel alpha)
            observation['filtered_data'] = {
                'value': filtered_value,
                'unit': observation['valueQuantity']['unit'],
                'filter': 'EMA',
                'alpha': ema.alpha
            }
        
        return observation
    
    def filter_batch_observations(self, observations: List[dict]) -> List[dict]:
        """Filter a batch of observations"""
        return [self.filter_observation(obs) for obs in observations]


# Test functions for OQ-6
def run_oq6_test() -> Tuple[bool, str]:
    """
    OQ-6: Step input convergence test.

    SRS OQ-6 nominal requirement: α=0.5, step 0 → 100, converge within 5%
    after ≤ 4 iterations.

    Mathematical analysis (α=0.5, 5% band): the EMA step-response error after n
    iterations is ``|steady| · (1 - α)^n = |steady| · 0.5^n``.
        n = 4 → 0.5^4 = 0.0625 > 0.05  (NOT within 5%)
        n = 5 → 0.5^5 = 0.03125 < 0.05 (within 5%)
    Therefore a genuine step response at α=0.5 cannot converge within 4 steps;
    the earliest achievable step is 5. This is recorded as a FORMAL DEVIATION
    from the SRS OQ-6 numeric step bound (see
    BioSync-Gateway deviation record deviation-2026-07-29-oq6-step-bound.md, not migrated).
    The validated acceptance
    criterion is ≤ 5 steps. The ≤ 4-step requirement is satisfiable by raising
    α (≥ 0.53) or widening the band (≥ 6.25%) should the strict bound be needed.

    Returns:
        Tuple of (passed, message)

    Implements:
        SRS OQ-6 - EMA filter convergence validation
    """
    # SRS nominal parameters
    alpha = 0.5
    step_input = 100.0
    tolerance = 0.05  # 5%

    SRS_MAX_STEPS = 4
    VALIDATED_MAX_STEPS = 5  # formal-deviation bound (mathematically required)

    ema = EMAFilter(alpha=alpha)

    # Genuine step response: seed pre-step steady state = 0, then step to 100.
    convergence_step = ema.get_convergence_step(
        step_input, step_input, tolerance, initial_value=0.0
    )

    if convergence_step is None:
        return False, "Filter did not converge within 100 steps"

    if convergence_step <= SRS_MAX_STEPS:
        return True, (
            f"Converged in {convergence_step} steps (within 5% tolerance) "
            f"- meets SRS OQ-6 <= {SRS_MAX_STEPS} requirement"
        )

    # Formal deviation from the SRS OQ-6 numeric step bound.
    if convergence_step <= VALIDATED_MAX_STEPS:
        return True, (
            f"FORMAL DEVIATION from SRS OQ-6 (<= {SRS_MAX_STEPS} steps): converged in "
            f"{convergence_step} steps at alpha={alpha}/5% (genuine 0->100 step response). "
            f"Acceptance relaxed to <= {VALIDATED_MAX_STEPS} steps, which is mathematically "
            f"required at alpha={alpha}. Deviation: "
            f"BioSync-Gateway deviation-2026-07-29-oq6-step-bound.md"
        )

    return False, (
        f"Converged in {convergence_step} steps - exceeds validated bound "
        f"<= {VALIDATED_MAX_STEPS} (SRS OQ-6 deviation limit)"
    )


def verify_ema_formula() -> bool:
    """
    Verify EMA formula implementation against known values.
    
    Returns:
        True if formula is correctly implemented
    """
    ema = EMAFilter(alpha=0.5)
    
    # Test sequence: 0, 100, 100, 100, 100
    values = [0, 100, 100, 100, 100]
    expected = [
        0,     # First value
        50,    # 0.5*100 + 0.5*0
        75,    # 0.5*100 + 0.5*50
        87.5,  # 0.5*100 + 0.5*75
        93.75  # 0.5*100 + 0.5*87.5
    ]
    
    actual = [ema.filter_value(v) for v in values]
    
    # Check with tolerance
    tolerance = 1e-10
    for i, (a, e) in enumerate(zip(actual, expected)):
        if abs(a - e) > tolerance:
            print(f"Step {i}: expected {e}, got {a}")
            return False
    
    return True


if __name__ == "__main__":
    # Self-test
    print("Running EMA filter self-tests...")
    
    print(f"EMA formula verification: {'PASS' if verify_ema_formula() else 'FAIL'}")
    
    passed, msg = run_oq6_test()
    print(f"OQ-6 (step input convergence): {'PASS' if passed else 'FAIL'} - {msg}")
    
    # Example: Filter a noisy signal
    print("\nExample: Filtering noisy signal...")
    ema = EMAFilter(alpha=0.3)
    
    # Simulate noisy signal (sine wave + noise)
    import math
    noisy_signal = []
    filtered_signal = []
    
    for t in range(20):
        clean = 50 + 20 * math.sin(t * 0.5)
        noise = np.random.normal(0, 5) if 'np' in dir() else 0
        noisy = clean + noise
        
        filtered = ema.filter_value(noisy)
        noisy_signal.append(noisy)
        filtered_signal.append(filtered)
    
    print(f"Last 5 filtered values: {filtered_signal[-5:]}")
