# SPDX-License-Identifier: MIT
# Co-simulation step request from the master to a participant node (SRS FR-MS-007, plan task 2.8 slice 2).
# The participant performs exactly one fmi3DoStep at master_time_ns with the given step, then replies on
# /srtra/fmi/step_reply with the same tick and the outputs it produced.
std_msgs/Header header
uint64 tick
uint64 master_time_ns
uint64 step_ns
string participant
float64 stimulus_value
