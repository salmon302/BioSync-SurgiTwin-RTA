# SPDX-License-Identifier: MIT
# Master clock tick (SRS FR-MS-007). One message per master base tick.
# header.stamp is the master steady-clock source stamp (ns since the steady clock epoch) taken immediately before publish.
std_msgs/Header header
uint64 tick
uint64 master_time_ns
uint64 scheduled_steady_ns
