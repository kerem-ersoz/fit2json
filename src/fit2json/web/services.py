"""Service layer: a cached view over the on-disk workout-JSON library.

Reuses ``output`` (load/serialize) and ``memory`` (headline metrics). The library is
scanned lazily and re-indexed only when files change (mtime/size signature), so list
calls stay cheap while detail/stream calls re-read the single relevant file on demand.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fit2json.memory import _session_metrics
from fit2json.models import DecodedActivity
from fit2json.output import activities_from_obj, activity_filename
from fit2json.web import streams as streams_mod
from fit2json.web.config import get_settings


def _read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Library:
    """A lazily-indexed directory of per-activity workout JSON files."""

    root: Path
    _sig: Optional[Tuple] = None
    _summaries: List[Dict[str, Any]] = field(default_factory=list)
    _locator: Dict[str, Tuple[Path, int]] = field(default_factory=dict)

    def _scan_files(self) -> List[Path]:
        if not self.root.exists():
            return []
        files = list(self.root.rglob("*.json")) + list(self.root.rglob("*.json.gz"))
        return sorted(p for p in files if p.name != "index.jsonl")

    @staticmethod
    def _signature(files: List[Path]) -> Tuple:
        out = []
        for p in files:
            try:
                st = p.stat()
                out.append((str(p), st.st_mtime_ns, st.st_size))
            except OSError:
                continue
        return tuple(out)

    def _ensure(self) -> None:
        files = self._scan_files()
        sig = self._signature(files)
        if sig == self._sig:
            return
        summaries: List[Dict[str, Any]] = []
        locator: Dict[str, Tuple[Path, int]] = {}
        for path in files:
            try:
                data = _read_json(path)
            except Exception:
                continue
            for i, act in enumerate(activities_from_obj(data)):
                aid = activity_filename(act, i)
                if aid in locator:  # disambiguate rare id collisions deterministically
                    n = 1
                    while f"{aid}-{n}" in locator:
                        n += 1
                    aid = f"{aid}-{n}"
                locator[aid] = (path, i)
                summaries.append(self._summarize(aid, path, act))
        summaries.sort(key=lambda s: s.get("start_time") or "", reverse=True)
        self._summaries, self._locator, self._sig = summaries, locator, sig

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return path.name

    def _summarize(self, aid: str, path: Path, act: DecodedActivity) -> Dict[str, Any]:
        available_series, has_gps = streams_mod.scan_capabilities(act)
        return {
            "id": aid,
            "sport": act.sport,
            "start_time": act.start_time,
            "source_file": act.source_file,
            "file": self._rel(path),
            "metrics": _session_metrics(act),
            "record_count": act.message_counts.get("record", 0),
            "available_series": available_series,
            "has_gps": has_gps,
        }

    def list(self) -> List[Dict[str, Any]]:
        self._ensure()
        return self._summaries

    def get(self, activity_id: str) -> Optional[DecodedActivity]:
        self._ensure()
        loc = self._locator.get(activity_id)
        if loc is None:
            return None
        path, index = loc
        try:
            acts = activities_from_obj(_read_json(path))
        except Exception:
            return None
        return acts[index] if index < len(acts) else None


_libraries: Dict[str, Library] = {}


def get_library() -> Library:
    """Return a process-cached Library for the configured library dir."""
    root = get_settings().library_dir
    key = str(root)
    lib = _libraries.get(key)
    if lib is None:
        lib = Library(root=root)
        _libraries[key] = lib
    return lib


# ── public accessors used by the routes ─────────────────────────────────────────


def list_activities() -> List[Dict[str, Any]]:
    return get_library().list()


def get_detail(activity_id: str) -> Optional[Dict[str, Any]]:
    act = get_library().get(activity_id)
    if act is None:
        return None
    available_series, has_gps = streams_mod.scan_capabilities(act)
    session = (act.messages.get("session") or [{}])[0]
    return {
        "id": activity_id,
        "sport": act.sport,
        "start_time": act.start_time,
        "source_file": act.source_file,
        "message_counts": act.message_counts,
        "field_units": act.field_units,
        "metrics": _session_metrics(act),
        "session": session,
        "available_series": available_series,
        "has_gps": has_gps,
    }


def get_streams(
    activity_id: str, fields: Optional[List[str]], max_points: int
) -> Optional[Dict[str, Any]]:
    act = get_library().get(activity_id)
    if act is None:
        return None
    return streams_mod.build_streams(act, fields, max_points)


def get_laps(activity_id: str) -> Optional[List[Dict[str, Any]]]:
    act = get_library().get(activity_id)
    if act is None:
        return None
    return act.messages.get("lap") or []


def get_raw(activity_id: str) -> Optional[Dict[str, Any]]:
    act = get_library().get(activity_id)
    if act is None:
        return None
    return act.to_dict()
