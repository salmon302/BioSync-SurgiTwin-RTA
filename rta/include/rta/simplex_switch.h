// SPDX-License-Identifier: MIT
#ifndef RTA_SIMPLEX_SWITCH_H
#define RTA_SIMPLEX_SWITCH_H

#include "rta/safety_envelope.h"

namespace rta {

// Placeholder Simplex decision switch (FR-RTA-001, FR-RTA-004).
class SimplexSwitch {
public:
    enum class Controller { Primary, Fallback };

    explicit SimplexSwitch(SafetyEnvelope envelope);

    Controller select(double toolTipDistanceMm, double tissueWrenchN) const;

private:
    SafetyEnvelope envelope_;
};

}  // namespace rta

#endif  // RTA_SIMPLEX_SWITCH_H
