# SPDX-License-Identifier: MIT
"""Subscribe to the srtra_bridge streams and measure rate, presence, drops, and clock agreement.

Runs under the ROS 2 Jazzy pixi environment (CPython 3.12, env/ros2-jazzy) with
RMW_IMPLEMENTATION=rmw_fastrtps_cpp. Writes two files: the JSON record at --out (schema
srtra-bridge-rate-measure/3) and a per-message sidecar named <out without .json>.messages.json
(schema srtra-bridge-messages/1). The record names the sidecar and its SHA-256.

Arrival method (slice 2a):
  Each callback takes time.perf_counter_ns() as its first statement, so the arrival time
  is the time the subscriber callback started for that message. Slice 1 stamped arrivals
  with time.monotonic_ns(), which on this Windows build uses GetTickCount64() with a
  15.625 ms resolution (time.get_clock_info('monotonic')). That quantization produced the
  16 ms arrival steps recorded in slice 1. perf_counter uses QueryPerformanceCounter
  (resolution 0.1 us). The executor is not the cause: the slice 1 pairing reproduced with
  the perf_counter stamp and no batching (see the slice 2a log, run D).
  --spin wait (default) calls rclpy.spin_once with timeout 0.05 s. --spin poll calls it
  with timeout 0 in a loop, which burns one core and is kept only for comparison.

Per-message capture (slice 3a):
  Every message keeps its arrival time (perf_counter_ns) and its source stamp (header.stamp in
  ns, node clock). One wall-clock anchor is taken once per run next to a perf_counter_ns value,
  so arrival_utc_ns = wall_utc_ns + (arrival_perf_ns - perf_counter_ns). The sidecar stores each
  list as a first value and integer deltas. The window statistic (tools/window_min.py) is
  computed from these values.

Clock agreement check:
  For each topic, the interval statistics of the arrival times (perf_counter clock) are
  compared with the interval statistics of header.stamp (node system clock). Both clocks
  measure the same tick train, so the intervals must agree. Tolerances (fixed before the
  verification run): the mean interval agrees within 1 percent of the nominal period, and
  the p95 interval agrees within 1.0 ms.

Per tick matching: the three messages of one tick share header.stamp, which is used for the
complete, partial, and missing tick counts. The mesh tick index is used for gap and duplicate
counts.

Replay value check (optional, --expect-csv): each received message is compared with the row of
the replay capture it should carry (pose and wrench by arrival order, mesh by tick index,
modulo the row count when the node loops). Mismatches are counted per topic.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import struct
import sys
import time
from datetime import datetime, timezone

import rclpy
from geometry_msgs.msg import PoseStamped, WrenchStamped
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from srtra_bridge.msg import MeshDeformationState

from window_min import WINDOW_S, complete_flags, encode, window_rates

TOPIC_POSE = '/srtra/bridge/tool_tip_pose'
TOPIC_WRENCH = '/srtra/bridge/tool_wrench'
TOPIC_MESH = '/srtra/bridge/mesh_deformation'

STREAMS = ('pose', 'wrench', 'mesh')
BIT_POSE = 1
BIT_WRENCH = 2
BIT_MESH = 4
ALL_BITS = BIT_POSE | BIT_WRENCH | BIT_MESH
NS_PER_MS = 1_000_000.0
NS_PER_S = 1_000_000_000

MEAN_TOLERANCE_FRACTION = 0.01
P95_TOLERANCE_MS = 1.0

REPLAY_FIXED_COLUMNS = 15


def stamp_ns(stamp):
    return stamp.sec * NS_PER_S + stamp.nanosec


def finite(values):
    return all(math.isfinite(v) for v in values)


def float32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def load_expected(path):
    with open(path, 'r', encoding='utf-8', newline='') as fh:
        reader = csv.reader(fh)
        header = next(reader)
        mode_count = len(header) - REPLAY_FIXED_COLUMNS
        rows = []
        for fields in reader:
            if not fields:
                continue
            v = [float(x) for x in fields]
            pose = tuple(v[2:9])
            wrench = tuple(v[9:15])
            modes = tuple(float32(x) for x in v[REPLAY_FIXED_COLUMNS:REPLAY_FIXED_COLUMNS + mode_count])
            rows.append((pose, wrench, modes))
    return rows


class Collector(Node):
    def __init__(self, queue_depth, expected_rows=None):
        super().__init__('srtra_bridge_measure')
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=queue_depth,
        )
        self.arrival_ns = {s: [] for s in STREAMS}
        self.source_ns = {s: [] for s in STREAMS}
        self.stamp_mask = {}
        self.mesh_ticks = []
        self.mesh_reference_frames = set()
        self.mesh_node_counts = set()
        self.mesh_mode_counts = set()
        self.nonfinite_messages = 0
        self.first_arrival_utc = None
        self.expected_rows = expected_rows
        self.value_checked = {s: 0 for s in STREAMS}
        self.value_mismatches = {s: 0 for s in STREAMS}
        self.create_subscription(PoseStamped, TOPIC_POSE, self._on_pose, qos)
        self.create_subscription(WrenchStamped, TOPIC_WRENCH, self._on_wrench, qos)
        self.create_subscription(MeshDeformationState, TOPIC_MESH, self._on_mesh, qos)
        self.anchor_wall_ns = time.time_ns()
        self.anchor_perf_ns = time.perf_counter_ns()

    def _mark(self, stream, stamp, bit, arrival_ns):
        if self.first_arrival_utc is None:
            self.first_arrival_utc = datetime.now(timezone.utc).isoformat()
        src = stamp_ns(stamp)
        self.arrival_ns[stream].append(arrival_ns)
        self.source_ns[stream].append(src)
        self.stamp_mask[src] = self.stamp_mask.get(src, 0) | bit

    def _expected(self, index):
        return self.expected_rows[index % len(self.expected_rows)]

    def _on_pose(self, msg):
        arrival_ns = time.perf_counter_ns()
        p, q = msg.pose.position, msg.pose.orientation
        if not finite((p.x, p.y, p.z, q.x, q.y, q.z, q.w)):
            self.nonfinite_messages += 1
        if self.expected_rows is not None:
            value = (p.x, p.y, p.z, q.x, q.y, q.z, q.w)
            self.value_checked['pose'] += 1
            if value != self._expected(len(self.arrival_ns['pose']))[0]:
                self.value_mismatches['pose'] += 1
        self._mark('pose', msg.header.stamp, BIT_POSE, arrival_ns)

    def _on_wrench(self, msg):
        arrival_ns = time.perf_counter_ns()
        f, t = msg.wrench.force, msg.wrench.torque
        if not finite((f.x, f.y, f.z, t.x, t.y, t.z)):
            self.nonfinite_messages += 1
        if self.expected_rows is not None:
            value = (f.x, f.y, f.z, t.x, t.y, t.z)
            self.value_checked['wrench'] += 1
            if value != self._expected(len(self.arrival_ns['wrench']))[1]:
                self.value_mismatches['wrench'] += 1
        self._mark('wrench', msg.header.stamp, BIT_WRENCH, arrival_ns)

    def _on_mesh(self, msg):
        arrival_ns = time.perf_counter_ns()
        if not finite(msg.mode_coefficients):
            self.nonfinite_messages += 1
        if self.expected_rows is not None:
            self.value_checked['mesh'] += 1
            if tuple(msg.mode_coefficients) != self.expected_rows[msg.tick % len(self.expected_rows)][2]:
                self.value_mismatches['mesh'] += 1
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


def agreement(arrival_ns, source_ns, nominal_period_ms):
    arr = interval_stats_ms(arrival_ns)
    src = interval_stats_ms(source_ns)
    if arr['count'] == 0 or src['count'] == 0:
        return {'arrival': arr, 'source_stamp': src, 'passed': False, 'reason': 'no intervals'}
    mean_rel = abs(arr['mean'] - src['mean']) / nominal_period_ms
    p95_abs = abs(arr['p95'] - src['p95'])
    passed = mean_rel <= MEAN_TOLERANCE_FRACTION and p95_abs <= P95_TOLERANCE_MS
    return {
        'arrival': arr,
        'source_stamp': src,
        'mean_difference_fraction_of_period': mean_rel,
        'p95_difference_ms': p95_abs,
        'tolerance_mean_fraction': MEAN_TOLERANCE_FRACTION,
        'tolerance_p95_ms': P95_TOLERANCE_MS,
        'passed': passed,
    }


def collect(node, args):
    spin_timeout = 0.0 if args.spin == 'poll' else 0.05
    wait_started = time.perf_counter_ns()
    first_ns = None
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=spin_timeout)
        now_ns = time.perf_counter_ns()
        arrivals = node.arrival_ns['wrench']
        if not arrivals:
            if (now_ns - wait_started) / NS_PER_S > args.startup_timeout:
                return 'no_messages_within_startup_timeout'
            continue
        if first_ns is None:
            first_ns = arrivals[0]
        if (now_ns - arrivals[-1]) / NS_PER_S > args.idle_timeout:
            return 'idle_timeout'
        if (now_ns - first_ns) / NS_PER_S > args.max_collect:
            return 'max_collect_s'
    return 'shutdown'


def write_messages(node, path):
    doc = {
        'schema': 'srtra-bridge-messages/1',
        'encoding': 'each list is {"first": raw int, "delta": differences to the previous message '
                    'of the same topic}; times in ns',
        'arrival_clock': 'time.perf_counter_ns at callback entry',
        'source_clock': 'header.stamp, node system clock, ns',
        'topics': {},
    }
    for s in STREAMS:
        entry = {
            'count': len(node.arrival_ns[s]),
            'arrival_perf_ns': encode(node.arrival_ns[s]),
            'source_stamp_ns': encode(node.source_ns[s]),
        }
        if s == 'mesh':
            entry['tick'] = encode(node.mesh_ticks)
        doc['topics'][s] = entry
    payload = (json.dumps(doc, separators=(',', ':')) + '\n').encode('utf-8')
    with open(path, 'wb') as fh:
        fh.write(payload)
    return hashlib.sha256(payload).hexdigest(), len(payload)


def summarize(node, args, stop_reason):
    counts = {s: len(node.arrival_ns[s]) for s in STREAMS}
    masks = node.stamp_mask.values()
    complete = sum(1 for m in masks if m == ALL_BITS)
    partial = sum(1 for m in masks if m != ALL_BITS)
    ticks = sorted(set(node.mesh_ticks))
    unique_ticks = len(ticks)
    span = ticks[-1] - ticks[0] + 1 if ticks else 0
    gaps = span - unique_ticks if ticks else 0
    nominal_ms = 1000.0 / args.rate
    wrench_arrivals = node.arrival_ns['wrench']
    wall_s = (wrench_arrivals[-1] - wrench_arrivals[0]) / NS_PER_S if len(wrench_arrivals) > 1 else 0.0
    achieved_mean_hz = (len(wrench_arrivals) - 1) / wall_s if wall_s > 0 else None
    per_topic = {
        s: agreement(node.arrival_ns[s], node.source_ns[s], nominal_ms) for s in STREAMS
    }
    for s in STREAMS:
        per_topic[s]['message_count_match'] = counts[s] == len(node.source_ns[s])
    window = window_rates(wrench_arrivals, complete_flags(node.source_ns), WINDOW_S)
    perf_anchor = node.anchor_perf_ns
    wall_anchor = node.anchor_wall_ns
    record = {
        'schema': 'srtra-bridge-rate-measure/3',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'stop_reason': stop_reason,
        'first_arrival_utc': node.first_arrival_utc,
        'rmw_implementation': os.environ.get('RMW_IMPLEMENTATION'),
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'data_source': args.data_source,
        'clock_anchor': {
            'wall_utc_ns': wall_anchor,
            'perf_counter_ns': perf_anchor,
            'relation': 'arrival_utc_ns = wall_utc_ns + (arrival_perf_ns - perf_counter_ns)',
        },
        'arrival_method': {
            'clock': 'time.perf_counter_ns at callback entry',
            'clock_implementation': time.get_clock_info('perf_counter').implementation,
            'clock_resolution_s': time.get_clock_info('perf_counter').resolution,
            'monotonic_implementation': time.get_clock_info('monotonic').implementation,
            'monotonic_resolution_s': time.get_clock_info('monotonic').resolution,
            'spin': args.spin,
            'tolerance_mean_fraction_of_period': MEAN_TOLERANCE_FRACTION,
            'tolerance_p95_ms': P95_TOLERANCE_MS,
        },
        'topics': {'pose': TOPIC_POSE, 'wrench': TOPIC_WRENCH, 'mesh': TOPIC_MESH},
        'target_rate_hz': args.rate,
        'node_duration_s': args.duration,
        'expected_ticks': args.expected_ticks,
        'messages_received': counts,
        'ticks_with_all_three_streams': complete,
        'ticks_with_partial_streams': partial,
        'missing_complete_ticks_vs_expected': max(0, args.expected_ticks - complete),
        'mesh_tick_index_first': ticks[0] if ticks else None,
        'mesh_tick_index_last': ticks[-1] if ticks else None,
        'mesh_unique_tick_indices': unique_ticks,
        'mesh_tick_index_gaps': gaps,
        'mesh_duplicate_messages': counts['mesh'] - unique_ticks,
        'wrench_wall_duration_s': wall_s,
        'wrench_achieved_mean_rate_hz': achieved_mean_hz,
        'window_statistic': window,
        'per_topic': per_topic,
        'nonfinite_messages': node.nonfinite_messages,
        'mesh_reference_frames': sorted(node.mesh_reference_frames),
        'mesh_node_counts': sorted(node.mesh_node_counts),
        'mesh_mode_counts': sorted(node.mesh_mode_counts),
    }
    if node.expected_rows is not None:
        record['value_check'] = {
            'expected_csv': args.expect_csv_name,
            'expected_rows': len(node.expected_rows),
            'messages_checked': node.value_checked,
            'mismatches': node.value_mismatches,
        }
    return record


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--rate', type=int, required=True, help='target rate of the node in Hz (record only)')
    parser.add_argument('--duration', type=int, required=True, help='node duration in seconds (record only)')
    parser.add_argument('--expected-ticks', type=int, default=None, help='ticks the node should publish (default rate*duration)')
    parser.add_argument('--out', required=True, help='JSON output path; the per-message sidecar is written next to it')
    parser.add_argument('--ready-file', default=None, help='file written after the subscriptions exist')
    parser.add_argument('--spin', choices=('poll', 'wait'), default='wait',
                        help='wait (default): spin_once(timeout 0.05). poll: spin_once(timeout 0), one core busy.')
    parser.add_argument('--queue-depth', type=int, default=1000)
    parser.add_argument('--startup-timeout', type=float, default=120.0)
    parser.add_argument('--idle-timeout', type=float, default=3.0)
    parser.add_argument('--max-collect', type=float, default=None, help='hard stop in seconds (default duration+60)')
    parser.add_argument('--data-source', default='unspecified',
                        help='label of the node data source, recorded as given (for example synthetic or replay:<file>)')
    parser.add_argument('--expect-csv', default=None,
                        help='replay capture the node publishes; every message is checked against its row')
    args = parser.parse_args(argv)
    if args.expected_ticks is None:
        args.expected_ticks = args.rate * args.duration
    if args.max_collect is None:
        args.max_collect = float(args.duration + 60)
    args.expect_csv_name = os.path.basename(args.expect_csv) if args.expect_csv else None
    return args


def set_timer_resolution_ms(ms, enable):
    # The default Windows timer is about 15.6 ms. Keep 1 ms resolution while collecting.
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
    expected_rows = load_expected(args.expect_csv) if args.expect_csv else None
    rclpy.init()
    node = Collector(args.queue_depth, expected_rows)
    set_timer_resolution_ms(1, True)
    try:
        if args.ready_file:
            with open(args.ready_file, 'w', encoding='utf-8') as fh:
                fh.write('ready\n')
        stop_reason = collect(node, args)
        record = summarize(node, args, stop_reason)
    finally:
        set_timer_resolution_ms(1, False)
        node.destroy_node()
        rclpy.shutdown()
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    stem = args.out[:-5] if args.out.endswith('.json') else args.out
    messages_path = stem + '.messages.json'
    sha, size = write_messages(node, messages_path)
    record['per_message'] = {
        'file': os.path.basename(messages_path),
        'sha256': sha,
        'bytes': size,
        'bytes_per_message': size / max(1, sum(len(node.arrival_ns[s]) for s in STREAMS)),
    }
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(record, fh, indent=2)
        fh.write('\n')
    summary = {k: record[k] for k in (
        'stop_reason', 'messages_received', 'ticks_with_all_three_streams',
        'ticks_with_partial_streams', 'missing_complete_ticks_vs_expected',
        'mesh_tick_index_gaps', 'wrench_achieved_mean_rate_hz')}
    summary['agreement_passed'] = {s: record['per_topic'][s]['passed'] for s in STREAMS}
    summary['window_min_rate_hz'] = record['window_statistic']['min_rate_hz']
    if 'value_check' in record:
        summary['value_mismatches'] = record['value_check']['mismatches']
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
