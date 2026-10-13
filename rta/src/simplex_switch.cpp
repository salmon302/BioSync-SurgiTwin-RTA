// SPDX-License-Identifier: MIT
#include "rta/simplex_switch.h"

namespace rta {

SimplexSwitch::SimplexSwitch(SafetyEnvelope envelope) : envelope_{envelope} {}

SimplexSwitch::Controller SimplexSwitch::select(double toolTipDistanceMm, double tissueWrenchN) const {
    if (envelope_.isSafe(toolTipDistanceMm, tissueWrenchN)) {
        return Controller::Primary;
    }
    return Controller::Fallback;
}

}  // namespace rta
