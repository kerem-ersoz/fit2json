"""Server-Sent Events helpers shared by the streaming endpoints (analyze, infographic)."""

from __future__ import annotations

import json
from typing import Iterator, List

# Headers that keep SSE responses unbuffered through dev servers and proxies.
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
SSE_HEARTBEAT_SECONDS = 15.0


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_text_events(stream: Iterator[str], chunks: List[str]) -> Iterator[str]:
    """Translate text chunks and idle markers to SSE, closing the source on disconnect."""
    try:
        for chunk in stream:
            if chunk:
                chunks.append(chunk)
                yield sse("delta", {"text": chunk})
            else:
                yield sse("ping", {})
    finally:
        close = getattr(stream, "close", None)
        if close is not None:
            close()
