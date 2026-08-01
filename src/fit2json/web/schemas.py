"""Pydantic response models for the stable meta endpoints.

Dynamic, lossless payloads (activity detail / streams / raw) are returned as plain
dicts since their shape mirrors the FIT data itself.
"""

from __future__ import annotations

from typing import List, Optional

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
    chats_dir: str
    base_path: str
    workout_prompt_default: str


class AnalyzeRequest(BaseModel):
    # One of activity_id / activity_ids is required. activity_ids enables analyzing
    # several workouts together (comparisons, weekly reviews); activity_id is kept for
    # back-compat with the single-workout detail panel.
    activity_id: Optional[str] = None
    activity_ids: Optional[List[str]] = None
    prompt: str
    # Overrides the per-workout building-block prompt used by the multi-workout map step.
    workout_prompt: Optional[str] = None
    backend: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    recall: str = "auto"
    recall_days: Optional[int] = None
    recall_limit: int = 8
    no_memory: bool = False
    charts: bool = True


class InfographicRequest(BaseModel):
    """Optional second pass: re-render a finished analysis as an HTML infographic.

    ``analysis`` is the markdown analysis text to visualize. The model/backend fields
    mirror :class:`AnalyzeRequest` so the infographic can be produced at the same tier
    as the analysis it came from.
    """

    analysis: str
    backend: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None


class InfographicOptions(BaseModel):
    """Optional generation controls for a saved analysis's infographic (all default)."""

    backend: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None


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


class ChatMessage(BaseModel):
    """One durable turn in a persisted conversation."""

    id: str
    role: str  # "user" | "assistant"
    content: str
    created_at: Optional[str] = None


class ChatSave(BaseModel):
    """Upsert payload for a chat session (PUT /chats/{id})."""

    title: Optional[str] = None
    backend: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    activity_ids: List[str] = Field(default_factory=list)
    messages: List[ChatMessage] = Field(default_factory=list)


class Chat(BaseModel):
    """A full persisted chat session, including its messages."""

    id: str
    title: str
    created_at: str
    updated_at: str
    backend: str = ""
    model: str = ""
    reasoning_effort: str = ""
    activity_ids: List[str] = Field(default_factory=list)
    messages: List[ChatMessage] = Field(default_factory=list)


class ChatSummary(BaseModel):
    """Lightweight list item for the chat history (no message bodies)."""

    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    backend: str = ""
    model: str = ""
    activity_ids: List[str] = Field(default_factory=list)


class ChatList(BaseModel):
    chats: List[ChatSummary]
