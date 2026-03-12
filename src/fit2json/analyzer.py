"""GitHub Models API integration for LLM-powered activity analysis."""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

import click


DEFAULT_MODEL = "openai/gpt-5-chat"
GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference"

SYSTEM_PROMPT = """\
You are an expert running/cycling/fitness coach and data analyst. \
You analyze workout data provided as structured JSON and give insightful, \
actionable feedback. Be specific — reference actual numbers from the data. \
Keep your analysis concise but thorough. Use markdown formatting for readability.\
"""

# GitHub Models token limits vary by model; keep well under to leave room for response
MAX_INPUT_CHARS = 11_000


def _compact_for_llm(json_data: str) -> str:
    """Intelligently compact activity JSON for LLM consumption.

    For large datasets (many activities), strips time_series_1min data and keeps
    only summaries and laps. For small datasets, keeps everything.
    """
    if len(json_data) <= MAX_INPUT_CHARS:
        return json_data

    try:
        doc = json.loads(json_data)
    except json.JSONDecodeError:
        return json_data[:MAX_INPUT_CHARS] + "\n... (truncated)"

    activities = doc.get("activities", [])

    # First pass: remove time series
    for act in activities:
        act.pop("time_series_1min", None)

    compact = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
    if len(compact) <= MAX_INPUT_CHARS:
        click.echo(
            f"Note: Removed time-series data to fit {len(activities)} activities in context.",
            err=True,
        )
        return compact

    # Second pass: also remove laps
    for act in activities:
        act.pop("laps", None)

    compact = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
    if len(compact) <= MAX_INPUT_CHARS:
        click.echo(
            f"Note: Removed time-series and lap data to fit {len(activities)} activities in context.",
            err=True,
        )
        return compact

    # Third pass: keep only essential summary fields
    essential_keys = {
        "total_distance_km", "total_duration_s", "avg_pace_min_per_km",
        "avg_heart_rate_bpm", "max_heart_rate_bpm", "avg_speed_kmh",
        "total_calories", "total_ascent_m",
    }
    for act in activities:
        summary = act.get("summary", {})
        act["summary"] = {k: v for k, v in summary.items() if k in essential_keys}

    compact = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
    if len(compact) <= MAX_INPUT_CHARS:
        click.echo(
            f"Note: Using minimal summaries to fit {len(activities)} activities in context.",
            err=True,
        )
        return compact

    # Last resort: truncate
    click.echo("Note: Activity data is very large; truncating to fit context window.", err=True)
    return compact[:MAX_INPUT_CHARS] + "\n... (truncated)"


def analyze_activities(
    json_data: str,
    prompt: str,
    model: Optional[str] = None,
    token: Optional[str] = None,
    stream: bool = True,
) -> str:
    """Send activity JSON to GitHub Models API for analysis.

    Args:
        json_data: The activity JSON string to analyze.
        prompt: User's analysis prompt/question.
        model: Model to use. Defaults to gpt-4o.
        token: GitHub personal access token. Falls back to GITHUB_TOKEN env var.
        stream: Whether to stream the response.

    Returns:
        The LLM's analysis response text.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise click.ClickException("openai package required. Install with: pip install openai")

    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise click.ClickException(
            "GitHub token required for analysis. Set GITHUB_TOKEN environment variable "
            "or pass --token. Get a token at https://github.com/settings/tokens"
        )

    model = model or DEFAULT_MODEL

    client = OpenAI(
        base_url=GITHUB_MODELS_ENDPOINT,
        api_key=token,
    )

    json_data = _compact_for_llm(json_data)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Here is my workout data:\n\n```json\n{json_data}\n```\n\n{prompt}",
        },
    ]

    # Reasoning models don't support temperature or streaming
    is_reasoning = model.split("/")[-1].startswith("o") or model.endswith("gpt-5")

    if is_reasoning:
        click.echo(f"Using {model} — this may take a moment...", err=True)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=16384,
        )
        text = response.choices[0].message.content or ""
        click.echo(text)
        return text
    elif stream:
        response_text = ""
        stream_resp = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.7,
            max_completion_tokens=4096,
        )
        for chunk in stream_resp:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                sys.stdout.write(content)
                sys.stdout.flush()
                response_text += content
        sys.stdout.write("\n")
        return response_text
    else:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_completion_tokens=4096,
        )
        text = response.choices[0].message.content or ""
        click.echo(text)
        return text
