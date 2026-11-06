# SPDX-License-Identifier: MIT
"""Per-message capture codec and 1-minute window rate for the srtra_bridge subscriber records.

Schema srtra-bridge-rate-measure/3 stores each message's arrival time and source stamp in a
sidecar file (the per-message file, named by the record). This module encodes and decodes that
file and computes the pre-registered window statistic from it. It needs no ROS import, so it runs
in any CPython.

Window definition (G2.4 pre-registration, slice 3a): a tick is complete when pose, wrench, and
mesh messages with the same source stamp are all received. The tick time is the wrench arrival
time. t_first is the wrench arrival of the first complete tick. Window k covers
[t_first + k * window_s, t_first + (k + 1) * window_s). The window count is floor(span / window_s)
+ 1, where span = t_last - t_first, so a run of 600 s gives ten windows. Each rate is the count of
complete ticks in the window divided by window_s. The statistic is the minimum window rate.

Command line: python window_min.py <record.json>
Re-reads the per-message file named in the record, checks its SHA-256, recomputes the window
statistic, and compares it with the value stored in the record.
"""

import hashlib
import itertools
import json
import os
import sys

WINDOW_S = 60
NS_PER_S = 1_000_000_000
TOPICS = ('pose', 'wrench', 'mesh')


def encode(values):
    if not values:
        return {'first': None, 'delta': []}
    return {'first': values[0], 'delta': [b - a for a, b in zip(values, values[1:])]}


def decode(encoded):
    first = encoded['first']
    if first is None:
        return []
    return list(itertools.accumulate(encoded['delta'], initial=first))


def complete_flags(source_by_topic):
    common = set.intersection(*(set(source_by_topic[t]) for t in TOPICS))
    return [s in common for s in source_by_topic['wrench']]


def window_rates(arrival_ns, complete, window_s=WINDOW_S):
    window_ns = window_s * NS_PER_S
    complete_arrivals = [a for a, c in zip(arrival_ns, complete) if c]
    if not complete_arrivals:
        return {'window_s': window_s, 't_first_perf_ns': None, 't_last_perf_ns': None,
                'windows': [], 'min_rate_hz': None, 'min_window_index': None}
    t_first = complete_arrivals[0]
    t_last = complete_arrivals[-1]
    count_windows = (t_last - t_first) // window_ns + 1
    counts = [0] * count_windows
    for a in complete_arrivals:
        counts[(a - t_first) // window_ns] += 1
    rates = [c / window_s for c in counts]
    min_index = min(range(count_windows), key=lambda k: rates[k])
    return {
        'window_s': window_s,
        't_first_perf_ns': t_first,
        't_last_perf_ns': t_last,
        'windows': [
            {'index': k, 'start_s': k * window_s, 'complete_ticks': counts[k], 'rate_hz': rates[k]}
            for k in range(count_windows)
        ],
        'min_rate_hz': rates[min_index],
        'min_window_index': min_index,
    }


def load_messages(path):
    with open(path, 'rb') as fh:
        raw = fh.read()
    doc = json.loads(raw.decode('utf-8'))
    topics = doc['topics']
    arrival = {t: decode(topics[t]['arrival_perf_ns']) for t in TOPICS}
    source = {t: decode(topics[t]['source_stamp_ns']) for t in TOPICS}
    mesh_tick = decode(topics['mesh']['tick'])
    return {
        'sha256': hashlib.sha256(raw).hexdigest(),
        'arrival_ns': arrival,
        'source_ns': source,
        'mesh_tick': mesh_tick,
    }


def window_statistic_from_messages(messages, window_s=WINDOW_S):
    flags = complete_flags(messages['source_ns'])
    return window_rates(messages['arrival_ns']['wrench'], flags, window_s)


def main(argv):
    if len(argv) != 2:
        print('usage: window_min.py <record.json>', file=sys.stderr)
        return 2
    record_path = argv[1]
    with open(record_path, 'r', encoding='utf-8') as fh:
        record = json.load(fh)
    messages_path = os.path.join(os.path.dirname(os.path.abspath(record_path)),
                                 record['per_message']['file'])
    messages = load_messages(messages_path)
    if messages['sha256'] != record['per_message']['sha256']:
        print('per-message file sha256 does not match the record', file=sys.stderr)
        return 1
    result = window_statistic_from_messages(messages)
    stored = record['window_statistic']['min_rate_hz']
    agree = stored is not None and result['min_rate_hz'] == stored
    print(json.dumps({
        'windows': len(result['windows']),
        'min_rate_hz': result['min_rate_hz'],
        'min_window_index': result['min_window_index'],
        'stored_min_rate_hz': stored,
        'stored_matches_recomputed': agree,
    }, indent=2))
    return 0 if agree else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
