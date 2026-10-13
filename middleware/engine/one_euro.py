# SPDX-License-Identifier: MIT
"""
One Euro adaptive low-pass filter
Implements SRS FR-RTA-005 - adaptive One Euro low-pass filter for 6-DOF teleoperation input.

Reference:
    G. Casiez, N. Roussel, D. Vogel, "1 Euro Filter: A Simple Speed-based Low-pass Filter
    for Noisy Input in Interactive Systems", CHI 2012.

Algorithm (per sample x_t at time t, with frequency f = 1 / (t - t_prev)):
    dx_t      = (x_t - x_hat_{t-1}) * f
    dx_hat_t  = alpha(d_cutoff) * dx_t + (1 - alpha(d_cutoff)) * dx_hat_{t-1}
    cutoff_t  = min_cutoff + beta * |dx_hat_t|
    x_hat_t   = alpha(cutoff_t) * x_t + (1 - alpha(cutoff_t)) * x_hat_{t-1}
    alpha(fc) = 1 / (1 + tau / Te),  tau = 1 / (2 * pi * fc),  Te = 1 / f

Low speed keeps the cutoff at min_cutoff (strong smoothing, suppresses jitter). High speed
raises the cutoff by beta (weak smoothing, low lag during intentional motion).

Integration into the 6-DOF pipeline (MANO constraints, per-axis configuration from the RTA
envelope) is new development and is not part of this module.
"""

import math
from typing import Optional


def _smoothing_factor(frequency: float, cutoff: float) -> float:
    """Smoothing factor for a first-order low-pass with the given cutoff (Hz)."""
    if cutoff <= 0:
        raise ValueError(f"cutoff must be positive, got {cutoff}")
    te = 1.0 / frequency
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / te)


class OneEuroFilter:
    """Scalar One Euro filter. Use one instance per axis."""

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.0,
        d_cutoff: float = 1.0,
        frequency: float = 100.0,
    ):
        """
        Args:
            min_cutoff: Minimum cutoff frequency in Hz (jitter suppression at low speed)
            beta: Speed coefficient (lag reduction at high speed)
            d_cutoff: Cutoff frequency in Hz for the derivative estimate
            frequency: Nominal sampling frequency in Hz, used until timestamps are supplied
        """
        if min_cutoff <= 0 or d_cutoff <= 0:
            raise ValueError("min_cutoff and d_cutoff must be positive")
        if beta < 0:
            raise ValueError("beta must be non-negative")
        if frequency <= 0:
            raise ValueError("frequency must be positive")

        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.frequency = frequency
        self._x_hat: Optional[float] = None
        self._dx_hat = 0.0
        self._t_prev: Optional[float] = None

    def reset(self) -> None:
        self._x_hat = None
        self._dx_hat = 0.0
        self._t_prev = None

    def filter_value(self, x: float, t: Optional[float] = None) -> float:
        """
        Filter one sample.

        Args:
            x: Raw sample
            t: Optional timestamp in seconds. When omitted, the nominal frequency is used.

        Returns:
            Filtered sample
        """
        if self._x_hat is None:
            self._x_hat = float(x)
            self._dx_hat = 0.0
            self._t_prev = t
            return self._x_hat

        if t is not None and self._t_prev is not None and t > self._t_prev:
            frequency = 1.0 / (t - self._t_prev)
        else:
            frequency = self.frequency
        self._t_prev = t if t is not None else self._t_prev

        dx = (float(x) - self._x_hat) * frequency
        a_d = _smoothing_factor(frequency, self.d_cutoff)
        self._dx_hat = a_d * dx + (1.0 - a_d) * self._dx_hat

        cutoff = self.min_cutoff + self.beta * abs(self._dx_hat)
        a = _smoothing_factor(frequency, cutoff)
        self._x_hat = a * float(x) + (1.0 - a) * self._x_hat
        return self._x_hat
