"""
OQ-6: EMA Filter Step Input Convergence
Implements SRS OQ-6 - EMA filter converges within 5% after a step input.

NOTE: The SRS OQ-6 numeric bound of ≤ 4 steps is mathematically unachievable for
the nominal α=0.5 / 5% band (the genuine step response converges at step 5). This
is recorded as a FORMAL DEVIATION (BioSync-Gateway deviation-2026-07-29-oq6-step-bound.md)
with a validated acceptance of ≤ 5 steps. The ≤ 4 bound is satisfiable with a
larger α (see test_convergence_meets_4_steps_with_larger_alpha).
"""

import pytest
from engine.signal import EMAFilter, run_oq6_test


class TestOQ6EMAFilterConvergence:
    """Test suite for OQ-6"""

    def test_step_input_convergence_alpha_0_5(self):
        """α=0.5, genuine 0→100 step, converge within 5% after exactly 5 steps.

        The filter is seeded to the pre-step steady state (0) so this measures a
        true step response. SRS OQ-6 nominally requires ≤ 4 steps, but α=0.5 at a
        5% band can only reach 5 steps (formal deviation, see
        BioSync-Gateway deviation-2026-07-29-oq6-step-bound.md).
        """
        ema = EMAFilter(alpha=0.5)

        step_input = 100.0
        tolerance = 0.05  # 5%

        convergence_step = ema.get_convergence_step(
            step_input, step_input, tolerance, initial_value=0.0
        )

        assert convergence_step is not None, "Filter should converge"
        # Genuine step response at α=0.5: 50, 75, 87.5, 93.75, 96.875
        assert convergence_step == 5, (
            f"α=0.5 genuine step response should converge in 5 steps, got {convergence_step}"
        )

    def test_ema_formula_correct(self):
        """Verify EMA formula: EMAₜ = α × xₜ + (1 - α) × EMAₜ₋₁"""
        ema = EMAFilter(alpha=0.5)

        # Apply values and check formula
        values = [0, 100, 100, 100, 100]
        expected = [
            0,     # First value
            50,    # 0.5*100 + 0.5*0
            75,    # 0.5*100 + 0.5*50
            87.5,  # 0.5*100 + 0.5*75
            93.75  # 0.5*100 + 0.5*87.5
        ]

        for i, value in enumerate(values):
            actual = ema.filter_value(value)
            assert abs(actual - expected[i]) < 0.01, f"Step {i}: expected {expected[i]}, got {actual}"

    def test_filter_single_value(self):
        """First value should initialize EMA"""
        ema = EMAFilter(alpha=0.3)

        result = ema.filter_value(50.0)
        assert result == 50.0, "First value should initialize EMA"

    def test_filter_reset(self):
        """Reset should clear filter state"""
        ema = EMAFilter(alpha=0.5)

        ema.filter_value(100.0)
        ema.filter_value(200.0)

        ema.reset()
        assert ema.ema_value is None, "EMA should be None after reset"
        assert ema.step_count == 0, "Step count should be 0 after reset"

    def test_convergence_meets_4_steps_with_larger_alpha(self):
        """Enforceability proof: with α=0.6 the SRS ≤4 bound IS satisfiable.

        |EMA error| after n steps = |steady|·(1-α)^n. At α=0.6, (0.4)^4 = 0.0256
        < 0.05, so the 4th step is already within 5%. This demonstrates the
        ≤4-step requirement is achievable when α is chosen appropriately.
        """
        ema = EMAFilter(alpha=0.6)
        convergence_step = ema.get_convergence_step(100.0, 100.0, 0.05, initial_value=0.0)
        assert convergence_step is not None and convergence_step <= 4, (
            f"α=0.6 should converge within 4 steps, got {convergence_step}"
        )

    def test_run_oq6_test(self):
        """Run the official OQ-6 test (formally deviated to ≤5 steps)."""
        passed, msg = run_oq6_test()
        assert passed, f"OQ-6 test failed: {msg}"
        assert "FORMAL DEVIATION" in msg, (
            "OQ-6 reference test must record the formal deviation from the "
            "SRS ≤4 step bound"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
