# Virtual Proving Ground (M&S Tier)

Status: placeholder. No simulation code is implemented yet.

This tier holds the real-time soft-tissue physics and physiological simulation that feeds the RTA and Informatics tiers.

* `sofa/`: SOFA FEM scenes and plugins (SRS FR-MS-002, FR-MS-003)
* `pulse/`: Kitware Pulse Physiology co-simulation bridge. The Python side lands in `middleware/` (SRS FR-MS-006)
* `fmi/`: FMI 3.0 FMU packaging and co-simulation master (SRS FR-MS-007)
* `bridge/`: ROS 2 bridge node over Fast DDS (SRS FR-MS-004)

The CMake stubs in `sofa/`, `fmi/`, and `bridge/` are gated by the `SRTA_BUILD_SOFA`, `SRTA_BUILD_FMI`, and `SRTA_BUILD_BRIDGE` options, which default to OFF.
