# SPDX-License-Identifier: MIT
# Modal deformation state of the volumetric mesh at one publish tick.
# Size budget: header (about 40 bytes with frame_id), tick (8), node_count (4),
# reference_frame (about 20 bytes), and at most 16 float32 coefficients (64 bytes).
# The serialized message stays under 200 bytes at 500 Hz (about 100 kB/s).
std_msgs/Header header
# Publish tick index. Starts at 0 for each node run and increases by 1 per tick.
uint64 tick
# Reference frame of the modal coefficients. Equal to header.frame_id.
string reference_frame
# Number of mesh nodes that the modal basis represents.
uint32 node_count
# Modal amplitude coefficients, in meters. The bound is 16 entries.
float32[<=16] mode_coefficients
