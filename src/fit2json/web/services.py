"""Service layer: a cached view over the on-disk workout-JSON library.

Reuses ``output`` (load/serialize), ``memory`` (headline metrics + corpus), and derives
"view original" deep links back to Garmin Connect / Strava. The library is scanned lazily
and re-indexed only when files change, so list calls stay cheap while detail/stream calls
re-read the single relevant file on demand.
"""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fit2json.memory import MemoryStore, _session_metrics
from fit2json.memory import activity_id as memory_activity_id
from fit2json.models import DecodedActivity
from fit2json.output import activities_from_obj, activity_filename
from fit2json.web import streams as streams_mod
from fit2json.web.config import get_settings


def _read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


def derive_source_ref(source: Optional[str], source_file: str) -> Optional[Dict[str, str]]:
    """Best-effort deep link to the original activity on Garmin Connect / Strava.

    IDs are recovered from the recorded ``source_file`` name:
      * Strava  ``{start}_{id}.strava.json``  → strava.com/activities/{id}
      * Garmin  ``{start}_{activityId}.fit``   → connect.garmin.com/modern/activity/{id}
    Returns ``None`` when no external id can be recovered (e.g. a generic local .fit).
    """
    name = source_file or ""

    strava = re.search(r"_(\d+)\.strava(?:\.json)?$", name)
    if source == "strava" or strava:
        if strava:
            sid = strava.group(1)
            return {
                "platform": "strava",
                "label": "Strava",
                "id": sid,
                "url": f"https://www.strava.com/activities/{sid}",
            }

    stem = name[:-4] if name.endswith(".fit") else name
    garmin = re.search(r"_(\d{6,})$", stem)
    if source == "garmin" or garmin:
        if garmin:
            gid = garmin.group(1)
            return {
                "platform": "garmin",
                "label": "Garmin Connect",
                "id": gid,
                "url": f"https://connect.garmin.com/modern/activity/{gid}",
            }

    return None


@dataclass
class _Located:
    path: Path
    index: int
    source: Optional[str]


@dataclass
class Library:
    """A lazily-indexed directory of per-activity workout JSON files."""

    root: Path
    _sig: Optional[Tuple] = None
    _summaries: List[Dict[str, Any]] = field(default_factory=list)
    _locator: Dict[str, _Located] = field(default_factory=dict)

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
        locator: Dict[str, _Located] = {}
        for path in files:
            try:
                data = _read_json(path)
            except Exception:
                continue
            source = None
            if isinstance(data, dict):
                source = (data.get("metadata") or {}).get("source")
            for i, act in enumerate(activities_from_obj(data)):
                aid = activity_filename(act, i)
                if aid in locator:  # disambiguate rare id collisions deterministically
                    n = 1
                    while f"{aid}-{n}" in locator:
                        n += 1
                    aid = f"{aid}-{n}"
                locator[aid] = _Located(path=path, index=i, source=source)
                summaries.append(self._summarize(aid, act, source))
        summaries.sort(key=lambda s: s.get("start_time") or "", reverse=True)
        self._summaries, self._locator, self._sig = summaries, locator, sig

    def _summarize(self, aid: str, act: DecodedActivity, source: Optional[str]) -> Dict[str, Any]:
        available_series, has_gps = streams_mod.scan_capabilities(act)
        return {
            "id": aid,
            "sport": act.sport,
            "start_time": act.start_time,
            "source_file": act.source_file,
            "source": source,
            "source_ref": derive_source_ref(source, act.source_file),
            "metrics": _session_metrics(act),
            "record_count": act.message_counts.get("record", 0),
            "available_series": available_series,
            "has_gps": has_gps,
        }

    def list(self) -> List[Dict[str, Any]]:
        self._ensure()
        return self._summaries

    def locate(self, activity_id: str) -> Optional[_Located]:
        self._ensure()
        return self._locator.get(activity_id)

    def get(self, activity_id: str) -> Optional[DecodedActivity]:
        loc = self.locate(activity_id)
        if loc is None:
            return None
        try:
            acts = activities_from_obj(_read_json(loc.path))
        except Exception:
            return None
        return acts[loc.index] if loc.index < len(acts) else None


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


def _memory_store() -> MemoryStore:
    return MemoryStore(get_settings().memory_dir)


# ── public accessors used by the routes ─────────────────────────────────────────


def list_activities() -> List[Dict[str, Any]]:
    return get_library().list()


def get_detail(activity_id: str) -> Optional[Dict[str, Any]]:
    lib = get_library()
    loc = lib.locate(activity_id)
    act = lib.get(activity_id)
    if act is None or loc is None:
        return None
    available_series, has_gps = streams_mod.scan_capabilities(act)
    session = (act.messages.get("session") or [{}])[0]
    return {
        "id": activity_id,
        "sport": act.sport,
        "start_time": act.start_time,
        "source_file": act.source_file,
        "source": loc.source,
        "source_ref": derive_source_ref(loc.source, act.source_file),
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


# ── analysis + memory ────────────────────────────────────────────────────────


def get_activity_for_analysis(activity_id: str) -> Optional[Tuple[DecodedActivity, Path]]:
    """Return the decoded activity and its on-disk path (for the copilot backend)."""
    lib = get_library()
    loc = lib.locate(activity_id)
    act = lib.get(activity_id)
    if act is None or loc is None:
        return None
    return act, loc.path


def _entry_view(store: MemoryStore, entry: Dict[str, Any], with_body: bool) -> Dict[str, Any]:
    view = {
        "entry_id": entry.get("entry_id"),
        "prompt": entry.get("prompt"),
        "created_at": entry.get("created_at"),
        "backend": entry.get("backend"),
        "model": entry.get("model"),
        "sport": entry.get("sport"),
        "date": entry.get("date"),
        "metrics": entry.get("metrics", {}),
    }
    if with_body:
        view["content"] = (store._entry_body(entry) or "").strip()
    return view


def list_analyses(activity_id: str) -> Optional[List[Dict[str, Any]]]:
    """Past analyses saved for one activity, newest first (with rendered body)."""
    act = get_library().get(activity_id)
    if act is None:
        return None
    store = _memory_store()
    aid = memory_activity_id(act)
    entries = [e for e in store.load_index() if e.get("activity_id") == aid]
    entries.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return [_entry_view(store, e, with_body=True) for e in entries]


def list_memory(
    sport: Optional[str] = None, days: Optional[int] = None, limit: int = 50
) -> List[Dict[str, Any]]:
    store = _memory_store()
    mode = "same-sport" if sport else "all"
    entries = store.recall(sport=sport, days=days, limit=limit, mode=mode)
    return [_entry_view(store, e, with_body=False) for e in entries]


def get_memory_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    store = _memory_store()
    for entry in store.load_index():
        if entry.get("entry_id") == entry_id:
            return _entry_view(store, entry, with_body=True)
    return None


# ── ingest (upload / fetch) ──────────────────────────────────────────────────


def store_activities(
    decoded: List[DecodedActivity], source: str
) -> Dict[str, Any]:
    """Write new activities to the library as JSON, deduped by activity id.

    Re-uploading or re-fetching the same activity is a no-op (skipped), so the
    library never accumulates duplicates. Returns the added summaries + skip count.
    """
    from fit2json.output import write_per_activity

    library_dir = get_settings().library_dir
    library_dir.mkdir(parents=True, exist_ok=True)

    lib = get_library()
    existing = {s["id"] for s in lib.list()}
    added_ids: List[str] = []
    skipped = 0

    for act in decoded:
        aid = activity_filename(act, 0)
        if aid in existing:
            skipped += 1
            continue
        write_per_activity([act], str(library_dir), source=source)
        existing.add(aid)
        added_ids.append(aid)

    lib._sig = None  # force re-index so the new files are picked up
    added_set = set(added_ids)
    added = [s for s in lib.list() if s["id"] in added_set]
    return {"added": added, "skipped": skipped}


def fetch_and_store(
    platform: str,
    days: int,
    email: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch recent activities from Garmin/Strava and store the new ones."""
    import tempfile

    from fit2json.parser import decode_fit_file

    raw_dir = tempfile.mkdtemp(prefix="fitsift_fetch_")
    decoded: List[DecodedActivity] = []

    if platform == "garmin":
        from fit2json.sources.garmin import fetch_garmin_activities

        paths = fetch_garmin_activities(
            days=days, output_dir=raw_dir, email=email, password=password, interactive=False
        )
        for p in paths:
            try:
                decoded.append(decode_fit_file(p))
            except Exception:
                continue
    elif platform == "strava":
        from fit2json.sources.strava import fetch_strava_activities, parse_strava_json

        paths = fetch_strava_activities(days=days, output_dir=raw_dir)
        for p in paths:
            try:
                decoded.append(parse_strava_json(p))
            except Exception:
                continue
    else:
        raise ValueError(f"Unknown platform: {platform}")

    result = store_activities(decoded, source=platform)
    result["fetched"] = len(decoded)
    return result
