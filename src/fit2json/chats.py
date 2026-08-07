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
from threading import RLock
from typing import Any, Dict, List, Optional

DEFAULT_CHATS_DIR = "~/.fit2json/chats"

# Chat ids are used as filenames, so keep them to a safe, unsurprising alphabet.
_ID_RE = re.compile(r"[^A-Za-z0-9._-]")
_MAX_ID_LEN = 128
_TITLE_MAX = 80
_VALID_ROLES = ("user", "assistant")
_STORE_LOCK = RLock()

INTERRUPTED_ANALYSIS_MESSAGE = (
    "Analysis was interrupted because the FitSift server stopped. Please try again."
)


class ChatAnalysisInProgress(Exception):
    """Raised when another model call already owns a chat."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Chat already has an active analysis ({run_id}).")


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


def _merge_messages(
    existing: List[Dict[str, Any]],
    incoming: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Preserve durable history and append turns a client has not saved yet."""
    if not existing:
        return incoming

    merged = list(existing)
    cursor = 0
    for candidate in incoming:
        match = None
        for index in range(cursor, len(existing)):
            current = existing[index]
            same_id = bool(candidate.get("id")) and candidate.get("id") == current.get("id")
            same_turn = (
                (not candidate.get("id") or not current.get("id"))
                and candidate.get("role") == current.get("role")
                and candidate.get("content") == current.get("content")
            )
            if same_id or same_turn:
                match = index
                break
        if match is None:
            merged.append(candidate)
        else:
            cursor = match + 1
    return merged


class ChatStore:
    """Read/write persisted chat sessions as one JSON file per chat."""

    def __init__(self, root: str | Path = DEFAULT_CHATS_DIR):
        self.root = Path(root).expanduser()

    def _path(self, chat_id: str) -> Path:
        return self.root / f"{sanitize_id(chat_id)}.json"

    # ── writing ──────────────────────────────────────────────────────────────

    def _write(self, doc: Dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(str(doc["id"]))
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _save_locked(self, chat_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert a chat. Sets ``created_at`` once and bumps ``updated_at``.

        The stored document is normalized so the on-disk shape stays stable no matter
        what the client sends (unknown keys dropped, messages cleaned, title derived).
        """
        cid = sanitize_id(chat_id)
        existing = self.get(cid)
        now = _now()

        incoming = [m for m in (_clean_message(m) for m in data.get("messages") or []) if m]
        analysis_run = (existing or {}).get("analysis_run")
        if isinstance(analysis_run, dict) and analysis_run.get("status") in (
            "running",
            "cancelling",
        ):
            messages = list((existing or {}).get("messages") or [])
        else:
            messages = _merge_messages(list((existing or {}).get("messages") or []), incoming)
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
        if isinstance(analysis_run, dict):
            doc["analysis_run"] = analysis_run

        self._write(doc)
        return doc

    def save(self, chat_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with _STORE_LOCK:
            return self._save_locked(chat_id, data)

    def rename(self, chat_id: str, title: str) -> Optional[Dict[str, Any]]:
        """Update only the title, leaving a server-owned transcript untouched."""
        with _STORE_LOCK:
            doc = self.get(chat_id)
            if doc is None:
                return None
            doc["title"] = title.strip()[:_TITLE_MAX + 1] or doc.get("title") or "New chat"
            doc["updated_at"] = _now()
            self._write(doc)
            return doc

    def start_analysis(
        self,
        chat_id: str,
        data: Dict[str, Any],
        run_id: str,
        assistant_message_id: str,
    ) -> Dict[str, Any]:
        """Persist the athlete turn and mark its server-owned analysis as running."""
        with _STORE_LOCK:
            existing = self.get(chat_id)
            existing_run = (existing or {}).get("analysis_run")
            if isinstance(existing_run, dict) and existing_run.get("status") in (
                "running",
                "cancelling",
            ):
                if existing_run.get("id") == run_id:
                    assert existing is not None
                    return existing
                raise ChatAnalysisInProgress(str(existing_run.get("id") or "unknown"))

            doc = self._save_locked(chat_id, data)
            now = _now()
            doc["analysis_run"] = {
                "id": run_id,
                "assistant_message_id": assistant_message_id,
                "status": "running",
                "error": None,
                "started_at": now,
                "finished_at": None,
            }
            doc["updated_at"] = now
            self._write(doc)
            return doc

    def finish_analysis(
        self,
        chat_id: str,
        run_id: str,
        assistant_message_id: str,
        status: str,
        content: str,
        error: Optional[str] = None,
        thinking_summary: str = "",
        thinking: str = "",
    ) -> bool:
        """Commit a terminal run state and any generated assistant text."""
        with _STORE_LOCK:
            doc = self.get(chat_id)
            if doc is None:
                return False
            run = doc.get("analysis_run")
            if not isinstance(run, dict) or run.get("id") != run_id:
                return False

            now = _now()
            if content.strip():
                message = _clean_message(
                    {
                        "id": assistant_message_id,
                        "role": "assistant",
                        "content": content,
                        "thinking_summary": thinking_summary,
                        "thinking": thinking,
                        "created_at": now,
                    }
                )
                messages = list(doc.get("messages") or [])
                if message is not None:
                    replaced = False
                    for index, existing in enumerate(messages):
                        if existing.get("id") == assistant_message_id:
                            messages[index] = message
                            replaced = True
                            break
                    if not replaced:
                        messages.append(message)
                doc["messages"] = messages

            run.update(
                {
                    "status": status,
                    "error": error,
                    "finished_at": now,
                }
            )
            doc["analysis_run"] = run
            doc["updated_at"] = now
            self._write(doc)
            return True

    def recover_interrupted_analyses(self) -> int:
        """Turn runs left active by a server restart into explicit failures."""
        if not self.root.exists():
            return 0
        recovered = 0
        with _STORE_LOCK:
            for path in self.root.glob("*.json"):
                if path.name.startswith("._"):
                    continue
                try:
                    doc = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(doc, dict) or not doc.get("id"):
                    continue
                run = doc.get("analysis_run")
                if not isinstance(run, dict) or run.get("status") not in ("running", "cancelling"):
                    continue
                now = _now()
                run.update(
                    {
                        "status": "failed",
                        "error": INTERRUPTED_ANALYSIS_MESSAGE,
                        "finished_at": now,
                    }
                )
                doc["analysis_run"] = run
                doc["updated_at"] = now
                self._write(doc)
                recovered += 1
        return recovered

    def delete(self, chat_id: str) -> bool:
        with _STORE_LOCK:
            path = self._path(chat_id)
            if path.exists():
                path.unlink()
                return True
            return False

    # ── reading ──────────────────────────────────────────────────────────────

    def get(self, chat_id: str) -> Optional[Dict[str, Any]]:
        with _STORE_LOCK:
            path = self._path(chat_id)
            if not path.exists():
                return None
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                return None
            return data if isinstance(data, dict) else None

    def list(self) -> List[Dict[str, Any]]:
        """Summaries (no message bodies) for every chat, newest-first."""
        if not self.root.exists():
            return []
        summaries: List[Dict[str, Any]] = []
        with _STORE_LOCK:
            for path in self.root.glob("*.json"):
                if path.name.startswith("._"):
                    continue
                try:
                    doc = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if not isinstance(doc, dict):
                    continue
                summaries.append(self._summary(doc))
        summaries.sort(key=lambda s: s.get("updated_at") or "", reverse=True)
        return summaries

    @staticmethod
    def _summary(doc: Dict[str, Any]) -> Dict[str, Any]:
        messages = doc.get("messages") or []
        analysis_run = doc.get("analysis_run")
        return {
            "id": doc.get("id", ""),
            "title": doc.get("title") or _derive_title(messages),
            "created_at": doc.get("created_at", ""),
            "updated_at": doc.get("updated_at", ""),
            "message_count": len(messages),
            "backend": doc.get("backend", ""),
            "model": doc.get("model", ""),
            "activity_ids": doc.get("activity_ids") or [],
            "analysis_status": (
                analysis_run.get("status") if isinstance(analysis_run, dict) else None
            ),
        }
