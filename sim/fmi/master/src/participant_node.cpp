// SPDX-License-Identifier: MIT
// fmi_participant_node: runs one FMU on its own node and answers the master's step requests over Fast DDS
// (SRS FR-MS-007, plan task 2.8 slice 2). Each request carries a tick and a stimulus; the node performs exactly one
// fmi3DoStep for it and replies with the outputs and its own stamps.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include "builtin_interfaces/msg/time.hpp"
#include "rclcpp/rclcpp.hpp"
#include "srtra_fmi_master/fmu_participant.hpp"
#include "srtra_fmi_master/msg/step_reply.hpp"
#include "srtra_fmi_master/msg/step_request.hpp"

namespace
{

using SteadyClock = std::chrono::steady_clock;

std::int64_t steady_now_ns()
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(SteadyClock::now().time_since_epoch()).count();
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
  auto node = std::make_shared<rclcpp::Node>("srtra_fmi_participant");

  const std::string fmu_root = node->declare_parameter<std::string>("fmu_root", "");
  const std::string model = node->declare_parameter<std::string>("model_identifier", "");
  const std::string token = node->declare_parameter<std::string>("instantiation_token", "");
  const std::string resource_dir = node->declare_parameter<std::string>("resource_dir", "");
  const std::int64_t duration_s = node->declare_parameter<std::int64_t>("duration_s", 600);
  // Output value references, one per reported output, written as "r0:20;r1:21;r2:22". The "r0:" prefix keeps the
  // parameter a non-numeric string (a bare numeric string faulted the process in the slice-2 bring-up).
  const std::string output_list = node->declare_parameter<std::string>("output_value_references", "");
  std::vector<std::uint32_t> output_refs;
  {
    std::string token_text;
    for (std::size_t i = 0; i <= output_list.size(); ++i) {
      if (i == output_list.size() || output_list[i] == ';') {
        const std::size_t colon = token_text.find(':');
        if (colon != std::string::npos) {
          output_refs.push_back(static_cast<std::uint32_t>(std::stoul(token_text.substr(colon + 1))));
        }
        token_text.clear();
      } else {
        token_text += output_list[i];
      }
    }
  }

  if (fmu_root.empty() || model.empty() || token.empty()) {
    std::fprintf(stderr, "fmi_participant_node: fmu_root, model_identifier, and instantiation_token are required\n");
    rclcpp::shutdown();
    return 1;
  }

  std::string error;
  auto fmu = srtra_fmi_master::FmuParticipant::create(
    fmu_root + "/" + model + "/binaries/x86_64-windows/" + model + ".dll", token, model, error, resource_dir);
  if (!fmu) {
    std::fprintf(stderr, "fmi_participant_node: %s\n", error.c_str());
    rclcpp::shutdown();
    return 1;
  }
  if (!fmu->initialize(0.0)) {
    std::fprintf(stderr, "fmi_participant_node: initialize failed for %s: %s\n", model.c_str(), fmu->last_error());
    rclcpp::shutdown();
    return 2;
  }

  auto reply_pub = node->create_publisher<srtra_fmi_master::msg::StepReply>(
    "/srtra/fmi/step_reply", rclcpp::QoS(rclcpp::KeepLast(2000)).reliable());

  std::uint64_t steps = 0;
  int exit_code = 0;
  const auto wall_end = SteadyClock::now() + std::chrono::seconds(duration_s + 60);

  auto request_sub = node->create_subscription<srtra_fmi_master::msg::StepRequest>(
    "/srtra/fmi/step_request", rclcpp::QoS(rclcpp::KeepLast(2000)).reliable(),
    [&](srtra_fmi_master::msg::StepRequest::SharedPtr req) {
      if (req->participant != model || exit_code != 0) {
        return;
      }
      const std::int64_t received_ns = steady_now_ns();
      // The FMU wrapper checks the time against the FMU step; the master owns the step grid.
      const double t_s = static_cast<double>(req->master_time_ns) / 1.0e9;
      const double h_s = static_cast<double>(req->step_ns) / 1.0e9;
      if (!fmu->do_step(t_s, h_s)) {
        std::fprintf(stderr, "fmi_participant_node: %s step failed: %s\n", model.c_str(), fmu->last_error());
        exit_code = 2;
        return;
      }
      ++steps;
      double out[3] = {0.0, 0.0, 0.0};
      for (int k = 0; k < 3; ++k) {
        if (k < static_cast<int>(output_refs.size()) && !fmu->get_real(output_refs[k], out[k])) {
          std::fprintf(stderr, "fmi_participant_node: %s get_real failed: %s\n", model.c_str(), fmu->last_error());
          exit_code = 2;
          return;
        }
      }
      srtra_fmi_master::msg::StepReply reply;
      reply.tick = req->tick;
      reply.participant = model;
      reply.request_received_steady_ns = static_cast<std::uint64_t>(received_ns);
      reply.step_done_steady_ns = static_cast<std::uint64_t>(steady_now_ns());
      reply.output_0 = out[0];
      reply.output_1 = out[1];
      reply.output_2 = out[2];
      set_stamp(reply.header.stamp, steady_now_ns());
      reply.header.frame_id = model;
      reply_pub->publish(reply);
    });

  while (rclcpp::ok() && SteadyClock::now() < wall_end && exit_code == 0) {
    rclcpp::spin_some(node);
    std::this_thread::sleep_for(std::chrono::microseconds(200));
  }

  std::printf("{\"schema\":\"srtra-fmi-participant-run/1\",\"participant\":\"%s\",\"exit_code\":%d,\"steps\":%llu}\n",
    model.c_str(), exit_code, static_cast<unsigned long long>(steps));
  rclcpp::shutdown();
  return exit_code;
}
