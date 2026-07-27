"""Analysis orchestration harness.

Sends workout JSON plus a custom prompt to a pluggable backend:

* ``copilot``  — shells out to the GitHub Copilot CLI (`copilot -p ...`), passing the
  workout files (and the memory directory) by path so Copilot reads them with its own
  file tools. Sidesteps context-window limits for the large lossless schema.
* ``ollama`` / ``lmstudio`` — local OpenAI-compatible servers. Workout JSON is inlined
  (compacted to fit ``--max-chars``) since these can't read files themselves.
* ``--base-url`` — any other OpenAI-compatible endpoint.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, List, Optional

import click

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

SYSTEM_PROMPT = (
    "You are an expert running/cycling/fitness coach and data analyst. You analyze "
    "workout data provided as structured JSON (a faithful, lossless decode of the "
    "athlete's .fit files) and give specific, actionable feedback grounded in the actual "
    "numbers. When prior workout analyses are provided as memory/context, use them to "
    "comment on progress and trends over time. Use markdown for readability."
)

# Appended to the prompt (web UI only) to let the model draw bespoke, insightful charts
# instead of the basic graphs Garmin/Strava already show. Rendered client-side as Vega-Lite.
CHART_INSTRUCTIONS = (
    "\n\n---\n"
    "You may include up to 2 custom charts, but ONLY when they add genuine insight beyond "
    "the basic graphs the athlete already sees on Garmin/Strava — e.g. HR-vs-pace scatter, "
    "HR/pace decoupling over time, time-in-zone distribution, or week-over-week load from "
    "memory. To draw one, output a fenced code block whose info string is exactly "
    "`fitsift-chart`, containing a single valid Vega-Lite v5 JSON spec with the data inlined "
    "under `data.values`. Keep each spec small (aggregate or downsample to <=120 rows) and do "
    "NOT set `width` or `height`. Every chart must be grounded in this workout's actual "
    "numbers. Example:\n"
    "```fitsift-chart\n"
    '{"mark":"bar","data":{"values":[{"zone":"Z2","minutes":22},{"zone":"Z3","minutes":15}]},'
    '"encoding":{"x":{"field":"zone","type":"nominal"},"y":{"field":"minutes","type":"quantitative"}}}\n'
    "```\n"
    "Write the rest of your analysis as normal markdown around the chart(s)."
)

# Local OpenAI-compatible backends: (base_url, default api key)
LOCAL_BACKENDS = {
    "ollama": ("http://localhost:11434/v1", "ollama"),
    "lmstudio": ("http://localhost:1234/v1", "lm-studio"),
}


def copilot_available() -> bool:
    return shutil.which("copilot") is not None


def resolve_backend(backend: Optional[str], base_url: Optional[str]) -> str:
    """Pick a backend name. Auto-detects copilot (if installed) else ollama."""
    if base_url:
        return "openai-compatible"
    if backend:
        return backend
    if copilot_available():
        return "copilot"
    return "ollama"


# ── Copilot CLI backend ────────────────────────────────────────────────────────


def _build_copilot_prompt(
    prompt: str,
    workout_paths: List[Path],
    memory_dir: Optional[Path],
) -> str:
    lines = [SYSTEM_PROMPT, ""]
    if workout_paths:
        lines.append("Workout data to analyze (lossless FIT JSON), read these files:")
        lines += [f"  - {p}" for p in workout_paths]
        lines.append("")
    if memory_dir is not None:
        lines.append(
            f"Prior analyses are stored under: {memory_dir}\n"
            "Browse the relevant ones (by sport/date) to reason about progress and trends. "
            "The index.jsonl there lists every past analysis."
        )
        lines.append("")
    lines.append(f"Athlete's request:\n{prompt}")
    lines.append("")
    lines.append("Write the analysis to stdout as markdown. Do not modify any files.")
    return "\n".join(lines)


def run_copilot(
    prompt: str,
    workout_paths: List[Path],
    memory_dir: Optional[Path] = None,
    model: Optional[str] = None,
    stream: bool = True,
    silent: bool = True,
    reasoning_effort: Optional[str] = None,
) -> str:
    """Run analysis via the GitHub Copilot CLI subprocess.

    Thin wrapper over :func:`stream_copilot` that collects the streamed chunks and
    (optionally) echoes them to stdout, preserving the original CLI behavior.
    """
    chunks: List[str] = []
    for chunk in stream_copilot(
        prompt, workout_paths, memory_dir, model, silent=silent, reasoning_effort=reasoning_effort
    ):
        chunks.append(chunk)
        if stream:
            sys.stdout.write(chunk)
            sys.stdout.flush()
    return "".join(chunks)


def stream_copilot(
    prompt: str,
    workout_paths: List[Path],
    memory_dir: Optional[Path] = None,
    model: Optional[str] = None,
    silent: bool = True,
    reasoning_effort: Optional[str] = None,
) -> Iterator[str]:
    """Yield analysis text chunks from the GitHub Copilot CLI subprocess.

    Streams the CLI's stdout line by line so callers (CLI or web) can consume it
    incrementally. Raises ``click.ClickException`` if the CLI is missing or fails.

    When ``silent`` is True, passes ``--silent`` so the CLI emits *only* the final
    agent response — no tool-call trace or stats footer. Used by the web UI so saved
    analyses are clean prose + charts.
    """
    if not copilot_available():
        raise click.ClickException(
            "The 'copilot' CLI was not found on PATH. Install GitHub Copilot CLI, or use "
            "--backend ollama|lmstudio (or --base-url) for a local model."
        )

    full_prompt = _build_copilot_prompt(prompt, workout_paths, memory_dir)

    cmd = [
        "copilot",
        "-p", full_prompt,
        "--allow-all-tools",
        "--no-color",
        "--log-level", "none",
        "--model", model or "auto",
    ]
    if silent:
        cmd.append("--silent")
    if reasoning_effort:
        cmd += ["--reasoning-effort", reasoning_effort]
    allow_dirs = {str(p.parent.resolve()) for p in workout_paths}
    if memory_dir is not None:
        allow_dirs.add(str(Path(memory_dir).resolve()))
    for d in sorted(allow_dirs):
        cmd += ["--add-dir", d]

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        yield line
    proc.wait()
    if proc.returncode != 0:
        err = proc.stderr.read() if proc.stderr else ""
        raise click.ClickException(f"copilot CLI failed (exit {proc.returncode}): {err.strip()}")


# ── OpenAI-compatible backend (Ollama / LM Studio / custom) ─────────────────────


def _make_client(base_url: str, api_key: str):
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise click.ClickException("openai package required. Install with: pip install openai") from exc
    return OpenAI(base_url=base_url, api_key=api_key)


def _first_available_model(client) -> Optional[str]:
    try:
        models = client.models.list()
        data = list(getattr(models, "data", []) or [])
        if data:
            return data[0].id
    except Exception:
        return None
    return None


def _build_openai_messages(
    prompt: str,
    workout_json: str,
    memory_digest: Optional[str],
    max_chars: int,
) -> "List[ChatCompletionMessageParam]":
    """Build the system+user chat messages, compacting the workout JSON to fit."""
    workout_json = compact_workout_json(workout_json, max_chars)

    user_parts = []
    if memory_digest:
        user_parts.append(
            "Prior workout analyses (memory, for trend context):\n" + memory_digest
        )
    user_parts.append("Workout data (lossless FIT JSON):\n```json\n" + workout_json + "\n```")
    user_parts.append("Athlete's request:\n" + prompt)

    messages: "List[ChatCompletionMessageParam]" = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]
    return messages


def stream_openai_compatible(
    prompt: str,
    workout_json: str,
    base_url: str,
    api_key: str,
    memory_digest: Optional[str] = None,
    model: Optional[str] = None,
    max_chars: int = 200_000,
) -> Iterator[str]:
    """Yield analysis text chunks from an OpenAI-compatible chat endpoint."""
    client = _make_client(base_url, api_key)
    resolved_model = model or _first_available_model(client) or "local-model"
    messages = _build_openai_messages(prompt, workout_json, memory_digest, max_chars)

    resp = client.chat.completions.create(model=resolved_model, messages=messages, stream=True)
    for event in resp:
        delta = event.choices[0].delta.content if event.choices else None
        if delta:
            yield delta


def run_openai_compatible(
    prompt: str,
    workout_json: str,
    base_url: str,
    api_key: str,
    memory_digest: Optional[str] = None,
    model: Optional[str] = None,
    stream: bool = True,
    max_chars: int = 200_000,
) -> str:
    """Run analysis against a local/remote OpenAI-compatible chat endpoint."""
    if stream:
        collected: List[str] = []
        for delta in stream_openai_compatible(
            prompt, workout_json, base_url, api_key, memory_digest, model, max_chars
        ):
            collected.append(delta)
            sys.stdout.write(delta)
            sys.stdout.flush()
        sys.stdout.write("\n")
        return "".join(collected)

    client = _make_client(base_url, api_key)
    resolved_model = model or _first_available_model(client) or "local-model"
    messages = _build_openai_messages(prompt, workout_json, memory_digest, max_chars)
    resp = client.chat.completions.create(model=resolved_model, messages=messages)
    text = resp.choices[0].message.content or ""
    sys.stdout.write(text + "\n")
    return text


# ── Compaction for context-limited local models ────────────────────────────────


def compact_workout_json(json_data: str, max_chars: int) -> str:
    """Shrink lossless workout JSON to fit a local model's context window.

    Progressively thins the largest per-sample arrays (records first) rather than
    dropping whole activities, so summaries/laps survive.
    """
    if len(json_data) <= max_chars:
        return json_data
    try:
        doc = json.loads(json_data)
    except json.JSONDecodeError:
        return json_data[:max_chars] + "\n... (truncated)"

    activities = doc.get("activities") if isinstance(doc, dict) else None
    if activities is None:
        activities = [doc] if isinstance(doc, dict) else []

    def size() -> int:
        return len(json.dumps(doc, separators=(",", ":"), ensure_ascii=False))

    # 1) Stride-thin record arrays with increasing factor until it fits.
    for stride in (2, 4, 8, 16, 32, 64):
        for act in activities:
            msgs = act.get("messages", {})
            records = msgs.get("record")
            if isinstance(records, list) and len(records) > 60:
                msgs["record"] = records[::stride]
                act.setdefault("_note", f"records thinned (every {stride}th sample)")
        if size() <= max_chars:
            break

    # 2) Still too big: drop record arrays entirely, keep sessions/laps.
    if size() > max_chars:
        for act in activities:
            act.get("messages", {}).pop("record", None)
            act["_note"] = "per-second records omitted to fit context"

    compact = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
    if len(compact) > max_chars:
        compact = compact[:max_chars] + "... (truncated)"
    return compact
