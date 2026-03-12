"""Data models for fit2json activity data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TimeSeriesSample:
    """A single 1-minute time-series sample."""

    elapsed_min: int
    heart_rate_bpm: Optional[int] = None
    cadence_spm: Optional[int] = None
    speed_kmh: Optional[float] = None
    power_w: Optional[int] = None


@dataclass
class Lap:
    """Per-lap summary data."""

    lap_number: int
    distance_km: Optional[float] = None
    duration_s: Optional[float] = None
    avg_heart_rate_bpm: Optional[int] = None
    max_heart_rate_bpm: Optional[int] = None
    avg_pace_min_per_km: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    avg_cadence_spm: Optional[int] = None
    avg_power_w: Optional[int] = None


@dataclass
class HRZoneSeconds:
    """Time spent in each heart rate zone (seconds)."""

    z1: int = 0
    z2: int = 0
    z3: int = 0
    z4: int = 0
    z5: int = 0


@dataclass
class ActivitySummary:
    """Aggregated summary of an activity."""

    total_distance_km: Optional[float] = None
    total_duration_s: Optional[float] = None
    avg_pace_min_per_km: Optional[float] = None
    max_pace_min_per_km: Optional[float] = None
    avg_heart_rate_bpm: Optional[int] = None
    max_heart_rate_bpm: Optional[int] = None
    avg_cadence_spm: Optional[int] = None
    max_cadence_spm: Optional[int] = None
    avg_power_w: Optional[int] = None
    max_power_w: Optional[int] = None
    avg_speed_kmh: Optional[float] = None
    max_speed_kmh: Optional[float] = None
    total_calories: Optional[int] = None
    total_ascent_m: Optional[float] = None
    total_descent_m: Optional[float] = None
    hr_zone_seconds: Optional[HRZoneSeconds] = None


@dataclass
class Activity:
    """A fully parsed activity with summary, laps, and time series."""

    source_file: str
    sport: str
    start_time: Optional[str] = None  # ISO 8601
    summary: Optional[ActivitySummary] = None
    laps: List[Lap] = field(default_factory=list)
    time_series_1min: List[TimeSeriesSample] = field(default_factory=list)


@dataclass
class OutputDocument:
    """Top-level JSON output document."""

    activities: List[Activity] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dict, dropping None values."""
        return _strip_nones(asdict(self))

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _strip_nones(obj: Any) -> Any:
    """Recursively remove keys with None values from dicts."""
    if isinstance(obj, dict):
        return {k: _strip_nones(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nones(item) for item in obj]
    return obj
