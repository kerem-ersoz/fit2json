"""Parse .fit files into Activity data models using fitdecode."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitdecode

from fit2json.models import (
    Activity,
    ActivitySummary,
    HRZoneSeconds,
    Lap,
    TimeSeriesSample,
)
from fit2json.sampler import downsample_to_1min


# FIT sport enum mapping (common values)
SPORT_MAP = {
    0: "generic",
    1: "running",
    2: "cycling",
    5: "swimming",
    6: "basketball",
    7: "soccer",
    9: "fitness_equipment",
    10: "tennis",
    11: "hiking",
    13: "walking",
    15: "multi_sport",
    17: "rowing",
    22: "rock_climbing",
    23: "stand_up_paddleboarding",
    29: "strength_training",
    37: "yoga",
    53: "elliptical",
    62: "inline_skating",
}


def _get_field(frame: fitdecode.FitDataMessage, name: str, fallback: Any = None) -> Any:
    """Safely get a field value from a FIT data message."""
    try:
        field = frame.get_field(name)
        return field.value if field and field.value is not None else fallback
    except KeyError:
        return fallback


def _semicircles_to_degrees(semicircles: Optional[int]) -> Optional[float]:
    """Convert Garmin semicircle coordinates to degrees."""
    if semicircles is None:
        return None
    return semicircles * (180 / 2**31)


def _format_timestamp(ts: Any) -> Optional[str]:
    """Convert a FIT timestamp to ISO 8601 string."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.isoformat()
    return str(ts)


def _speed_mps_to_kmh(mps: Optional[float]) -> Optional[float]:
    """Convert m/s to km/h."""
    if mps is None:
        return None
    return round(mps * 3.6, 2)


def _speed_to_pace(speed_mps: Optional[float]) -> Optional[float]:
    """Convert m/s to min/km pace."""
    if speed_mps is None or speed_mps <= 0:
        return None
    return round(1000 / speed_mps / 60, 2)


def _meters_to_km(meters: Optional[float]) -> Optional[float]:
    """Convert meters to kilometers."""
    if meters is None:
        return None
    return round(meters / 1000, 3)


def parse_fit_file(filepath: str | Path) -> Activity:
    """Parse a single .fit file and return an Activity object.

    Args:
        filepath: Path to a .fit file.

    Returns:
        A fully populated Activity with summary, laps, and 1-min time series.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"FIT file not found: {filepath}")

    raw_records: List[Dict[str, Any]] = []
    raw_laps: List[Dict[str, Any]] = []
    session_data: Dict[str, Any] = {}
    sport_name = "unknown"
    start_time: Optional[str] = None

    with fitdecode.FitReader(str(filepath)) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue

            if frame.name == "record":
                raw_records.append(_extract_record(frame))

            elif frame.name == "lap":
                raw_laps.append(_extract_lap(frame))

            elif frame.name == "session":
                session_data = _extract_session(frame)
                sport_val = _get_field(frame, "sport")
                if isinstance(sport_val, int):
                    sport_name = SPORT_MAP.get(sport_val, f"sport_{sport_val}")
                elif isinstance(sport_val, str):
                    sport_name = sport_val.lower()
                ts = _get_field(frame, "start_time")
                start_time = _format_timestamp(ts)

    summary = _build_summary(session_data)
    laps = _build_laps(raw_laps)
    time_series = downsample_to_1min(raw_records)

    return Activity(
        source_file=filepath.name,
        sport=sport_name,
        start_time=start_time,
        summary=summary,
        laps=laps,
        time_series_1min=time_series,
    )


def _extract_record(frame: fitdecode.FitDataMessage) -> Dict[str, Any]:
    """Extract relevant fields from a FIT record message."""
    ts = _get_field(frame, "timestamp")
    return {
        "timestamp": ts,
        "heart_rate": _get_field(frame, "heart_rate"),
        "cadence": _get_field(frame, "cadence"),
        "speed": _get_field(frame, "speed"),  # m/s
        "power": _get_field(frame, "power"),
        "altitude": _get_field(frame, "altitude"),
        "distance": _get_field(frame, "distance"),  # meters cumulative
    }


def _extract_lap(frame: fitdecode.FitDataMessage) -> Dict[str, Any]:
    """Extract relevant fields from a FIT lap message."""
    return {
        "total_distance": _get_field(frame, "total_distance"),
        "total_elapsed_time": _get_field(frame, "total_elapsed_time"),
        "avg_heart_rate": _get_field(frame, "avg_heart_rate"),
        "max_heart_rate": _get_field(frame, "max_heart_rate"),
        "avg_speed": _get_field(frame, "avg_speed"),
        "avg_cadence": _get_field(frame, "avg_cadence"),
        "avg_power": _get_field(frame, "avg_power"),
    }


def _extract_session(frame: fitdecode.FitDataMessage) -> Dict[str, Any]:
    """Extract relevant fields from a FIT session message."""
    return {
        "total_distance": _get_field(frame, "total_distance"),
        "total_elapsed_time": _get_field(frame, "total_elapsed_time"),
        "total_timer_time": _get_field(frame, "total_timer_time"),
        "avg_heart_rate": _get_field(frame, "avg_heart_rate"),
        "max_heart_rate": _get_field(frame, "max_heart_rate"),
        "avg_speed": _get_field(frame, "avg_speed"),
        "max_speed": _get_field(frame, "max_speed"),
        "avg_cadence": _get_field(frame, "avg_cadence"),
        "max_cadence": _get_field(frame, "max_cadence"),
        "avg_power": _get_field(frame, "avg_power"),
        "max_power": _get_field(frame, "max_power"),
        "total_calories": _get_field(frame, "total_calories"),
        "total_ascent": _get_field(frame, "total_ascent"),
        "total_descent": _get_field(frame, "total_descent"),
    }


def _build_summary(session: Dict[str, Any]) -> ActivitySummary:
    """Build an ActivitySummary from raw session data."""
    avg_speed = session.get("avg_speed")
    max_speed = session.get("max_speed")

    return ActivitySummary(
        total_distance_km=_meters_to_km(session.get("total_distance")),
        total_duration_s=session.get("total_timer_time") or session.get("total_elapsed_time"),
        avg_pace_min_per_km=_speed_to_pace(avg_speed),
        max_pace_min_per_km=_speed_to_pace(max_speed),
        avg_heart_rate_bpm=session.get("avg_heart_rate"),
        max_heart_rate_bpm=session.get("max_heart_rate"),
        avg_cadence_spm=_double_cadence(session.get("avg_cadence")),
        max_cadence_spm=_double_cadence(session.get("max_cadence")),
        avg_power_w=session.get("avg_power"),
        max_power_w=session.get("max_power"),
        avg_speed_kmh=_speed_mps_to_kmh(avg_speed),
        max_speed_kmh=_speed_mps_to_kmh(max_speed),
        total_calories=session.get("total_calories"),
        total_ascent_m=session.get("total_ascent"),
        total_descent_m=session.get("total_descent"),
    )


def _double_cadence(value: Optional[int]) -> Optional[int]:
    """FIT stores running cadence as half-cycles; double for steps/min."""
    if value is None:
        return None
    return value * 2


def _build_laps(raw_laps: List[Dict[str, Any]]) -> List[Lap]:
    """Build Lap objects from raw lap data."""
    laps = []
    for i, raw in enumerate(raw_laps, start=1):
        avg_speed = raw.get("avg_speed")
        laps.append(
            Lap(
                lap_number=i,
                distance_km=_meters_to_km(raw.get("total_distance")),
                duration_s=raw.get("total_elapsed_time"),
                avg_heart_rate_bpm=raw.get("avg_heart_rate"),
                max_heart_rate_bpm=raw.get("max_heart_rate"),
                avg_pace_min_per_km=_speed_to_pace(avg_speed),
                avg_speed_kmh=_speed_mps_to_kmh(avg_speed),
                avg_cadence_spm=_double_cadence(raw.get("avg_cadence")),
                avg_power_w=raw.get("avg_power"),
            )
        )
    return laps
