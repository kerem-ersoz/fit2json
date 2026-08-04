"""Service layer: a cached view over the on-disk workout-JSON library.

Reuses ``output`` (load/serialize), ``memory`` (headline metrics + corpus), and derives
"view original" deep links back to Garmin Connect / Strava. The library is scanned lazily
and re-indexed only when files change, so list calls stay cheap while detail/stream calls
re-read the single relevant file on demand.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fit2json.memory import MemoryStore, _session_metrics
from fit2json.memory import activity_id as memory_activity_id
from fit2json.models import DecodedActivity
from fit2json.output import activity_filename
from fit2json.profile import load_profile, save_profile
from fit2json.web import streams as streams_mod
from fit2json.web.config import get_settings

logger = logging.getLogger(__name__)


def _read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(path.read_text(encoding="utf-8"))


# ── format compatibility (fit2json 0.1 "compact" ↔ 0.2 "lossless") ───────────────


def _is_legacy_activity(a: Any) -> bool:
    """True for a fit2json 0.1 compact activity (summary/time_series, no messages)."""
    return isinstance(a, dict) and "messages" not in a and (
        "summary" in a or "time_series_1min" in a
    )


def _legacy_to_decoded(a: Dict[str, Any]) -> DecodedActivity:
    """Adapt a 0.1 compact activity into a DecodedActivity (synthetic session + laps).

    The 0.1 format stored a rolled-up ``summary`` + 1-minute ``time_series`` rather than
    the lossless per-message tree, so we rebuild just enough (session + laps) for the UI's
    headline metrics. There's no GPS/per-second data at this fidelity.
    """
    summary = a.get("summary") or {}
    session: Dict[str, Any] = {}
    if a.get("sport"):
        session["sport"] = a["sport"]
    if a.get("start_time"):
        session["start_time"] = a["start_time"]

    def put(key: str, value: Any, mul: float = 1.0) -> None:
        if isinstance(value, (int, float)):
            session[key] = value * mul

    dist_km = summary.get("total_distance_km")
    dur_s = summary.get("total_duration_s")
    put("total_distance", dist_km, 1000.0)
    put("total_timer_time", dur_s)
    put("avg_heart_rate", summary.get("avg_heart_rate_bpm"))
    put("max_heart_rate", summary.get("max_heart_rate_bpm"))
    put("avg_cadence", summary.get("avg_cadence_spm"))
    put("total_calories", summary.get("total_calories"))
    put("total_ascent", summary.get("total_ascent_m"))
    put("total_descent", summary.get("total_descent_m"))
    if isinstance(dist_km, (int, float)) and isinstance(dur_s, (int, float)) and dur_s > 0:
        session["avg_speed"] = dist_km * 1000.0 / dur_s

    messages: Dict[str, List[Dict[str, Any]]] = {"session": [session]} if session else {}

    laps = a.get("laps")
    if isinstance(laps, list) and laps:
        lap_msgs: List[Dict[str, Any]] = []
        for lap in laps:
            if not isinstance(lap, dict):
                continue
            lm: Dict[str, Any] = {}
            ld = lap.get("distance_km")
            lt = lap.get("duration_s")
            if isinstance(ld, (int, float)):
                lm["total_distance"] = ld * 1000.0
            if isinstance(lt, (int, float)):
                lm["total_timer_time"] = lt
            if isinstance(lap.get("avg_heart_rate_bpm"), (int, float)):
                lm["avg_heart_rate"] = lap["avg_heart_rate_bpm"]
            if isinstance(lap.get("max_heart_rate_bpm"), (int, float)):
                lm["max_heart_rate"] = lap["max_heart_rate_bpm"]
            if isinstance(lap.get("avg_cadence_spm"), (int, float)):
                lm["avg_cadence"] = lap["avg_cadence_spm"]
            if isinstance(ld, (int, float)) and isinstance(lt, (int, float)) and lt > 0:
                lm["enhanced_avg_speed"] = ld * 1000.0 / lt
            lap_msgs.append(lm)
        if lap_msgs:
            messages["lap"] = lap_msgs

    field_units = {
        "total_distance": "m", "total_timer_time": "s", "avg_heart_rate": "bpm",
        "max_heart_rate": "bpm", "avg_cadence": "spm", "total_calories": "kcal",
        "total_ascent": "m", "total_descent": "m", "avg_speed": "m/s",
        "enhanced_avg_speed": "m/s",
    }
    return DecodedActivity(
        source_file=a.get("source_file", "unknown"), messages=messages, field_units=field_units
    )


def decoded_from_obj(data: Any) -> List[DecodedActivity]:
    """Decode a workout JSON object to activities, tolerant of 0.1 and 0.2 formats."""
    if isinstance(data, dict) and "activities" in data:
        items = data.get("activities") or []
    elif isinstance(data, dict):
        items = [data]
    else:
        items = []
    out: List[DecodedActivity] = []
    for a in items:
        out.append(_legacy_to_decoded(a) if _is_legacy_activity(a) else DecodedActivity.from_dict(a))
    return out


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
            for i, act in enumerate(decoded_from_obj(data)):
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
            "metrics": _clean_metrics(_session_metrics(act)),
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
            acts = decoded_from_obj(_read_json(loc.path))
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


def _scalar(value: Any) -> Any:
    """Unwrap a lossless multi-value field (e.g. [5.42, None]) to one value.

    The lossless decoder keeps repeated FIT fields as lists; headline metrics want a
    single number, so take the first non-None element.
    """
    if isinstance(value, list):
        for item in value:
            if item is not None:
                return item
        return None
    return value


def _clean_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _scalar(v) for k, v in metrics.items()}


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
        "metrics": _clean_metrics(_session_metrics(act)),
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


def get_activities_for_analysis(
    activity_ids: List[str],
) -> Optional[List[Tuple[DecodedActivity, Path]]]:
    """Resolve several activities (decoded + on-disk path). Returns None if any id is unknown."""
    lib = get_library()
    resolved: List[Tuple[DecodedActivity, Path]] = []
    for activity_id in activity_ids:
        loc = lib.locate(activity_id)
        act = lib.get(activity_id)
        if act is None or loc is None:
            return None
        resolved.append((act, loc.path))
    return resolved


# A fixed prompt for per-workout building-block analyses, so reused blocks are consistent.
CANONICAL_WORKOUT_PROMPT = (
    "Analyze this single workout: summarize pacing, heart-rate/power zones, effort "
    "distribution, and overall execution, with the key numbers. Be concise and factual — "
    "this will be reused as a building block when comparing several workouts. Output only "
    "the analysis itself, with no preamble."
)


def analysis_tier(
    backend: Optional[str], model: Optional[str], reasoning_effort: Optional[str]
) -> str:
    """Signature of the model/effort tier that produced an analysis.

    Building blocks fed into one synthesis must share a tier, so a weak-model analysis is
    never combined with a powerful-model one. 'auto' and an unset model are the same tier.
    """
    model_norm = (model or "").strip().lower()
    if model_norm == "auto":
        model_norm = ""
    return "|".join(
        [
            (backend or "").strip().lower(),
            model_norm,
            (reasoning_effort or "").strip().lower(),
        ]
    )


def available_models(backend: str) -> Dict[str, Any]:
    """Selectable models + reasoning-effort levels for a backend.

    - copilot: no list API, so offer 'auto', FitSift's long-context presets, and models
      actually used before (from the memory corpus); efforts come from the installed CLI.
    - ollama / lmstudio: live from the OpenAI-compatible ``/v1/models`` endpoint; no efforts.
    """
    from fit2json import analyzer

    b = (backend or "").strip().lower()
    if b == "copilot":
        curated = list(analyzer.COPILOT_LONG_CONTEXT_MODELS)
        seen: List[str] = []
        for entry in _all_memory_entries():
            if (entry.get("backend") or "").strip().lower() != "copilot":
                continue
            model = (entry.get("model") or "").strip()
            if model and model.lower() != "auto" and model not in curated and model not in seen:
                seen.append(model)
        seen.sort()
        return {
            "backend": "copilot",
            "models": ["auto", *curated, *seen],
            "efforts": analyzer.copilot_reasoning_efforts(),
            "allow_custom": True,
            "reachable": analyzer.copilot_available(),
        }
    if b in analyzer.LOCAL_BACKENDS:
        url, key = analyzer.LOCAL_BACKENDS[b]
        models: List[str] = []
        reachable = False
        try:
            client = analyzer._make_client(url, key)
            data = list(getattr(client.models.list(), "data", []) or [])
            models = [d.id for d in data if getattr(d, "id", None)]
            reachable = True
        except Exception:
            reachable = False
        return {
            "backend": b,
            "models": models,
            "efforts": [],
            "allow_custom": True,
            "reachable": reachable,
        }
    return {"backend": b, "models": [], "efforts": [], "allow_custom": True, "reachable": False}


def _raw_analyses_for(activity_id: str) -> List[Dict[str, Any]]:
    """Raw memory entries saved for one activity, newest first."""
    act = get_library().get(activity_id)
    if act is None:
        return []
    aid = memory_activity_id(act)
    src = act.source_file
    entries = [
        e
        for e in _all_memory_entries()
        if e.get("source_file") == src or e.get("activity_id") == aid
    ]
    entries.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return entries


def latest_compatible_analysis(
    activity_id: str,
    backend: str,
    model: Optional[str],
    reasoning_effort: Optional[str],
    prompt: Optional[str] = None,
) -> Optional[str]:
    """Body of the newest saved analysis for this activity at a matching tier (and prompt).

    Building blocks must be homogeneous, so reuse requires the same model/effort tier and,
    when a specific building-block prompt is in play, the same prompt.
    """
    target = analysis_tier(backend, model, reasoning_effort)
    store = _memory_store()
    for entry in _raw_analyses_for(activity_id):
        if analysis_tier(entry.get("backend"), entry.get("model"), entry.get("reasoning_effort")) != target:
            continue
        if prompt is not None and (entry.get("prompt") or "") != prompt:
            continue
        body = (store._entry_body(entry) or "").strip()
        if body:
            return body
    return None


def generate_workout_analysis(
    activity: DecodedActivity,
    path: Path,
    backend: str,
    model: Optional[str],
    reasoning_effort: Optional[str],
    prompt: Optional[str] = None,
    save: bool = True,
) -> str:
    """Run a concise single-workout analysis and (optionally) persist it as a memory building block."""
    from fit2json import analyzer

    workout_prompt = prompt or CANONICAL_WORKOUT_PROMPT

    if backend == "copilot":
        text = "".join(
            analyzer.stream_copilot(
                prompt=workout_prompt,
                workout_paths=[path],
                memory_dir=None,
                model=model,
                silent=True,
                reasoning_effort=reasoning_effort or None,
            )
        )
    elif backend in analyzer.LOCAL_BACKENDS:
        url, key = analyzer.LOCAL_BACKENDS[backend]
        workout_json = json.dumps({"activities": [activity.to_dict()]}, ensure_ascii=False)
        text = "".join(
            analyzer.stream_openai_compatible(
                prompt=workout_prompt,
                workout_json=workout_json,
                base_url=url,
                api_key=key,
                memory_digest=None,
                model=model,
            )
        )
    else:
        raise ValueError(f"Unsupported analysis backend: {backend}")

    text = (text or "").strip()
    if save and text:
        store = _memory_store()
        store.root.mkdir(parents=True, exist_ok=True)
        try:
            store.record(
                activity,
                workout_prompt,
                text,
                backend=backend,
                model=model or "",
                reasoning_effort=reasoning_effort or "",
            )
        except Exception:
            pass
    return text


def activity_index(limit: int = 200) -> str:
    """Compact one-line-per-workout index (for local backends in freeform mode)."""
    lines = []
    for s in list_activities()[:limit]:
        m = s.get("metrics") or {}
        parts = [
            s.get("id", ""),
            s.get("sport") or "activity",
            (s.get("start_time") or "")[:10],
        ]
        if m.get("distance_m"):
            parts.append(f"{round(m['distance_m'] / 1000, 2)}km")
        if m.get("duration_s"):
            parts.append(f"{round(m['duration_s'] / 60)}min")
        if m.get("avg_hr"):
            parts.append(f"{round(m['avg_hr'])}bpm")
        lines.append(" · ".join(str(p) for p in parts if p))
    return "\n".join(lines)


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
    src = act.source_file
    # Match by source_file (stable across formats) or the derived memory id.
    entries = [
        e for e in _all_memory_entries()
        if e.get("source_file") == src or e.get("activity_id") == aid
    ]
    entries.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return [_entry_view(store, e, with_body=True) for e in entries]


def list_memory(
    sport: Optional[str] = None, days: Optional[int] = None, limit: int = 50
) -> List[Dict[str, Any]]:
    from datetime import datetime, timedelta, timezone

    from fit2json.memory import _parse_date

    store = _memory_store()
    entries = _all_memory_entries()
    entries.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    if sport:
        entries = [e for e in entries if (e.get("sport") or "").lower() == sport.lower()]
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        floor = datetime.min.replace(tzinfo=timezone.utc)
        entries = [e for e in entries if (_parse_date(e.get("date")) or floor) >= cutoff]
    entries = entries[:limit]
    return [_entry_view(store, e, with_body=False) for e in entries]


def get_memory_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    store = _memory_store()
    for entry in _all_memory_entries():
        if entry.get("entry_id") == entry_id:
            return _entry_view(store, entry, with_body=True)
    return None


def _parse_memory_md(path: Path, root: Path) -> Optional[Dict[str, Any]]:
    """Parse one analysis .md file's front-matter into an index-style entry."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        logger.warning("Skipping non-UTF-8 memory file %s: %s", path, exc)
        return None
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    entry: Dict[str, Any] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if key == "prompt":
            try:
                entry["prompt"] = json.loads(value) if value else ""
            except json.JSONDecodeError:
                entry["prompt"] = value
        elif key == "metrics":
            try:
                entry["metrics"] = json.loads(value) if value else {}
            except json.JSONDecodeError:
                entry["metrics"] = {}
        else:
            entry[key] = value or None
    try:
        entry["path"] = str(path.relative_to(root))
    except ValueError:
        entry["path"] = path.name
    return entry


def _all_memory_entries() -> List[Dict[str, Any]]:
    """All saved analyses, reading the .md corpus as source of truth (index is a cache).

    Starts from index.jsonl (fast) then scans ``<memory>/<sport>/*.md`` so analyses that
    were never indexed (or an out-of-date index) are still picked up.
    """
    store = _memory_store()
    by_id: Dict[str, Dict[str, Any]] = {}
    for entry in store.load_index():
        eid = entry.get("entry_id")
        if eid:
            by_id[eid] = entry
    root = store.root
    if root.exists():
        for md in sorted(root.glob("*/*.md")):
            if md.name.startswith("."):
                continue
            parsed = _parse_memory_md(md, root)
            if parsed and parsed.get("entry_id") and parsed["entry_id"] not in by_id:
                by_id[parsed["entry_id"]] = parsed
    return list(by_id.values())


# ── athlete profile ──────────────────────────────────────────────────────────


def get_profile() -> Dict[str, Any]:
    """The saved athlete profile (empty dict when unset)."""
    return load_profile(get_settings().profile_path)


def update_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the athlete profile and return the cleaned, stored version."""
    return save_profile(get_settings().profile_path, profile)


def get_profile_prompt() -> Optional[str]:
    """Render the saved profile as a prompt block, or None when nothing is set."""
    from fit2json.profile import format_profile_prompt

    return format_profile_prompt(get_profile()) or None


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
