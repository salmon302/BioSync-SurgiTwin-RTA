# SPDX-License-Identifier: MIT
# Reply to a StepRequest (SRS FR-MS-007, plan task 2.8 slice 2). header.stamp is the participant steady-clock stamp
# taken when the step finished and before the reply is published.
std_msgs/Header header
uint64 tick
string participant
uint64 request_received_steady_ns
uint64 step_done_steady_ns
float64 output_0
float64 output_1
float64 output_2
