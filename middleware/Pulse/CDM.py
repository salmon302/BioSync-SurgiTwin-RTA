# SPDX-License-Identifier: MIT
"""
Legacy ``Pulse.CDM`` surface backed by ``pulse.cdm.*`` (Pulse 4.3.2).

Re-exports the CDM symbols the middleware imports from ``Pulse.CDM`` and
provides thin compatibility stand-ins for the two classes whose 4.3.2 API
differs enough to break the legacy call sites (``SEDataRequest`` construction
and ``SEState`` serialization).
"""
from pulse.cdm.patient import SEPatientConfiguration, SEPatient, eSex
from pulse.cdm.scalars import TimeUnit, MassUnit, LengthUnit

__all__ = [
    "SEPatientConfiguration",
    "SEPatient",
    "TimeUnit",
    "MassUnit",
    "LengthUnit",
    "eSex",
    "SEDataRequest",
    "SEState",
]


class _SEDataRequestShim:
    """Legacy ``SEDataRequest()`` / ``set_name()`` / ``set_unit()`` builder.

    The 4.3.2 ``SEDataRequest`` is constructed with a category/property and has
    no ``set_name``/``set_unit`` accessors. The legacy middleware only builds
    throwaway request objects after init (the real requests are registered by
    the default FR-3.6.4 DRM), so a no-op shim keeps those call sites working.
    """

    def __init__(self):
        self._name = None
        self._unit = None

    def set_name(self, name):
        self._name = name
        return self

    def set_unit(self, unit):
        self._unit = unit
        return self


def SEDataRequest(*_args, **_kwargs):
    return _SEDataRequestShim()


class SEState:
    """Legacy ``SEState()`` / ``SerializeToString()`` backed by binary state."""

    def __init__(self):
        self._serialized = b""

    def SerializeToString(self):
        return self._serialized
