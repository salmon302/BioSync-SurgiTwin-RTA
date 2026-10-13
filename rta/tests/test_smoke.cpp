// SPDX-License-Identifier: MIT
#include "rta/simplex_switch.h"

int main() {
    const rta::SimplexSwitch switchUnderTest{rta::SafetyEnvelope{5.0, 2.0}};

    if (switchUnderTest.select(10.0, 1.0) != rta::SimplexSwitch::Controller::Primary) {
        return 1;
    }
    if (switchUnderTest.select(0.0, 1.0) != rta::SimplexSwitch::Controller::Fallback) {
        return 2;
    }
    if (switchUnderTest.select(10.0, 3.0) != rta::SimplexSwitch::Controller::Fallback) {
        return 3;
    }
    return 0;
}
