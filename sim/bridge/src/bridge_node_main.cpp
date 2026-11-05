// SPDX-License-Identifier: MIT
#include <exception>
#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "srtra_bridge/bridge_node.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  int status = 0;
  try {
    auto node = std::make_shared<srtra_bridge::BridgeNode>(rclcpp::NodeOptions());
    node->run();
  } catch (const std::exception & e) {
    RCLCPP_FATAL(rclcpp::get_logger("srtra_bridge"), "bridge_node failed: %s", e.what());
    status = 1;
  }
  rclcpp::shutdown();
  return status;
}
