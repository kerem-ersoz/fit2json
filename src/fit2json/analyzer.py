"""LLM-powered activity analysis — supports OpenAI, Ollama, and any OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import sys
import time
from typing import List, Optional

import click


# Provider presets: (base_url, env_var_for_key, default_model)
PROVIDERS = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4.1"),
    "ollama": ("http://localhost:11434/v1", None, "llama3.1"),
    "github": ("https://models.github.ai/inference", "GITHUB_TOKEN", "openai/gpt-5-chat"),
}

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

# Default context budget — can be overridden via --max-chars
MAX_INPUT_CHARS = 100_000


def _resolve_provider(
    provider: Optional[str],
    base_url: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
) -> tuple:
    """Resolve provider settings into (base_url, api_key, model).

    Auto-detects provider from available env vars if not specified.
    """
    if base_url:
        # Custom endpoint — use as-is
        key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("GITHUB_TOKEN") or "no-key"
        mdl = model or "gpt-4.1"
        return base_url, key, mdl

    if provider:
        preset = PROVIDERS.get(provider)
        if not preset:
            raise click.ClickException(f"Unknown provider '{provider}'. Choose from: {', '.join(PROVIDERS)}")
        url, env_var, default_model = preset
        key = api_key or (os.environ.get(env_var) if env_var else "ollama")
        if not key:
            raise click.ClickException(f"API key required for {provider}. Set {env_var} or pass --api-key.")
        return url, key, model or default_model

    # Auto-detect: prefer OpenAI > Ollama > GitHub Models
    if api_key or os.environ.get("OPENAI_API_KEY"):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        return PROVIDERS["openai"][0], key, model or PROVIDERS["openai"][2]
    if os.environ.get("GITHUB_TOKEN"):
        return PROVIDERS["github"][0], os.environ["GITHUB_TOKEN"], model or PROVIDERS["github"][2]
    # Fallback to Ollama (no key needed)
    return PROVIDERS["ollama"][0], "ollama", model or PROVIDERS["ollama"][2]


def _compact_for_llm(json_data: str, max_chars: int = MAX_INPUT_CHARS) -> str:
    """Intelligently compact activity JSON for LLM consumption.

    Progressively strips detail to fit within max_chars.
    """
    if len(json_data) <= max_chars:
        return json_data

    try:
        doc = json.loads(json_data)
    except json.JSONDecodeError:
        return json_data[:max_chars] + "\n... (truncated)"

    activities = doc.get("activities", [])

    # First pass: remove time series
    for act in activities:
        act.pop("time_series_1min", None)

    compact = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
    if len(compact) <= max_chars:
        click.echo(
            f"Note: Removed time-series data to fit {len(activities)} activities in context.",
            err=True,
        )
        return compact

    # Second pass: also remove laps
    for act in activities:
        act.pop("laps", None)

    compact = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
    if len(compact) <= max_chars:
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
    if len(compact) <= max_chars:
        click.echo(
            f"Note: Using minimal summaries to fit {len(activities)} activities in context.",
            err=True,
        )
        return compact

    # Fourth pass: ultra-compact — flat list with only key metrics
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
    if len(compact) <= max_chars:
        click.echo(
            f"Note: Using ultra-compact format to fit all {len(activities)} activities in context.",
            err=True,
        )
        return compact

    # Last resort: truncate
    click.echo(
        f"Note: Truncating ultra-compact data to fit context window ({len(activities)} activities).",
        err=True,
    )
    return compact[:max_chars] + "]"


def _make_client(base_url: str, api_key: str):
    """Create an OpenAI-compatible client."""
    from openai import OpenAI

    return OpenAI(base_url=base_url, api_key=api_key)


def _call_llm(client, model: str, system: str, user: str, max_tokens: int = 4096) -> str:
    """Make a single LLM call with retry on rate limit and connection errors."""
    from openai import APIConnectionError, RateLimitError

    is_reasoning = model.split("/")[-1].startswith("o") or model.endswith("gpt-5")

    for attempt in range(12):
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
        except (RateLimitError, APIConnectionError) as e:
            wait = min(2 ** attempt * 3, 180)
            kind = "Rate limited" if isinstance(e, RateLimitError) else "Connection error"
            click.echo(f"  {kind}, waiting {wait}s (attempt {attempt+1}/12)...", err=True)
            time.sleep(wait)
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower() or "connection" in str(e).lower():
                wait = min(2 ** attempt * 3, 180)
                click.echo(f"  Retryable error, waiting {wait}s (attempt {attempt+1}/12)...", err=True)
                time.sleep(wait)
            else:
                raise
    return ""


def analyze_activities_deep(
    json_data: str,
    prompt: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    fast_model: Optional[str] = None,
) -> str:
    """Multi-pass analysis: analyze each activity individually, then synthesize.

    Pass 1: Send each activity with full time-series data for detailed analysis.
    Pass 2: Send all per-activity summaries + user prompt for final synthesis.

    Supports checkpoint/resume: saves per-activity results to a temp file so
    interrupted runs can continue where they left off.
    """
    import hashlib
    import tempfile

    try:
        from openai import OpenAI
    except ImportError:
        raise click.ClickException("openai package required. Install with: pip install openai")

    url, key, resolved_model = _resolve_provider(provider, base_url, api_key, model)
    synthesis_model = resolved_model

    # Fast model for per-activity pass: user-specified or auto-pick based on provider
    if fast_model:
        p1_model = fast_model
    elif "openai.com" in url:
        p1_model = "gpt-4.1-mini"
    elif "github" in url:
        p1_model = "openai/gpt-4.1"
    else:
        p1_model = resolved_model  # Ollama / custom: use same model

    client = _make_client(url, key)

    doc = json.loads(json_data)
    activities = doc.get("activities", [])
    total = len(activities)

    # Checkpoint file keyed by hash of activity data
    data_hash = hashlib.sha256(json_data.encode()).hexdigest()[:12]
    checkpoint_path = os.path.join(tempfile.gettempdir(), f"fit2json_deep_{data_hash}.json")

    # Load existing checkpoint if available
    checkpoint: dict = {}
    if os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path) as f:
                checkpoint = json.load(f)
            done = len(checkpoint.get("analyses", {}))
            click.echo(f"Resuming from checkpoint: {done}/{total} activities already analyzed.", err=True)
        except (json.JSONDecodeError, OSError):
            checkpoint = {}

    analyses_map: dict = checkpoint.get("analyses", {})

    click.echo(f"Pass 1: Analyzing {total} activities individually with {p1_model}...", err=True)

    for i, act in enumerate(activities, 1):
        sport = act.get("sport", "unknown")
        date = (act.get("start_time") or "unknown")[:10]
        label = f"{date} {sport}"
        key = f"{i}_{label}"

        # Skip if already analyzed
        if key in analyses_map:
            click.echo(f"  [{i}/{total}] {label} (cached)", err=True)
            continue

        activity_json = json.dumps(act, separators=(",", ":"), ensure_ascii=False)
        click.echo(f"  [{i}/{total}] {label} ({len(activity_json)} chars)", err=True)

        analysis = _call_llm(
            client, p1_model,
            system=SYSTEM_PROMPT,
            user=f"Workout data:\n```json\n{activity_json}\n```\n\n{PER_ACTIVITY_PROMPT}",
            max_tokens=512,
        )
        analyses_map[key] = analysis.strip()

        # Save checkpoint after each activity
        checkpoint["analyses"] = analyses_map
        try:
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint, f)
        except OSError:
            pass

        time.sleep(2)

    # Build ordered list of analyses
    per_activity_analyses = []
    for i, act in enumerate(activities, 1):
        sport = act.get("sport", "unknown")
        date = (act.get("start_time") or "unknown")[:10]
        label = f"{date} {sport}"
        key = f"{i}_{label}"
        text = analyses_map.get(key, "")
        if text:
            per_activity_analyses.append(f"**{label}**: {text}")

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

    # Clean up checkpoint on success
    try:
        os.remove(checkpoint_path)
    except OSError:
        pass

    click.echo("\n" + synthesis)
    return synthesis


def analyze_activities(
    json_data: str,
    prompt: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    stream: bool = True,
    deep: bool = False,
    fast_model: Optional[str] = None,
    max_chars: Optional[int] = None,
) -> str:
    """Send activity JSON to an LLM for analysis.

    Supports OpenAI, Ollama, GitHub Models, and any OpenAI-compatible endpoint.
    Auto-detects provider from environment variables if not specified.

    Args:
        json_data: The activity JSON string to analyze.
        prompt: User's analysis prompt/question.
        model: Model to use (provider-specific).
        provider: Provider name: 'openai', 'ollama', or 'github'.
        base_url: Custom OpenAI-compatible API base URL.
        api_key: API key. Falls back to env vars per provider.
        stream: Whether to stream the response.
        deep: If True, use multi-pass per-activity analysis.
        fast_model: Model for per-activity pass in deep mode.
        max_chars: Max input chars for compaction (default: 100K).

    Returns:
        The LLM's analysis response text.
    """
    if deep:
        return analyze_activities_deep(
            json_data, prompt, model=model, provider=provider,
            base_url=base_url, api_key=api_key, fast_model=fast_model,
        )

    try:
        from openai import OpenAI
    except ImportError:
        raise click.ClickException("openai package required. Install with: pip install openai")

    url, key, resolved_model = _resolve_provider(provider, base_url, api_key, model)
    client = OpenAI(base_url=url, api_key=key)

    budget = max_chars or MAX_INPUT_CHARS
    json_data = _compact_for_llm(json_data, max_chars=budget)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Here is my workout data:\n\n```json\n{json_data}\n```\n\n{prompt}",
        },
    ]

    # Reasoning models don't support temperature or streaming
    bare_model = resolved_model.split("/")[-1]
    is_reasoning = bare_model.startswith("o") or bare_model.endswith("gpt-5")

    if is_reasoning:
        click.echo(f"Using {resolved_model} — this may take a moment...", err=True)
        response = client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            max_completion_tokens=16384,
        )
        text = response.choices[0].message.content or ""
        click.echo(text)
        return text
    elif stream:
        response_text = ""
        stream_resp = client.chat.completions.create(
            model=resolved_model,
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
            model=resolved_model,
            messages=messages,
            temperature=0.7,
            max_completion_tokens=4096,
        )
        text = response.choices[0].message.content or ""
        click.echo(text)
        return text
