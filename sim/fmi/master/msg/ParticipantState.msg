# SPDX-License-Identifier: MIT
# Participant state after the schedule at this tick (SRS FR-MS-007). Outputs are held between FMU step points.
std_msgs/Header header
uint64 tick
uint64 steps
string participant
float64 fmu_time_s
float64 t_max_k
float64 t_mean_k
float64 v60_mm3
float64 v_lesion_mm3
