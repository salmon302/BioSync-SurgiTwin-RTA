// SPDX-License-Identifier: MIT
// fmi_multirate_node: the FMI 3.0 co-simulation master for the three-FMU roster (thermal, mechanical, Pulse) on a
// 1 ms master step (SRS FR-MS-007, plan task 2.8 slice 2). It publishes the master clock and one state message per
// participant per master tick over Fast DDS.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "builtin_interfaces/msg/time.hpp"
#include "rclcpp/rclcpp.hpp"
#include "srtra_fmi_master/fmu_participant.hpp"
#include "srtra_fmi_master/scheduler.hpp"
#include "srtra_fmi_master/tick_waiter.hpp"
#include "srtra_fmi_master/msg/master_clock.hpp"
#include "srtra_fmi_master/msg/participant_state.hpp"

namespace
{

using SteadyClock = std::chrono::steady_clock;
using srtra_fmi_master::Ns;

constexpr Ns kBaseNs = 1000000;      // 1 ms master step (mechanical DoStep step)
constexpr Ns kThermalNs = 100000000;  // 0.1 s
constexpr Ns kPulseNs = 10000000;     // 0.01 s
constexpr Ns kMechanicalNs = 1000000; // 0.001 s

// thermal_pennes value references (sim/fmi/model/modelDescription.xml)
constexpr std::uint32_t kThermalPowerIn = 11;
constexpr std::uint32_t kThermalHbcIn = 12;
constexpr std::uint32_t kThermalEnvIn = 13;
// mechanical_sofa value references (sim/fmi/mechanical/model/modelDescription.xml)
constexpr std::uint32_t kMechTipX = 10, kMechTipY = 11, kMechTipZ = 12;
constexpr std::uint32_t kMechForceX = 20, kMechForceY = 21, kMechForceZ = 22;
constexpr std::uint32_t kMechMaxDisp = 40;
// pulse_physiology value references (sim/fmi/pulse/model/modelDescription.xml)
constexpr std::uint32_t kPulseExercise = 10;
constexpr std::uint32_t kPulseHeartRate = 20;
constexpr std::uint32_t kPulseSpo2 = 24;
constexpr std::uint32_t kPulsePaO2 = 26;

double power_profile_w(Ns t_ns) { return t_ns < 30000000000LL ? 5.0 : 0.0; }
double zero_input(Ns) { return 0.0; }
double ambient_k(Ns) { return 310.15; }
double tip_x(Ns) { return 0.10; }
double tip_y(Ns) { return 0.195; }
double tip_z(Ns) { return 0.10; }
double exercise_zero(Ns) { return 0.0; }

std::int64_t steady_now_ns()
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(SteadyClock::now().time_since_epoch()).count();
}

std::int64_t system_now_ns()
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
    std::chrono::system_clock::now().time_since_epoch()).count();
}

void set_stamp(builtin_interfaces::msg::Time & stamp, std::int64_t ns)
{
  stamp.sec = static_cast<std::int32_t>(ns / 1000000000);
  stamp.nanosec = static_cast<std::uint32_t>(ns % 1000000000);
}

}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("srtra_fmi_multirate");

  const std::string fmu_root = node->declare_parameter<std::string>("fmu_root", "");
  const std::int64_t duration_s = node->declare_parameter<std::int64_t>("duration_s", 600);
  const std::string timer_mode = node->declare_parameter<std::string>("timer_mode", "high_resolution");
  // Integer parameter: a numeric-looking string on the command line is parsed as an integer by the ROS parameter
  // parser, and reading it as a std::string faulted in ucrtbase (0xC0000409) in the slice-2 bring-up.
  const std::int64_t pulse_port = node->declare_parameter<std::int64_t>("pulse_port", 5055);

  if (fmu_root.empty() || duration_s <= 0) {
    std::fprintf(stderr, "fmi_multirate_node: fmu_root and a positive duration_s are required\n");
    rclcpp::shutdown();
    return 1;
  }
  // The Pulse FMU connects to its worker on the default port 5055 (the FMU's tcp_port default). The node has no
  // setter path for it, so any other port is refused with an error.
  if (pulse_port != 5055) {
    std::fprintf(stderr, "fmi_multirate_node: pulse_port must be 5055 (the FMU default) in this slice\n");
    rclcpp::shutdown();
    return 1;
  }

  std::string error;
  auto thermal = srtra_fmi_master::FmuParticipant::create(
    fmu_root + "/thermal_pennes/binaries/x86_64-windows/thermal_pennes.dll",
    "5d6f2a8e-3c1b-4f7a-9e2d-7b8c0a1f4e63", "thermal_pennes", error, fmu_root + "/thermal_pennes/resources/");
  if (!thermal) { std::fprintf(stderr, "thermal: %s\n", error.c_str()); rclcpp::shutdown(); return 1; }
  auto mech = srtra_fmi_master::FmuParticipant::create(
    fmu_root + "/mechanical_sofa/binaries/x86_64-windows/mechanical_sofa.dll",
    "7c1e5a2b-94d0-4f63-b8a1-2e6d0f3c9a57", "mechanical_sofa", error, fmu_root + "/mechanical_sofa/resources/");
  if (!mech) { std::fprintf(stderr, "mechanical: %s\n", error.c_str()); rclcpp::shutdown(); return 1; }
  auto pulse = srtra_fmi_master::FmuParticipant::create(
    fmu_root + "/pulse_physiology/binaries/x86_64-windows/pulse_physiology.dll",
    "b3e1d7a4-5f20-4c8e-9a61-0d2f7c4e8b19", "pulse_physiology", error, fmu_root + "/pulse_physiology/resources/");
  if (!pulse) { std::fprintf(stderr, "pulse: %s\n", error.c_str()); rclcpp::shutdown(); return 1; }

  // Participant index order is also the within-tick step order: thermal, mechanical, Pulse.
  std::vector<srtra_fmi_master::ParticipantConfig> participants(3);
  participants[0].name = "thermal_pennes";
  participants[0].participant = thermal.get();
  participants[0].period_ns = kThermalNs;
  participants[0].fixed_step_ns = kThermalNs;
  participants[0].output_value_references = {20, 21, 22, 23};
  participants[1].name = "mechanical_sofa";
  participants[1].participant = mech.get();
  participants[1].period_ns = kMechanicalNs;
  participants[1].fixed_step_ns = kMechanicalNs;
  participants[1].output_value_references = {20, 21, 22, 40};
  participants[2].name = "pulse_physiology";
  participants[2].participant = pulse.get();
  participants[2].period_ns = kPulseNs;
  participants[2].fixed_step_ns = kPulseNs;
  participants[2].output_value_references = {kPulseHeartRate, kPulseSpo2, kPulsePaO2};

  std::vector<srtra_fmi_master::Stimulus> stimuli = {
    {0, kThermalPowerIn, power_profile_w},
    {0, kThermalHbcIn, zero_input},
    {0, kThermalEnvIn, ambient_k},
    {1, kMechTipX, tip_x},
    {1, kMechTipY, tip_y},
    {1, kMechTipZ, tip_z},
    {2, kPulseExercise, exercise_zero},
  };

  std::unique_ptr<srtra_fmi_master::Scheduler> scheduler;
  try {
    scheduler = std::make_unique<srtra_fmi_master::Scheduler>(
      kBaseNs, participants, std::vector<srtra_fmi_master::Wire>{}, stimuli);
  } catch (const std::invalid_argument & e) {
    std::fprintf(stderr, "fmi_multirate_node: %s\n", e.what());
    rclcpp::shutdown();
    return 1;
  }
  srtra_fmi_master::Status status = scheduler->initialize();
  if (!status.ok()) {
    std::fprintf(stderr, "fmi_multirate_node: initialize failed for %s: %s (%s)\n",
      participants[status.participant].name.c_str(), status.message, status.detail);
    rclcpp::shutdown();
    return 2;
  }

  auto clock_pub = node->create_publisher<srtra_fmi_master::msg::MasterClock>(
    "/srtra/fmi/master/clock", rclcpp::QoS(rclcpp::KeepLast(2000)).reliable());
  std::vector<rclcpp::Publisher<srtra_fmi_master::msg::ParticipantState>::SharedPtr> state_pubs;
  for (const auto & p : participants) {
    state_pubs.push_back(node->create_publisher<srtra_fmi_master::msg::ParticipantState>(
      "/srtra/fmi/participant/" + p.name, rclcpp::QoS(rclcpp::KeepLast(2000)).reliable()));
  }

  const auto subscriber_deadline = SteadyClock::now() + std::chrono::seconds(30);
  while (clock_pub->get_subscription_count() == 0 && SteadyClock::now() < subscriber_deadline) {
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }

  srtra_fmi_master::TickWaiter waiter(timer_mode == "high_resolution");
  const std::int64_t anchor_system_ns = system_now_ns();
  const std::int64_t anchor_steady_ns = steady_now_ns();
  const SteadyClock::time_point start = SteadyClock::now() + std::chrono::milliseconds(200);

  // The run ends on the wall clock: duration_s seconds after start. The master loop runs at its paced rate (about
  // 12 ms per tick on this host with the mechanical FMU), so the tick count is a result, not an input.
  const SteadyClock::time_point wall_end = start + std::chrono::seconds(duration_s);
  srtra_fmi_master::msg::MasterClock clock_msg;
  srtra_fmi_master::msg::ParticipantState state_msg;
  std::uint64_t late_ticks = 0;
  Ns max_lateness_ns = 0;
  int exit_code = 0;
  std::string failure;

  std::uint64_t k = 0;
  for (;; ++k) {
    const Ns tick_ns = static_cast<Ns>(k) * kBaseNs;
    const SteadyClock::time_point target = start + std::chrono::nanoseconds(tick_ns);
    if (SteadyClock::now() >= wall_end) {
      break;
    }
    waiter.wait_until(target);

    status = scheduler->advance_to(tick_ns);
    if (!status.ok()) {
      failure = std::string(status.message) + ": " + status.detail;
      exit_code = 2;
      break;
    }

    const std::int64_t stamp_ns = steady_now_ns();
    const std::int64_t scheduled_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
      target.time_since_epoch()).count();
    const Ns lateness = stamp_ns - scheduled_ns;
    if (lateness > 1000000) {
      ++late_ticks;
    }
    if (lateness > max_lateness_ns) {
      max_lateness_ns = lateness;
    }

    set_stamp(clock_msg.header.stamp, stamp_ns);
    clock_msg.header.frame_id = "srtra_master";
    clock_msg.tick = k;
    clock_msg.master_time_ns = static_cast<std::uint64_t>(tick_ns);
    clock_msg.scheduled_steady_ns = static_cast<std::uint64_t>(scheduled_ns);
    clock_pub->publish(clock_msg);

    for (std::size_t p = 0; p < participants.size(); ++p) {
      state_msg.participant = participants[p].name;
      set_stamp(state_msg.header.stamp, stamp_ns);
      state_msg.header.frame_id = "srtra_master";
      state_msg.tick = k;
      state_msg.steps = scheduler->step_count(p);
      state_msg.fmu_time_s = static_cast<double>(tick_ns) / 1.0e9;
      state_msg.t_max_k = p == 0 ? scheduler->output(0, 0) : 0.0;
      state_msg.t_mean_k = p == 0 ? scheduler->output(0, 1) : 0.0;
      state_msg.v60_mm3 = p == 0 ? scheduler->output(0, 2) : 0.0;
      state_msg.v_lesion_mm3 = p == 0 ? scheduler->output(0, 3) : 0.0;
      state_pubs[p]->publish(state_msg);
    }
  }

  std::printf(
    "{\"schema\":\"srtra-fmi-multirate-run/1\",\"exit_code\":%d,\"failure\":\"%s\","
    "\"timer_mechanism\":\"%s\",\"base_step_ns\":%lld,\"ticks_run\":%llu,\"wall_duration_s\":%lld,"
    "\"late_ticks_over_1ms\":%llu,\"max_lateness_ns\":%lld,"
    "\"thermal_steps\":%llu,\"mechanical_steps\":%llu,\"pulse_steps\":%llu,"
    "\"anchor_system_ns\":%lld,\"anchor_steady_ns\":%lld}\n",
    exit_code, failure.c_str(), waiter.mechanism(), static_cast<long long>(kBaseNs),
    static_cast<unsigned long long>(k), static_cast<long long>(duration_s), static_cast<unsigned long long>(late_ticks),
    static_cast<long long>(max_lateness_ns),
    static_cast<unsigned long long>(scheduler->step_count(0)),
    static_cast<unsigned long long>(scheduler->step_count(1)),
    static_cast<unsigned long long>(scheduler->step_count(2)),
    static_cast<long long>(anchor_system_ns), static_cast<long long>(anchor_steady_ns));

  rclcpp::shutdown();
  return exit_code;
}
