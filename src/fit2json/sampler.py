"""Downsample per-second FIT records to 1-minute intervals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fit2json.models import TimeSeriesSample


def downsample_to_1min(records: List[Dict[str, Any]]) -> List[TimeSeriesSample]:
    """Aggregate raw FIT records into 1-minute samples.

    For each 1-minute bucket, computes the average of available values for
    heart_rate, cadence, speed, and power.

    Args:
        records: List of raw record dicts with 'timestamp' and data fields.

    Returns:
        List of TimeSeriesSample, one per minute from activity start.
    """
    if not records:
        return []

    # Determine start time from the first record with a valid timestamp
    start_time = None
    for r in records:
        if r.get("timestamp") is not None:
            start_time = r["timestamp"]
            break

    if start_time is None:
        return []

    # Group records into 1-minute buckets
    buckets: Dict[int, List[Dict[str, Any]]] = {}
    for r in records:
        ts = r.get("timestamp")
        if ts is None:
            continue
        if isinstance(ts, datetime) and isinstance(start_time, datetime):
            elapsed_s = (ts - start_time).total_seconds()
        else:
            continue

        if elapsed_s < 0:
            continue

        minute = int(elapsed_s // 60)
        buckets.setdefault(minute, []).append(r)

    if not buckets:
        return []

    # Build samples for each minute
    max_minute = max(buckets.keys())
    samples = []

    for minute in range(max_minute + 1):
        bucket = buckets.get(minute, [])
        if not bucket:
            # Include empty minute to show gaps
            samples.append(TimeSeriesSample(elapsed_min=minute))
            continue

        samples.append(
            TimeSeriesSample(
                elapsed_min=minute,
                heart_rate_bpm=_avg_int(bucket, "heart_rate"),
                cadence_spm=_avg_int_doubled(bucket, "cadence"),
                speed_kmh=_avg_speed_kmh(bucket, "speed"),
                power_w=_avg_int(bucket, "power"),
            )
        )

    return samples


def _avg_int(bucket: List[Dict[str, Any]], key: str) -> Optional[int]:
    """Compute the integer average of a field across a bucket of records."""
    values = [r[key] for r in bucket if r.get(key) is not None]
    if not values:
        return None
    return round(sum(values) / len(values))


def _avg_int_doubled(bucket: List[Dict[str, Any]], key: str) -> Optional[int]:
    """Average a field and double it (for cadence: half-cycles → steps/min)."""
    avg = _avg_int(bucket, key)
    if avg is None:
        return None
    return avg * 2


def _avg_speed_kmh(bucket: List[Dict[str, Any]], key: str) -> Optional[float]:
    """Average speed in m/s and convert to km/h."""
    values = [r[key] for r in bucket if r.get(key) is not None]
    if not values:
        return None
    avg_mps = sum(values) / len(values)
    return round(avg_mps * 3.6, 2)
