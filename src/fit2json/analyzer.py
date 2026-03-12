"""GitHub Models API integration for LLM-powered activity analysis."""

from __future__ import annotations

import json
import os
import sys
import time
from typing import List, Optional

import click


DEFAULT_MODEL = "openai/gpt-5-chat"
GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference"

SYSTEM_PROMPT = """\
You are an expert running/cycling/fitness coach and data analyst. \
You analyze workout data provided as structured JSON and give insightful, \
actionable feedback. Be specific — reference actual numbers from the data. \
Keep your analysis concise but thorough. Use markdown formatting for readability.\
"""

PER_ACTIVITY_PROMPT = """\
Analyze this single workout in 2-3 sentences. Note the sport, key metrics \
(distance, duration, pace/speed, HR), and anything notable about the effort. \
Be brief and data-driven.\
"""

SYNTHESIS_PROMPT = """\
You are an expert fitness coach. Below are individual analyses of a person's \
workouts over time. Synthesize these into a comprehensive fitness overview.\
"""

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

    # Fourth pass: ultra-compact — flat list with only key metrics, all activities kept
    ultra = []
    for act in activities:
        s = act.get("summary", {})
        ultra.append({
            "sport": act.get("sport"),
            "date": (act.get("start_time") or "")[:10],
            "km": s.get("total_distance_km"),
            "dur_s": s.get("total_duration_s"),
            "hr": s.get("avg_heart_rate_bpm"),
            "spd": s.get("avg_speed_kmh"),
        })
    compact = json.dumps(ultra, separators=(",", ":"), ensure_ascii=False)
    if len(compact) <= MAX_INPUT_CHARS:
        click.echo(
            f"Note: Using ultra-compact format to fit all {len(activities)} activities in context.",
            err=True,
        )
        return compact

    # Last resort: truncate the ultra-compact list
    click.echo(
        f"Note: Truncating ultra-compact data to fit context window ({len(activities)} activities).",
        err=True,
    )
    return compact[:MAX_INPUT_CHARS] + "]"


def _make_client(token: str):
    """Create an OpenAI client for GitHub Models."""
    from openai import OpenAI

    return OpenAI(base_url=GITHUB_MODELS_ENDPOINT, api_key=token)


def _call_llm(client, model: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """Make a single LLM call with retry on rate limit."""
    from openai import RateLimitError

    is_reasoning = model.split("/")[-1].startswith("o") or model.endswith("gpt-5")

    for attempt in range(8):
        try:
            if is_reasoning:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_completion_tokens=max_tokens,
                )
            else:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.7,
                    max_completion_tokens=max_tokens,
                )
            return resp.choices[0].message.content or ""
        except RateLimitError:
            wait = min(2 ** attempt * 3, 120)
            click.echo(f"  Rate limited, waiting {wait}s...", err=True)
            time.sleep(wait)
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                wait = min(2 ** attempt * 3, 120)
                click.echo(f"  Rate limited, waiting {wait}s...", err=True)
                time.sleep(wait)
            else:
                raise
    return ""


def analyze_activities_deep(
    json_data: str,
    prompt: str,
    model: Optional[str] = None,
    token: Optional[str] = None,
) -> str:
    """Multi-pass analysis: analyze each activity individually, then synthesize.

    Pass 1: Send each activity with full time-series data for detailed analysis.
    Pass 2: Send all per-activity summaries + user prompt for final synthesis.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise click.ClickException("openai package required. Install with: pip install openai")

    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise click.ClickException("GitHub token required. Set GITHUB_TOKEN env var.")

    model = model or DEFAULT_MODEL
    # Use gpt-4.1 for per-activity pass (fast, higher rate limit)
    # and the requested model for synthesis
    fast_model = "openai/gpt-4.1"
    synthesis_model = model
    client = _make_client(token)

    doc = json.loads(json_data)
    activities = doc.get("activities", [])
    total = len(activities)

    click.echo(f"Pass 1: Analyzing {total} activities individually with {fast_model}...", err=True)

    per_activity_analyses: List[str] = []
    for i, act in enumerate(activities, 1):
        sport = act.get("sport", "unknown")
        date = (act.get("start_time") or "unknown")[:10]
        label = f"{date} {sport}"

        activity_json = json.dumps(act, separators=(",", ":"), ensure_ascii=False)
        click.echo(f"  [{i}/{total}] {label} ({len(activity_json)} chars)", err=True)

        analysis = _call_llm(
            client, fast_model,
            system=SYSTEM_PROMPT,
            user=f"Workout data:\n```json\n{activity_json}\n```\n\n{PER_ACTIVITY_PROMPT}",
            max_tokens=512,
        )
        per_activity_analyses.append(f"**{label}**: {analysis.strip()}")
        # Pace requests to avoid rate limiting
        time.sleep(2)

    # Pass 2: Synthesis
    click.echo(f"\nPass 2: Synthesizing {total} activity analyses with {synthesis_model}...", err=True)

    all_analyses = "\n\n".join(per_activity_analyses)

    # If analyses fit in context, send them all
    if len(all_analyses) <= MAX_INPUT_CHARS:
        synthesis = _call_llm(
            client, synthesis_model,
            system=SYNTHESIS_PROMPT,
            user=f"Here are individual workout analyses:\n\n{all_analyses}\n\n{prompt}",
            max_tokens=4096,
        )
    else:
        # Chunk the analyses into groups that fit
        chunks = []
        current_chunk = []
        current_len = 0
        chunk_limit = MAX_INPUT_CHARS - 500  # leave room for prompt

        for analysis in per_activity_analyses:
            if current_len + len(analysis) > chunk_limit and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_len = 0
            current_chunk.append(analysis)
            current_len += len(analysis) + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        click.echo(f"  Synthesizing in {len(chunks)} chunks...", err=True)

        chunk_summaries = []
        for j, chunk in enumerate(chunks, 1):
            click.echo(f"  Chunk {j}/{len(chunks)}...", err=True)
            summary = _call_llm(
                client, synthesis_model,
                system=SYNTHESIS_PROMPT,
                user=f"Summarize these workout analyses into key trends and patterns:\n\n{chunk}",
                max_tokens=2048,
            )
            chunk_summaries.append(summary)

        combined = "\n\n---\n\n".join(chunk_summaries)
        synthesis = _call_llm(
            client, synthesis_model,
            system=SYNTHESIS_PROMPT,
            user=f"Here are partial fitness summaries covering different time periods. "
                 f"Combine them into one comprehensive response:\n\n{combined}\n\n{prompt}",
            max_tokens=4096,
        )

    click.echo("\n" + synthesis)
    return synthesis


def analyze_activities(
    json_data: str,
    prompt: str,
    model: Optional[str] = None,
    token: Optional[str] = None,
    stream: bool = True,
    deep: bool = False,
) -> str:
    """Send activity JSON to GitHub Models API for analysis.

    Args:
        json_data: The activity JSON string to analyze.
        prompt: User's analysis prompt/question.
        model: Model to use.
        token: GitHub personal access token. Falls back to GITHUB_TOKEN env var.
        stream: Whether to stream the response.
        deep: If True, use multi-pass per-activity analysis.

    Returns:
        The LLM's analysis response text.
    """
    if deep:
        return analyze_activities_deep(json_data, prompt, model, token)

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
