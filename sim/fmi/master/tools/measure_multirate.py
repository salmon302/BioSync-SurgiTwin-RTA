# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: rclpy measurement harness for the multi-rate master (plan task 2.8 slice 2)
# Date: 2026-11-11T09:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.8 slice 2
# Summary: Subscribes to the master clock and the three participant state topics, records per-message arrival and source stamps for every stream (delta encoded), and reports clock skew and message jitter per stream against the 1 ms G2.6 bounds.
"""Measure skew and jitter of the multi-rate master (SRS FR-MS-007, G2.6, plan task 2.8 slice 2).

Runs under the ROS 2 Jazzy pixi environment (CPython 3.12) with RMW_IMPLEMENTATION=rmw_fastrtps_cpp.
The JSON record is written to --out (schema srtra-fmi-multirate-measure/1) and the per-message sidecar to
<stem>.messages.json (schema srtra-fmi-multirate-messages/1). Each stream is one of: clock, thermal_pennes,
mechanical_sofa, pulse_physiology.

Definitions (the clause metric, unchanged from slice 1):
  Arrival: time.perf_counter_ns() at callback entry (QueryPerformanceCounter on Windows, the same counter as the
  master steady clock), so the arrival and the source stamp share one epoch on this host.
  Source stamp: header.stamp, taken by the master immediately before publish.
  Skew (per message): arrival minus source stamp. With the reference clock on the same counter this is the
  one-way delivery time plus the epoch error (see the README, measurement section). The distribution is reported
  with its median removed (skew variation) as a diagnostic.
  Jitter (per stream): the deviation of each message's arrival interval from the nominal 1 ms grid of the master
  (the arrival interval minus 1 ms for the clock stream). The source-stamp interval deviation is reported beside
  it, so master pacing and delivery are separated.
  Pass criteria (G2.6 clause): max absolute skew at most 1 ms per stream, and max absolute jitter at most 1 ms per
  stream. The p95 and p99 values are reported. A run that misses a bound is FAIL with its location (the stream).
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
PARTICIPANTS = ('thermal_pennes', 'mechanical_sofa', 'pulse_physiology')
STREAMS = ('clock',) + PARTICIPANTS
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
    absolute = sorted(abs(v) for v in s)
    n = len(s)
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
        super().__init__('srtra_fmi_multirate_measure')
        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=depth)
        self.arrival = {s: [] for s in STREAMS}
        self.stamp = {s: [] for s in STREAMS}
        self.tick = {s: [] for s in STREAMS}
        self.scheduled = []
        self.create_subscription(MasterClock, TOPIC_CLOCK, self._on_clock, qos)
        for name in PARTICIPANTS:
            self.create_subscription(
                ParticipantState, f'/srtra/fmi/participant/{name}',
                (lambda n: lambda msg: self._on_state(n, msg))(name), qos)

    def _on_clock(self, msg):
        arrival = time.perf_counter_ns()
        self.arrival['clock'].append(arrival)
        self.stamp['clock'].append(stamp_ns(msg.header.stamp))
        self.tick['clock'].append(msg.tick)
        self.scheduled.append(msg.scheduled_steady_ns)

    def _on_state(self, name, msg):
        arrival = time.perf_counter_ns()
        self.arrival[name].append(arrival)
        self.stamp[name].append(stamp_ns(msg.header.stamp))
        self.tick[name].append(msg.tick)


def collect(node, args):
    wait_started = time.perf_counter_ns()
    first_ns = None
    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.05)
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


def topic_report(node, s, nominal_ns, expected):
    arrival = node.arrival[s]
    stamps = node.stamp[s]
    ticks = node.tick[s]
    skew = [a - b for a, b in zip(arrival, stamps)]
    arrival_jitter = [d - nominal_ns for d in intervals(arrival)]
    source_jitter = [d - nominal_ns for d in intervals(stamps)]
    median = sorted(skew)[len(skew) // 2] if skew else 0
    return {
        'messages_received': len(arrival),
        'messages_expected': expected,
        'tick_sequence_consecutive': ticks == list(range(len(ticks))),
        'skew_arrival_minus_source_ms': stats_ms(skew),
        'skew_variation_about_median_ms': stats_ms([v - median for v in skew]),
        'arrival_interval_jitter_ms': stats_ms(arrival_jitter),
        'source_interval_jitter_ms': stats_ms(source_jitter),
    }


def write_sidecar(node, path):
    doc = {
        'schema': 'srtra-fmi-multirate-messages/1',
        'encoding': 'each list is {"first": raw int, "delta": differences to the previous message of the same '
                    'stream}; times in ns',
        'arrival_clock': 'time.perf_counter_ns at callback entry (QueryPerformanceCounter on Windows)',
        'source_clock': 'header.stamp, master steady clock, ns',
        'streams': {},
    }
    for s in STREAMS:
        entry = {
            'count': len(node.arrival[s]),
            'arrival_perf_ns': encode(node.arrival[s]),
            'source_stamp_ns': encode(node.stamp[s]),
            'tick': encode(node.tick[s]),
        }
        doc['streams'][s] = entry
    payload = (json.dumps(doc, separators=(',', ':')) + '\n').encode('utf-8')
    with open(path, 'wb') as fh:
        fh.write(payload)
    return hashlib.sha256(payload).hexdigest(), len(payload)


def summarize(node, args, stop_reason, wall_anchor, perf_anchor):
    nominal_ns = 1.0e9 / args.rate_hz
    expected = args.rate_hz * args.duration
    per_stream = {s: topic_report(node, s, nominal_ns, expected) for s in STREAMS}
    clock_arrivals = node.arrival['clock']
    clock_stamps = node.stamp['clock']
    epoch_offset_ns = clock_arrivals[0] - clock_stamps[0] if clock_arrivals else None
    epoch_ok = epoch_offset_ns is not None and 0 < epoch_offset_ns <= EPOCH_WINDOW_NS

    stream_verdicts = {}
    for s in STREAMS:
        skew_max = per_stream[s]['skew_arrival_minus_source_ms'].get('max_abs_ms', float('inf'))
        jitter_max = per_stream[s]['arrival_interval_jitter_ms'].get('max_abs_ms', float('inf'))
        stream_verdicts[s] = {
            'skew_max_abs_ms': skew_max,
            'skew_passed': skew_max <= BOUND_NS / NS_PER_MS,
            'jitter_max_abs_ms': jitter_max,
            'jitter_passed': jitter_max <= BOUND_NS / NS_PER_MS,
            'count_and_sequence_passed': (
                per_stream[s]['messages_received'] == expected and per_stream[s]['tick_sequence_consecutive']),
        }
    all_pass = epoch_ok and all(
        v['skew_passed'] and v['jitter_passed'] and v['count_and_sequence_passed']
        for v in stream_verdicts.values())
    return {
        'schema': 'srtra-fmi-multirate-measure/1',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'stop_reason': stop_reason,
        'rmw_implementation': os.environ.get('RMW_IMPLEMENTATION'),
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'arrival_clock': {
            'implementation': time.get_clock_info('perf_counter').implementation,
            'resolution_s': time.get_clock_info('perf_counter').resolution,
        },
        'clock_anchor': {'wall_utc_ns': wall_anchor, 'perf_counter_ns': perf_anchor},
        'epoch_check': {
            'first_arrival_minus_first_stamp_ns': epoch_offset_ns,
            'window_ns': [0, EPOCH_WINDOW_NS],
            'passed': epoch_ok,
        },
        'run': {
            'planned_master_rate_hz': args.rate_hz,
            'duration_s': args.duration,
            'expected_messages_per_stream': expected,
            'master_base_step_ms': 1,
            'fmu_steps': {'thermal_pennes_ms': 100, 'mechanical_sofa_ms': 1, 'pulse_physiology_ms': 10},
            'scope': args.scope,
        },
        'per_stream': per_stream,
        'stream_verdicts': stream_verdicts,
        'bounds_ms': {'skew_max_abs': BOUND_NS / NS_PER_MS, 'jitter_max_abs': BOUND_NS / NS_PER_MS},
        'verdict': {'passed': all_pass},
    }


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('--rate-hz', type=int, default=1000, help='planned master tick rate (Hz)')
    parser.add_argument('--duration', type=int, required=True, help='run duration in seconds')
    parser.add_argument('--out', required=True, help='JSON output path; the sidecar is written next to it')
    parser.add_argument('--ready-file', default=None)
    parser.add_argument('--scope', default='single-host loopback', help='measurement scope label for the record')
    parser.add_argument('--queue-depth', type=int, default=5000)
    parser.add_argument('--startup-timeout', type=float, default=180.0)
    parser.add_argument('--idle-timeout', type=float, default=5.0)
    parser.add_argument('--max-collect', type=float, default=None, help='hard stop in seconds (default duration+120)')
    args = parser.parse_args(argv)
    if args.max_collect is None:
        args.max_collect = float(args.duration + 120)
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
        'messages_received': {s: record['per_stream'][s]['messages_received'] for s in STREAMS},
        'stream_verdicts': record['stream_verdicts'],
        'verdict': record['verdict'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
