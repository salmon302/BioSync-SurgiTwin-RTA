// SPDX-License-Identifier: MIT
#include "srtra_bridge/bridge_node.hpp"

#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <thread>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <mmsystem.h>
#endif

namespace srtra_bridge
{

namespace
{

constexpr double kTwoPi = 6.283185307179586;
constexpr double kPathHz = 0.2;
constexpr std::int64_t kNanosPerSecond = 1000000000LL;
constexpr std::chrono::seconds kSubscriberWaitLimit(30);

// The default Windows timer resolution is about 15.6 ms, which is coarser than a 2 ms tick.
// This guard raises the resolution to 1 ms for the lifetime of the publish loop.
class TimerResolutionGuard
{
public:
  TimerResolutionGuard()
  {
#ifdef _WIN32
    timeBeginPeriod(1U);
#endif
  }
  ~TimerResolutionGuard()
  {
#ifdef _WIN32
    timeEndPeriod(1U);
#endif
  }
  TimerResolutionGuard(const TimerResolutionGuard &) = delete;
  TimerResolutionGuard & operator=(const TimerResolutionGuard &) = delete;
};

}  // namespace

BridgeNode::BridgeNode(const rclcpp::NodeOptions & options)
: Node("srtra_bridge", options),
  rate_hz_(declare_parameter<std::int64_t>("rate_hz", 500)),
  duration_s_(declare_parameter<std::int64_t>("duration_s", 0)),
  period_ns_(0),
  reference_frame_(declare_parameter<std::string>("reference_frame", "srtra_world")),
  mesh_node_count_(0U),
  wait_for_subscribers_(declare_parameter<bool>("wait_for_subscribers", true)),
  late_ticks_(0U)
{
  if (rate_hz_ < kMinRateHz || rate_hz_ > kMaxRateHz) {
    throw std::invalid_argument("rate_hz must be in [1, 1000]");
  }
  if (duration_s_ < 0) {
    throw std::invalid_argument("duration_s must be 0 (unbounded) or positive");
  }
  const std::int64_t node_count = declare_parameter<std::int64_t>("mesh_node_count", 4096);
  if (node_count <= 0 || node_count > static_cast<std::int64_t>(UINT32_MAX)) {
    throw std::invalid_argument("mesh_node_count must be in [1, 4294967295]");
  }
  mesh_node_count_ = static_cast<std::uint32_t>(node_count);
  period_ns_ = kNanosPerSecond / rate_hz_;

  const rclcpp::QoS qos = rclcpp::QoS(rclcpp::KeepLast(kQueueDepth)).reliable();
  pose_pub_ = create_publisher<geometry_msgs::msg::PoseStamped>(kTopicToolTipPose, qos);
  wrench_pub_ = create_publisher<geometry_msgs::msg::WrenchStamped>(kTopicToolWrench, qos);
  mesh_pub_ = create_publisher<srtra_bridge::msg::MeshDeformationState>(kTopicMeshDeformation, qos);

  pose_msg_.header.frame_id = reference_frame_;
  wrench_msg_.header.frame_id = reference_frame_;
  mesh_msg_.header.frame_id = reference_frame_;
  mesh_msg_.reference_frame = reference_frame_;
  mesh_msg_.node_count = mesh_node_count_;
  mesh_msg_.mode_coefficients.assign(kModeCount, 0.0F);

  RCLCPP_INFO(
    get_logger(), "bridge configured: rate_hz=%lld duration_s=%lld reference_frame=%s mesh_node_count=%u",
    static_cast<long long>(rate_hz_), static_cast<long long>(duration_s_), reference_frame_.c_str(),
    mesh_node_count_);
}

void BridgeNode::fill_tick(std::uint64_t tick, const builtin_interfaces::msg::Time & stamp)
{
  const double t = static_cast<double>(tick) / static_cast<double>(rate_hz_);
  const double w = kTwoPi * kPathHz * t;

  const double yaw = 0.3 * std::sin(w);
  pose_msg_.header.stamp = stamp;
  pose_msg_.pose.position.x = 0.02 * std::sin(w);
  pose_msg_.pose.position.y = 0.01 * std::sin(2.0 * w);
  pose_msg_.pose.position.z = 0.10 + 0.005 * std::cos(w);
  pose_msg_.pose.orientation.x = 0.0;
  pose_msg_.pose.orientation.y = 0.0;
  pose_msg_.pose.orientation.z = std::sin(0.5 * yaw);
  pose_msg_.pose.orientation.w = std::cos(0.5 * yaw);

  wrench_msg_.header.stamp = stamp;
  wrench_msg_.wrench.force.x = 1.5 * std::sin(w + 0.5);
  wrench_msg_.wrench.force.y = 0.8 * std::cos(w);
  wrench_msg_.wrench.force.z = 2.0 + 0.5 * std::sin(2.0 * w);
  wrench_msg_.wrench.torque.x = 0.02 * std::cos(w);
  wrench_msg_.wrench.torque.y = 0.01 * std::sin(2.0 * w);
  wrench_msg_.wrench.torque.z = 0.005 * std::sin(w + 1.0);

  mesh_msg_.header.stamp = stamp;
  mesh_msg_.tick = tick;
  for (std::size_t k = 0U; k < kModeCount; ++k) {
    const double f = static_cast<double>(k + 1U);
    mesh_msg_.mode_coefficients[k] = static_cast<float>((0.002 / f) * std::sin(f * w + 0.3 * f));
  }
}

void BridgeNode::publish_tick()
{
  pose_pub_->publish(pose_msg_);
  wrench_pub_->publish(wrench_msg_);
  mesh_pub_->publish(mesh_msg_);
}

void BridgeNode::wait_for_matched_subscribers()
{
  using Clock = std::chrono::steady_clock;
  const Clock::time_point deadline = Clock::now() + kSubscriberWaitLimit;
  while (rclcpp::ok() &&
    (pose_pub_->get_subscription_count() == 0U || wrench_pub_->get_subscription_count() == 0U ||
    mesh_pub_->get_subscription_count() == 0U))
  {
    if (Clock::now() > deadline) {
      throw std::runtime_error("no subscriber matched all three topics within 30 s");
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  RCLCPP_INFO(get_logger(), "matched subscribers on all three topics, starting tick schedule");
}

std::uint64_t BridgeNode::run()
{
  using Clock = std::chrono::steady_clock;
  const TimerResolutionGuard timer_guard;
  const std::chrono::nanoseconds period(period_ns_);
  const std::chrono::nanoseconds limit(static_cast<std::int64_t>(duration_s_) * kNanosPerSecond);

  if (wait_for_subscribers_) {
    wait_for_matched_subscribers();
  }

  const Clock::time_point start = Clock::now();
  Clock::time_point next = start;
  std::uint64_t tick = 0U;

  while (rclcpp::ok()) {
    if (duration_s_ > 0 && (next - start) >= limit) {
      break;
    }
    std::this_thread::sleep_until(next);
    if (!rclcpp::ok()) {
      break;
    }
    if (Clock::now() - next >= period) {
      ++late_ticks_;
    }

    const rclcpp::Time now = get_clock()->now();
    const builtin_interfaces::msg::Time stamp = now;
    fill_tick(tick, stamp);
    publish_tick();

    ++tick;
    next += period;
  }

  const double elapsed_s =
    std::chrono::duration<double>(Clock::now() - start).count();
  RCLCPP_INFO(
    get_logger(), "publish loop finished: ticks=%llu late_ticks=%llu elapsed_s=%.3f",
    static_cast<unsigned long long>(tick), static_cast<unsigned long long>(late_ticks_),
    elapsed_s);
  return tick;
}

}  // namespace srtra_bridge
