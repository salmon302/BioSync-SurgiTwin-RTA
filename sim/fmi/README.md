# FMI 3.0 FMU Packaging and Co-Simulation Master

Status: placeholder.

This directory will hold FMU packaging for the thermal, mechanical, and physiological plant models, plus the co-simulation master that uses FMI 3.0 clocks and scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer (SRS FR-MS-007, VAL-028). The master holds clock skew and message jitter to at most 1 ms each. The build stub is `CMakeLists.txt`, enabled with `-DSRTA_BUILD_FMI=ON`.
