"""Read-only activity endpoints backed by the on-disk workout-JSON library."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from fit2json.web import services

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("")
def list_activities():
    """List all activities in the library, most recent first."""
    return services.list_activities()


@router.get("/{activity_id}")
def get_activity(activity_id: str):
    """Summary detail for one activity (session, metrics, capabilities)."""
    detail = services.get_detail(activity_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return detail


@router.get("/{activity_id}/streams")
def get_streams(
    activity_id: str,
    fields: Optional[str] = Query(
        None, description="Comma-separated series (e.g. heart_rate,speed,altitude)."
    ),
    max_points: int = Query(2000, ge=0, le=50000, description="Downsample target; 0 = no limit."),
):
    """Downsampled, chart-ready time-series + GPS polyline for one activity."""
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None
    data = services.get_streams(activity_id, field_list, max_points)
    if data is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return data


@router.get("/{activity_id}/laps")
def get_laps(activity_id: str):
    """Lap messages for one activity."""
    laps = services.get_laps(activity_id)
    if laps is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return {"laps": laps}


@router.get("/{activity_id}/raw")
def get_raw(activity_id: str):
    """The full lossless activity document (for download / inspection)."""
    raw = services.get_raw(activity_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return JSONResponse(raw)
