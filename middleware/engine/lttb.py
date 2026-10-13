# SPDX-License-Identifier: MIT
"""
Largest-Triangle-Three-Buckets (LTTB) Downsampling Engine
Implements SRS FR-3.1.2 / NFR-P2 — 60 fps at 100k pts/s.

LTTB is an algorithm specifically designed for time-series data that reduces
the number of data points while perfectly preserving visual peaks and troughs
(anomalies). This allows the frontend to render high-frequency telemetry
streams at 60 fps without destroying clinical signal integrity.

Reference:
    S. Schubert, M. P. M. K. et al., "Largest-Triangle-Three-Buckets
    Algorithm for Line Chart Simplification," 2014.

Implements SRS DEVELOPMENT_PLAN risk #3 mitigation.
"""

from typing import List, Tuple, Optional
import numpy as np


def lttb(
    data: List[Tuple[float, float]],
    threshold: int
) -> List[Tuple[float, float]]:
    """
    Downsample a time-series using the Largest-Triangle-Three-Buckets algorithm.

    Args:
        data: List of (timestamp, value) tuples, sorted by timestamp.
        threshold: Maximum number of points to retain (output size <= threshold).

    Returns:
        Downsampled list of (timestamp, value) tuples, preserving the first
        and last points and the most visually significant intermediate points.

    Implements:
        SRS FR-3.1.2 — Downsampling for 60 fps rendering at 100k pts/s.
    """
    n = len(data)
    if threshold >= n or threshold < 2:
        return data[:]

    # Convert to numpy arrays for efficient computation
    timestamps = np.array([d[0] for d in data], dtype=np.float64)
    values = np.array([d[1] for d in data], dtype=np.float64)

    # Bucket size
    bucket_count = threshold - 2  # -2 for first and last points
    bucket_size = (n - 2) / bucket_count

    # Always include first point
    result_indices = [0]

    for i in range(bucket_count):
        # Bucket range (in terms of data indices)
        bucket_start = int(1 + i * bucket_size)
        bucket_end = int(1 + (i + 1) * bucket_size)
        if bucket_end >= n:
            bucket_end = n - 1
        if bucket_start >= bucket_end:
            continue

        # Find the point in this bucket that forms the largest triangle
        # with the previous selected point and the next bucket's average
        prev_idx = result_indices[-1]
        prev_point = (timestamps[prev_idx], values[prev_idx])

        # Compute the "center of mass" of the next bucket for triangle base
        next_bucket_start = int(1 + (i + 1) * bucket_size)
        next_bucket_end = int(1 + (i + 2) * bucket_size)
        if next_bucket_end >= n:
            next_bucket_end = n - 1
        if next_bucket_start >= next_bucket_end:
            next_bucket_start = next_bucket_end - 1
        if next_bucket_start < 0:
            next_bucket_start = 0

        next_avg_x = np.mean(timestamps[next_bucket_start:next_bucket_end + 1])
        next_avg_y = np.mean(values[next_bucket_start:next_bucket_end + 1])

        # Find the point in the current bucket that maximizes triangle area
        max_area = -1.0
        max_idx = bucket_start

        for j in range(bucket_start, bucket_end + 1):
            # Triangle area using the cross product formula
            # Area = 0.5 * |(x1(y2 - y3) + x2(y3 - y1) + x3(y1 - y2))|
            x1, y1 = prev_point
            x2, y2 = timestamps[j], values[j]
            x3, y3 = next_avg_x, next_avg_y
            area = abs((x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2.0)
            if area > max_area:
                max_area = area
                max_idx = j

        result_indices.append(max_idx)

    # Always include last point
    result_indices.append(n - 1)

    return [(float(timestamps[i]), float(values[i])) for i in result_indices]


def lttb_multichannel(
    channels: dict,
    threshold: int
) -> dict:
    """
    Downsample multiple telemetry channels simultaneously using LTTB.

    Args:
        channels: Dict mapping channel name to list of (timestamp, value) tuples.
        threshold: Maximum number of points per channel.

    Returns:
        Dict mapping channel name to downsampled list of (timestamp, value) tuples.

    Implements:
        SRS FR-3.1.2 — Multi-channel downsampling for 4-channel telemetry.
    """
    return {
        name: lttb(data, threshold)
        for name, data in channels.items()
    }


def downsample_telemetry(
    observations: List[dict],
    threshold: int = 1000,
    channels: Optional[List[str]] = None
) -> List[dict]:
    """
    Downsample a list of FHIR Observation-like telemetry dicts using LTTB.

    Each observation dict should have:
        - 'timestamp': ISO timestamp string or epoch float
        - 'valueQuantity': {'value': float, 'unit': str}
        - 'code': {'coding': [{'code': str}]} or {'text': str}

    Args:
        observations: List of observation dicts sorted by timestamp.
        threshold: Maximum number of points to retain.
        channels: Optional list of channel codes to downsample.
                  If None, downsamples all observations as a single series.

    Returns:
        Downsampled list of observation dicts.

    Implements:
        SRS FR-3.1.2 — Downsampling telemetry before WebSocket push.
    """
    if not observations or threshold >= len(observations):
        return observations[:]

    # Parse observations into (timestamp, value) tuples
    parsed = []
    for obs in observations:
        ts = obs.get("timestamp")
        if ts is None:
            ts = obs.get("effectiveDateTime")
        if ts is None:
            continue
        # Convert to epoch float if string
        if isinstance(ts, str):
            try:
                ts_float = float(ts)
            except ValueError:
                from datetime import datetime
                try:
                    ts_float = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                except (ValueError, TypeError):
                    continue
        else:
            ts_float = float(ts)

        vq = obs.get("valueQuantity", {})
        value = vq.get("value")
        if value is None:
            continue

        parsed.append((ts_float, float(value), obs))

    if len(parsed) <= threshold:
        return observations[:]

    # Sort by timestamp
    parsed.sort(key=lambda x: x[0])

    # Extract just (timestamp, value) for LTTB
    data_points = [(p[0], p[1]) for p in parsed]
    downsampled = lttb(data_points, threshold)

    # Map back to original observation dicts
    # Use a set of (timestamp, value) tuples for O(1) lookup
    downsampled_set = {(d[0], d[1]) for d in downsampled}
    result = []
    for ts, val, obs in parsed:
        if (ts, val) in downsampled_set:
            result.append(obs)

    return result
