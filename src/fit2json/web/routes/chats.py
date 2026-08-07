"""Persisted chat-session endpoints: list, read, upsert, and delete conversations.

The Analyze chat is durable and resumable — each conversation is stored as a JSON file
by :class:`fit2json.chats.ChatStore`. The client owns the message ids and PUTs the whole
document after each turn (upsert), so there's no separate create call and saves stay
idempotent.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from fit2json.chats import ChatStore
from fit2json.web.analysis_runs import get_analysis_run_registry
from fit2json.web.config import get_settings
from fit2json.web.schemas import Chat, ChatList, ChatRename, ChatSave, ChatSummary

router = APIRouter(prefix="/chats", tags=["chats"])


def _store() -> ChatStore:
    return ChatStore(get_settings().chats_dir)


@router.get("", response_model=ChatList)
def list_chats() -> ChatList:
    """All saved chats as lightweight summaries, most recently updated first."""
    return ChatList(chats=[ChatSummary(**chat) for chat in _store().list()])


@router.get("/{chat_id}", response_model=Chat)
def get_chat(chat_id: str) -> Chat:
    doc = _store().get(chat_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return Chat(**doc)


@router.put("/{chat_id}", response_model=Chat)
def save_chat(chat_id: str, body: ChatSave) -> Chat:
    """Upsert a chat. Creates the file on first save; overwrites it thereafter."""
    doc = _store().save(chat_id, body.model_dump())
    return Chat(**doc)


@router.patch("/{chat_id}", response_model=Chat)
def rename_chat(chat_id: str, body: ChatRename) -> Chat:
    doc = _store().rename(chat_id, body.title)
    if doc is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return Chat(**doc)


@router.delete("/{chat_id}")
def delete_chat(chat_id: str):
    store = _store()
    doc = store.get(chat_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    run = doc.get("analysis_run")
    if isinstance(run, dict) and run.get("status") in ("running", "cancelling"):
        active = get_analysis_run_registry(get_settings().chats_dir).get(str(run.get("id") or ""))
        if active is not None:
            active.cancel()
    store.delete(chat_id)
    return {"ok": True}
