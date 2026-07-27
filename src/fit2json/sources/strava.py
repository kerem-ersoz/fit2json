"""Strava API client for fetching .fit files."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import click
import requests

from fit2json.models import DecodedActivity


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


def parse_strava_json(filepath: Path) -> DecodedActivity:
    """Parse a Strava JSON activity file into a (best-effort) DecodedActivity.

    Strava exposes processed time-series *streams* rather than raw .fit data, so this
    path is inherently lower-fidelity than the Garmin/local .fit path. We map the streams
    to FIT-like ``session`` + ``record`` messages (at native stream resolution) so Strava
    activities flow through the same output/memory pipeline.
    """
    import json

    data = json.loads(filepath.read_text())
    streams = data.get("streams", {})

    session = {
        "sport": data.get("sport", "unknown"),
        "start_time": data.get("start_date"),
        "total_distance": data.get("distance"),
        "total_timer_time": data.get("moving_time"),
        "total_elapsed_time": data.get("elapsed_time"),
        "avg_heart_rate": data.get("average_heartrate"),
        "max_heart_rate": data.get("max_heartrate"),
        "avg_cadence": data.get("average_cadence"),
        "avg_power": data.get("average_watts"),
        "total_calories": data.get("calories"),
        "total_ascent": data.get("total_elevation_gain"),
        "kilojoules": data.get("kilojoules"),
    }
    session = {k: v for k, v in session.items() if v is not None}

    stream_to_field = {
        "time": "time_offset_s",
        "heartrate": "heart_rate",
        "cadence": "cadence",
        "watts": "power",
        "velocity_smooth": "speed",
        "altitude": "altitude",
        "distance": "distance",
    }
    time_data = streams.get("time", [])
    records = []
    for i in range(len(time_data)):
        record = {}
        for stream_key, field_name in stream_to_field.items():
            series = streams.get(stream_key)
            if series and i < len(series) and series[i] is not None:
                record[field_name] = series[i]
        if record:
            records.append(record)

    messages = {"session": [session]}
    if records:
        messages["record"] = records

    field_units = {
        "total_distance": "m", "total_timer_time": "s", "total_elapsed_time": "s",
        "avg_heart_rate": "bpm", "max_heart_rate": "bpm", "avg_power": "W",
        "total_ascent": "m", "time_offset_s": "s", "heart_rate": "bpm",
        "power": "W", "speed": "m/s", "altitude": "m", "distance": "m",
    }

    return DecodedActivity(
        source_file=filepath.name,
        messages=messages,
        field_units=field_units,
    )
