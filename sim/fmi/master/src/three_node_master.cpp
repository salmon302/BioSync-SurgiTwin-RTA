// SPDX-License-Identifier: MIT
// fmi_three_node_master: node 1 of the three-node G2.6 run (SRS FR-MS-007, plan task 2.8 slice 2). It owns the
// master clock and the thermal FMU. The mechanical and Pulse FMUs run on nodes 2 and 3 (fmi_participant_node) and
// are stepped by request over Fast DDS: at each step point of their schedule, the master publishes a StepRequest and
// does not advance the tick until the matching StepReply arrives.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <map>
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
#include "srtra_fmi_master/msg/step_reply.hpp"
#include "srtra_fmi_master/msg/step_request.hpp"
#include "srtra_fmi_master/pipelined_exchange.hpp"

namespace
{

using SteadyClock = std::chrono::steady_clock;
using srtra_fmi_master::Ns;

constexpr Ns kBaseNs = 1000000;       // 1 ms master tick (mechanical DoStep step)
constexpr Ns kThermalNs = 100000000;  // 0.1 s
constexpr Ns kPulseNs = 10000000;     // 0.01 s
constexpr Ns kMechanicalNs = 1000000; // 0.001 s

constexpr std::uint32_t kThermalPowerIn = 11;
constexpr std::uint32_t kThermalHbcIn = 12;
constexpr std::uint32_t kThermalEnvIn = 13;

double power_profile_w(Ns t_ns) { return t_ns < 30000000000LL ? 5.0 : 0.0; }
double zero_input(Ns) { return 0.0; }
double ambient_k(Ns) { return 310.15; }

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
  auto node = std::make_shared<rclcpp::Node>("srtra_fmi_three_node_master");

  const std::string fmu_root = node->declare_parameter<std::string>("fmu_root", "");
  const std::int64_t duration_s = node->declare_parameter<std::int64_t>("duration_s", 600);
  const std::int64_t reply_timeout_ms = node->declare_parameter<std::int64_t>("reply_timeout_ms", 5000);
  // 1 = pipelined remote steps (VAL-033 slice 3); 0 = serialized remote steps (slice 2 attempt 1, kept for comparison).
  const std::int64_t pipelined_flag = node->declare_parameter<std::int64_t>("pipelined", 1);
  const bool pipelined = pipelined_flag != 0;

  if (fmu_root.empty() || duration_s <= 0) {
    std::fprintf(stderr, "fmi_three_node_master: fmu_root and a positive duration_s are required\n");
    rclcpp::shutdown();
    return 1;
  }

  std::string error;
  auto thermal = srtra_fmi_master::FmuParticipant::create(
    fmu_root + "/thermal_pennes/binaries/x86_64-windows/thermal_pennes.dll",
    "5d6f2a8e-3c1b-4f7a-9e2d-7b8c0a1f4e63", "thermal_pennes", error, "");
  if (!thermal) { std::fprintf(stderr, "thermal: %s\n", error.c_str()); rclcpp::shutdown(); return 1; }

  // Remote participants (nodes 2 and 3). The master keeps their schedule and wires; the FMU runs in the participant node.
  // Scheduler index 1 = mechanical, index 2 = Pulse. A null participant pointer is refused by the scheduler, so the
  // remote entries use a local proxy that only records state (its do_step is driven by the request/reply exchange).
  struct Proxy : public srtra_fmi_master::Participant
  {
    bool initialize(double) override { return true; }
    bool set_real(std::uint32_t, double) override { return true; }
    bool get_real(std::uint32_t, double & v) override { v = 0.0; return true; }
    bool do_step(double, double) override { return true; }
    bool reset() override { return true; }
    const char * last_error() const override { return ""; }
  };
  Proxy mech_proxy;
  Proxy pulse_proxy;

  std::vector<srtra_fmi_master::ParticipantConfig> participants(3);
  participants[0].name = "thermal_pennes";
  participants[0].participant = thermal.get();
  participants[0].period_ns = kThermalNs;
  participants[0].fixed_step_ns = kThermalNs;
  participants[0].output_value_references = {20, 21, 22, 23};
  participants[1].name = "mechanical_sofa";
  participants[1].participant = &mech_proxy;
  participants[1].period_ns = kMechanicalNs;
  participants[1].fixed_step_ns = kMechanicalNs;
  participants[1].output_value_references = {20, 21, 22};
  participants[2].name = "pulse_physiology";
  participants[2].participant = &pulse_proxy;
  participants[2].period_ns = kPulseNs;
  participants[2].fixed_step_ns = kPulseNs;
  participants[2].output_value_references = {20, 24, 26};

  std::vector<srtra_fmi_master::Stimulus> stimuli = {
    {0, kThermalPowerIn, power_profile_w},
    {0, kThermalHbcIn, zero_input},
    {0, kThermalEnvIn, ambient_k},
  };

  std::unique_ptr<srtra_fmi_master::Scheduler> scheduler;
  try {
    scheduler = std::make_unique<srtra_fmi_master::Scheduler>(
      kBaseNs, participants, std::vector<srtra_fmi_master::Wire>{}, stimuli);
  } catch (const std::invalid_argument & e) {
    std::fprintf(stderr, "fmi_three_node_master: %s\n", e.what());
    rclcpp::shutdown();
    return 1;
  }
  // The scheduler initializes the thermal FMU. The remote proxies are initialized by their nodes.
  srtra_fmi_master::Status status = scheduler->initialize();
  if (!status.ok()) {
    std::fprintf(stderr, "fmi_three_node_master: initialize failed: %s (%s)\n", status.message, status.detail);
    rclcpp::shutdown();
    return 2;
  }

  auto clock_pub = node->create_publisher<srtra_fmi_master::msg::MasterClock>(
    "/srtra/fmi/master/clock", rclcpp::QoS(rclcpp::KeepLast(4000)).reliable());
  auto request_pub = node->create_publisher<srtra_fmi_master::msg::StepRequest>(
    "/srtra/fmi/step_request", rclcpp::QoS(rclcpp::KeepLast(4000)).reliable());
  std::vector<rclcpp::Publisher<srtra_fmi_master::msg::ParticipantState>::SharedPtr> state_pubs;
  for (const auto & p : participants) {
    state_pubs.push_back(node->create_publisher<srtra_fmi_master::msg::ParticipantState>(
      "/srtra/fmi/participant/" + p.name, rclcpp::QoS(rclcpp::KeepLast(4000)).reliable()));
  }

  // Replies from the remote nodes, keyed by (participant, tick).
  std::map<std::string, std::map<std::uint64_t, srtra_fmi_master::msg::StepReply>> replies;
  auto reply_sub = node->create_subscription<srtra_fmi_master::msg::StepReply>(
    "/srtra/fmi/step_reply", rclcpp::QoS(rclcpp::KeepLast(4000)).reliable(),
    [&replies](srtra_fmi_master::msg::StepReply::SharedPtr msg) {
      replies[msg->participant][msg->tick] = *msg;
    });

  // Wait until each remote participant node has matched the request topic (two nodes) and the clock has a subscriber.
  const auto subscriber_deadline = SteadyClock::now() + std::chrono::seconds(60);
  while ((clock_pub->get_subscription_count() == 0 || request_pub->get_subscription_count() < 2) &&
    SteadyClock::now() < subscriber_deadline)
  {
    rclcpp::spin_some(node);
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  if (request_pub->get_subscription_count() < 2) {
    std::fprintf(stderr, "fmi_three_node_master: fewer than two participant nodes matched the request topic\n");
    rclcpp::shutdown();
    return 3;
  }

  srtra_fmi_master::TickWaiter waiter(true);
  const std::int64_t anchor_system_ns = system_now_ns();
  const std::int64_t anchor_steady_ns = steady_now_ns();
  const SteadyClock::time_point start = SteadyClock::now() + std::chrono::milliseconds(200);
  const SteadyClock::time_point wall_end = start + std::chrono::seconds(duration_s);

  srtra_fmi_master::msg::MasterClock clock_msg;
  srtra_fmi_master::msg::StepRequest req;
  std::uint64_t reply_timeouts = 0;
  std::uint64_t late_replies = 0;
  // Pipelined exchange state: one per remote participant (period 1 tick for mechanical, 10 for Pulse), the master
  // tick at which each step was requested, and the send stamp of each step.
  srtra_fmi_master::PipelinedExchange mech_ex(1);
  srtra_fmi_master::PipelinedExchange pulse_ex(10);
  std::map<std::string, std::map<std::uint64_t, std::uint64_t>> step_index_tick;
  std::map<std::string, std::map<std::uint64_t, std::int64_t>> step_sent_ns;
  std::uint64_t late_ticks = 0;
  Ns max_lateness_ns = 0;
  std::uint64_t remote_round_trips = 0;
  double remote_wait_ms_max = 0.0;
  double remote_wait_ms_sum = 0.0;
  double split_request_sum_ms = 0.0;
  double split_step_sum_ms = 0.0;
  double split_reply_sum_ms = 0.0;
  std::uint64_t split_count = 0;
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

    // Remote step points due at this tick.
    const bool mech_due = (tick_ns % kMechanicalNs) == 0;
    const bool pulse_due = (tick_ns % kPulseNs) == 0;
    std::vector<std::pair<std::string, Ns>> due;
    if (mech_due) due.push_back({"mechanical_sofa", kMechanicalNs});
    if (pulse_due) due.push_back({"pulse_physiology", kPulseNs});

    if (pipelined) {
      // Deliver any replies that arrived since the last tick. The subscription callback fills the reply map, so the
      // node must spin here (a non-blocking spin, not a wait).
      rclcpp::spin_some(node);
      // Pipelined (VAL-033 slice 3): at each step point, read the reply of the step in flight if it has arrived
      // (never wait), then request the next step. The reply of step s is read at the next step point after its
      // request, so the held value is one period stale (zero-order hold, see PipelinedExchange).
      for (const auto & d : due) {
        auto & ex = d.first == "mechanical_sofa" ? mech_ex : pulse_ex;
        if (ex.in_flight() >= 0) {
          auto by_participant = replies.find(d.first);
          const std::uint64_t step_index = static_cast<std::uint64_t>(ex.in_flight());
          if (by_participant != replies.end() && by_participant->second.count(step_index_tick[d.first][step_index])) {
            const auto & rep = by_participant->second[step_index_tick[d.first][step_index]];
            ex.receive_reply(step_index, rep.output_0);
            const double req_transit_ms = (static_cast<double>(rep.request_received_steady_ns) -
              static_cast<double>(step_sent_ns[d.first][step_index])) / 1.0e6;
            const double step_ms = (static_cast<double>(rep.step_done_steady_ns) -
              static_cast<double>(rep.request_received_steady_ns)) / 1.0e6;
            const double reply_transit_ms = (static_cast<double>(steady_now_ns()) -
              static_cast<double>(rep.step_done_steady_ns)) / 1.0e6;
            split_request_sum_ms += req_transit_ms;
            split_step_sum_ms += step_ms;
            split_reply_sum_ms += reply_transit_ms;
            ++split_count;
            ++remote_round_trips;
          } else {
            // The reply of the step in flight has not arrived. The step point is still due, so the master counts
            // this as a late reply and holds the previous value. It does not block.
            ++late_replies;
            const double age_ms = (static_cast<double>(steady_now_ns()) -
              static_cast<double>(step_sent_ns[d.first][step_index])) / 1.0e6;
            if (age_ms > static_cast<double>(reply_timeout_ms)) {
              ++reply_timeouts;
              failure = "reply timeout from " + d.first + " for step " + std::to_string(step_index);
              exit_code = 3;
              break;
            }
            continue;
          }
        }
        // Request the next step of this participant (the due step point).
        const std::uint64_t step_index = ex.requests_sent();
        if (!ex.request_sent(k)) {
          continue;
        }
        step_index_tick[d.first][step_index] = k;
        const std::int64_t sent_ns = steady_now_ns();
        step_sent_ns[d.first][step_index] = sent_ns;
        req = srtra_fmi_master::msg::StepRequest();
        req.tick = k;
        // The request time is the participant's own next step time (step index times step size), not the tick at
        // which the request is sent. A pipelined reply arrives after the step's duration, so the send tick runs ahead
        // of the FMU time; the participant must receive the FMU time it is due to step (see slice-3a diagnosis).
        req.master_time_ns = step_index * static_cast<std::uint64_t>(d.second);
        req.step_ns = static_cast<std::uint64_t>(d.second);
        req.participant = d.first;
        req.stimulus_value = 0.0;
        set_stamp(req.header.stamp, sent_ns);
        req.header.frame_id = "srtra_master";
        request_pub->publish(req);
      }
      if (exit_code != 0) {
        break;
      }
    } else {
    // Serialized mode (slice 2, kept for comparison): request, then wait inside the tick for the matching reply.
    for (const auto & d : due) {
      req = srtra_fmi_master::msg::StepRequest();
      req.tick = k;
      req.master_time_ns = static_cast<std::uint64_t>(tick_ns);
      req.step_ns = static_cast<std::uint64_t>(d.second);
      req.participant = d.first;
      req.stimulus_value = 0.0;
      const std::int64_t request_sent_ns = steady_now_ns();
      set_stamp(req.header.stamp, request_sent_ns);
      req.header.frame_id = "srtra_master";
      request_pub->publish(req);
      const SteadyClock::time_point wait_start = SteadyClock::now();
      bool got = false;
      while (!got) {
        rclcpp::spin_some(node);
        auto by_participant = replies.find(d.first);
        if (by_participant != replies.end() && by_participant->second.count(k)) {
          got = true;
          break;
        }
        const double waited_ms = std::chrono::duration<double, std::milli>(SteadyClock::now() - wait_start).count();
        if (waited_ms > static_cast<double>(reply_timeout_ms)) {
          break;
        }
        std::this_thread::sleep_for(std::chrono::microseconds(100));
      }
      const double waited_ms = std::chrono::duration<double, std::milli>(SteadyClock::now() - wait_start).count();
      if (!got) {
        ++reply_timeouts;
        failure = "reply timeout from " + d.first + " at tick " + std::to_string(k);
        exit_code = 3;
        break;
      }
      {
        // Split of the round trip (participant stamps): request transit (participant receive minus master send),
        // FMU step (step done minus receive), reply transit (master receive minus participant step done).
        const auto & rep = replies[d.first][k];
        const std::int64_t sent_ns = request_sent_ns;
        const double req_transit_ms = (static_cast<double>(rep.request_received_steady_ns) - static_cast<double>(sent_ns)) / 1.0e6;
        const double step_ms = (static_cast<double>(rep.step_done_steady_ns) - static_cast<double>(rep.request_received_steady_ns)) / 1.0e6;
        const double reply_transit_ms = (static_cast<double>(steady_now_ns()) - static_cast<double>(rep.step_done_steady_ns)) / 1.0e6;
        split_request_sum_ms += req_transit_ms;
        split_step_sum_ms += step_ms;
        split_reply_sum_ms += reply_transit_ms;
        ++split_count;
      }
      ++remote_round_trips;
      remote_wait_ms_sum += waited_ms;
      if (waited_ms > remote_wait_ms_max) remote_wait_ms_max = waited_ms;
    }
    if (exit_code != 0) {
      break;
    }
    }  // end serialized mode

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

    srtra_fmi_master::msg::ParticipantState state_msg;
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
    // Drop replies older than the current tick to bound memory (the map is keyed per participant).
    for (auto & entry : replies) {
      auto & by_tick = entry.second;
      while (!by_tick.empty() && by_tick.begin()->first + 1000 < k) {
        by_tick.erase(by_tick.begin());
      }
    }
  }

  const double remote_mean_ms = remote_round_trips > 0 ? remote_wait_ms_sum / static_cast<double>(remote_round_trips) : 0.0;
  std::printf(
    "{\"schema\":\"srtra-fmi-three-node-run/1\",\"exit_code\":%d,\"failure\":\"%s\","
    "\"ticks_run\":%llu,\"wall_duration_s\":%lld,\"late_ticks_over_1ms\":%llu,\"max_lateness_ns\":%lld,"
    "\"thermal_steps\":%llu,\"remote_round_trips\":%llu,\"remote_wait_mean_ms\":%.6f,\"remote_wait_max_ms\":%.6f,"
    "\"reply_timeouts\":%llu,\"late_replies\":%llu,\"pipelined\":%s,\"split_request_transit_mean_ms\":%.6f,\"split_fmu_step_mean_ms\":%.6f,"
    "\"split_reply_transit_mean_ms\":%.6f,\"anchor_system_ns\":%lld,\"anchor_steady_ns\":%lld}\n",
    exit_code, failure.c_str(), static_cast<unsigned long long>(k), static_cast<long long>(duration_s),
    static_cast<unsigned long long>(late_ticks), static_cast<long long>(max_lateness_ns),
    static_cast<unsigned long long>(scheduler->step_count(0)),
    static_cast<unsigned long long>(remote_round_trips), remote_mean_ms, remote_wait_ms_max,
    static_cast<unsigned long long>(reply_timeouts),
    static_cast<unsigned long long>(late_replies), pipelined ? "true" : "false",
    split_count > 0 ? split_request_sum_ms / static_cast<double>(split_count) : 0.0,
    split_count > 0 ? split_step_sum_ms / static_cast<double>(split_count) : 0.0,
    split_count > 0 ? split_reply_sum_ms / static_cast<double>(split_count) : 0.0,
    static_cast<long long>(anchor_system_ns), static_cast<long long>(anchor_steady_ns));

  rclcpp::shutdown();
  return exit_code;
}
