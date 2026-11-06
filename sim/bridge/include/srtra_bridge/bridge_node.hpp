// SPDX-License-Identifier: MIT
#ifndef SRTA_BRIDGE__BRIDGE_NODE_HPP_
#define SRTA_BRIDGE__BRIDGE_NODE_HPP_

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "builtin_interfaces/msg/time.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "geometry_msgs/msg/wrench_stamped.hpp"
#include "rclcpp/rclcpp.hpp"
#include "srtra_bridge/msg/mesh_deformation_state.hpp"

namespace srtra_bridge
{

constexpr char kTopicToolTipPose[] = "/srtra/bridge/tool_tip_pose";
constexpr char kTopicToolWrench[] = "/srtra/bridge/tool_wrench";
constexpr char kTopicMeshDeformation[] = "/srtra/bridge/mesh_deformation";

// Modal coefficients per tick in synthetic mode. Must not exceed the MeshDeformationState bound
// of 16.
constexpr std::size_t kModeCount = 8U;
constexpr std::size_t kModeCountMax = 16U;
constexpr std::size_t kQueueDepth = 100U;
constexpr int kMinRateHz = 1;
constexpr int kMaxRateHz = 1000;

// One row of a replay capture (schema in sim/bridge/README.md). The table is preallocated from
// the file at load, so the publish loop does not allocate replay data.
struct ReplayRow
{
  std::array<double, 3> position;
  std::array<double, 4> orientation;
  std::array<double, 3> force;
  std::array<double, 3> torque;
  std::array<float, kModeCountMax> modes;
};

class BridgeNode : public rclcpp::Node
{
public:
  explicit BridgeNode(const rclcpp::NodeOptions & options);

  // Publishes one pose, one wrench, and one mesh state per tick until rclcpp::ok() is false,
  // duration_s elapses, or (replay without loop) the capture ends. Returns the number of ticks
  // published.
  std::uint64_t run();

private:
  void fill_tick(std::uint64_t tick, const builtin_interfaces::msg::Time & stamp);
  void fill_replay_tick(std::uint64_t tick, const builtin_interfaces::msg::Time & stamp);
  void publish_tick();
  void wait_for_matched_subscribers();
  void load_replay_file();

  std::int64_t rate_hz_;
  std::int64_t duration_s_;
  std::int64_t period_ns_;
  std::string reference_frame_;
  std::uint32_t mesh_node_count_;
  bool wait_for_subscribers_;
  bool prefer_high_resolution_;
  bool replay_;
  bool replay_loop_;
  std::string replay_file_;
  std::size_t mode_count_;
  std::vector<ReplayRow> replay_rows_;

  rclcpp::Publisher<geometry_msgs::msg::PoseStamped>::SharedPtr pose_pub_;
  rclcpp::Publisher<geometry_msgs::msg::WrenchStamped>::SharedPtr wrench_pub_;
  rclcpp::Publisher<srtra_bridge::msg::MeshDeformationState>::SharedPtr mesh_pub_;

  geometry_msgs::msg::PoseStamped pose_msg_;
  geometry_msgs::msg::WrenchStamped wrench_msg_;
  srtra_bridge::msg::MeshDeformationState mesh_msg_;

  std::uint64_t late_ticks_;
};

}  // namespace srtra_bridge

#endif  // SRTA_BRIDGE__BRIDGE_NODE_HPP_
