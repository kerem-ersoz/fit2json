"""Athlete-profile endpoints: read and update the "You" configuration.

The profile is a small JSON file (see :mod:`fit2json.profile`) that personalizes
analyses. Physical measurements are stored in canonical metric units; the frontend
handles imperial display/entry.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import ValidationError

from fit2json.web import services
from fit2json.web.schemas import AthleteProfile

router = APIRouter(tags=["profile"])


def _coerce(raw: dict) -> AthleteProfile:
    """Build the model from a stored dict, tolerating a hand-edited/out-of-range file.

    ``profile.json`` is user-editable, so a correctly-typed but out-of-range value
    (e.g. ``height_cm: 400``) must not 500 the endpoint. Drop only the offending
    field(s) and keep the rest.
    """
    try:
        return AthleteProfile(**raw)
    except ValidationError:
        valid = {}
        for key, value in raw.items():
            try:
                AthleteProfile(**{key: value})
            except ValidationError:
                continue
            valid[key] = value
        return AthleteProfile(**valid)


@router.get("/profile", response_model=AthleteProfile)
def get_profile() -> AthleteProfile:
    return _coerce(services.get_profile())


@router.put("/profile", response_model=AthleteProfile)
def put_profile(profile: AthleteProfile) -> AthleteProfile:
    saved = services.update_profile(profile.model_dump(exclude_none=True))
    return AthleteProfile(**saved)
