// SPDX-License-Identifier: MIT
// Scheduler unit tests against a fake FMU stub (plan task 2.8 slice 1). No DLL and no ROS are used.
#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "srtra_fmi_master/participant.hpp"
#include "srtra_fmi_master/scheduler.hpp"

using srtra_fmi_master::Code;
using srtra_fmi_master::ParticipantConfig;
using srtra_fmi_master::Ns;
using srtra_fmi_master::Scheduler;
using srtra_fmi_master::Status;
using srtra_fmi_master::Stimulus;
using srtra_fmi_master::Wire;

namespace
{

constexpr Ns kMs = 1000000;
constexpr std::uint32_t kProbeVr = 7;

struct Record
{
  std::string name;
  Ns t_ns;
  Ns h_ns;
  double probe;
};

// Fake FMU: output vr 0 is the number of completed steps, input vr 7 is the probe value.
class FakeFmu : public srtra_fmi_master::Participant
{
public:
  FakeFmu(std::string name, std::vector<Record> * log)
  : name_(std::move(name)), log_(log) {}

  bool initialize(double) override
  {
    ++init_calls;
    if (!init_ok) {
      error_ = "init refused";
      return false;
    }
    return true;
  }

  bool set_real(std::uint32_t vr, double value) override
  {
    if (vr != kProbeVr) {
      error_ = "unknown input";
      return false;
    }
    probe_ = value;
    return true;
  }

  bool get_real(std::uint32_t vr, double & value) override
  {
    if (vr != 0) {
      error_ = "unknown output";
      return false;
    }
    value = static_cast<double>(steps);
    return true;
  }

  bool do_step(double t_s, double h_s) override
  {
    ++steps;
    const Ns t_ns = static_cast<Ns>(std::llround(t_s * 1.0e9));
    const Ns h_ns = static_cast<Ns>(std::llround(h_s * 1.0e9));
    log_->push_back(Record{name_, t_ns, h_ns, probe_});
    if (fail_at == steps) {
      error_ = "fake failure";
      return false;
    }
    return true;
  }

  bool reset() override
  {
    ++reset_calls;
    if (!reset_ok) {
      error_ = "reset refused";
      return false;
    }
    steps = 0;
    probe_ = 0.0;
    return true;
  }

  const char * last_error() const override { return error_.c_str(); }

  int init_calls = 0;
  int reset_calls = 0;
  bool init_ok = true;
  bool reset_ok = true;
  long long fail_at = -1;
  long long steps = 0;

private:
  std::string name_;
  std::vector<Record> * log_;
  double probe_ = 0.0;
  std::string error_;
};

ParticipantConfig config(
  const std::string & name, srtra_fmi_master::Participant * p, Ns period, Ns offset)
{
  ParticipantConfig c;
  c.name = name;
  c.participant = p;
  c.period_ns = period;
  c.offset_ns = offset;
  c.fixed_step_ns = period;
  c.output_value_references = {0};
  return c;
}

// Runs ticks 0, base, ..., last_ms and returns the status of the last call.
Status run_until(Scheduler & s, Ns last_ns)
{
  Status st;
  const Ns base = s.base_step_ns();
  for (Ns t = 0; t <= last_ns; t += base) {
    st = s.advance_to(t);
    if (!st.ok()) {
      break;
    }
  }
  return st;
}

}  // namespace

TEST_CASE("step points run in schedule order with participant index as tie break", "[scheduler][ordering]")
{
  std::vector<Record> log;
  FakeFmu a("A", &log);
  FakeFmu b("B", &log);
  Scheduler s(10 * kMs,
    {config("A", &a, 10 * kMs, 0), config("B", &b, 30 * kMs, 10 * kMs)},
    {}, {});
  REQUIRE(s.initialize().ok());
  REQUIRE(run_until(s, 40 * kMs).ok());

  const std::vector<std::pair<std::string, Ns>> expected = {
    {"A", 0}, {"A", 10 * kMs}, {"B", 10 * kMs}, {"A", 20 * kMs}, {"A", 30 * kMs},
    {"A", 40 * kMs}, {"B", 40 * kMs},
  };
  REQUIRE(log.size() == expected.size());
  for (std::size_t i = 0; i < expected.size(); ++i) {
    CHECK(log[i].name == expected[i].first);
    CHECK(log[i].t_ns == expected[i].second);
  }
  CHECK(s.step_count(0) == 5);
  CHECK(s.step_count(1) == 2);
}

TEST_CASE("step size must equal the FMU fixed step and the schedule grid", "[scheduler][step]")
{
  std::vector<Record> log;
  FakeFmu a("A", &log);

  ParticipantConfig wrong_fixed = config("A", &a, 10 * kMs, 0);
  wrong_fixed.fixed_step_ns = 20 * kMs;
  CHECK_THROWS_AS(Scheduler(10 * kMs, {wrong_fixed}, {}, {}), std::invalid_argument);

  CHECK_THROWS_AS(Scheduler(10 * kMs, {config("A", &a, 25 * kMs, 0)}, {}, {}), std::invalid_argument);
  CHECK_THROWS_AS(Scheduler(10 * kMs, {config("A", &a, 10 * kMs, 5 * kMs)}, {}, {}), std::invalid_argument);
  CHECK_THROWS_AS(Scheduler(10 * kMs, {config("A", &a, 10 * kMs, -10 * kMs)}, {}, {}), std::invalid_argument);
  CHECK_THROWS_AS(Scheduler(0, {config("A", &a, 10 * kMs, 0)}, {}, {}), std::invalid_argument);
  CHECK_THROWS_AS(Scheduler(10 * kMs, {}, {}, {}), std::invalid_argument);

  std::vector<Wire> bad_wire = {{0, 5, 0, 1}};
  CHECK_THROWS_AS(Scheduler(10 * kMs, {config("A", &a, 10 * kMs, 0)}, bad_wire, {}), std::invalid_argument);
}

TEST_CASE("fmi3DoStep failure latches and is returned by every later call", "[scheduler][error]")
{
  std::vector<Record> log;
  FakeFmu a("A", &log);
  a.fail_at = 2;
  Scheduler s(10 * kMs, {config("A", &a, 10 * kMs, 0)}, {}, {});
  REQUIRE(s.initialize().ok());
  REQUIRE(s.advance_to(0).ok());

  Status st = s.advance_to(10 * kMs);
  CHECK(st.code == Code::kParticipantError);
  CHECK(st.participant == 0);
  CHECK(st.time_ns == 10 * kMs);
  CHECK(std::string(st.message) == "fmi3DoStep failed");
  CHECK(std::string(st.detail) == "fake failure");
  CHECK(log.size() == 2);

  Status later = s.advance_to(20 * kMs);
  CHECK(later.code == Code::kParticipantError);
  CHECK(log.size() == 2);
}

TEST_CASE("initialization failure is reported and latched", "[scheduler][error]")
{
  std::vector<Record> log;
  FakeFmu a("A", &log);
  a.init_ok = false;
  Scheduler s(10 * kMs, {config("A", &a, 10 * kMs, 0)}, {}, {});
  Status st = s.initialize();
  CHECK(st.code == Code::kParticipantError);
  CHECK(std::string(st.message) == "initialization failed");
  CHECK(std::string(st.detail) == "init refused");
  CHECK(s.advance_to(0).code == Code::kParticipantError);
  CHECK(log.empty());
}

TEST_CASE("ticks must be consecutive and initialize comes first", "[scheduler][timeline]")
{
  std::vector<Record> log;
  FakeFmu a("A", &log);
  Scheduler s(10 * kMs, {config("A", &a, 10 * kMs, 0)}, {}, {});
  CHECK(s.advance_to(0).code == Code::kNotInitialized);
  REQUIRE(s.initialize().ok());
  CHECK(s.advance_to(20 * kMs).code == Code::kTimeError);
  CHECK(s.advance_to(0).ok());
  CHECK(s.next_tick_ns() == 10 * kMs);
}

TEST_CASE("inputs are wired from the producer cache with zero-order hold", "[scheduler][wiring]")
{
  std::vector<Record> log;
  FakeFmu a("A", &log);
  FakeFmu b("B", &log);
  Scheduler s(10 * kMs,
    {config("A", &a, 10 * kMs, 0), config("B", &b, 10 * kMs, 0)},
    {Wire{0, 0, 1, kProbeVr}},
    {});
  REQUIRE(s.initialize().ok());
  REQUIRE(run_until(s, 20 * kMs).ok());

  // A steps before B at each tick, so B sees the output that A published at the same tick.
  REQUIRE(log.size() == 6);
  CHECK(log[1].name == "B");
  CHECK(log[1].probe == 1.0);
  CHECK(log[3].name == "B");
  CHECK(log[3].probe == 2.0);
  CHECK(log[5].probe == 3.0);
}

TEST_CASE("stimulus values are evaluated at the step point", "[scheduler][stimulus]")
{
  std::vector<Record> log;
  FakeFmu a("A", &log);
  const Stimulus stim{0, kProbeVr, [](Ns t_ns) { return static_cast<double>(t_ns) / 1.0e9; }};
  Scheduler s(10 * kMs, {config("A", &a, 10 * kMs, 0)}, {}, {stim});
  REQUIRE(s.initialize().ok());
  REQUIRE(run_until(s, 20 * kMs).ok());
  REQUIRE(log.size() == 3);
  CHECK(log[2].t_ns == 20 * kMs);
  CHECK(std::fabs(log[2].probe - 0.02) < 1.0e-12);
  CHECK(log[0].h_ns == 10 * kMs);
}

TEST_CASE("reset restores the timeline and reproduces the run exactly", "[scheduler][reset]")
{
  std::vector<Record> first;
  FakeFmu a("A", &first);
  FakeFmu b("B", &first);
  Scheduler s(10 * kMs,
    {config("A", &a, 10 * kMs, 0), config("B", &b, 30 * kMs, 10 * kMs)},
    {Wire{0, 0, 1, kProbeVr}},
    {});
  REQUIRE(s.initialize().ok());
  REQUIRE(run_until(s, 50 * kMs).ok());
  const std::vector<Record> run_one = first;

  first.clear();
  Status r = s.reset();
  REQUIRE(r.ok());
  CHECK(s.next_tick_ns() == 0);
  CHECK(s.step_count(0) == 0);
  CHECK(a.reset_calls == 1);
  CHECK(a.init_calls == 2);
  REQUIRE(run_until(s, 50 * kMs).ok());

  REQUIRE(first.size() == run_one.size());
  for (std::size_t i = 0; i < run_one.size(); ++i) {
    CHECK(first[i].name == run_one[i].name);
    CHECK(first[i].t_ns == run_one[i].t_ns);
    CHECK(first[i].h_ns == run_one[i].h_ns);
    CHECK(first[i].probe == run_one[i].probe);
  }
}

TEST_CASE("a failing reset is reported", "[scheduler][reset]")
{
  std::vector<Record> log;
  FakeFmu a("A", &log);
  Scheduler s(10 * kMs, {config("A", &a, 10 * kMs, 0)}, {}, {});
  REQUIRE(s.initialize().ok());
  a.reset_ok = false;
  Status r = s.reset();
  CHECK(r.code == Code::kParticipantError);
  CHECK(std::string(r.message) == "reset failed");
  CHECK(std::string(r.detail) == "reset refused");
}

TEST_CASE("ten-minute run at 100 Hz steps the 0.1 s FMU exactly 6000 times", "[scheduler][timeline]")
{
  std::vector<Record> log;
  FakeFmu a("A", &log);
  Scheduler s(10 * kMs, {config("A", &a, 100 * kMs, 0)}, {}, {});
  REQUIRE(s.initialize().ok());
  REQUIRE(run_until(s, 600000 * kMs - 10 * kMs).ok());
  CHECK(s.step_count(0) == 6000);
  REQUIRE(log.size() == 6000);
  CHECK(log.back().t_ns == 599900 * kMs);
  CHECK(log.back().h_ns == 100 * kMs);
  CHECK(s.next_tick_ns() == 600000 * kMs);
}
