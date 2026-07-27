"""CLI entry point for fit2json — a fetch → lossless JSON → analysis harness."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import click
from dotenv import load_dotenv

from fit2json import __version__
from fit2json.models import DecodedActivity

load_dotenv()


@click.group()
@click.version_option(version=__version__, prog_name="fit2json")
def cli():
    """Pull workouts, store them as lossless JSON, and analyze them with an LLM."""


# ── helpers ──────────────────────────────────────────────────────────────────


def _human(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def _emit_activities(
    activities: List[DecodedActivity],
    output_path: Optional[str],
    gzip_out: bool,
    indent: Optional[int],
    source: str,
) -> None:
    """Write activities to stdout, a combined file, or per-activity files in a dir."""
    from fit2json.output import build_document, write_combined, write_per_activity

    is_combined_file = bool(output_path) and (
        output_path.endswith(".json") or output_path.endswith(".json.gz")
    )

    if not output_path:
        doc = build_document(activities, source)
        write_combined(doc, None, indent=indent, gzip_out=False)
        return

    if is_combined_file:
        doc = build_document(activities, source)
        path = write_combined(
            doc, output_path, indent=indent, gzip_out=gzip_out or output_path.endswith(".gz")
        )
        assert path is not None  # write_combined returns a path when output_path is set
        click.echo(
            f"Wrote {len(activities)} activity/ies to {path} ({_human(path.stat().st_size)})",
            err=True,
        )
        return

    paths = write_per_activity(
        activities, output_path, source=source, indent=indent, gzip_out=gzip_out
    )
    total = sum(p.stat().st_size for p in paths)
    click.echo(f"Wrote {len(paths)} file(s) to {output_path}/ ({_human(total)} total):", err=True)
    for p in paths:
        click.echo(f"  {p.name} ({_human(p.stat().st_size)})", err=True)


def _decode_fit_paths(fit_files: List[Path]) -> List[DecodedActivity]:
    from fit2json.parser import decode_fit_file

    activities: List[DecodedActivity] = []
    for i, fp in enumerate(fit_files, 1):
        click.echo(f"  [{i}/{len(fit_files)}] {fp.name}", err=True)
        try:
            activities.append(decode_fit_file(fp))
        except Exception as e:  # pragma: no cover - defensive
            click.echo(f"    Warning: Failed to parse {fp.name}: {e}", err=True)
    return activities


# ── convert ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "-o", "--output", "output_path", default=None,
    help="Output file (.json / .json.gz) or a directory (one file per activity). "
         "Defaults to stdout.",
)
@click.option("--gzip", "gzip_out", is_flag=True, help="Gzip the output.")
@click.option("--indent", type=int, default=2, help="JSON indentation (default: 2).")
@click.option("--compact", is_flag=True, help="No indentation — smallest files.")
def convert(path: str, output_path: Optional[str], gzip_out: bool, indent: int, compact: bool):
    """Decode local .fit file(s) into lossless JSON.

    PATH is a single .fit file or a directory of them.
    """
    from fit2json.sources.local import collect_fit_files

    try:
        fit_files = collect_fit_files(path)
    except (FileNotFoundError, ValueError) as e:
        raise click.ClickException(str(e)) from e

    click.echo(f"Decoding {len(fit_files)} .fit file(s)...", err=True)
    activities = _decode_fit_paths(fit_files)
    if not activities:
        raise click.ClickException("No activities were successfully parsed.")

    _emit_activities(activities, output_path, gzip_out, None if compact else indent, "local")


# ── fetch ──────────────────────────────────────────────────────────────────────


@cli.group()
def fetch():
    """Fetch activities from Garmin Connect or Strava."""


@fetch.command(name="garmin")
@click.option("--days", type=int, default=30, help="Days of history to fetch.")
@click.option("-o", "--output", "output_path", default="workouts",
              help="Output directory (one file per activity) or .json file. Default: ./workouts/")
@click.option("--gzip", "gzip_out", is_flag=True, help="Gzip the output.")
@click.option("--email", default=None, help="Garmin Connect email.")
@click.option("--password", default=None, help="Garmin Connect password.")
@click.option("--raw-dir", default=None, help="Directory to keep raw .fit files.")
@click.option("--token-dir", default=None,
              help="Garmin session token cache dir (or set GARMINTOKENS; default ~/.garminconnect). "
                   "Reuses a saved session so frequent polling avoids CAPTCHA / rate limiting.")
def fetch_garmin(days, output_path, gzip_out, email, password, raw_dir, token_dir):
    """Fetch Garmin Connect activities and store them as lossless JSON."""
    from fit2json.sources.garmin import fetch_garmin_activities

    fit_files = fetch_garmin_activities(
        days=days, output_dir=raw_dir, email=email, password=password, token_dir=token_dir
    )
    if not fit_files:
        return
    activities = _decode_fit_paths(fit_files)
    if activities:
        _emit_activities(activities, output_path, gzip_out, 2, "garmin")


@fetch.command(name="strava")
@click.option("--days", type=int, default=30, help="Days of history to fetch.")
@click.option("-o", "--output", "output_path", default="workouts",
              help="Output directory (one file per activity) or .json file. Default: ./workouts/")
@click.option("--gzip", "gzip_out", is_flag=True, help="Gzip the output.")
@click.option("--client-id", default=None, help="Strava API client ID.")
@click.option("--client-secret", default=None, help="Strava API client secret.")
@click.option("--refresh-token", default=None, help="Strava OAuth2 refresh token.")
@click.option("--raw-dir", default=None, help="Directory to keep raw stream files.")
def fetch_strava(days, output_path, gzip_out, client_id, client_secret, refresh_token, raw_dir):
    """Fetch Strava activities (best-effort, lower fidelity than .fit) as JSON.

    Note: Strava's API returns processed time-series streams, not raw .fit files, so this
    path cannot be truly lossless. For full fidelity, use Strava's bulk .fit export with
    `fit2json convert`.
    """
    from fit2json.sources.strava import fetch_strava_activities, parse_strava_json

    activity_files = fetch_strava_activities(
        days=days, output_dir=raw_dir, client_id=client_id,
        client_secret=client_secret, refresh_token=refresh_token,
    )
    if not activity_files:
        return

    activities: List[DecodedActivity] = []
    for fp in activity_files:
        try:
            activities.append(parse_strava_json(fp))
        except Exception as e:  # pragma: no cover - defensive
            click.echo(f"  Warning: Failed to parse {fp.name}: {e}", err=True)

    if activities:
        _emit_activities(activities, output_path, gzip_out, 2, "strava")


# ── analyze ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("source", type=click.Path(exists=True), required=False)
@click.option("-p", "--prompt", required=True, help="Analysis prompt / question.")
@click.option("--backend", type=click.Choice(["copilot", "ollama", "lmstudio"]), default=None,
              help="Analysis backend. Auto-detects Copilot CLI, else Ollama.")
@click.option("--base-url", default=None, help="Custom OpenAI-compatible endpoint.")
@click.option("--model", default=None, help="Model name (backend-specific).")
@click.option("--reasoning-effort", "--effort", "reasoning_effort",
              type=click.Choice(["none", "minimal", "low", "medium", "high", "xhigh", "max"]),
              default=None,
              help="Reasoning effort for the copilot backend (passed to the Copilot CLI).")
@click.option("--api-key", default=None, help="API key for a custom --base-url endpoint.")
@click.option("--no-stream", is_flag=True, help="Disable streaming output.")
@click.option("--max-chars", type=int, default=200_000,
              help="Max workout JSON chars to inline for local models (default: 200K).")
@click.option("--memory", "memory_dir", default=None,
              help="Memory corpus directory (default: ./fit2json-memory/).")
@click.option("--no-memory", is_flag=True, help="Do not read or write training memory.")
@click.option("--recall", type=click.Choice(["auto", "same-sport", "all", "none"]),
              default="auto", help="Which past memories to recall as context.")
@click.option("--recall-days", type=int, default=None, help="Only recall memories within N days.")
@click.option("--recall-limit", type=int, default=8, help="Max memories to recall (default: 8).")
def analyze(source, prompt, backend, base_url, model, reasoning_effort, api_key, no_stream, max_chars,
            memory_dir, no_memory, recall, recall_days, recall_limit):
    """Analyze workout JSON with an LLM, using and updating training memory.

    SOURCE is a workout JSON file or a directory of them. If omitted, JSON is read
    from stdin (e.g. piped from `fit2json convert`).
    """
    from fit2json import analyzer
    from fit2json.memory import DEFAULT_MEMORY_DIR, MemoryStore
    from fit2json.output import activities_from_obj, load_activities

    # 1) Resolve workout input into file paths (for copilot) and activities (for memory).
    workout_paths: List[Path] = []
    activities: List[DecodedActivity] = []
    inline_json: Optional[str] = None

    if source:
        src = Path(source)
        if src.is_dir():
            workout_paths = sorted(
                p for p in list(src.rglob("*.json")) + list(src.rglob("*.json.gz"))
                if p.name != "index.jsonl"
            )
        else:
            workout_paths = [src]
        activities = load_activities(src)
    else:
        if sys.stdin.isatty():
            raise click.ClickException("Provide a workout JSON file/dir or pipe data via stdin.")
        stdin_text = sys.stdin.read()
        if not stdin_text.strip():
            raise click.ClickException("No data received from stdin.")
        import json as _json
        activities = activities_from_obj(_json.loads(stdin_text))
        inline_json = stdin_text

    if not activities:
        raise click.ClickException("No activities found in the input.")

    # Primary activity (most recent) drives memory recall + the recorded entry.
    primary = max(activities, key=lambda a: a.start_time or "")

    # 2) Set up memory.
    store: Optional[MemoryStore] = None
    if not no_memory:
        store = MemoryStore(memory_dir or DEFAULT_MEMORY_DIR)
        store.root.mkdir(parents=True, exist_ok=True)

    resolved = analyzer.resolve_backend(backend, base_url)

    # 3) Run the chosen backend.
    if resolved == "copilot":
        # Copilot reads files itself; give it the workout(s) + memory dir by path.
        if not workout_paths and inline_json is not None:
            tmp = Path(tempfile.mkdtemp(prefix="fit2json_")) / "workout.json"
            tmp.write_text(inline_json, encoding="utf-8")
            workout_paths = [tmp]
        analysis = analyzer.run_copilot(
            prompt=prompt,
            workout_paths=workout_paths,
            memory_dir=(store.root if store else None),
            model=model,
            stream=not no_stream,
            reasoning_effort=reasoning_effort,
        )
    else:
        if base_url:
            key = api_key or "no-key"
            url = base_url
        else:
            url, key = analyzer.LOCAL_BACKENDS[resolved]
        # Combine workout JSON for inlining.
        if inline_json is not None:
            workout_json = inline_json
        else:
            import json as _json
            workout_json = _json.dumps(
                {"activities": [a.to_dict() for a in activities]}, ensure_ascii=False
            )
        digest = ""
        if store:
            entries = store.recall(primary.sport, recall_days, recall_limit, recall)
            digest = store.digest(entries)
        analysis = analyzer.run_openai_compatible(
            prompt=prompt,
            workout_json=workout_json,
            base_url=url,
            api_key=key,
            memory_digest=digest,
            model=model,
            stream=not no_stream,
            max_chars=max_chars,
        )

    # 4) Record memory.
    if store and analysis.strip():
        path = store.record(
            primary, prompt, analysis, backend=resolved, model=model or "",
        )
        click.echo(f"\nSaved analysis to memory: {path}", err=True)


# ── memory ─────────────────────────────────────────────────────────────────────


@cli.group()
def memory():
    """Inspect the training-memory corpus."""


@memory.command(name="path")
@click.option("--memory", "memory_dir", default=None, help="Memory directory.")
def memory_path(memory_dir):
    """Print the memory corpus location."""
    from fit2json.memory import DEFAULT_MEMORY_DIR, MemoryStore

    click.echo(MemoryStore(memory_dir or DEFAULT_MEMORY_DIR).root.resolve())


@memory.command(name="list")
@click.option("--memory", "memory_dir", default=None, help="Memory directory.")
@click.option("--sport", default=None, help="Filter by sport.")
@click.option("--days", type=int, default=None, help="Only entries within N days.")
@click.option("--limit", type=int, default=20, help="Max entries to show.")
def memory_list(memory_dir, sport, days, limit):
    """List stored analyses, most recent first."""
    from fit2json.memory import DEFAULT_MEMORY_DIR, MemoryStore

    store = MemoryStore(memory_dir or DEFAULT_MEMORY_DIR)
    mode = "same-sport" if sport else "all"
    entries = store.recall(sport=sport, days=days, limit=limit, mode=mode)
    if not entries:
        click.echo("No memories found.")
        return
    for e in entries:
        m = e.get("metrics", {})
        dist = m.get("distance_m")
        dist_km = f"{dist / 1000:.1f}km" if isinstance(dist, (int, float)) else "-"
        click.echo(
            f"{(e.get('date') or '')[:10]:10}  {e.get('sport','?'):10}  {dist_km:>8}  "
            f"{e.get('entry_id','')}"
        )


@memory.command(name="show")
@click.argument("entry_id")
@click.option("--memory", "memory_dir", default=None, help="Memory directory.")
def memory_show(entry_id, memory_dir):
    """Print a stored analysis by its entry id."""
    from fit2json.memory import DEFAULT_MEMORY_DIR, MemoryStore

    store = MemoryStore(memory_dir or DEFAULT_MEMORY_DIR)
    content = store.read_entry(entry_id)
    if content is None:
        raise click.ClickException(f"No memory entry found: {entry_id}")
    click.echo(content)


if __name__ == "__main__":
    cli()
