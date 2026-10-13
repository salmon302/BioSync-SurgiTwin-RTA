// SPDX-License-Identifier: MIT
#ifndef RTA_TIMED_AUTOMATA_H
#define RTA_TIMED_AUTOMATA_H

namespace rta {

// Minimal placeholder for the timed automata monitor.
// TODO(FR-RTA-002): model clock constraints, forward state prediction, and
// sensor and network lag accounting. No algorithm is designed here yet.
class TimedAutomaton {
public:
    bool isDeadlineMet(double elapsedMs, double deadlineMs) const;
};

}  // namespace rta

#endif  // RTA_TIMED_AUTOMATA_H
