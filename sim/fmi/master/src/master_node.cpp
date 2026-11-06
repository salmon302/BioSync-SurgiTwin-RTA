// SPDX-License-Identifier: MIT
// fmi_master_node: runs the FMI 3.0 co-simulation master for one participant and publishes the master
// clock and the participant state over Fast DDS (SRS FR-MS-007, plan task 2.8 slice 1).
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

constexpr Ns kLatenessBoundNs = 1000000;  // 1 ms: a publish later than this counts as a late tick.
constexpr std::uint32_t kVrPowerInput = 11;
constexpr std::uint32_t kVrHbcInput = 12;
constexpr std::uint32_t kVrEnvInput = 13;
constexpr std::uint32_t kVrTmax = 20;
constexpr std::uint32_t kVrTmean = 21;
constexpr std::uint32_t kVrV60 = 22;
constexpr std::uint32_t kVrVlesion = 23;
constexpr Ns kPowerOffNs = 30000000000;  // P_abl is on for t < 30 s, matching the check_fmu.py case B1 profile.

double power_profile_w(Ns t_ns)
{
  return t_ns < kPowerOffNs ? 5.0 : 0.0;
}

double zero_input(Ns)
{
  return 0.0;
}

double ambient_k(Ns)
{
  return 310.15;
}

std::int64_t steady_now_ns()
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
    SteadyClock::now().time_since_epoch()).count();
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
  auto node = std::make_shared<rclcpp::Node>("srtra_fmi_master");

  const std::string fmu_dir = node->declare_parameter<std::string>("fmu_dir", "");
  const std::string model = node->declare_parameter<std::string>("model_identifier", "thermal_pennes");
  const std::string token = node->declare_parameter<std::string>("instantiation_token", "");
  const std::int64_t duration_s = node->declare_parameter<std::int64_t>("duration_s", 600);
  const std::int64_t base_step_ms = node->declare_parameter<std::int64_t>("base_step_ms", 10);
  const std::int64_t fmu_step_ms = node->declare_parameter<std::int64_t>("fmu_step_ms", 100);
  const std::string timer_mode = node->declare_parameter<std::string>("timer_mode", "high_resolution");
  const std::string participant_name = node->declare_parameter<std::string>("participant_name", "thermal_pennes");

  if (fmu_dir.empty() || token.empty()) {
    std::fprintf(stderr, "fmi_master_node: fmu_dir and instantiation_token are required\n");
    rclcpp::shutdown();
    return 1;
  }
  if (base_step_ms <= 0 || fmu_step_ms <= 0 || duration_s <= 0) {
    std::fprintf(stderr, "fmi_master_node: durations and steps must be positive\n");
    rclcpp::shutdown();
    return 1;
  }

  const std::string dll_path = fmu_dir + "/binaries/x86_64-windows/" + model + ".dll";
  std::string error;
  std::unique_ptr<srtra_fmi_master::FmuParticipant> fmu = srtra_fmi_master::FmuParticipant::create(
    dll_path, token, participant_name, error);
  if (!fmu) {
    std::fprintf(stderr, "fmi_master_node: %s\n", error.c_str());
    rclcpp::shutdown();
    return 1;
  }

  const Ns base_ns = base_step_ms * 1000000;
  const Ns fmu_step_ns = fmu_step_ms * 1000000;
  const Ns run_ns = duration_s * 1000000000;

  srtra_fmi_master::ParticipantConfig config;
  config.name = participant_name;
  config.participant = fmu.get();
  config.period_ns = fmu_step_ns;
  config.offset_ns = 0;
  config.fixed_step_ns = fmu_step_ns;
  config.output_value_references = {kVrTmax, kVrTmean, kVrV60, kVrVlesion};

  std::vector<srtra_fmi_master::Stimulus> stimuli = {
    {0, kVrPowerInput, power_profile_w},
    {0, kVrHbcInput, zero_input},
    {0, kVrEnvInput, ambient_k},
  };

  std::unique_ptr<srtra_fmi_master::Scheduler> scheduler;
  try {
    scheduler = std::make_unique<srtra_fmi_master::Scheduler>(
      base_ns, std::vector<srtra_fmi_master::ParticipantConfig>{config},
      std::vector<srtra_fmi_master::Wire>{}, stimuli);
  } catch (const std::invalid_argument & e) {
    std::fprintf(stderr, "fmi_master_node: %s\n", e.what());
    rclcpp::shutdown();
    return 1;
  }
  srtra_fmi_master::Status status = scheduler->initialize();
  if (!status.ok()) {
    std::fprintf(stderr, "fmi_master_node: initialize failed: %s (%s)\n", status.message, status.detail);
    rclcpp::shutdown();
    return 2;
  }

  auto clock_pub = node->create_publisher<srtra_fmi_master::msg::MasterClock>(
    "/srtra/fmi/master/clock", rclcpp::QoS(rclcpp::KeepLast(1000)).reliable());
  auto state_pub = node->create_publisher<srtra_fmi_master::msg::ParticipantState>(
    "/srtra/fmi/participant/" + participant_name, rclcpp::QoS(rclcpp::KeepLast(1000)).reliable());

  // Wait for both subscribers (up to 30 s) so the first tick is not published into an empty topic.
  const auto subscriber_deadline = SteadyClock::now() + std::chrono::seconds(30);
  while ((clock_pub->get_subscription_count() == 0 || state_pub->get_subscription_count() == 0) &&
    SteadyClock::now() < subscriber_deadline)
  {
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }

  srtra_fmi_master::TickWaiter waiter(timer_mode == "high_resolution");

  // Anchor pair, read once at start (bridge v3 pattern): system clock and steady clock together.
  const std::int64_t anchor_system_ns = system_now_ns();
  const std::int64_t anchor_steady_ns = steady_now_ns();
  const SteadyClock::time_point start = SteadyClock::now() + std::chrono::milliseconds(200);

  srtra_fmi_master::msg::MasterClock clock_msg;
  srtra_fmi_master::msg::ParticipantState state_msg;
  state_msg.participant = participant_name;
  const std::uint64_t ticks = static_cast<std::uint64_t>(run_ns / base_ns);

  std::uint64_t late_ticks = 0;
  Ns max_lateness_ns = 0;
  int exit_code = 0;
  std::string failure;

  for (std::uint64_t k = 0; k < ticks; ++k) {
    const Ns tick_ns = static_cast<Ns>(k) * base_ns;
    const SteadyClock::time_point target = start + std::chrono::nanoseconds(tick_ns);
    waiter.wait_until(target);

    status = scheduler->advance_to(tick_ns);
    if (!status.ok()) {
      failure = std::string(status.message) + ": " + status.detail;
      exit_code = 2;
      break;
    }

    // Source stamp: steady clock immediately before publish. It is the value that goes in header.stamp.
    const std::int64_t stamp_ns = steady_now_ns();
    const Ns lateness = stamp_ns - std::chrono::duration_cast<std::chrono::nanoseconds>(
      target.time_since_epoch()).count();
    if (lateness > kLatenessBoundNs) {
      ++late_ticks;
    }
    if (lateness > max_lateness_ns) {
      max_lateness_ns = lateness;
    }
    const std::int64_t scheduled_steady_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
      target.time_since_epoch()).count();

    set_stamp(clock_msg.header.stamp, stamp_ns);
    clock_msg.header.frame_id = "srtra_master";
    clock_msg.tick = k;
    clock_msg.master_time_ns = static_cast<std::uint64_t>(tick_ns);
    clock_msg.scheduled_steady_ns = static_cast<std::uint64_t>(scheduled_steady_ns);
    clock_pub->publish(clock_msg);

    set_stamp(state_msg.header.stamp, stamp_ns);
    state_msg.header.frame_id = "srtra_master";
    state_msg.tick = k;
    state_msg.steps = scheduler->step_count(0);
    state_msg.fmu_time_s = static_cast<double>(state_msg.steps) * static_cast<double>(fmu_step_ns) / 1.0e9;
    state_msg.t_max_k = scheduler->output(0, 0);
    state_msg.t_mean_k = scheduler->output(0, 1);
    state_msg.v60_mm3 = scheduler->output(0, 2);
    state_msg.v_lesion_mm3 = scheduler->output(0, 3);
    state_pub->publish(state_msg);
  }

  std::printf(
    "{\"schema\":\"srtra-fmi-master-run/1\",\"exit_code\":%d,\"failure\":\"%s\","
    "\"timer_mechanism\":\"%s\",\"base_step_ns\":%lld,\"fmu_step_ns\":%lld,"
    "\"ticks_planned\":%llu,\"fmu_steps\":%llu,\"late_ticks_over_1ms\":%llu,"
    "\"max_lateness_ns\":%lld,\"anchor_system_ns\":%lld,\"anchor_steady_ns\":%lld,"
    "\"participant\":\"%s\"}\n",
    exit_code, failure.c_str(), waiter.mechanism(),
    static_cast<long long>(base_ns), static_cast<long long>(fmu_step_ns),
    static_cast<unsigned long long>(ticks),
    static_cast<unsigned long long>(scheduler->step_count(0)),
    static_cast<unsigned long long>(late_ticks), static_cast<long long>(max_lateness_ns),
    static_cast<long long>(anchor_system_ns), static_cast<long long>(anchor_steady_ns),
    participant_name.c_str());

  rclcpp::shutdown();
  return exit_code;
}
