// SPDX-License-Identifier: MIT
// Unit suite for the TimedAutomaton stub (FR-RTA-002, plan task 3.8 slice 1).
// The stub compares elapsed time against the deadline; task 3.3 replaces the body
// with the timed automaton clock evaluation.
#include <catch2/catch_test_macros.hpp>

#include "rta/timed_automata.h"

TEST_CASE("TimedAutomaton reports the deadline state of the stub", "[timed_automata]") {
    const rta::TimedAutomaton monitor{};

    REQUIRE(monitor.isDeadlineMet(0.0, 1.0));
    REQUIRE(monitor.isDeadlineMet(0.999, 1.0));
    REQUIRE(monitor.isDeadlineMet(1.0, 1.0));
    REQUIRE_FALSE(monitor.isDeadlineMet(1.001, 1.0));
}

TEST_CASE("TimedAutomaton handles a zero-length deadline", "[timed_automata]") {
    const rta::TimedAutomaton monitor{};

    REQUIRE(monitor.isDeadlineMet(0.0, 0.0));
    REQUIRE_FALSE(monitor.isDeadlineMet(0.001, 0.0));
}