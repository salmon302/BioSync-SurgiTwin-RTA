// SPDX-License-Identifier: MIT
// Unit suite for the SimplexSwitch stub (FR-RTA-001, FR-RTA-004, plan task 3.8 slice 1).
// The first three assertions repeat rta/tests/test_smoke.cpp so the smoke regression
// cases also live in the Catch2 suite.
#include <catch2/catch_test_macros.hpp>

#include "rta/simplex_switch.h"

TEST_CASE("SimplexSwitch selects the primary controller inside the envelope", "[simplex_switch]") {
    const rta::SimplexSwitch switchUnderTest{rta::SafetyEnvelope{5.0, 2.0}};

    REQUIRE(switchUnderTest.select(10.0, 1.0) == rta::SimplexSwitch::Controller::Primary);
}

TEST_CASE("SimplexSwitch falls back when the tool tip is inside the keep-out distance", "[simplex_switch]") {
    const rta::SimplexSwitch switchUnderTest{rta::SafetyEnvelope{5.0, 2.0}};

    REQUIRE(switchUnderTest.select(0.0, 1.0) == rta::SimplexSwitch::Controller::Fallback);
}

TEST_CASE("SimplexSwitch falls back when the tissue wrench exceeds the limit", "[simplex_switch]") {
    const rta::SimplexSwitch switchUnderTest{rta::SafetyEnvelope{5.0, 2.0}};

    REQUIRE(switchUnderTest.select(10.0, 3.0) == rta::SimplexSwitch::Controller::Fallback);
}

TEST_CASE("SimplexSwitch keeps the primary controller exactly at the thresholds", "[simplex_switch]") {
    const rta::SimplexSwitch switchUnderTest{rta::SafetyEnvelope{5.0, 2.0}};

    REQUIRE(switchUnderTest.select(5.0, 2.0) == rta::SimplexSwitch::Controller::Primary);
    REQUIRE(switchUnderTest.select(5.0, 2.0001) == rta::SimplexSwitch::Controller::Fallback);
    REQUIRE(switchUnderTest.select(4.9999, 2.0) == rta::SimplexSwitch::Controller::Fallback);
}

TEST_CASE("SimplexSwitch follows its configured envelope", "[simplex_switch]") {
    const rta::SimplexSwitch switchUnderTest{rta::SafetyEnvelope{1.0, 10.0}};

    REQUIRE(switchUnderTest.select(2.0, 9.0) == rta::SimplexSwitch::Controller::Primary);
    REQUIRE(switchUnderTest.select(0.5, 9.0) == rta::SimplexSwitch::Controller::Fallback);
    REQUIRE(switchUnderTest.select(2.0, 11.0) == rta::SimplexSwitch::Controller::Fallback);
}