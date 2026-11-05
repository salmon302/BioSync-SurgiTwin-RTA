# SPDX-License-Identifier: MIT
# ROS 2 bridge package for SurgiTwin-RTA (SRS FR-MS-004).
# Build with colcon from the pixi environment: see sim/bridge/build.ps1 and sim/bridge/README.md.
# The root option SRTA_BUILD_BRIDGE gates add_subdirectory(sim/bridge) in the top-level CMakeLists.txt.
# This package requires ament_cmake from the ROS 2 Jazzy environment (env/ros2-jazzy).
cmake_minimum_required(VERSION 3.22)
project(srtra_bridge)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()
if(NOT CMAKE_BUILD_TYPE MATCHES "^(Release|RelWithDebInfo)$")
  message(FATAL_ERROR "srtra_bridge: CMAKE_BUILD_TYPE must be Release or RelWithDebInfo for ABI compatibility with the pinned ROS 2 binaries (got '${CMAKE_BUILD_TYPE}')")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MeshDeformationState.msg"
  DEPENDENCIES std_msgs
)

rosidl_get_typesupport_target(srtra_bridge_cpp_typesupport
  ${PROJECT_NAME} rosidl_typesupport_cpp)

add_executable(bridge_node
  src/bridge_node.cpp
  src/bridge_node_main.cpp
)
target_include_directories(bridge_node PRIVATE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_compile_features(bridge_node PRIVATE cxx_std_17)
if(MSVC)
  target_compile_options(bridge_node PRIVATE /W4 /permissive-)
  target_link_libraries(bridge_node winmm)
endif()
ament_target_dependencies(bridge_node
  geometry_msgs
  rclcpp
  std_msgs
)
target_link_libraries(bridge_node "${srtra_bridge_cpp_typesupport}")

install(TARGETS bridge_node
  DESTINATION lib/${PROJECT_NAME}
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
