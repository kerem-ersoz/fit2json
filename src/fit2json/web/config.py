"""Runtime settings for the FitSift web app, resolved from env vars with sane defaults.

Env vars (all optional):
  FITSIFT_LIBRARY        Directory of per-activity workout JSON (default ~/.fit2json/library/json).
  FITSIFT_MEMORY         Training-memory corpus dir (default ./fit2json-memory).
  FITSIFT_FRONTEND_DIST  Path to the built SPA (frontend/dist) to serve alongside the API.
  FITSIFT_CORS_ORIGINS   Comma-separated allowed origins (default "*", fine for local use).
  FITSIFT_BASE_PATH      Base path the app is mounted under (default "/"; e.g. "/fitsift" later).
  FITSIFT_PROFILE        Athlete-profile JSON file (default ~/.fit2json/profile.json).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from fit2json.memory import DEFAULT_MEMORY_DIR
from fit2json.profile import default_profile_path
from fit2json.web import BRAND_NAME, BRAND_TAGLINE

load_dotenv()


def _default_library() -> Path:
    return Path.home() / ".fit2json" / "library" / "json"


@dataclass
class Settings:
    library_dir: Path
    memory_dir: Path
    frontend_dist: Optional[Path]
    cors_origins: List[str]
    profile_path: Path
    base_path: str = "/"
    brand_name: str = BRAND_NAME
    brand_tagline: str = BRAND_TAGLINE


def get_settings() -> Settings:
    """Resolve settings from the environment on each call (cheap; test-friendly)."""
    lib = os.environ.get("FITSIFT_LIBRARY") or os.environ.get("FIT2JSON_LIBRARY")
    mem = os.environ.get("FITSIFT_MEMORY") or os.environ.get("FIT2JSON_MEMORY")
    dist = os.environ.get("FITSIFT_FRONTEND_DIST")
    origins = os.environ.get("FITSIFT_CORS_ORIGINS")
    base = os.environ.get("FITSIFT_BASE_PATH", "/") or "/"
    profile = os.environ.get("FITSIFT_PROFILE")

    return Settings(
        library_dir=Path(lib).expanduser() if lib else _default_library(),
        memory_dir=Path(mem).expanduser() if mem else Path(DEFAULT_MEMORY_DIR),
        frontend_dist=Path(dist).expanduser() if dist else None,
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()] if origins else ["*"],
        profile_path=Path(profile).expanduser() if profile else default_profile_path(),
        base_path=base if base.startswith("/") else f"/{base}",
    )
