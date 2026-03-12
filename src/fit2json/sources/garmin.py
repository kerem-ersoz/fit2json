"""Garmin Connect API client for fetching .fit files."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import click


def fetch_garmin_activities(
    days: int = 30,
    output_dir: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
) -> List[Path]:
    """Download recent .fit files from Garmin Connect.

    Args:
        days: Number of days of history to fetch.
        output_dir: Directory to save .fit files. Uses temp dir if None.
        email: Garmin Connect email. Falls back to GARMIN_EMAIL env var.
        password: Garmin Connect password. Falls back to GARMIN_PASSWORD env var.

    Returns:
        List of Paths to downloaded .fit files.
    """
    try:
        from garminconnect import Garmin
    except ImportError:
        raise click.ClickException(
            "garminconnect package required. Install with: pip install garminconnect"
        )

    email = email or os.environ.get("GARMIN_EMAIL")
    password = password or os.environ.get("GARMIN_PASSWORD")

    if not email or not password:
        raise click.ClickException(
            "Garmin credentials required. Set GARMIN_EMAIL and GARMIN_PASSWORD "
            "environment variables or pass --email and --password."
        )

    save_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="fit2json_garmin_"))
    save_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Connecting to Garmin Connect as {email}...")
    client = Garmin(email, password)
    client.login()

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    click.echo(f"Fetching activities from {start_date} to {end_date}...")
    activities = client.get_activities_by_date(start_date, end_date)

    if not activities:
        click.echo("No activities found in the date range.")
        return []

    downloaded: List[Path] = []
    for act in activities:
        activity_id = act.get("activityId")
        activity_name = act.get("activityName", "activity")
        start = act.get("startTimeLocal", "unknown")

        click.echo(f"  Downloading: {activity_name} ({start})...")
        try:
            fit_data = client.download_activity(activity_id, dl_fmt=client.ActivityDownloadFormat.ORIGINAL)
            # Garmin may return a zip; handle both cases
            filename = f"{start}_{activity_id}.fit".replace(" ", "_").replace(":", "-")
            filepath = save_dir / filename

            if isinstance(fit_data, bytes):
                # Check if it's a zip file
                if fit_data[:2] == b"PK":
                    import zipfile
                    import io

                    with zipfile.ZipFile(io.BytesIO(fit_data)) as zf:
                        for name in zf.namelist():
                            if name.lower().endswith(".fit"):
                                extracted = save_dir / f"{start}_{activity_id}.fit".replace(
                                    " ", "_"
                                ).replace(":", "-")
                                extracted.write_bytes(zf.read(name))
                                downloaded.append(extracted)
                                break
                else:
                    filepath.write_bytes(fit_data)
                    downloaded.append(filepath)
        except Exception as e:
            click.echo(f"    Warning: Failed to download activity {activity_id}: {e}", err=True)

    click.echo(f"Downloaded {len(downloaded)} .fit file(s) to {save_dir}")
    return downloaded
