"""Garmin Connect API client for fetching .fit files."""

from __future__ import annotations

import os
import sys
import inspect
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import click

DEFAULT_TOKEN_DIR = "~/.garminconnect"


def _supports_param(func, name: str) -> bool:
    """Return True if ``func`` accepts a keyword parameter named ``name``."""
    try:
        return name in inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False


def _persist_tokens(client, token_dir: str) -> bool:
    """Persist the garth session to ``token_dir`` (best-effort, version-tolerant).

    garminconnect exposes its underlying garth client as ``.garth`` (<= 0.2.x) or
    ``.client`` (>= 0.3.x); try both so tokens are cached regardless of version.
    """
    for attr in ("garth", "client"):
        garth_client = getattr(client, attr, None)
        if garth_client is not None and hasattr(garth_client, "dump"):
            try:
                Path(token_dir).mkdir(parents=True, exist_ok=True)
                garth_client.dump(token_dir)
                return True
            except Exception:  # noqa: BLE001 - persistence is best-effort
                return False
    return False


def _resolve_token_dir(token_dir: Optional[str]) -> str:
    """Resolve the garth token-store directory to an absolute path.

    Priority: explicit ``token_dir`` argument > ``GARMINTOKENS`` env var >
    the library default (``~/.garminconnect``). The directory need not exist yet.
    """
    raw = token_dir or os.environ.get("GARMINTOKENS") or DEFAULT_TOKEN_DIR
    return str(Path(raw).expanduser())


def _init_garmin_client(
    email: Optional[str],
    password: Optional[str],
    token_dir: str,
    interactive: bool,
):
    """Return an authenticated Garmin client, reusing a cached session when possible.

    First tries to resume from the garth token store (no credentials required). If
    that fails (missing/expired/revoked tokens), falls back to an email/password
    login and persists the resulting tokens to ``token_dir`` so later runs can resume
    without a fresh login — which is what keeps frequent polling from tripping
    Garmin's CAPTCHA / rate limiting.
    """
    try:
        from garminconnect import (
            Garmin,
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
        )
    except ImportError:
        raise click.ClickException(
            "garminconnect package required. Install with: pip install garminconnect"
        )

    # 1) Try to resume from a previously cached token store.
    resume_error: Optional[Exception] = None
    try:
        client = Garmin()
        client.login(token_dir)
        click.echo(f"Resumed Garmin session from cached tokens ({token_dir}).")
        return client
    except GarminConnectTooManyRequestsError as e:
        raise click.ClickException(
            f"Garmin rate limit hit while resuming session: {e}. "
            "Wait a while before retrying."
        )
    except Exception as e:  # noqa: BLE001 - any resume failure falls back to login
        resume_error = e

    # 2) No usable cached session — fall back to a credential login.
    email = email or os.environ.get("GARMIN_EMAIL")
    password = password or os.environ.get("GARMIN_PASSWORD")

    if not email or not password:
        raise click.ClickException(
            "No cached Garmin session and no credentials provided. "
            "Set GARMIN_EMAIL and GARMIN_PASSWORD (or pass --email/--password). "
            f"(resume error: {resume_error})"
        )

    click.echo(f"Logging in to Garmin Connect as {email}...")

    # MFA handling varies by library version. When the constructor supports a
    # prompt_mfa callback (garminconnect >= 0.3), wire one up: prompt interactively,
    # or fail cleanly when unattended (the background job must rely on a pre-seeded
    # token store rather than blocking on an MFA prompt).
    ctor_kwargs = {"email": email, "password": password}
    if _supports_param(Garmin.__init__, "prompt_mfa"):
        if interactive:
            ctor_kwargs["prompt_mfa"] = lambda: click.prompt("Garmin MFA code").strip()
        else:
            def _mfa_unattended():
                raise GarminConnectAuthenticationError(
                    "Garmin requested an MFA code but this run is non-interactive."
                )

            ctor_kwargs["prompt_mfa"] = _mfa_unattended

    # login() resolves its tokenstore from GARMINTOKENS when given no argument, which
    # would make it try to *resume* again instead of authenticating. Clear it so this
    # is a genuine fresh credential login on every library version.
    saved_tokens_env = os.environ.pop("GARMINTOKENS", None)
    try:
        client = Garmin(**ctor_kwargs)
        client.login()
    except GarminConnectTooManyRequestsError as e:
        raise click.ClickException(f"Garmin rate limit hit during login: {e}.")
    except (GarminConnectAuthenticationError, GarminConnectConnectionError) as e:
        hint = (
            ""
            if interactive
            else " If this account uses MFA, seed the token store once with an "
            "interactive login (scripts/seed-garmin-login.sh) before enabling the "
            "background job."
        )
        raise click.ClickException(f"Garmin authentication failed: {e}.{hint}")
    except Exception as e:  # noqa: BLE001 - unexpected login failure
        raise click.ClickException(f"Garmin login failed: {e}")
    finally:
        if saved_tokens_env is not None:
            os.environ["GARMINTOKENS"] = saved_tokens_env

    # Persist tokens so subsequent runs can resume without a fresh login.
    if _persist_tokens(client, token_dir):
        click.echo(f"Saved Garmin session tokens to {token_dir}.")
    else:
        click.echo(f"Warning: could not persist Garmin tokens to {token_dir}.", err=True)

    return client


def _already_downloaded(save_dir: Path, activity_id) -> bool:
    """Return True if a .fit file for ``activity_id`` already exists in ``save_dir``.

    Downloaded files are named ``{startTimeLocal}_{activityId}.fit``, so the activity
    id is matched via the ``*_{activityId}.fit`` suffix.
    """
    return any(save_dir.glob(f"*_{activity_id}.fit"))


def fetch_garmin_activities(
    days: int = 30,
    output_dir: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    token_dir: Optional[str] = None,
    interactive: Optional[bool] = None,
) -> List[Path]:
    """Download recent .fit files from Garmin Connect.

    Args:
        days: Number of days of history to fetch.
        output_dir: Directory to save .fit files. Uses temp dir if None.
        email: Garmin Connect email. Falls back to GARMIN_EMAIL env var.
        password: Garmin Connect password. Falls back to GARMIN_PASSWORD env var.
        token_dir: garth token-store directory. Falls back to GARMINTOKENS env var,
            then ``~/.garminconnect``. Enables session reuse across runs.
        interactive: Whether a fresh login may prompt (e.g. for MFA). Defaults to
            whether stdin is a TTY.

    Returns:
        List of Paths to newly downloaded .fit files (already-present activities are
        skipped when ``output_dir`` points at a persistent library).
    """
    if interactive is None:
        interactive = sys.stdin.isatty()

    token_store = _resolve_token_dir(token_dir)

    save_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="fit2json_garmin_"))
    save_dir.mkdir(parents=True, exist_ok=True)

    client = _init_garmin_client(email, password, token_store, interactive)

    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    click.echo(f"Fetching activities from {start_date} to {end_date}...")
    activities = client.get_activities_by_date(start_date, end_date)

    if not activities:
        click.echo("No activities found in the date range.")
        return []

    downloaded: List[Path] = []
    skipped = 0
    for act in activities:
        activity_id = act.get("activityId")
        activity_name = act.get("activityName", "activity")
        start = act.get("startTimeLocal", "unknown")

        if activity_id is not None and _already_downloaded(save_dir, activity_id):
            skipped += 1
            continue

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

    if skipped:
        click.echo(f"Skipped {skipped} already-downloaded activity/activities.")
    click.echo(f"Downloaded {len(downloaded)} new .fit file(s) to {save_dir}")
    return downloaded
