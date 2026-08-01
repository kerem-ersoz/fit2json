"""Training-memory read endpoints, plus cached infographic renderings of saved analyses.

An analysis saved in the memory corpus can be rendered as an infographic on demand; the
result is persisted next to the entry (keyed by ``entry_id``) so revisiting is instant and
never re-calls the model. The generation + serving mechanics are shared with the ephemeral
(chat) path in ``routes.infographic``.
"""

from __future__ import annotations

import re
from typing import Iterator, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from fit2json import analyzer
from fit2json.memory import MemoryStore
from fit2json.web import services
from fit2json.web.config import get_settings
from fit2json.web.routes import infographic as ig
from fit2json.web.schemas import InfographicOptions
from fit2json.web.sse import SSE_HEADERS
from fit2json.web.sse import sse as _sse

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


# ── infographic (cached visual rendering of a saved analysis) ────────────────────


def _store() -> MemoryStore:
    return MemoryStore(get_settings().memory_dir)


def _analysis_body(entry_id: str) -> Optional[str]:
    """The saved analysis text to visualize, minus the redundant header + prompt echo.

    Returns ``None`` when the entry doesn't exist. Mirrors the frontend's ``stripEcho`` so
    the infographic is built from the prose, not the "# Sport — date" / "**Prompt:**" lines.
    """
    entry = services.get_memory_entry(entry_id)
    if entry is None:
        return None
    body = entry.get("content") or ""
    body = re.sub(r"^\s*#\s+.*(?:\r?\n)+", "", body)  # "# Sport — date"
    prompt = entry.get("prompt")
    if prompt:
        body = body.replace(f"**Prompt:** {prompt}", "", 1)
    body = re.sub(r"^\s*\*\*Prompt:\*\*.*(?:\r?\n)+", "", body)  # fallback
    return body.strip()


@router.get("/{entry_id}/infographic")
def infographic_status(entry_id: str):
    """Whether a cached infographic exists for this saved analysis."""
    if services.get_memory_entry(entry_id) is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    store = _store()
    return {
        "exists": store.has_infographic(entry_id),
        "generated_at": store.infographic_generated_at(entry_id),
    }


@router.get("/{entry_id}/infographic/view")
def infographic_view(entry_id: str):
    """Serve the cached infographic as a CSP'd HTML page for the iframe."""
    html = _store().read_infographic(entry_id)
    if html is None:
        raise HTTPException(status_code=404, detail="No infographic for this analysis yet.")
    return ig.html_response(html)


@router.get("/{entry_id}/infographic/raw")
def infographic_raw(entry_id: str):
    """The stored infographic HTML as-is (for copy / download), without the resize shim."""
    html = _store().read_infographic(entry_id)
    if html is None:
        raise HTTPException(status_code=404, detail="No infographic for this analysis yet.")
    return Response(content=html, media_type="text/html", headers={"Cache-Control": "no-store"})


@router.post("/{entry_id}/infographic")
def infographic_generate(entry_id: str, opts: Optional[InfographicOptions] = None):
    """Generate (or regenerate) the infographic for a saved analysis and persist it.

    Streams SSE progress like the chat endpoint; on completion the HTML is written to the
    entry's sidecar so ``GET .../view`` serves it instantly thereafter.
    """
    body = _analysis_body(entry_id)
    if body is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    if not body.strip():
        raise HTTPException(status_code=422, detail="This analysis has no text to visualize.")

    opts = opts or InfographicOptions()
    resolved = analyzer.resolve_backend(opts.backend, None)
    store = _store()

    def gen() -> Iterator[str]:
        yield _sse("start", {"backend": resolved})
        chunks: List[str] = []
        try:
            for chunk in ig.stream_html(resolved, body, opts.model, opts.reasoning_effort):
                chunks.append(chunk)
                yield _sse("delta", {"text": chunk})
        except Exception as exc:  # analyzer raises click.ClickException on failure
            yield _sse("error", {"message": getattr(exc, "message", None) or str(exc)})
            return

        html = ig.clean_html("".join(chunks))
        if not html:
            yield _sse("error", {"message": "The model returned no HTML."})
            return
        store.write_infographic(entry_id, html)
        yield _sse(
            "done",
            {"chars": len(html), "backend": resolved, "generated_at": store.infographic_generated_at(entry_id)},
        )

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
