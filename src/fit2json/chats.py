"""Persistent chat sessions for the FitSift web app.

The Analyze chat used to be ephemeral (in-browser only). This module gives each
conversation a durable home on disk so it can be resumed later: one JSON file per chat
under ``<chats>/`` (default ``~/.fit2json/chats``), named by a path-safe id. Listing
reads the small files and returns lightweight summaries (no message bodies) newest-first.

Only file I/O lives here; the web layer owns request/response shaping. This mirrors the
profile/memory persistence patterns already used elsewhere in the app.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CHATS_DIR = "~/.fit2json/chats"

# Chat ids are used as filenames, so keep them to a safe, unsurprising alphabet.
_ID_RE = re.compile(r"[^A-Za-z0-9._-]")
_MAX_ID_LEN = 128
_TITLE_MAX = 80
_VALID_ROLES = ("user", "assistant")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_id(chat_id: str) -> str:
    """Reduce an id to a safe filename stem (guards against path traversal)."""
    cleaned = _ID_RE.sub("-", (chat_id or "").strip()).strip("-.")
    return cleaned[:_MAX_ID_LEN] or "chat"


def _derive_title(messages: List[Dict[str, Any]]) -> str:
    """Fall back to the first user message (truncated) when no title is set."""
    for msg in messages:
        if msg.get("role") == "user":
            text = " ".join(str(msg.get("content", "")).split())
            if text:
                return text[:_TITLE_MAX] + ("…" if len(text) > _TITLE_MAX else "")
    return "New chat"


def _clean_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Keep only the durable parts of a message."""
    role = msg.get("role")
    if role not in _VALID_ROLES:
        return None
    content = msg.get("content")
    content = "" if content is None else str(content)
    out: Dict[str, Any] = {
        "id": str(msg.get("id") or ""),
        "role": role,
        "content": content,
    }
    if role == "assistant":
        thinking_summary = str(msg.get("thinking_summary") or "").strip()
        thinking = str(msg.get("thinking") or "").strip()
        if thinking_summary:
            out["thinking_summary"] = thinking_summary
        if thinking:
            out["thinking"] = thinking
    out["created_at"] = str(msg.get("created_at") or _now())
    return out


class ChatStore:
    """Read/write persisted chat sessions as one JSON file per chat."""

    def __init__(self, root: str | Path = DEFAULT_CHATS_DIR):
        self.root = Path(root).expanduser()

    def _path(self, chat_id: str) -> Path:
        return self.root / f"{sanitize_id(chat_id)}.json"

    # ── writing ──────────────────────────────────────────────────────────────

    def save(self, chat_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert a chat. Sets ``created_at`` once and bumps ``updated_at``.

        The stored document is normalized so the on-disk shape stays stable no matter
        what the client sends (unknown keys dropped, messages cleaned, title derived).
        """
        cid = sanitize_id(chat_id)
        existing = self.get(cid)
        now = _now()

        messages = [m for m in (_clean_message(m) for m in data.get("messages") or []) if m]
        title = str(data.get("title") or "").strip() or _derive_title(messages)

        activity_ids = [str(a) for a in (data.get("activity_ids") or []) if a]

        doc: Dict[str, Any] = {
            "id": cid,
            "title": title[:_TITLE_MAX + 1],
            "created_at": (existing or {}).get("created_at") or now,
            "updated_at": now,
            "backend": str(data.get("backend") or ""),
            "model": str(data.get("model") or ""),
            "reasoning_effort": str(data.get("reasoning_effort") or ""),
            "activity_ids": activity_ids,
            "messages": messages,
        }

        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(cid)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)  # atomic on the same filesystem
        return doc

    def delete(self, chat_id: str) -> bool:
        path = self._path(chat_id)
        if path.exists():
            path.unlink()
            return True
        return False

    # ── reading ──────────────────────────────────────────────────────────────

    def get(self, chat_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(chat_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def list(self) -> List[Dict[str, Any]]:
        """Summaries (no message bodies) for every chat, newest-first."""
        if not self.root.exists():
            return []
        summaries: List[Dict[str, Any]] = []
        for path in self.root.glob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            summaries.append(self._summary(doc))
        summaries.sort(key=lambda s: s.get("updated_at") or "", reverse=True)
        return summaries

    @staticmethod
    def _summary(doc: Dict[str, Any]) -> Dict[str, Any]:
        messages = doc.get("messages") or []
        return {
            "id": doc.get("id", ""),
            "title": doc.get("title") or _derive_title(messages),
            "created_at": doc.get("created_at", ""),
            "updated_at": doc.get("updated_at", ""),
            "message_count": len(messages),
            "backend": doc.get("backend", ""),
            "model": doc.get("model", ""),
            "activity_ids": doc.get("activity_ids") or [],
        }
