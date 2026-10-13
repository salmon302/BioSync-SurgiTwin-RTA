// SPDX-License-Identifier: MIT
#ifndef RTA_SAFETY_ENVELOPE_H
#define RTA_SAFETY_ENVELOPE_H

namespace rta {

// Placeholder envelope. Thresholds are stub values, not clinical limits (FR-RTA-003).
class SafetyEnvelope {
public:
    SafetyEnvelope() = default;
    SafetyEnvelope(double minToolTipDistanceMm, double maxTissueWrenchN);

    bool isSafe(double toolTipDistanceMm, double tissueWrenchN) const;

private:
    double minToolTipDistanceMm_{5.0};
    double maxTissueWrenchN_{2.0};
};

}  // namespace rta

#endif  // RTA_SAFETY_ENVELOPE_H
