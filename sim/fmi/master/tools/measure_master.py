# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: rclpy measurement harness for the FMI master publish stream (plan task 2.8 slice 1)
# Date: 2026-11-05T21:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.8 slice 1
# Summary: Subscribes to the master clock and participant state topics, records per-message arrival and source stamps, and reports clock skew and message jitter against the 1 ms G2.6 bounds.
"""Measure clock skew and message jitter of fmi_master_node (SRS FR-MS-007, plan task 2.8 slice 1).

Runs under the ROS 2 Jazzy pixi environment (CPython 3.12, env/ros2-jazzy) with
RMW_IMPLEMENTATION=rmw_fastrtps_cpp. Writes the JSON record at --out (schema srtra-fmi-master-measure/1)
and a per-message sidecar named <out without .json>.messages.json (schema srtra-fmi-master-messages/1).

Measurement definitions (single node):
  Arrival: time.perf_counter_ns() at callback entry. On Windows this reads QueryPerformanceCounter,
  the same counter as the master steady clock (MSVC steady_clock), so the two values share one epoch.
  The first clock message checks the epoch: first arrival minus first stamp must be in (0, 50 ms).
  Source stamp: header.stamp (master steady clock, ns) taken immediately before publish.
  Clock skew of a message: arrival minus source stamp. On one node the reference clock and the master
  read the same counter, so this value is the one-way DDS delivery time plus the epoch error. It is an
  upper bound on the skew between the master clock and the reference clock. The three-node run separates
  the clocks (README, inter-node protocol sketch).
  Message jitter of a topic: arrival interval minus the nominal period, per consecutive pair. The source
  stamp interval minus the nominal period is reported beside it, so pacing jitter of the master is
  separated from delivery jitter.
  Publish pacing: header.stamp minus scheduled_steady_ns, for the master clock messages.

Pass criteria (fixed before the 10-minute run, see SNDEV/docs/impl-2026-11-05-task28-slice1-master.md):
  the maximum absolute skew over all messages is at most 1 ms, and the maximum absolute arrival jitter of
  each topic is at most 1 ms. The p95 and p99 values are reported in addition.
"""

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
from datetime import datetime, timezone

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from srtra_fmi_master.msg import MasterClock, ParticipantState

TOPIC_CLOCK = '/srtra/fmi/master/clock'
TOPIC_STATE = '/srtra/fmi/participant/thermal_pennes'
STREAMS = ('clock', 'state')
NS_PER_MS = 1.0e6
NS_PER_S = 1_000_000_000
BOUND_NS = 1.0e6
EPOCH_WINDOW_NS = 50.0e6


def stamp_ns(stamp):
    return stamp.sec * NS_PER_S + stamp.nanosec


def encode(values):
    """Bridge v3 delta encoding: first raw value, then differences to the previous message."""
    if not values:
        return {'first': None, 'delta': []}
    return {'first': values[0], 'delta': [b - a for a, b in zip(values, values[1:])]}


def percentile(sorted_values, pct):
    index = max(0, math.ceil(pct / 100.0 * len(sorted_values)) - 1)
    return sorted_values[index]


def stats_ms(values_ns):
    if not values_ns:
        return {'count': 0}
    s = sorted(values_ns)
    n = len(s)
    absolute = sorted(abs(v) for v in s)
    return {
        'count': n,
        'mean_ms': sum(s) / n / NS_PER_MS,
        'p50_ms': percentile(s, 50) / NS_PER_MS,
        'p95_ms': percentile(s, 95) / NS_PER_MS,
        'p99_ms': percentile(s, 99) / NS_PER_MS,
        'min_ms': s[0] / NS_PER_MS,
        'max_ms': s[-1] / NS_PER_MS,
        'max_abs_ms': absolute[-1] / NS_PER_MS,
        'p95_abs_ms': percentile(absolute, 95) / NS_PER_MS,
        'p99_abs_ms': percentile(absolute, 99) / NS_PER_MS,
    }


def intervals(values):
    return [b - a for a, b in zip(values, values[1:])]


class Collector(Node):
    def __init__(self, depth):
        super().__init__('srtra_fmi_measure')
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=depth,
        )
        self.arrival = {s: [] for s in STREAMS}
        self.stamp = {s: [] for s in STREAMS}
        self.tick = {s: [] for s in STREAMS}
        self.scheduled = []
        self.last_state = None
        self.create_subscription(MasterClock, TOPIC_CLOCK, self._on_clock, qos)
        self.create_subscription(ParticipantState, TOPIC_STATE, self._on_state, qos)

    def _on_clock(self, msg):
        arrival = time.perf_counter_ns()
        self.arrival['clock'].append(arrival)
        self.stamp['clock'].append(stamp_ns(msg.header.stamp))
        self.tick['clock'].append(msg.tick)
        self.scheduled.append(msg.scheduled_steady_ns)

    def _on_state(self, msg):
        arrival = time.perf_counter_ns()
        self.arrival['state'].append(arrival)
        self.stamp['state'].append(stamp_ns(msg.header.stamp))
        self.tick['state'].append(msg.tick)
        self.last_state = {
            'tick': msg.tick,
            'steps': msg.steps,
            'fmu_time_s': msg.fmu_time_s,
            't_max_k': msg.t_max_k,
            't_mean_k': msg.t_mean_k,
            'v60_mm3': msg.v60_mm3,
            'v_lesion_mm3': msg.v_lesion_mm3,
        }


def collect(node, args):
    spin_timeout = 0.05
    wait_started = time.perf_counter_ns()
    first_ns = None
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=spin_timeout)
        now_ns = time.perf_counter_ns()
        arrivals = node.arrival['clock']
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


def write_sidecar(node, path):
    doc = {
        'schema': 'srtra-fmi-master-messages/1',
        'encoding': 'each list is {"first": raw int, "delta": differences to the previous message of '
                    'the same topic}; times in ns',
        'arrival_clock': 'time.perf_counter_ns at callback entry (QueryPerformanceCounter on Windows)',
        'source_clock': 'header.stamp, master steady clock, ns',
        'topics': {},
    }
    for s in STREAMS:
        entry = {
            'count': len(node.arrival[s]),
            'arrival_perf_ns': encode(node.arrival[s]),
            'source_stamp_ns': encode(node.stamp[s]),
            'tick': encode(node.tick[s]),
        }
        if s == 'clock':
            entry['scheduled_steady_ns'] = encode(node.scheduled)
        doc['topics'][s] = entry
    payload = (json.dumps(doc, separators=(',', ':')) + '\n').encode('utf-8')
    with open(path, 'wb') as fh:
        fh.write(payload)
    return hashlib.sha256(payload).hexdigest(), len(payload)


def topic_report(node, s, nominal_ns, expected):
    arrival = node.arrival[s]
    stamps = node.stamp[s]
    ticks = node.tick[s]
    skew = [a - b for a, b in zip(arrival, stamps)]
    arrival_jitter = [d - nominal_ns for d in intervals(arrival)]
    source_jitter = [d - nominal_ns for d in intervals(stamps)]
    tick_sequence_ok = ticks == list(range(len(ticks)))
    about_median = []
    if skew:
        median = percentile(sorted(skew), 50)
        about_median = [v - median for v in skew]
    return {
        'messages_received': len(arrival),
        'messages_expected': expected,
        'tick_sequence_consecutive': tick_sequence_ok,
        'skew_arrival_minus_source_ms': stats_ms(skew),
        'skew_variation_about_median_ms': stats_ms(about_median),
        'arrival_interval_jitter_ms': stats_ms(arrival_jitter),
        'source_interval_jitter_ms': stats_ms(source_jitter),
    }


def summarize(node, args, stop_reason, wall_anchor, perf_anchor):
    nominal_ns = 1.0e9 / args.rate_hz
    expected = args.rate_hz * args.duration
    per_topic = {s: topic_report(node, s, nominal_ns, expected) for s in STREAMS}

    clock_arrivals = node.arrival['clock']
    clock_stamps = node.stamp['clock']
    epoch_offset_ns = clock_arrivals[0] - clock_stamps[0] if clock_arrivals else None
    epoch_ok = epoch_offset_ns is not None and 0 < epoch_offset_ns <= EPOCH_WINDOW_NS

    pacing = [a - b for a, b in zip(node.stamp['clock'], node.scheduled)]
    pacing_stats = stats_ms(pacing)

    all_skew = []
    for s in STREAMS:
        all_skew.extend(a - b for a, b in zip(node.arrival[s], node.stamp[s]))
    skew_all = stats_ms(all_skew)
    max_jitter = max(per_topic[s]['arrival_interval_jitter_ms'].get('max_abs_ms', float('inf')) for s in STREAMS)
    skew_pass = skew_all.get('max_abs_ms', float('inf')) <= BOUND_NS / NS_PER_MS
    jitter_pass = max_jitter <= BOUND_NS / NS_PER_MS
    counts_pass = all(
        per_topic[s]['messages_received'] == expected and per_topic[s]['tick_sequence_consecutive']
        for s in STREAMS
    )

    return {
        'schema': 'srtra-fmi-master-measure/1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'stop_reason': stop_reason,
        'rmw_implementation': os.environ.get('RMW_IMPLEMENTATION'),
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'arrival_clock': {
            'implementation': time.get_clock_info('perf_counter').implementation,
            'resolution_s': time.get_clock_info('perf_counter').resolution,
        },
        'clock_anchor': {
            'wall_utc_ns': wall_anchor,
            'perf_counter_ns': perf_anchor,
            'note': 'taken once by the harness; the epoch of the master source stamps is checked below',
        },
        'epoch_check': {
            'first_arrival_minus_first_stamp_ns': epoch_offset_ns,
            'window_ns': [0, EPOCH_WINDOW_NS],
            'passed': epoch_ok,
        },
        'run': {
            'planned_publish_rate_hz': args.rate_hz,
            'duration_s': args.duration,
            'expected_messages_per_topic': expected,
            'node_base_step_ms': args.base_step_ms,
            'fmu_step_ms': args.fmu_step_ms,
            'timer_mode': args.timer_mode,
        },
        'per_topic': per_topic,
        'publish_pacing_ms': pacing_stats,
        'skew_all_messages_ms': skew_all,
        'last_state': node.last_state,
        'bounds_ms': {'skew_max_abs': BOUND_NS / NS_PER_MS, 'jitter_max_abs': BOUND_NS / NS_PER_MS},
        'verdict': {
            'skew_max_abs_ms': skew_all.get('max_abs_ms'),
            'skew_passed': skew_pass,
            'arrival_jitter_max_abs_ms': max_jitter,
            'jitter_passed': jitter_pass,
            'message_counts_and_ticks_passed': counts_pass,
            'epoch_check_passed': epoch_ok,
            'passed': skew_pass and jitter_pass and counts_pass and epoch_ok,
        },
    }


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--rate-hz', type=int, default=100, help='planned publish rate of the master (Hz)')
    parser.add_argument('--duration', type=int, required=True, help='run duration in seconds')
    parser.add_argument('--base-step-ms', type=int, default=10)
    parser.add_argument('--fmu-step-ms', type=int, default=100)
    parser.add_argument('--timer-mode', default='high_resolution')
    parser.add_argument('--out', required=True, help='JSON output path; the sidecar is written next to it')
    parser.add_argument('--ready-file', default=None)
    parser.add_argument('--queue-depth', type=int, default=2000)
    parser.add_argument('--startup-timeout', type=float, default=120.0)
    parser.add_argument('--idle-timeout', type=float, default=5.0)
    parser.add_argument('--max-collect', type=float, default=None, help='hard stop in seconds (default duration+90)')
    args = parser.parse_args(argv)
    if args.max_collect is None:
        args.max_collect = float(args.duration + 90)
    return args


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    wall_anchor = time.time_ns()
    perf_anchor = time.perf_counter_ns()
    rclpy.init()
    node = Collector(args.queue_depth)
    try:
        if args.ready_file:
            with open(args.ready_file, 'w', encoding='utf-8') as fh:
                fh.write('ready\n')
        stop_reason = collect(node, args)
        record = summarize(node, args, stop_reason, wall_anchor, perf_anchor)
    finally:
        node.destroy_node()
        rclpy.shutdown()

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    stem = args.out[:-5] if args.out.endswith('.json') else args.out
    sidecar = stem + '.messages.json'
    sha, size = write_sidecar(node, sidecar)
    total = sum(len(node.arrival[s]) for s in STREAMS)
    record['per_message'] = {
        'file': os.path.basename(sidecar),
        'sha256': sha,
        'bytes': size,
        'bytes_per_message': size / max(1, total),
        'messages': total,
    }
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(record, fh, indent=2)
        fh.write('\n')
    print(json.dumps({
        'stop_reason': record['stop_reason'],
        'messages_received': {s: record['per_topic'][s]['messages_received'] for s in STREAMS},
        'verdict': record['verdict'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
