// SPDX-License-Identifier: MIT
#include "rta/safety_envelope.h"

namespace rta {

SafetyEnvelope::SafetyEnvelope(double minToolTipDistanceMm, double maxTissueWrenchN)
    : minToolTipDistanceMm_{minToolTipDistanceMm}, maxTissueWrenchN_{maxTissueWrenchN} {}

bool SafetyEnvelope::isSafe(double toolTipDistanceMm, double tissueWrenchN) const {
    return toolTipDistanceMm >= minToolTipDistanceMm_ && tissueWrenchN <= maxTissueWrenchN_;
}

}  // namespace rta
