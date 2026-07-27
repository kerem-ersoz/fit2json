"""Extract chart-ready, downsampled time-series from a decoded activity.

The lossless schema keeps every per-second ``record`` (a long ride can be thousands of
samples), which is far more than a browser chart needs. These helpers pull only the
requested series, convert GPS from semicircles to degrees, and stride-downsample to a
target point budget so the frontend stays fast on mobile.
"""

from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Any, Dict, List, Optional, Tuple

from fit2json.models import DecodedActivity

# FIT stores latitude/longitude as 32-bit "semicircles"; convert to degrees.
SEMICIRCLE_TO_DEG = 180.0 / (2 ** 31)

# Plottable series -> (candidate record keys in priority order, default unit).
# ``distance`` is handled separately as an axis, not a plotted series.
_SERIES: Dict[str, Tuple[List[str], str]] = {
    "heart_rate": (["heart_rate"], "bpm"),
    "cadence": (["cadence"], "rpm"),
    "power": (["power"], "W"),
    "speed": (["enhanced_speed", "speed"], "m/s"),
    "altitude": (["enhanced_altitude", "altitude"], "m"),
    "temperature": (["temperature"], "C"),
}

_SAMPLE_SCAN = 80  # records to sample when detecting available series / GPS


def _parse_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _first(record: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        val = record.get(key)
        if val is not None:
            return val
    return None


def scan_capabilities(activity: DecodedActivity) -> Tuple[List[str], bool]:
    """Return (available plottable series, has_gps) by sampling the first records."""
    records = activity.messages.get("record") or []
    present: set = set()
    for rec in records[:_SAMPLE_SCAN]:
        present.update(rec.keys())
    series = [
        name for name, (keys, _) in _SERIES.items() if any(k in present for k in keys)
    ]
    has_gps = "position_lat" in present and "position_long" in present
    return series, has_gps


def build_streams(
    activity: DecodedActivity,
    fields: Optional[List[str]] = None,
    max_points: int = 2000,
) -> Dict[str, Any]:
    """Build downsampled, chart-ready arrays from an activity's ``record`` messages.

    Returns aligned axes (``time_s``, ``distance_m``), a ``series`` map of plottable
    values (with ``None`` for gaps), and a ``latlng`` polyline in degrees for the map.
    """
    records = activity.messages.get("record") or []
    n = len(records)
    result: Dict[str, Any] = {
        "total_records": n,
        "point_count": 0,
        "stride": 1,
        "time_s": [],
        "distance_m": [],
        "series": {},
        "latlng": [],
    }
    if n == 0:
        return result

    stride = ceil(n / max_points) if (max_points and n > max_points) else 1
    kept = records[::stride]
    result["stride"] = stride
    result["point_count"] = len(kept)

    # Time axis: seconds elapsed from the first timestamped record.
    t0: Optional[datetime] = None
    times: List[Optional[float]] = []
    for rec in kept:
        ts = _parse_ts(rec.get("timestamp"))
        if t0 is None and ts is not None:
            t0 = ts
        times.append((ts - t0).total_seconds() if (ts is not None and t0 is not None) else None)
    result["time_s"] = times
    result["distance_m"] = [_first(rec, ["distance"]) for rec in kept]

    wanted = fields if fields else list(_SERIES.keys())
    for name in wanted:
        spec = _SERIES.get(name)
        if not spec:
            continue
        keys, default_unit = spec
        values = [_first(rec, keys) for rec in kept]
        if not any(v is not None for v in values):
            continue
        unit = default_unit
        for key in keys:
            if key in activity.field_units:
                unit = activity.field_units[key]
                break
        result["series"][name] = {"unit": unit, "values": values}

    latlng: List[List[float]] = []
    for rec in kept:
        lat = rec.get("position_lat")
        lng = rec.get("position_long")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            latlng.append([lat * SEMICIRCLE_TO_DEG, lng * SEMICIRCLE_TO_DEG])
    result["latlng"] = latlng

    return result
