# SPDX-License-Identifier: MIT
# FMI 3.0 co-simulation master (SRS FR-MS-007, plan task 2.8 slice 1).
# Build with colcon from the pixi environment: see sim/fmi/master/build.ps1 and sim/fmi/master/README.md.
cmake_minimum_required(VERSION 3.22)
project(srtra_fmi_master)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()
if(NOT CMAKE_BUILD_TYPE MATCHES "^(Release|RelWithDebInfo)$")
  message(FATAL_ERROR "srtra_fmi_master: CMAKE_BUILD_TYPE must be Release or RelWithDebInfo for ABI compatibility with the pinned ROS 2 binaries (got '${CMAKE_BUILD_TYPE}')")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(SRTA_FMI_MASTER_BUILD_TESTS "Build the Catch2 scheduler tests (pinned Catch2 v3.9.1)" ON)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MasterClock.msg"
  "msg/ParticipantState.msg"
  DEPENDENCIES std_msgs
)
rosidl_get_typesupport_target(srtra_fmi_master_cpp_typesupport
  ${PROJECT_NAME} rosidl_typesupport_cpp)

# The FMI 3.0.2 headers are pinned in sim/fmi/include/fmi3 (sim/SOUP.md). Only the FMU adapter uses them.
set(SRTA_FMI_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../include/fmi3")

# Core library: no ROS dependency. Scheduler, participant interface, FMU adapter.
add_library(srtra_fmi_core STATIC
  src/scheduler.cpp
  src/fmu_participant.cpp
)
target_include_directories(srtra_fmi_core
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  PRIVATE ${SRTA_FMI_INCLUDE_DIR}
)
target_compile_features(srtra_fmi_core PUBLIC cxx_std_17)
if(MSVC)
  target_compile_options(srtra_fmi_core PRIVATE /W4 /WX /permissive-)
endif()

# ROS 2 node: master clock and participant state publisher over Fast DDS.
add_executable(fmi_master_node src/master_node.cpp)
target_include_directories(fmi_master_node PRIVATE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_compile_features(fmi_master_node PRIVATE cxx_std_17)
if(MSVC)
  target_compile_options(fmi_master_node PRIVATE /W4 /permissive-)
  target_link_libraries(fmi_master_node winmm)
endif()
ament_target_dependencies(fmi_master_node rclcpp std_msgs)
target_link_libraries(fmi_master_node srtra_fmi_core "${srtra_fmi_master_cpp_typesupport}")

install(TARGETS fmi_master_node
  DESTINATION lib/${PROJECT_NAME}
)

if(SRTA_FMI_MASTER_BUILD_TESTS)
  include(FetchContent)
  # Catch2 v3.9.1, BSL-1.0. The archive hash is recorded in sim/SOUP.md.
  FetchContent_Declare(Catch2
    URL https://github.com/catchorg/Catch2/archive/refs/tags/v3.9.1.tar.gz
    URL_HASH SHA256=A215C2A723BD7483EFD236DC86066842A389CB4E344C61119C978ACDF24D39BE
  )
  set(CATCH_INSTALL_DOCS OFF CACHE BOOL "" FORCE)
  set(CATCH_INSTALL_EXTRAS OFF CACHE BOOL "" FORCE)
  set(CATCH_INSTALL_HELPERS OFF CACHE BOOL "" FORCE)
  # The ROS 2 environment sets BUILD_SHARED_LIBS, which would build Catch2 as DLLs next to the test.
  set(BUILD_SHARED_LIBS OFF)
  FetchContent_MakeAvailable(Catch2)

  enable_testing()
  add_executable(srtra_fmi_master_tests tests/test_scheduler.cpp)
  target_compile_features(srtra_fmi_master_tests PRIVATE cxx_std_17)
  target_link_libraries(srtra_fmi_master_tests PRIVATE srtra_fmi_core Catch2::Catch2WithMain)
  add_test(NAME srtra_fmi_master_tests COMMAND srtra_fmi_master_tests)
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
