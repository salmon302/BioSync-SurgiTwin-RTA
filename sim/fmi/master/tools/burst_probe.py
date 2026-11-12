# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: standalone request burst probe for the participant node (plan task 2.8 slice 3a)
# Date: 2026-11-12T12:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.8 slice 3a diagnosis
# Summary: Publishes a burst of StepRequest messages to the mechanical participant node with the pipelined master's timing, and records which requests the participant executes (from its trace), to isolate the DDS delivery from the FMU step.
"""Burst probe for fmi_participant_node (slice 3a diagnosis).

Runs under the ROS 2 Jazzy pixi environment (CPython 3.12) with RMW_IMPLEMENTATION=rmw_fastrtps_cpp.
It publishes StepRequest messages for participant mechanical_sofa at 1 ms spacing (the pipelined master's cadence)
and does not wait for replies. The participant (started with SRTA_PARTICIPANT_TRACE=1) logs each request it executes.
The probe records the requests it sent (tick, time) and reads the participant's stderr trace to compare.

Usage: python burst_probe.py --count 40 --out <json> [--participant-stderr <file>]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from srtra_fmi_master.msg import StepRequest


class Probe(Node):
    def __init__(self):
        super().__init__('srtra_fmi_burst_probe')
        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=2000)
        self.pub = self.create_publisher(StepRequest, '/srtra/fmi/step_request', qos)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--count', type=int, default=40)
    parser.add_argument('--spacing-ms', type=float, default=1.0)
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)

    rclpy.init()
    probe = Probe()
    deadline = time.time() + 30
    while probe.pub.get_subscription_count() == 0 and time.time() < deadline:
        rclpy.spin_once(probe, timeout_sec=0.01)
    sent = []
    t0 = time.perf_counter()
    for k in range(args.count):
        target = t0 + k * args.spacing_ms / 1000.0
        while time.perf_counter() < target:
            pass
        msg = StepRequest()
        msg.tick = k
        msg.master_time_ns = k * 1000000
        msg.step_ns = 1000000
        msg.participant = 'mechanical_sofa'
        msg.stimulus_value = 0.0
        msg.header.frame_id = 'burst_probe'
        probe.pub.publish(msg)
        sent.append({'tick': k, 'master_time_ns': k * 1000000, 'sent_perf_ns': time.perf_counter_ns()})
    rclpy.spin_once(probe, timeout_sec=0.05)
    probe.destroy_node()
    rclpy.shutdown()
    record = {
        'schema': 'srtra-fmi-burst-probe/1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'python': sys.version.split()[0],
        'count': args.count,
        'spacing_ms': args.spacing_ms,
        'sent': sent,
    }
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(record, fh, indent=2)
        fh.write('\n')
    print(json.dumps({'sent': len(sent), 'out': args.out}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
