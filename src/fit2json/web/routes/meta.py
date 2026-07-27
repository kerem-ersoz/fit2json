"""Meta endpoints: health check and client bootstrap config."""

from __future__ import annotations

from fastapi import APIRouter, Query

from fit2json import __version__, analyzer
from fit2json.web import services
from fit2json.web.config import get_settings
from fit2json.web.schemas import Backends, Branding, Config, Health

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", version=__version__)


@router.get("/config", response_model=Config)
def config() -> Config:
    settings = get_settings()
    return Config(
        brand=Branding(name=settings.brand_name, tagline=settings.brand_tagline),
        backends=Backends(
            copilot=analyzer.copilot_available(),
            default=analyzer.resolve_backend(None, None),
        ),
        library_dir=str(settings.library_dir),
        memory_dir=str(settings.memory_dir),
        base_path=settings.base_path,
        workout_prompt_default=services.CANONICAL_WORKOUT_PROMPT,
    )


@router.get("/models")
def models(backend: str = Query("copilot", description="copilot | ollama | lmstudio")):
    """Selectable models + reasoning-effort levels for a backend (queried live where possible)."""
    return services.available_models(backend)
