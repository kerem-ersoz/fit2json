"""Streaming LLM analysis endpoint (Server-Sent Events).

- **Single workout**: analyze it directly (recall from memory, save the result).
- **Multiple workouts**: map-reduce. For each workout, reuse a saved analysis from the
  memory corpus when a tier-compatible one exists, otherwise run and save a concise
  per-workout analysis. Then run one nested synthesis over those per-workout analyses
  (not the raw data) and stream it back. The nested synthesis is not saved.

Reuse is tier-aware: an analysis is only reused when its (backend, model, reasoning
effort) matches the current request, so a weak-model analysis is never combined with a
powerful-model one inside a single synthesis.
"""

from __future__ import annotations

import json
from typing import Callable, Iterator, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from fit2json import analyzer
from fit2json.chats import ChatAnalysisInProgress, ChatStore, sanitize_id
from fit2json.memory import MemoryStore
from fit2json.web import services
from fit2json.web.analysis_runs import AnalysisRun, get_analysis_run_registry
from fit2json.web.config import get_settings
from fit2json.web.schemas import AnalysisRunInfo, AnalysisRunStart, AnalyzeRequest
from fit2json.web.sse import SSE_HEADERS, SSE_HEARTBEAT_SECONDS, stream_text_events
from fit2json.web.sse import sse as _sse

router = APIRouter(tags=["analyze"])


def _stream_text(
    backend: str,
    prompt: str,
    model,
    reasoning_effort,
    athlete_profile=None,
    event_handler: Optional[Callable[[dict], None]] = None,
) -> Iterator[str]:
    """Stream a model response for a prompt with no attached workout files."""
    if backend == "copilot":
        return analyzer.stream_copilot(
            prompt=prompt,
            workout_paths=[],
            memory_dir=None,
            model=model,
            silent=True,
            reasoning_effort=reasoning_effort or None,
            athlete_profile=athlete_profile,
            event_handler=event_handler,
            keepalive_interval=SSE_HEARTBEAT_SECONDS,
        )
    if backend in analyzer.LOCAL_BACKENDS:
        url, key = analyzer.LOCAL_BACKENDS[backend]
        return analyzer.stream_openai_compatible(
            prompt=prompt, workout_json="", base_url=url, api_key=key, memory_digest=None,
            model=model, athlete_profile=athlete_profile,
            keepalive_interval=SSE_HEARTBEAT_SECONDS,
        )
    raise ValueError(f"Unsupported analysis backend: {backend}")


def _model_events(stream: Iterator[str], copilot_events: List[dict]):
    """Separate durable answer text from live display events.

    Copilot message deltas are shown immediately, then replaced when the complete
    message reveals whether it was a final answer or an intermediate tool-call turn.
    Local backends have no structured event queue, so their text remains a normal delta.
    """
    committed: List[str] = []
    reasoning: dict = {}
    summary = ""
    structured = False

    def drain_pending():
        nonlocal summary
        emitted = []
        for event in copilot_events:
            event_type = event.get("type")
            data = event.get("data") or {}
            if event_type == "assistant.intent":
                summary = str(data.get("intent") or "").strip()
            elif event_type == "assistant.reasoning_delta":
                reasoning_id = str(data.get("reasoningId") or "reasoning")
                reasoning[reasoning_id] = reasoning.get(reasoning_id, "") + str(data.get("deltaContent") or "")
            elif event_type == "assistant.reasoning":
                reasoning_id = str(data.get("reasoningId") or "reasoning")
                reasoning[reasoning_id] = str(data.get("content") or "")
            elif event_type == "assistant.message_delta":
                text = str(data.get("deltaContent") or "")
                if text:
                    emitted.append(("delta", {"text": text}, ""))
                continue
            elif event_type == "assistant.message":
                phase = str(data.get("phase") or "")
                content = str(data.get("content") or "")
                accepted = bool(content) and not data.get("toolRequests") and phase not in {"thinking", "commentary"}
                display = "".join(committed) + (content if accepted else "")
                emitted.append(("replace", {"text": display}, ""))
                continue
            else:
                continue

            text = "\n\n".join(block.strip() for block in reasoning.values() if block.strip())
            if summary or text:
                emitted.append(("thinking", {"summary": summary, "text": text}, ""))
        copilot_events.clear()
        return emitted

    for chunk in stream:
        had_events = bool(copilot_events)
        if had_events:
            structured = True
            yield from drain_pending()
        if not chunk:
            if not had_events:
                yield "ping", {}, ""
            continue
        committed.append(chunk)
        yield None, {}, chunk
        if not structured:
            yield "delta", {"text": chunk}, ""

    if copilot_events:
        yield from drain_pending()


def _stream_response(stream: Iterator[str], copilot_events: List[dict]):
    """Yield SSE frames and the committed answer chunks used for persistence."""
    try:
        for event, data, answer_chunk in _model_events(stream, copilot_events):
            if event:
                yield _sse(event, data), ""
            if answer_chunk:
                yield "", answer_chunk
    finally:
        close = getattr(stream, "close", None)
        if close is not None:
            close()


def _synthesis_prompt(blocks, user_prompt: str) -> str:
    parts = [
        "You are comparing several of the athlete's workouts. Below are prior per-workout "
        "analyses, already distilled from the raw data. Reason over THESE analyses to answer "
        "the request — you are not given the raw files.",
    ]
    for i, (activity, text) in enumerate(blocks, 1):
        label = f"{activity.sport or 'workout'} — {activity.start_time or 'unknown date'}"
        parts.append(f"\n\n===== Workout {i}: {label} =====\n{text}")
    parts.append(f"\n\nThe athlete's request:\n{user_prompt}")
    return "\n".join(parts)


@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    gen = _prepare_event_gen(req)
    return StreamingResponse(gen, media_type="text/event-stream", headers=SSE_HEADERS)


def _prepare_event_gen(req: AnalyzeRequest) -> Iterator[str]:
    if not req.prompt.strip():
        raise HTTPException(status_code=422, detail="A prompt is required.")

    ids = req.activity_ids if req.activity_ids else ([req.activity_id] if req.activity_id else [])
    ids = [i for i in ids if i]

    resolved = analyzer.resolve_backend(req.backend, None)

    # No selection → freeform: the agent finds the relevant workouts itself.
    if not ids:
        return _freeform_event_gen(req, resolved)

    found = services.get_activities_for_analysis(ids)
    if found is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    return (
        _multi_event_gen(req, resolved, found, ids)
        if len(found) > 1
        else _single_event_gen(req, resolved, found[0])
    )


def _run_info(run: AnalysisRun) -> AnalysisRunInfo:
    return AnalysisRunInfo(**run.info())


@router.post("/analysis-runs", response_model=AnalysisRunInfo, status_code=202)
def start_analysis_run(body: AnalysisRunStart) -> AnalysisRunInfo:
    """Start inference independently of the response connection."""
    settings = get_settings()
    registry = get_analysis_run_registry(settings.chats_dir)

    supplied_chat_fields = (body.chat_id, body.assistant_message_id, body.chat)
    if any(value is not None for value in supplied_chat_fields) and not all(
        value is not None for value in supplied_chat_fields
    ):
        raise HTTPException(
            status_code=422,
            detail="chat_id, assistant_message_id, and chat must be provided together.",
        )

    chat_id = sanitize_id(body.chat_id) if body.chat_id is not None else None
    owner = (chat_id, body.assistant_message_id)
    store = ChatStore(settings.chats_dir) if chat_id is not None else None

    def finish(
        status: str,
        content: str,
        error: Optional[str],
        thinking_summary: str,
        thinking: str,
    ) -> None:
        if store is not None and chat_id is not None and body.assistant_message_id is not None:
            store.finish_analysis(
                chat_id,
                body.run_id,
                body.assistant_message_id,
                status,
                content,
                error,
                thinking_summary,
                thinking,
            )

    def persist_cancelled() -> None:
        if (
            store is None
            or chat_id is None
            or body.chat is None
            or body.assistant_message_id is None
        ):
            raise HTTPException(status_code=409, detail="Analysis run id is already in use.")
        store.start_analysis(
            chat_id,
            body.chat.model_dump(),
            body.run_id,
            body.assistant_message_id,
        )
        store.finish_analysis(
            chat_id,
            body.run_id,
            body.assistant_message_id,
            "cancelled",
            "",
        )

    def resolve_existing(run: AnalysisRun) -> AnalysisRunInfo:
        if run.matches_owner(owner):
            return _run_info(run)
        try:
            if run.claim_cancelled(owner, finish, persist_cancelled):
                return _run_info(run)
        except ChatAnalysisInProgress as exc:
            raise HTTPException(
                status_code=409,
                detail=f"This chat already has an active analysis ({exc.run_id}).",
            ) from exc
        if run.matches_owner(owner):
            return _run_info(run)
        raise HTTPException(status_code=409, detail="Analysis run id is already in use.")

    existing = registry.get(body.run_id)
    if existing is not None:
        return resolve_existing(existing)

    persisted = registry.persisted(body.run_id)
    if persisted is not None:
        info, persisted_owner = persisted
        if persisted_owner == owner:
            return AnalysisRunInfo(**info)
        if info["status"] == "cancelled" and persisted_owner == (None, None):
            persist_cancelled()
            claimed = registry.claim_persisted_cancelled(body.run_id, owner)
            if claimed is not None:
                return AnalysisRunInfo(**claimed)
        raise HTTPException(status_code=409, detail="Analysis run id is already in use.")

    source = _prepare_event_gen(body.analysis)

    run, created = registry.create(body.run_id, source, owner, finish)
    if not created:
        close = getattr(source, "close", None)
        if close is not None:
            close()
        return resolve_existing(run)

    try:
        if (
            store is not None
            and chat_id is not None
            and body.chat is not None
            and body.assistant_message_id is not None
        ):
            store.start_analysis(
                chat_id,
                body.chat.model_dump(),
                body.run_id,
                body.assistant_message_id,
            )
        run.start()
    except ChatAnalysisInProgress as exc:
        registry.discard(body.run_id)
        close = getattr(source, "close", None)
        if close is not None:
            close()
        raise HTTPException(
            status_code=409,
            detail=f"This chat already has an active analysis ({exc.run_id}).",
        ) from exc
    except Exception:
        registry.discard(body.run_id)
        if store is not None and chat_id is not None and body.assistant_message_id is not None:
            store.finish_analysis(
                chat_id,
                body.run_id,
                body.assistant_message_id,
                "failed",
                "",
                "Analysis could not be started.",
            )
        close = getattr(source, "close", None)
        if close is not None:
            close()
        raise
    return _run_info(run)


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunInfo)
def get_analysis_run(run_id: str) -> AnalysisRunInfo:
    run = get_analysis_run_registry(get_settings().chats_dir).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return _run_info(run)


@router.get("/analysis-runs/{run_id}/events")
def analysis_run_events(run_id: str, after: int = Query(default=0, ge=0)):
    run = get_analysis_run_registry(get_settings().chats_dir).get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return StreamingResponse(
        run.events(after),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/analysis-runs/{run_id}/cancel", response_model=AnalysisRunInfo)
def cancel_analysis_run(run_id: str) -> AnalysisRunInfo:
    registry = get_analysis_run_registry(get_settings().chats_dir)
    run, persisted = registry.cancel(run_id)
    if persisted is not None:
        info = persisted
        return AnalysisRunInfo(**info)
    assert run is not None
    return _run_info(run)


def _freeform_event_gen(req: AnalyzeRequest, resolved: str) -> Iterator[str]:
    """No workouts selected: let the backend find and analyze the relevant workouts itself."""
    settings = get_settings()
    effective_prompt = req.prompt + analyzer.CHART_INSTRUCTIONS if req.charts else req.prompt

    # Personal data from the "You" tab, injected so the model can personalize its analysis.
    athlete_profile = services.get_profile_prompt()
    copilot_events: List[dict] = []

    def build_stream() -> Iterator[str]:
        if resolved == "copilot":
            memory_dir = settings.memory_dir if settings.memory_dir.exists() else None
            return analyzer.stream_copilot(
                prompt=effective_prompt,
                workout_paths=[],
                memory_dir=memory_dir,
                model=req.model,
                silent=True,
                reasoning_effort=req.reasoning_effort or None,
                library_dir=settings.library_dir,
                athlete_profile=athlete_profile,
                event_handler=copilot_events.append,
                keepalive_interval=SSE_HEARTBEAT_SECONDS,
            )
        if resolved in analyzer.LOCAL_BACKENDS:
            url, key = analyzer.LOCAL_BACKENDS[resolved]
            index = (
                "The athlete's workout library (one line per workout: id · sport · date · "
                "distance · duration · avg HR):\n" + services.activity_index()
            )
            return analyzer.stream_openai_compatible(
                prompt=effective_prompt, workout_json=index, base_url=url, api_key=key,
                memory_digest=None, model=req.model, athlete_profile=athlete_profile,
                keepalive_interval=SSE_HEARTBEAT_SECONDS,
            )
        raise ValueError(f"Unsupported analysis backend: {resolved}")

    yield _sse("start", {"backend": resolved})
    chunks: List[str] = []
    try:
        for frame, chunk in _stream_response(build_stream(), copilot_events):
            if frame:
                yield frame
            if chunk:
                chunks.append(chunk)
    except Exception as exc:
        yield _sse("replace", {"text": "".join(chunks)})
        yield _sse("error", {"message": getattr(exc, "message", None) or str(exc)})
        return
    yield _sse("done", {"chars": len("".join(chunks)), "saved": None, "backend": resolved})


def _single_event_gen(req: AnalyzeRequest, resolved: str, found_one) -> Iterator[str]:
    activity, path = found_one

    # The model gets chart guidance appended (web only); memory keeps the original prompt.
    effective_prompt = req.prompt + analyzer.CHART_INSTRUCTIONS if req.charts else req.prompt

    # Personal data from the "You" tab, injected so the model can personalize its analysis.
    athlete_profile = services.get_profile_prompt()
    copilot_events: List[dict] = []

    store = None
    if not req.no_memory:
        store = MemoryStore(get_settings().memory_dir)
        store.root.mkdir(parents=True, exist_ok=True)

    def build_stream() -> Iterator[str]:
        if resolved == "copilot":
            return analyzer.stream_copilot(
                prompt=effective_prompt,
                workout_paths=[path],
                memory_dir=(store.root if store else None),
                model=req.model,
                silent=True,
                reasoning_effort=req.reasoning_effort,
                athlete_profile=athlete_profile,
                event_handler=copilot_events.append,
                keepalive_interval=SSE_HEARTBEAT_SECONDS,
            )
        if resolved in analyzer.LOCAL_BACKENDS:
            url, key = analyzer.LOCAL_BACKENDS[resolved]
            workout_json = json.dumps({"activities": [activity.to_dict()]}, ensure_ascii=False)
            digest = ""
            if store:
                entries = store.recall(activity.sport, req.recall_days, req.recall_limit, req.recall)
                digest = store.digest(entries)
            return analyzer.stream_openai_compatible(
                prompt=effective_prompt,
                workout_json=workout_json,
                base_url=url,
                api_key=key,
                memory_digest=digest,
                model=req.model,
                athlete_profile=athlete_profile,
                keepalive_interval=SSE_HEARTBEAT_SECONDS,
            )
        raise ValueError(f"Unsupported analysis backend: {resolved}")

    yield _sse("start", {"backend": resolved})
    chunks: List[str] = []
    try:
        for frame, chunk in _stream_response(build_stream(), copilot_events):
            if frame:
                yield frame
            if chunk:
                chunks.append(chunk)
    except Exception as exc:  # analyzer raises click.ClickException on failure
        yield _sse("replace", {"text": "".join(chunks)})
        yield _sse("error", {"message": getattr(exc, "message", None) or str(exc)})
        return

    analysis = "".join(chunks)
    saved = None
    if store and analysis.strip():
        try:
            saved = str(
                store.record(
                    activity,
                    req.prompt,
                    analysis,
                    backend=resolved,
                    model=req.model or "",
                    reasoning_effort=req.reasoning_effort or "",
                )
            )
        except Exception:
            saved = None
    yield _sse("done", {"chars": len(analysis), "saved": saved, "backend": resolved})


def _multi_event_gen(req: AnalyzeRequest, resolved: str, found, ids: List[str]) -> Iterator[str]:
    yield _sse("start", {"backend": resolved})
    total = len(found)
    blocks = []

    # MAP: ensure a tier-compatible per-workout analysis exists for each selected workout.
    workout_prompt = req.workout_prompt or services.CANONICAL_WORKOUT_PROMPT
    for i, ((activity, path), aid) in enumerate(zip(found, ids)):
        label = f"{activity.sport or 'workout'} · {(activity.start_time or '')[:10]}"
        yield _sse("step", {"index": i, "total": total, "label": label, "state": "start"})
        try:
            existing = services.latest_compatible_analysis(
                aid, resolved, req.model, req.reasoning_effort, workout_prompt
            )
            reused = existing is not None
            if reused:
                text = existing
            else:
                map_chunks: List[str] = []
                yield from stream_text_events(
                    services.stream_workout_analysis(
                        activity,
                        path,
                        resolved,
                        req.model,
                        req.reasoning_effort,
                        workout_prompt,
                        keepalive_interval=SSE_HEARTBEAT_SECONDS,
                    ),
                    map_chunks,
                )
                text = services.record_workout_analysis(
                    activity,
                    "".join(map_chunks),
                    resolved,
                    req.model,
                    req.reasoning_effort,
                    workout_prompt,
                )
        except Exception as exc:
            yield _sse("error", {"message": getattr(exc, "message", None) or str(exc)})
            return
        blocks.append((activity, text or ""))
        yield _sse("step", {"index": i, "total": total, "label": label, "reused": reused, "state": "done"})

    # REDUCE: one nested synthesis over the per-workout analyses. Never saved.
    synth = _synthesis_prompt(blocks, req.prompt)
    if req.charts:
        synth = synth + analyzer.CHART_INSTRUCTIONS
    # Personalize the synthesis (the step that answers the athlete's request) with the
    # "You" profile. The per-workout MAP analyses stay profile-free so they remain reusable.
    athlete_profile = services.get_profile_prompt()
    yield _sse("reduce", {"count": total})
    chunks: List[str] = []
    copilot_events: List[dict] = []
    try:
        stream = _stream_text(
            resolved,
            synth,
            req.model,
            req.reasoning_effort,
            athlete_profile,
            event_handler=copilot_events.append,
        )
        for frame, chunk in _stream_response(stream, copilot_events):
            if frame:
                yield frame
            if chunk:
                chunks.append(chunk)
    except Exception as exc:
        yield _sse("replace", {"text": "".join(chunks)})
        yield _sse("error", {"message": getattr(exc, "message", None) or str(exc)})
        return
    yield _sse("done", {"chars": len("".join(chunks)), "saved": None, "backend": resolved})
