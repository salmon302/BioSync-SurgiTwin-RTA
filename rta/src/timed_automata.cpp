// SPDX-License-Identifier: MIT
#include "rta/timed_automata.h"

namespace rta {

bool TimedAutomaton::isDeadlineMet(double elapsedMs, double deadlineMs) const {
    // TODO(FR-RTA-002): replace with timed automaton clock evaluation.
    return elapsedMs <= deadlineMs;
}

}  // namespace rta
