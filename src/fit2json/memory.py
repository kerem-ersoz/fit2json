"""Filesystem memory corpus for workout analyses.

Each analysis is saved as its own Markdown file (with a YAML-style front-matter block)
under ``<memory>/<sport>/`` with a date-prefixed name, and mirrored as one line in
``<memory>/index.jsonl``. This lets the harness — or Copilot's own file tools — recall
relevant past analyses by sport and time range to reason about training progress.

Default location: ``./fit2json-memory/`` (override with ``--memory``).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fit2json.models import DecodedActivity

DEFAULT_MEMORY_DIR = "fit2json-memory"
INDEX_NAME = "index.jsonl"


def _sanitize(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "-", text).strip("-") or "unknown"


def _short_hash(text: str, length: int = 8) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _session_metrics(activity: DecodedActivity) -> Dict[str, Any]:
    """Pull a compact set of headline metrics from the session message."""
    session = (activity.messages.get("session") or [{}])[0]

    def pick(*keys: str) -> Any:
        for key in keys:
            val = session.get(key)
            if val is not None:
                return val
        return None

    metrics = {
        "distance_m": pick("total_distance"),
        "duration_s": pick("total_timer_time", "total_elapsed_time"),
        "avg_hr": pick("avg_heart_rate"),
        "max_hr": pick("max_heart_rate"),
        "avg_speed_mps": pick("enhanced_avg_speed", "avg_speed"),
        "avg_power_w": pick("avg_power"),
        "total_calories": pick("total_calories"),
        "ascent_m": pick("total_ascent"),
    }
    metrics = {k: v for k, v in metrics.items() if v is not None}
    if metrics:
        return metrics

    # Legacy 0.1 compact schema: derive headline metrics from the top-level summary.
    summary = getattr(activity, "summary_hint", None) or {}
    if summary:
        dist_km = summary.get("total_distance_km")
        legacy = {
            "distance_m": dist_km * 1000 if isinstance(dist_km, (int, float)) else None,
            "duration_s": summary.get("total_duration_s"),
            "avg_hr": summary.get("avg_heart_rate_bpm"),
            "max_hr": summary.get("max_heart_rate_bpm"),
            "avg_power_w": summary.get("avg_power_w"),
            "total_calories": summary.get("total_calories"),
            "ascent_m": summary.get("total_ascent_m"),
        }
        metrics = {k: v for k, v in legacy.items() if v is not None}
    return metrics


def activity_id(activity: DecodedActivity) -> str:
    """Stable id for a workout, from start time + source file."""
    start = activity.start_time or ""
    stamp = _sanitize(start.replace(":", "").replace("+00:00", "Z")) if start else "nostart"
    return f"{stamp}_{_sanitize(Path(activity.source_file).stem)}"


class MemoryStore:
    """Read/write the filesystem memory corpus."""

    def __init__(self, root: str | Path = DEFAULT_MEMORY_DIR):
        self.root = Path(root)

    @property
    def index_path(self) -> Path:
        return self.root / INDEX_NAME

    # ── writing ────────────────────────────────────────────────────────────

    def record(
        self,
        activity: DecodedActivity,
        prompt: str,
        analysis: str,
        backend: str = "",
        model: str = "",
    ) -> Path:
        """Save one analysis as a memory file and append to the index."""
        sport = activity.sport or "unknown"
        aid = activity_id(activity)
        phash = _short_hash(prompt)
        entry_id = f"{aid}__{phash}"
        metrics = _session_metrics(activity)

        created_at = datetime.now(timezone.utc).isoformat()
        entry = {
            "entry_id": entry_id,
            "activity_id": aid,
            "date": activity.start_time,
            "sport": sport,
            "source_file": activity.source_file,
            "prompt": prompt,
            "backend": backend,
            "model": model,
            "created_at": created_at,
            "metrics": metrics,
        }

        sport_dir = self.root / _sanitize(sport)
        sport_dir.mkdir(parents=True, exist_ok=True)
        # aid is already date-prefixed and sortable; just append the prompt hash.
        path = sport_dir / f"{aid}_{phash}.md"
        entry["path"] = str(path.relative_to(self.root))

        path.write_text(self._render_markdown(entry, analysis), encoding="utf-8")
        self._append_index(entry)
        return path

    def _render_markdown(self, entry: Dict[str, Any], analysis: str) -> str:
        fm_keys = [
            "entry_id", "activity_id", "date", "sport", "source_file",
            "backend", "model", "created_at",
        ]
        lines = ["---"]
        for key in fm_keys:
            lines.append(f"{key}: {entry.get(key) if entry.get(key) is not None else ''}")
        lines.append(f"prompt: {json.dumps(entry.get('prompt', ''))}")
        if entry.get("metrics"):
            lines.append(f"metrics: {json.dumps(entry['metrics'])}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {entry.get('sport', 'workout').title()} — {entry.get('date', '')}")
        lines.append("")
        lines.append(f"**Prompt:** {entry.get('prompt', '')}")
        lines.append("")
        lines.append(analysis.strip())
        lines.append("")
        return "\n".join(lines)

    def _append_index(self, entry: Dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ── reading / recall ─────────────────────────────────────────────────────

    def load_index(self) -> List[Dict[str, Any]]:
        if not self.index_path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    def recall(
        self,
        sport: Optional[str] = None,
        days: Optional[int] = None,
        limit: Optional[int] = None,
        mode: str = "auto",
    ) -> List[Dict[str, Any]]:
        """Select relevant prior memories.

        modes: ``none`` (nothing), ``all`` (everything), ``same-sport`` (only ``sport``),
        ``auto`` (same sport within ``days``, then most-recent others up to ``limit``).
        """
        if mode == "none":
            return []

        entries = self.load_index()
        if not entries:
            return []

        entries.sort(key=lambda e: e.get("created_at") or "", reverse=True)

        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            entries = [e for e in entries if (_parse_date(e.get("date")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff]

        if mode == "same-sport" and sport:
            entries = [e for e in entries if (e.get("sport") or "").lower() == sport.lower()]
        elif mode == "auto" and sport:
            same = [e for e in entries if (e.get("sport") or "").lower() == sport.lower()]
            others = [e for e in entries if (e.get("sport") or "").lower() != sport.lower()]
            entries = same + others

        if limit:
            entries = entries[:limit]
        return entries

    def digest(self, entries: List[Dict[str, Any]], max_chars: int = 20_000) -> str:
        """Build a compact markdown digest of recalled memories for inlining."""
        if not entries:
            return ""
        lines = []
        for e in entries:
            m = e.get("metrics", {})
            dist = m.get("distance_m")
            dist_km = f"{dist / 1000:.2f}km" if isinstance(dist, (int, float)) else "?"
            dur = m.get("duration_s")
            dur_min = f"{dur / 60:.0f}min" if isinstance(dur, (int, float)) else "?"
            hr = m.get("avg_hr")
            date = (e.get("date") or "")[:10]
            lines.append(
                f"- {date} {e.get('sport','?')}: {dist_km}, {dur_min}"
                + (f", avg HR {hr}" if hr else "")
                + (f" — {e['prompt']}" if e.get("prompt") else "")
            )
            body = self._entry_body(e)
            if body:
                prose = [
                    ln for ln in body.splitlines()
                    if ln.strip() and not ln.startswith("#") and not ln.startswith("**Prompt:")
                ]
                snippet = " ".join(" ".join(prose).split())[:280]
                if snippet:
                    lines.append(f"    {snippet}")
            if sum(len(x) for x in lines) > max_chars:
                lines.append("    ...(older memories omitted)")
                break
        return "\n".join(lines)

    def _entry_body(self, entry: Dict[str, Any]) -> str:
        rel = entry.get("path")
        if not rel:
            return ""
        path = self.root / rel
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        return parts[2] if len(parts) == 3 else text

    def read_entry(self, entry_id: str) -> Optional[str]:
        for entry in self.load_index():
            if entry.get("entry_id") == entry_id:
                rel = entry.get("path")
                if rel and (self.root / rel).exists():
                    return (self.root / rel).read_text(encoding="utf-8")
        return None
