"""GitHub Models API integration for LLM-powered activity analysis."""

from __future__ import annotations

import os
import sys
from typing import Optional

import click


DEFAULT_MODEL = "gemini-3-pro-preview"
GITHUB_MODELS_ENDPOINT = "https://models.github.ai/inference"

SYSTEM_PROMPT = """\
You are an expert running/cycling/fitness coach and data analyst. \
You analyze workout data provided as structured JSON and give insightful, \
actionable feedback. Be specific — reference actual numbers from the data. \
Keep your analysis concise but thorough. Use markdown formatting for readability.\
"""


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

    # Truncate JSON if extremely large (keep under ~100k chars for context)
    if len(json_data) > 100_000:
        click.echo("Note: Activity data is large; truncating to fit context window.", err=True)
        json_data = json_data[:100_000] + "\n... (truncated)"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Here is my workout data:\n\n```json\n{json_data}\n```\n\n{prompt}",
        },
    ]

    if stream:
        response_text = ""
        stream_resp = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=4096,
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
            max_tokens=4096,
        )
        text = response.choices[0].message.content or ""
        click.echo(text)
        return text
