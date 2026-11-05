# SPDX-License-Identifier: MIT
"""Subscribe to the srtra_bridge streams and measure rate, presence, and drops.

Runs under the ROS 2 Jazzy pixi environment (CPython 3.12, env/ros2-jazzy) with
RMW_IMPLEMENTATION=rmw_fastrtps_cpp. Writes one JSON record to --out.

Each stream is matched per tick by header.stamp (the node gives the three
messages of one tick the same stamp). The mesh message also carries the tick
index, which is used for gap and duplicate counts.
"""

import argparse
import json
import math
import os
import platform
import sys
import time
from datetime import datetime, timezone

import rclpy
from geometry_msgs.msg import PoseStamped, WrenchStamped
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from srtra_bridge.msg import MeshDeformationState

TOPIC_POSE = '/srtra/bridge/tool_tip_pose'
TOPIC_WRENCH = '/srtra/bridge/tool_wrench'
TOPIC_MESH = '/srtra/bridge/mesh_deformation'

BIT_POSE = 1
BIT_WRENCH = 2
BIT_MESH = 4
ALL_BITS = BIT_POSE | BIT_WRENCH | BIT_MESH
NS_PER_MS = 1_000_000.0
NS_PER_S = 1_000_000_000


def stamp_ns(stamp):
    return stamp.sec * NS_PER_S + stamp.nanosec


def finite(values):
    return all(math.isfinite(v) for v in values)


class Collector(Node):
    def __init__(self, queue_depth):
        super().__init__('srtra_bridge_measure')
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=queue_depth,
        )
        self.arrivals = {'pose': [], 'wrench': [], 'mesh': []}
        self.wrench_stamps_ns = []
        self.stamp_mask = {}
        self.mesh_ticks = []
        self.mesh_reference_frames = set()
        self.mesh_node_counts = set()
        self.mesh_mode_counts = set()
        self.nonfinite_messages = 0
        self.first_arrival_utc = None
        self.create_subscription(PoseStamped, TOPIC_POSE, self._on_pose, qos)
        self.create_subscription(WrenchStamped, TOPIC_WRENCH, self._on_wrench, qos)
        self.create_subscription(MeshDeformationState, TOPIC_MESH, self._on_mesh, qos)

    def _mark(self, stream, stamp, bit, arrival_ns):
        if self.first_arrival_utc is None:
            self.first_arrival_utc = datetime.now(timezone.utc).isoformat()
        self.arrivals[stream].append(arrival_ns)
        key = stamp_ns(stamp)
        self.stamp_mask[key] = self.stamp_mask.get(key, 0) | bit

    def _on_pose(self, msg):
        arrival_ns = time.monotonic_ns()
        p, q = msg.pose.position, msg.pose.orientation
        if not finite((p.x, p.y, p.z, q.x, q.y, q.z, q.w)):
            self.nonfinite_messages += 1
        self._mark('pose', msg.header.stamp, BIT_POSE, arrival_ns)

    def _on_wrench(self, msg):
        arrival_ns = time.monotonic_ns()
        f, t = msg.wrench.force, msg.wrench.torque
        if not finite((f.x, f.y, f.z, t.x, t.y, t.z)):
            self.nonfinite_messages += 1
        self.wrench_stamps_ns.append(stamp_ns(msg.header.stamp))
        self._mark('wrench', msg.header.stamp, BIT_WRENCH, arrival_ns)

    def _on_mesh(self, msg):
        arrival_ns = time.monotonic_ns()
        if not finite(msg.mode_coefficients):
            self.nonfinite_messages += 1
        self.mesh_ticks.append(msg.tick)
        self.mesh_reference_frames.add(msg.reference_frame)
        self.mesh_node_counts.add(msg.node_count)
        self.mesh_mode_counts.add(len(msg.mode_coefficients))
        self._mark('mesh', msg.header.stamp, BIT_MESH, arrival_ns)


def percentile(sorted_values, pct):
    if not sorted_values:
        return None
    index = max(0, math.ceil(pct / 100.0 * len(sorted_values)) - 1)
    return sorted_values[index]


def interval_stats_ms(values_ns):
    diffs = sorted(b - a for a, b in zip(values_ns, values_ns[1:]))
    if not diffs:
        return {'count': 0}
    mean_ns = sum(diffs) / len(diffs)
    return {
        'count': len(diffs),
        'mean': mean_ns / NS_PER_MS,
        'p50': percentile(diffs, 50) / NS_PER_MS,
        'p95': percentile(diffs, 95) / NS_PER_MS,
        'p99': percentile(diffs, 99) / NS_PER_MS,
        'min': diffs[0] / NS_PER_MS,
        'max': diffs[-1] / NS_PER_MS,
    }


def collect(node, startup_timeout_s, idle_timeout_s, max_collect_s):
    wait_started = time.monotonic()
    first_ns = None
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.05)
        now_ns = time.monotonic_ns()
        if not node.arrivals['wrench']:
            if time.monotonic() - wait_started > startup_timeout_s:
                return 'no_messages_within_startup_timeout'
            continue
        if first_ns is None:
            first_ns = node.arrivals['wrench'][0]
        if (now_ns - node.arrivals['wrench'][-1]) / NS_PER_S > idle_timeout_s:
            return 'idle_timeout'
        if (now_ns - first_ns) / NS_PER_S > max_collect_s:
            return 'max_collect_s'
    return 'shutdown'


def summarize(node, args, stop_reason):
    counts = {k: len(v) for k, v in node.arrivals.items()}
    masks = node.stamp_mask.values()
    complete = sum(1 for m in masks if m == ALL_BITS)
    partial = sum(1 for m in masks if m != ALL_BITS)
    ticks = sorted(set(node.mesh_ticks))
    unique_ticks = len(ticks)
    if ticks:
        span = ticks[-1] - ticks[0] + 1
        gaps = span - unique_ticks
    else:
        span = 0
        gaps = 0
    expected = args.expected_ticks
    wrench_arrivals = node.arrivals['wrench']
    wall_s = (wrench_arrivals[-1] - wrench_arrivals[0]) / NS_PER_S if len(wrench_arrivals) > 1 else 0.0
    achieved_mean_hz = (len(wrench_arrivals) - 1) / wall_s if wall_s > 0 else None
    return {
        'schema': 'srtra-bridge-rate-measure/1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'stop_reason': stop_reason,
        'first_arrival_utc': node.first_arrival_utc,
        'rmw_implementation': os.environ.get('RMW_IMPLEMENTATION'),
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'topics': {'pose': TOPIC_POSE, 'wrench': TOPIC_WRENCH, 'mesh': TOPIC_MESH},
        'target_rate_hz': args.rate,
        'node_duration_s': args.duration,
        'expected_ticks': expected,
        'messages_received': counts,
        'ticks_with_all_three_streams': complete,
        'ticks_with_partial_streams': partial,
        'missing_complete_ticks_vs_expected': max(0, expected - complete),
        'mesh_tick_index_first': ticks[0] if ticks else None,
        'mesh_tick_index_last': ticks[-1] if ticks else None,
        'mesh_unique_tick_indices': unique_ticks,
        'mesh_tick_index_gaps': gaps,
        'mesh_duplicate_messages': counts['mesh'] - unique_ticks,
        'wrench_wall_duration_s': wall_s,
        'wrench_achieved_mean_rate_hz': achieved_mean_hz,
        'wrench_arrival_interval_ms': interval_stats_ms(wrench_arrivals),
        'wrench_source_stamp_interval_ms': interval_stats_ms(node.wrench_stamps_ns),
        'nonfinite_messages': node.nonfinite_messages,
        'mesh_reference_frames': sorted(node.mesh_reference_frames),
        'mesh_node_counts': sorted(node.mesh_node_counts),
        'mesh_mode_counts': sorted(node.mesh_mode_counts),
    }


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--rate', type=int, required=True, help='target rate of the node in Hz (record only)')
    parser.add_argument('--duration', type=int, required=True, help='node duration in seconds (record only)')
    parser.add_argument('--expected-ticks', type=int, default=None, help='ticks the node should publish (default rate*duration)')
    parser.add_argument('--out', required=True, help='JSON output path')
    parser.add_argument('--ready-file', default=None, help='file written after the subscriptions exist')
    parser.add_argument('--queue-depth', type=int, default=1000)
    parser.add_argument('--startup-timeout', type=float, default=120.0)
    parser.add_argument('--idle-timeout', type=float, default=3.0)
    parser.add_argument('--max-collect', type=float, default=None, help='hard stop in seconds (default duration+60)')
    args = parser.parse_args(argv)
    if args.expected_ticks is None:
        args.expected_ticks = args.rate * args.duration
    if args.max_collect is None:
        args.max_collect = float(args.duration + 60)
    return args


def set_timer_resolution_ms(ms, enable):
    # The default Windows timer is about 15.6 ms. Arrival timestamps need 1 ms resolution.
    if os.name != 'nt':
        return
    import ctypes
    winmm = ctypes.WinDLL('winmm')
    if enable:
        winmm.timeBeginPeriod(ms)
    else:
        winmm.timeEndPeriod(ms)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rclpy.init()
    node = Collector(args.queue_depth)
    set_timer_resolution_ms(1, True)
    try:
        if args.ready_file:
            with open(args.ready_file, 'w', encoding='utf-8') as fh:
                fh.write('ready\n')
        stop_reason = collect(node, args.startup_timeout, args.idle_timeout, args.max_collect)
        record = summarize(node, args, stop_reason)
    finally:
        set_timer_resolution_ms(1, False)
        node.destroy_node()
        rclpy.shutdown()
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(record, fh, indent=2)
        fh.write('\n')
    print(json.dumps({k: record[k] for k in (
        'stop_reason', 'messages_received', 'ticks_with_all_three_streams',
        'ticks_with_partial_streams', 'missing_complete_ticks_vs_expected',
        'mesh_tick_index_gaps', 'wrench_achieved_mean_rate_hz')}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
