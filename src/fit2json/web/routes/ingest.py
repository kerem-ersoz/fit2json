"""Ingest endpoints: upload/convert .fit files, or fetch from Garmin / Strava."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from fit2json.web import services
from fit2json.web.schemas import FetchRequest

router = APIRouter(tags=["ingest"])


@router.post("/convert")
async def convert(files: List[UploadFile] = File(...)):
    """Decode uploaded .fit file(s) to lossless JSON and store them in the library."""
    from fit2json.parser import decode_fit_file

    decoded = []
    errors = []
    for upload in files:
        name = upload.filename or "upload.fit"
        if not name.lower().endswith(".fit"):
            errors.append({"file": name, "error": "Not a .fit file"})
            continue
        content = await upload.read()
        tmp_dir = Path(tempfile.mkdtemp(prefix="fitsift_up_"))
        tmp = tmp_dir / Path(name).name
        try:
            tmp.write_bytes(content)
            decoded.append(decode_fit_file(tmp))
        except Exception as exc:
            errors.append({"file": name, "error": str(exc)})
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass

    result = services.store_activities(decoded, source="local")
    return {"added": result["added"], "skipped": result["skipped"], "errors": errors}


@router.post("/fetch/{platform}")
def fetch(platform: str, req: FetchRequest):
    """Fetch recent activities from Garmin Connect or Strava and store new ones."""
    if platform not in ("garmin", "strava"):
        raise HTTPException(status_code=404, detail="Unknown platform")
    try:
        return services.fetch_and_store(platform, req.days, req.email, req.password)
    except HTTPException:
        raise
    except Exception as exc:  # click.ClickException / requests errors → friendly 400
        message = getattr(exc, "message", None) or str(exc)
        raise HTTPException(status_code=400, detail=message) from exc
