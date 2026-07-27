"""Streaming LLM analysis endpoint (Server-Sent Events).

Reuses the analyzer's streaming generators so the browser gets tokens as they are
produced (Copilot CLI or a local OpenAI-compatible model), then saves the finished
analysis to the training-memory corpus — exactly like the CLI ``analyze`` command.
"""

from __future__ import annotations

import json
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from fit2json import analyzer
from fit2json.memory import MemoryStore
from fit2json.web import services
from fit2json.web.config import get_settings
from fit2json.web.schemas import AnalyzeRequest

router = APIRouter(tags=["analyze"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=422, detail="A prompt is required.")

    found = services.get_activity_for_analysis(req.activity_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    activity, path = found

    resolved = analyzer.resolve_backend(req.backend, None)

    store = None
    if not req.no_memory:
        store = MemoryStore(get_settings().memory_dir)
        store.root.mkdir(parents=True, exist_ok=True)

    def build_stream() -> Iterator[str]:
        if resolved == "copilot":
            return analyzer.stream_copilot(
                prompt=req.prompt,
                workout_paths=[path],
                memory_dir=(store.root if store else None),
                model=req.model,
            )
        if resolved in analyzer.LOCAL_BACKENDS:
            url, key = analyzer.LOCAL_BACKENDS[resolved]
            workout_json = json.dumps({"activities": [activity.to_dict()]}, ensure_ascii=False)
            digest = ""
            if store:
                entries = store.recall(
                    activity.sport, req.recall_days, req.recall_limit, req.recall
                )
                digest = store.digest(entries)
            return analyzer.stream_openai_compatible(
                prompt=req.prompt,
                workout_json=workout_json,
                base_url=url,
                api_key=key,
                memory_digest=digest,
                model=req.model,
            )
        raise ValueError(f"Unsupported analysis backend: {resolved}")

    def event_gen() -> Iterator[str]:
        yield _sse("start", {"backend": resolved})
        chunks: list[str] = []
        try:
            for chunk in build_stream():
                chunks.append(chunk)
                yield _sse("delta", {"text": chunk})
        except Exception as exc:  # analyzer raises click.ClickException on failure
            message = getattr(exc, "message", None) or str(exc)
            yield _sse("error", {"message": message})
            return

        analysis = "".join(chunks)
        saved = None
        if store and analysis.strip():
            try:
                saved = str(
                    store.record(
                        activity, req.prompt, analysis, backend=resolved, model=req.model or ""
                    )
                )
            except Exception:
                saved = None
        yield _sse("done", {"chars": len(analysis), "saved": saved, "backend": resolved})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
