"""Pydantic response models for the stable meta endpoints.

Dynamic, lossless payloads (activity detail / streams / raw) are returned as plain
dicts since their shape mirrors the FIT data itself.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Health(BaseModel):
    status: str
    version: str


class Branding(BaseModel):
    name: str
    tagline: str


class Backends(BaseModel):
    copilot: bool
    default: str


class Config(BaseModel):
    brand: Branding
    backends: Backends
    library_dir: str
    memory_dir: str
    base_path: str


class AnalyzeRequest(BaseModel):
    activity_id: str
    prompt: str
    backend: Optional[str] = None
    model: Optional[str] = None
    recall: str = "auto"
    recall_days: Optional[int] = None
    recall_limit: int = 8
    no_memory: bool = False
    charts: bool = True


class FetchRequest(BaseModel):
    days: int = 30
    email: Optional[str] = None
    password: Optional[str] = None


class AthleteProfile(BaseModel):
    """Personal data configured on the "You" tab; injected into analyses.

    All fields are optional — the athlete fills in only what they know. Physical
    measurements are stored in canonical metric units (cm / kg); the frontend converts
    to/from the user's chosen unit system.
    """

    name: Optional[str] = None
    sex: Optional[str] = None
    birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    height_cm: Optional[float] = Field(default=None, gt=0, le=300)
    weight_kg: Optional[float] = Field(default=None, gt=0, le=500)
    resting_hr: Optional[int] = Field(default=None, gt=0, le=250)
    max_hr: Optional[int] = Field(default=None, gt=0, le=300)
    lactate_threshold_hr: Optional[int] = Field(default=None, gt=0, le=300)
    ftp_w: Optional[int] = Field(default=None, gt=0, le=2000)
    vo2max: Optional[float] = Field(default=None, gt=0, le=120)
    goals: Optional[str] = None
