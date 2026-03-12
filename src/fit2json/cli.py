"""CLI entry point for fit2json."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from fit2json import __version__

# Load .env file if present
load_dotenv()


@click.group()
@click.version_option(version=__version__, prog_name="fit2json")
def cli():
    """Convert Garmin/Strava .fit files to LLM-ready JSON and analyze with AI."""


# ── convert ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("-o", "--output", "output_path", type=click.Path(), default=None, help="Output JSON file path. Defaults to stdout.")
@click.option("--indent", type=int, default=2, help="JSON indentation level.")
def convert(path: str, output_path: Optional[str], indent: int):
    """Convert .fit file(s) to LLM-ready JSON.

    PATH can be a single .fit file or a directory containing .fit files.
    """
    from fit2json.sources.local import collect_fit_files
    from fit2json.parser import parse_fit_file
    from fit2json.output import build_output, write_json

    try:
        fit_files = collect_fit_files(path)
    except (FileNotFoundError, ValueError) as e:
        raise click.ClickException(str(e))

    click.echo(f"Processing {len(fit_files)} .fit file(s)...", err=True)

    activities = []
    for i, fp in enumerate(fit_files, 1):
        click.echo(f"  [{i}/{len(fit_files)}] {fp.name}", err=True)
        try:
            activity = parse_fit_file(fp)
            activities.append(activity)
        except Exception as e:
            click.echo(f"    Warning: Failed to parse {fp.name}: {e}", err=True)

    if not activities:
        raise click.ClickException("No activities were successfully parsed.")

    doc = build_output(activities)
    write_json(doc, output_path, indent=indent)

    if output_path:
        click.echo(f"Written {len(activities)} activity/activities to {output_path}", err=True)


# ── fetch ────────────────────────────────────────────────────────────────────


@cli.group()
def fetch():
    """Fetch activities from Garmin Connect or Strava."""


@fetch.command(name="garmin")
@click.option("--days", type=int, default=30, help="Number of days of history to fetch.")
@click.option("-o", "--output", "output_path", type=click.Path(), default=None, help="Output JSON file path.")
@click.option("--email", default=None, help="Garmin Connect email.")
@click.option("--password", default=None, help="Garmin Connect password.")
@click.option("--raw-dir", default=None, help="Directory to save raw .fit files.")
def fetch_garmin(days: int, output_path: Optional[str], email: Optional[str], password: Optional[str], raw_dir: Optional[str]):
    """Fetch and convert activities from Garmin Connect."""
    from fit2json.sources.garmin import fetch_garmin_activities
    from fit2json.parser import parse_fit_file
    from fit2json.output import build_output, write_json

    fit_files = fetch_garmin_activities(days=days, output_dir=raw_dir, email=email, password=password)

    if not fit_files:
        return

    activities = []
    for fp in fit_files:
        try:
            activity = parse_fit_file(fp)
            activities.append(activity)
        except Exception as e:
            click.echo(f"  Warning: Failed to parse {fp.name}: {e}", err=True)

    if activities:
        doc = build_output(activities)
        write_json(doc, output_path)
        if output_path:
            click.echo(f"Written {len(activities)} activity/activities to {output_path}", err=True)


@fetch.command(name="strava")
@click.option("--days", type=int, default=30, help="Number of days of history to fetch.")
@click.option("-o", "--output", "output_path", type=click.Path(), default=None, help="Output JSON file path.")
@click.option("--client-id", default=None, help="Strava API client ID.")
@click.option("--client-secret", default=None, help="Strava API client secret.")
@click.option("--refresh-token", default=None, help="Strava OAuth2 refresh token.")
@click.option("--raw-dir", default=None, help="Directory to save raw activity files.")
def fetch_strava(days: int, output_path: Optional[str], client_id: Optional[str], client_secret: Optional[str], refresh_token: Optional[str], raw_dir: Optional[str]):
    """Fetch and convert activities from Strava."""
    from fit2json.sources.strava import fetch_strava_activities, parse_strava_json
    from fit2json.output import build_output, write_json

    activity_files = fetch_strava_activities(
        days=days,
        output_dir=raw_dir,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
    )

    if not activity_files:
        return

    activities = []
    for fp in activity_files:
        try:
            activity = parse_strava_json(fp)
            activities.append(activity)
        except Exception as e:
            click.echo(f"  Warning: Failed to parse {fp.name}: {e}", err=True)

    if activities:
        doc = build_output(activities)
        write_json(doc, output_path)
        if output_path:
            click.echo(f"Written {len(activities)} activity/activities to {output_path}", err=True)


# ── analyze ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("file", type=click.Path(exists=True), required=False)
@click.option("-p", "--prompt", required=True, help="Analysis prompt or question.")
@click.option("--model", default=None, help="Model to use (default: gemini-3-pro-preview).")
@click.option("--token", default=None, help="GitHub personal access token.")
@click.option("--no-stream", is_flag=True, help="Disable streaming output.")
def analyze(file: Optional[str], prompt: str, model: Optional[str], token: Optional[str], no_stream: bool):
    """Analyze activity JSON with AI using GitHub Models API.

    Reads JSON from FILE or stdin (for piping from convert).
    """
    from fit2json.analyzer import analyze_activities

    if file:
        json_data = Path(file).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        json_data = sys.stdin.read()
        if not json_data.strip():
            raise click.ClickException("No data received from stdin.")
    else:
        raise click.ClickException("Provide a JSON file or pipe data from stdin.")

    analyze_activities(
        json_data=json_data,
        prompt=prompt,
        model=model,
        token=token,
        stream=not no_stream,
    )


if __name__ == "__main__":
    cli()
