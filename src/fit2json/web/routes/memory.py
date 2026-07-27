"""Training-memory read endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from fit2json.web import services

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("")
def list_memory(
    sport: Optional[str] = Query(None, description="Filter by sport."),
    days: Optional[int] = Query(None, description="Only entries within N days."),
    limit: int = Query(50, ge=1, le=500),
):
    """List saved analyses across all activities, most recent first."""
    return {"entries": services.list_memory(sport=sport, days=days, limit=limit)}


@router.get("/{entry_id}")
def get_entry(entry_id: str):
    """Full markdown of one saved analysis."""
    entry = services.get_memory_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    return entry
