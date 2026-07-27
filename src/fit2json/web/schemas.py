"""Pydantic response models for the stable meta endpoints.

Dynamic, lossless payloads (activity detail / streams / raw) are returned as plain
dicts since their shape mirrors the FIT data itself.
"""

from __future__ import annotations

from pydantic import BaseModel


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
