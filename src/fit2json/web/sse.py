"""Server-Sent Events helpers shared by the streaming endpoints (analyze, infographic)."""

from __future__ import annotations

import json

# Headers that keep SSE responses unbuffered through dev servers and proxies.
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
