# SPDX-License-Identifier: MIT
"""
Compatibility shim: expose the legacy ``Pulse`` Python API (the surface the
BioSync-Gateway middleware was written against) on top of the real Pulse
4.3.2 ``pulse`` / ``PyPulse`` bindings that the vendored ``.pulse`` source
actually builds.

The vendored engine produces a lowercase ``pulse`` package plus a compiled
``PyPulse`` extension module. This shim re-exports the symbols the middleware
and the IQ-4/OQ-16 qualification tests expect, and adapts the handful of
signature differences between the legacy API and 4.3.2:

  * Engine.initialize_engine(pc)          -> initialize_engine(pc, drm)
  * Engine.get_data_request_manager()     -> the engine (pull_data() lives there)
  * Engine.get_state(proto)               -> serialize_to_string(BINARY)
  * SEDataRequest().set_name()/set_unit() -> SEDataRequest.create_physiology_request
  * SEState()/SerializeToString()         -> engine binary state wrapper
"""
import os
import PyPulse
from pulse.engine.PulseEngine import PulseEngine, eModelType
from pulse.cdm.engine import SEDataRequest, SEDataRequestManager, eSerializationFormat
from pulse.cdm.engine import SEDataRequest, SEDataRequestManager

# Default FR-3.6.4 data requests (mirrors middleware.engine.pulse._PULSE_DATA_REQUESTS).
# Requested without a unit so the resulting DataFrame columns keep the bare
# property names the middleware's metric extractor looks for.
_FR364_REQUESTS = [
    "HeartRate",
    "SystolicArterialPressure",
    "DiastolicArterialPressure",
    "RespirationRate",
    "OxygenSaturation",
    "MeanAirwayPressure",
    "ArterialOxygenPartialPressure",
]


def _default_fr364_drm() -> SEDataRequestManager:
    reqs = [SEDataRequest.create_physiology_request(name) for name in _FR364_REQUESTS]
    drm = SEDataRequestManager()
    drm.set_data_requests(reqs)
    return drm


class Engine(PulseEngine):
    """Legacy-compatible wrapper around ``pulse.engine.PulseEngine``."""

    def __init__(self, eModelType=eModelType.HumanAdultWholeBody, data_root_dir="./"):
        super().__init__(eModelType, data_root_dir)
        self._data_root_dir = data_root_dir

    def initialize_engine(self, patient_configuration, data_request_mgr=None):
        if data_request_mgr is None:
            data_request_mgr = _default_fr364_drm()
        self._drm = data_request_mgr
        # Pulse 4.3.2's Controller::Initialize reloads the substance set from
        # the *process CWD* (engine log: "Reading substance files from ./"),
        # NOT from the data_root_dir supplied at construction. When CWD is not
        # the data root, the reload finds nothing -> GetSubstance("Oxygen")
        # returns null -> AddActiveSubstance(*m_O2) SIGSEGV. PyPulse exposes no
        # data-root setter, so we temporarily chdir into data_root_dir around
        # init and restore CWD afterward. See SNDEV/docs/impl-2026-07-28-
        # pulse-segfault-diag-plan.md (root cause: CWD/data-root mismatch).
        prev_cwd = os.getcwd()
        try:
            if self._data_root_dir:
                os.chdir(self._data_root_dir)
            return super().initialize_engine(patient_configuration, data_request_mgr)
        finally:
            os.chdir(prev_cwd)

    def serialize_to_string(self, fmt):
        # The SWIG PyPulse binding's serialize_to_string expects the
        # PyPulse.serialization_format enum, but the CDM layer (and the
        # middleware) pass pulse.cdm.engine.eSerializationFormat. Translate so
        # callers can use the CDM enum consistently. (Without this, the call
        # raises TypeError: incompatible function arguments.)
        if isinstance(fmt, eSerializationFormat):
            fmt = (PyPulse.serialization_format.binary
                   if fmt == eSerializationFormat.BINARY
                   else PyPulse.serialization_format.json)
        return super().serialize_to_string(fmt)

    def get_data_request_manager(self):
        # In 4.3.2 the engine owns pull_data(); the legacy API returned a DRM
        # that also exposed pull_data(). We return self and provide the legacy
        # create_data_request() as a no-op (requests are already registered).
        return self

    def create_data_request(self, dr):
        # Legacy middleware registers requests after init; they are already
        # covered by the default FR-3.6.4 DRM passed at initialize_engine().
        return

    def get_state(self, proto):
        proto._serialized = self.serialize_to_string(eSerializationFormat.BINARY)
        return True


# Expose the legacy sub-package surface expected by the middleware.
from . import CDM  # noqa: E402,F401

__all__ = ["Engine", "CDM"]
