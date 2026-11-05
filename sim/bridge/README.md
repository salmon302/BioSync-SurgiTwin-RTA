# ROS 2 Bridge Node (Fast DDS)

Status: placeholder.

This directory will hold a native ROS 2 bridge node, built against the pinned ROS 2 Jazzy environment on Windows (RoboStack, `rmw_fastrtps_cpp`). The node publishes tool-tip poses, mesh deformation state, and 6-axis wrench data to ROS 2 nodes over Fast DDS (SRS FR-MS-004, VAL-027 Option B). The SlicerROS2 module is not used, and no WSL2 build is required.

The build stub is `CMakeLists.txt`, enabled with `-DSRTA_BUILD_BRIDGE=ON`.
