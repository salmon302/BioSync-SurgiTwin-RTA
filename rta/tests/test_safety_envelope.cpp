// SPDX-License-Identifier: MIT
// Unit suite for the SafetyEnvelope stub (FR-RTA-003, plan task 3.8 slice 1).
// Thresholds are the stub values 5.0 mm and 2.0 N until task 3.1 carries the risk-file values.
#include <catch2/catch_test_macros.hpp>

#include "rta/safety_envelope.h"

TEST_CASE("SafetyEnvelope applies the default stub thresholds", "[safety_envelope]") {
    const rta::SafetyEnvelope envelope{};

    REQUIRE_FALSE(envelope.isSafe(4.999, 1.0));
    REQUIRE(envelope.isSafe(5.0, 1.0));
    REQUIRE(envelope.isSafe(100.0, 2.0));
    REQUIRE_FALSE(envelope.isSafe(100.0, 2.001));
}

TEST_CASE("SafetyEnvelope honours its configured bounds", "[safety_envelope]") {
    const rta::SafetyEnvelope envelope{10.0, 3.0};

    REQUIRE_FALSE(envelope.isSafe(9.999, 3.0));
    REQUIRE(envelope.isSafe(10.0, 3.0));
    REQUIRE(envelope.isSafe(100.0, 0.0));
    REQUIRE_FALSE(envelope.isSafe(0.0, 0.0));
}

TEST_CASE("SafetyEnvelope evaluates the distance and wrench dimensions independently", "[safety_envelope]") {
    const rta::SafetyEnvelope envelope{5.0, 2.0};

    SECTION("distance below the bound with a safe wrench is rejected") {
        REQUIRE_FALSE(envelope.isSafe(4.0, 1.0));
    }
    SECTION("wrench above the bound with a safe distance is rejected") {
        REQUIRE_FALSE(envelope.isSafe(10.0, 3.0));
    }
    SECTION("both dimensions inside their bounds are accepted") {
        REQUIRE(envelope.isSafe(6.0, 1.0));
    }
}