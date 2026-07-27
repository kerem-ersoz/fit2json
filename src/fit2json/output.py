"""Serialize decoded activities to JSON — per-activity files, a combined file, or stdout."""

from __future__ import annotations

import gzip
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from fit2json import __version__
from fit2json.models import ActivityDocument, DecodedActivity


def build_document(activities: List[DecodedActivity], source: str = "local") -> ActivityDocument:
    """Wrap decoded activities with tool metadata."""
    return ActivityDocument(
        activities=activities,
        metadata={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool_version": __version__,
            "source": source,
            "activity_count": len(activities),
            "schema": "lossless-fit",
        },
    )


def _sanitize(text: str) -> str:
    """Make a string safe for use in a filename."""
    return re.sub(r"[^0-9A-Za-z._-]+", "-", text).strip("-") or "activity"


def activity_filename(activity: DecodedActivity, index: int = 0) -> str:
    """Build a stable, sortable base filename (no extension) for one activity."""
    start = activity.start_time or ""
    stamp = _sanitize(start.replace(":", "").replace("+00:00", "Z")) if start else f"activity{index:03d}"
    sport = _sanitize(activity.sport or "unknown")
    stem = _sanitize(Path(activity.source_file).stem)
    return f"{stamp}_{sport}_{stem}"


def _dumps(obj, indent: Optional[int]) -> str:
    return json.dumps(obj, indent=indent, ensure_ascii=False)


def _write_text(text: str, path: Path, gzip_out: bool) -> int:
    """Write text to path (optionally gzipped). Returns bytes written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    if gzip_out:
        with gzip.open(path, "wb") as fh:
            fh.write(data)
        return path.stat().st_size
    path.write_bytes(data)
    return len(data)


def write_combined(
    doc: ActivityDocument,
    output_path: Optional[str],
    indent: Optional[int] = 2,
    gzip_out: bool = False,
) -> Optional[Path]:
    """Write all activities as one document to a file, or to stdout if no path."""
    text = _dumps(doc.to_dict(), indent)
    if not output_path:
        sys.stdout.write(text)
        sys.stdout.write("\n")
        return None

    path = Path(output_path)
    if gzip_out and path.suffix != ".gz":
        path = path.with_suffix(path.suffix + ".gz")
    _write_text(text, path, gzip_out)
    return path


def _read_json_path(path: Path) -> Any:
    """Read a JSON file, transparently handling .gz."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


def load_activities(path: str | Path) -> List[DecodedActivity]:
    """Load decoded activities from a workout JSON file or a directory of them."""
    path = Path(path)
    files: List[Path]
    if path.is_dir():
        files = sorted(
            [p for p in path.rglob("*.json")] + [p for p in path.rglob("*.json.gz")]
        )
        files = [p for p in files if p.name != "index.jsonl"]
    else:
        files = [path]

    activities: List[DecodedActivity] = []
    for fp in files:
        data = _read_json_path(fp)
        activities.extend(activities_from_obj(data))
    return activities


def activities_from_obj(data: Any) -> List[DecodedActivity]:
    """Turn a parsed JSON object (combined doc or single activity) into activities."""
    if isinstance(data, dict) and "activities" in data:
        return [DecodedActivity.from_dict(a) for a in data.get("activities", [])]
    if isinstance(data, dict):
        return [DecodedActivity.from_dict(data)]
    return []


def write_per_activity(
    activities: List[DecodedActivity],
    out_dir: str,
    source: str = "local",
    indent: Optional[int] = 2,
    gzip_out: bool = False,
) -> List[Path]:
    """Write one JSON file per activity into ``out_dir``. Returns written paths."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    ext = ".json.gz" if gzip_out else ".json"

    for i, activity in enumerate(activities):
        payload = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "tool_version": __version__,
                "source": source,
                "schema": "lossless-fit",
            },
            **activity.to_dict(),
        }
        base = activity_filename(activity, i)
        path = directory / f"{base}{ext}"
        # Avoid clobbering when two activities share a base name.
        n = 1
        while path.exists():
            path = directory / f"{base}-{n}{ext}"
            n += 1
        _write_text(_dumps(payload, indent), path, gzip_out)
        written.append(path)

    return written
