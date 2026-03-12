"""Strava API client for fetching .fit files."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import click
import requests


def fetch_strava_activities(
    days: int = 30,
    output_dir: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> List[Path]:
    """Download recent activity files from Strava.

    Note: Strava API doesn't provide raw .fit downloads for most activities.
    It provides streams (time series data) which we convert to a pseudo-FIT
    JSON structure. For actual .fit files, use the Strava bulk export feature
    and the `convert` command instead.

    Args:
        days: Number of days of history to fetch.
        output_dir: Directory to save activity files.
        client_id: Strava API client ID.
        client_secret: Strava API client secret.
        refresh_token: Strava OAuth2 refresh token.

    Returns:
        List of Paths to downloaded activity JSON files.
    """
    client_id = client_id or os.environ.get("STRAVA_CLIENT_ID")
    client_secret = client_secret or os.environ.get("STRAVA_CLIENT_SECRET")
    refresh_token = refresh_token or os.environ.get("STRAVA_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise click.ClickException(
            "Strava credentials required. Set STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, "
            "and STRAVA_REFRESH_TOKEN environment variables or use the Strava bulk export "
            "and `fit2json convert` instead."
        )

    save_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="fit2json_strava_"))
    save_dir.mkdir(parents=True, exist_ok=True)

    # Refresh access token
    click.echo("Authenticating with Strava...")
    token_resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch activities
    after = int((datetime.now() - timedelta(days=days)).timestamp())
    click.echo(f"Fetching activities from the last {days} days...")

    activities = []
    page = 1
    while True:
        resp = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            params={"after": after, "per_page": 50, "page": page},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        activities.extend(batch)
        page += 1

    if not activities:
        click.echo("No activities found in the date range.")
        return []

    # Download streams for each activity
    downloaded: List[Path] = []
    for act in activities:
        activity_id = act["id"]
        name = act.get("name", "activity")
        sport = act.get("type", "unknown").lower()
        start_date = act.get("start_date", "unknown")

        click.echo(f"  Fetching streams: {name} ({start_date})...")
        try:
            streams_resp = requests.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}/streams",
                headers=headers,
                params={
                    "keys": "time,heartrate,cadence,watts,velocity_smooth,altitude,distance",
                    "key_type": "time",
                },
            )
            streams_resp.raise_for_status()
            streams = {s["type"]: s["data"] for s in streams_resp.json()}

            # Save as a JSON file that our parser can handle
            import json

            activity_data = {
                "source": "strava",
                "activity_id": activity_id,
                "name": name,
                "sport": sport,
                "start_date": start_date,
                "distance": act.get("distance"),
                "moving_time": act.get("moving_time"),
                "elapsed_time": act.get("elapsed_time"),
                "total_elevation_gain": act.get("total_elevation_gain"),
                "average_heartrate": act.get("average_heartrate"),
                "max_heartrate": act.get("max_heartrate"),
                "average_cadence": act.get("average_cadence"),
                "average_watts": act.get("average_watts"),
                "kilojoules": act.get("kilojoules"),
                "calories": act.get("calories"),
                "streams": streams,
            }

            filename = f"{start_date}_{activity_id}.strava.json".replace(" ", "_").replace(":", "-")
            filepath = save_dir / filename
            filepath.write_text(json.dumps(activity_data, indent=2))
            downloaded.append(filepath)

        except Exception as e:
            click.echo(f"    Warning: Failed to fetch activity {activity_id}: {e}", err=True)

    click.echo(f"Downloaded {len(downloaded)} activity file(s) to {save_dir}")
    return downloaded


def parse_strava_json(filepath: Path) -> dict:
    """Parse a Strava JSON activity file into a structure compatible with our models.

    This allows Strava stream data to be converted using the same pipeline as FIT files.
    """
    import json
    from fit2json.models import (
        Activity,
        ActivitySummary,
        TimeSeriesSample,
    )

    data = json.loads(filepath.read_text())
    streams = data.get("streams", {})

    # Build summary
    distance_m = data.get("distance")
    moving_time = data.get("moving_time")
    avg_speed = (distance_m / moving_time) if (distance_m and moving_time) else None

    summary = ActivitySummary(
        total_distance_km=round(distance_m / 1000, 3) if distance_m else None,
        total_duration_s=moving_time,
        avg_pace_min_per_km=round(1000 / avg_speed / 60, 2) if avg_speed and avg_speed > 0 else None,
        avg_heart_rate_bpm=_round_or_none(data.get("average_heartrate")),
        max_heart_rate_bpm=_round_or_none(data.get("max_heartrate")),
        avg_cadence_spm=_round_or_none(data.get("average_cadence"), multiply=2),
        avg_power_w=_round_or_none(data.get("average_watts")),
        avg_speed_kmh=round(avg_speed * 3.6, 2) if avg_speed else None,
        total_calories=_round_or_none(data.get("calories")),
        total_ascent_m=data.get("total_elevation_gain"),
    )

    # Build 1-minute time series from streams
    time_series = []
    time_data = streams.get("time", [])
    hr_data = streams.get("heartrate", [])
    cadence_data = streams.get("cadence", [])
    power_data = streams.get("watts", [])
    speed_data = streams.get("velocity_smooth", [])

    if time_data:
        # Group by minute
        from collections import defaultdict

        buckets = defaultdict(list)
        for i, t in enumerate(time_data):
            minute = t // 60
            buckets[minute].append(i)

        max_min = max(buckets.keys()) if buckets else 0
        for m in range(max_min + 1):
            indices = buckets.get(m, [])
            if not indices:
                time_series.append(TimeSeriesSample(elapsed_min=m))
                continue

            sample = TimeSeriesSample(
                elapsed_min=m,
                heart_rate_bpm=_avg_from_indices(hr_data, indices),
                cadence_spm=_avg_from_indices_doubled(cadence_data, indices),
                speed_kmh=_avg_speed_from_indices(speed_data, indices),
                power_w=_avg_from_indices(power_data, indices),
            )
            time_series.append(sample)

    return Activity(
        source_file=filepath.name,
        sport=data.get("sport", "unknown"),
        start_time=data.get("start_date"),
        summary=summary,
        laps=[],
        time_series_1min=time_series,
    )


def _round_or_none(val, multiply=1):
    if val is None:
        return None
    return round(val * multiply)


def _avg_from_indices(data, indices):
    if not data:
        return None
    vals = [data[i] for i in indices if i < len(data) and data[i] is not None]
    return round(sum(vals) / len(vals)) if vals else None


def _avg_from_indices_doubled(data, indices):
    avg = _avg_from_indices(data, indices)
    return avg * 2 if avg is not None else None


def _avg_speed_from_indices(data, indices):
    if not data:
        return None
    vals = [data[i] for i in indices if i < len(data) and data[i] is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals) * 3.6, 2)
