// SPDX-License-Identifier: MIT
// Stale-input rule of the pipelined remote-step exchange (SRS FR-MS-007, VAL-033, plan task 2.8 slice 3).
#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <vector>

#include "srtra_fmi_master/pipelined_exchange.hpp"

using srtra_fmi_master::PipelinedExchange;

TEST_CASE("the first exchange point holds no value", "[pipelined][stale]")
{
  PipelinedExchange mech(1);
  const auto held = mech.exchange_point(0);
  CHECK_FALSE(held.valid);
}

TEST_CASE("the exchange point at tick k holds the output of step k-1 (one-step stale, zero-order hold)",
  "[pipelined][stale]")
{
  PipelinedExchange mech(1);
  // Tick 0: request step 0. Its reply is not read in the same tick.
  REQUIRE(mech.request_sent(0));
  CHECK_FALSE(mech.exchange_point(0).valid);
  // Tick 1: read the reply of step 0 (the first exchange point that holds a value), then request step 1.
  REQUIRE(mech.receive_reply(0, 10.0));
  const auto at_tick1 = mech.exchange_point(1);
  REQUIRE(at_tick1.valid);
  CHECK(at_tick1.step_index == 0);
  CHECK(at_tick1.value == 10.0);
  REQUIRE(mech.request_sent(1));
  // Tick 2: the held value is still the step-0 output until the step-1 reply is read.
  CHECK(mech.exchange_point(2).value == 10.0);
  CHECK(mech.exchange_point(2).step_index == 0);
}

TEST_CASE("a held value is the previous tick's output, for every tick of a run", "[pipelined][stale]")
{
  // The participant output at step k is 100 + k. The master must hold, at tick t, the output of the last
  // completed step, which for a one-tick period is step t-1 (value 100 + (t-1)).
  PipelinedExchange mech(1);
  std::vector<double> held_at_tick;
  std::vector<std::uint64_t> held_step;
  for (std::uint64_t t = 0; t < 200; ++t) {
    // Order at a step point: read the reply of the step in flight (if it has arrived), hold it, then request
    // the next step. Only one step is in flight at a time, so the reply is read before the next request.
    if (t > 0) {
      REQUIRE(mech.receive_reply(t - 1, 100.0 + static_cast<double>(t - 1)));
    }
    const auto held = mech.exchange_point(t);
    held_at_tick.push_back(held.valid ? held.value : -1.0);
    held_step.push_back(held.step_index);
    REQUIRE(mech.request_sent(t));
  }
  // With the read-then-request order, the value held at tick t is the output of step t-1: the one-step stale state.
  CHECK(held_at_tick[0] == -1.0);
  for (std::uint64_t t = 1; t < 200; ++t) {
    CHECK(held_at_tick[t] == 100.0 + static_cast<double>(t - 1));
    CHECK(held_step[t] == t - 1);
  }
}

TEST_CASE("a second request while a step is in flight is refused (no skipped or doubled step)",
  "[pipelined][stale]")
{
  PipelinedExchange pulse(10);
  REQUIRE(pulse.request_sent(0));
  CHECK_FALSE(pulse.request_sent(10));
  CHECK(pulse.in_flight() == 0);
  CHECK(pulse.requests_sent() == 1);
}

TEST_CASE("a reply that does not match the step in flight is rejected and holds the old value",
  "[pipelined][stale]")
{
  PipelinedExchange pulse(10);
  REQUIRE(pulse.request_sent(0));
  REQUIRE(pulse.receive_reply(0, 72.0));
  // A duplicate of step 0 (and a reply for a step that was never requested) must not change the held value.
  CHECK_FALSE(pulse.receive_reply(0, 999.0));
  CHECK_FALSE(pulse.receive_reply(5, 999.0));
  CHECK(pulse.replies_rejected() == 2);
  CHECK(pulse.exchange_point(10).value == 72.0);
}

TEST_CASE("the Pulse period delivers one reply per 10 ticks and holds it between steps", "[pipelined][stale]")
{
  PipelinedExchange pulse(10);
  std::uint64_t reads = 0;
  for (std::uint64_t t = 0; t < 100; ++t) {
    if (pulse.due(t)) {
      if (t > 0) {
        // The reply of step s carries the value 80 + s.
        REQUIRE(pulse.receive_reply((t / 10) - 1, 80.0 + static_cast<double>((t / 10) - 1)));
        reads++;
      }
      REQUIRE(pulse.request_sent(t));
    }
  }
  CHECK(reads == 9);
  // The held value after tick 90 is the reply of step 8 (sent at tick 80, read at tick 90).
  CHECK(pulse.exchange_point(95).value == 80.0 + 8.0);
  CHECK(pulse.exchange_point(95).step_index == 8);
}
