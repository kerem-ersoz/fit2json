"""Athlete profile: personal data used to personalize analyses.

A small JSON file (default ``~/.fit2json/profile.json``) holds the athlete's height,
weight, heart-rate/power benchmarks, and goals. The web "You" tab reads/writes it, and
the ``analyze`` path (web + CLI, both backends) injects a human-readable summary into the
prompt so the model can reason about zones, calories, effort, and pacing in context.

Only the file I/O and prompt formatting live here; the analyzer stays decoupled and simply
takes the pre-formatted text block.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Known profile fields (used to filter what we persist / render). Everything is optional;
# the file only ever contains the fields the athlete actually set.
PROFILE_FIELDS = (
    "name",
    "sex",
    "birth_year",
    "height_cm",
    "weight_kg",
    "resting_hr",
    "max_hr",
    "lactate_threshold_hr",
    "ftp_w",
    "vo2max",
    "goals",
)


def default_profile_path() -> Path:
    return Path.home() / ".fit2json" / "profile.json"


def load_profile(path: Path) -> Dict[str, Any]:
    """Read the profile JSON, returning an empty dict if missing/unreadable."""
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k in PROFILE_FIELDS and v not in (None, "")}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def save_profile(path: Path, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the profile, dropping empty/unknown fields. Returns the cleaned dict."""
    cleaned = {
        k: v for k, v in profile.items() if k in PROFILE_FIELDS and v not in (None, "")
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False), encoding="utf-8")
    return cleaned


def format_profile_prompt(profile: Dict[str, Any]) -> str:
    """Render the profile as a compact prompt block, or "" when nothing is set."""
    if not profile:
        return ""

    lines: list[str] = []

    def add(label: str, value: Any, suffix: str = "") -> None:
        if value not in (None, ""):
            lines.append(f"- {label}: {value}{suffix}")

    add("Name", profile.get("name"))
    sex = profile.get("sex")
    if sex and str(sex).lower() not in ("", "unspecified"):
        add("Sex", sex)

    birth_year = profile.get("birth_year")
    if isinstance(birth_year, int) and 1900 < birth_year <= datetime.now(timezone.utc).year:
        age = datetime.now(timezone.utc).year - birth_year
        add("Age", f"{age} (born {birth_year})")

    add("Height", profile.get("height_cm"), " cm")
    add("Weight", profile.get("weight_kg"), " kg")
    add("Resting HR", profile.get("resting_hr"), " bpm")
    add("Max HR", profile.get("max_hr"), " bpm")
    add("Lactate threshold HR", profile.get("lactate_threshold_hr"), " bpm")
    add("FTP", profile.get("ftp_w"), " W")
    add("VO2max", profile.get("vo2max"), " ml/kg/min")
    add("Goals / notes", profile.get("goals"))

    if not lines:
        return ""

    header = (
        "The athlete has provided this personal profile. Use it to personalize heart-rate "
        "and power zones, calorie and effort estimates, pacing, and coaching advice:"
    )
    return header + "\n" + "\n".join(lines)
