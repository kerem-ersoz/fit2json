"""Data models for the lossless fit2json schema.

A decoded activity is a faithful dump of every FIT message and field. Messages are
grouped by name (order preserved within each group); every field keeps its decoded
value, and units are recorded once in a top-level legend for readability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Minimal fallback for the rare case a device stores `sport` as a raw integer
# (fitdecode normally decodes it to a string like "running").
SPORT_MAP = {
    0: "generic", 1: "running", 2: "cycling", 5: "swimming", 6: "basketball",
    7: "soccer", 9: "fitness_equipment", 10: "tennis", 11: "hiking", 13: "walking",
    15: "multi_sport", 17: "rowing", 22: "rock_climbing",
    23: "stand_up_paddleboarding", 29: "strength_training", 37: "yoga",
    53: "elliptical", 62: "inline_skating",
}


@dataclass
class DecodedActivity:
    """A losslessly decoded .fit file.

    Attributes:
        source_file: Original file name.
        messages: Mapping of FIT message name -> list of message dicts, each a
            mapping of field name -> decoded value. Preserves every message and field.
        field_units: Legend mapping field name -> unit string (e.g. "distance": "m").
    """

    source_file: str
    messages: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    field_units: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecodedActivity":
        """Reconstruct from a serialized workout dict (sport/start_time re-derived)."""
        return cls(
            source_file=data.get("source_file", "unknown"),
            messages=data.get("messages", {}) or {},
            field_units=data.get("field_units", {}) or {},
        )

    @property
    def _session(self) -> Dict[str, Any]:
        sessions = self.messages.get("session") or []
        return sessions[0] if sessions else {}

    @property
    def sport(self) -> Optional[str]:
        """Best-effort sport name, derived from the session message."""
        val = self._session.get("sport")
        if isinstance(val, str):
            return val.lower()
        if isinstance(val, int):
            return SPORT_MAP.get(val, f"sport_{val}")
        return None

    @property
    def start_time(self) -> Optional[str]:
        """ISO 8601 start time, from session, then activity, then first record."""
        activity = (self.messages.get("activity") or [{}])[0]
        record = (self.messages.get("record") or [{}])[0]
        for candidate in (
            self._session.get("start_time"),
            activity.get("local_timestamp"),
            activity.get("timestamp"),
            record.get("timestamp"),
        ):
            if candidate:
                return candidate
        return None

    @property
    def message_counts(self) -> Dict[str, int]:
        return {name: len(items) for name, items in self.messages.items()}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-ready dict with readable metadata up front."""
        return {
            "source_file": self.source_file,
            "sport": self.sport,
            "start_time": self.start_time,
            "message_counts": self.message_counts,
            "field_units": self.field_units,
            "messages": self.messages,
        }


@dataclass
class ActivityDocument:
    """A collection of decoded activities plus tool metadata."""

    activities: List[DecodedActivity] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata,
            "activities": [a.to_dict() for a in self.activities],
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
