"""Infographic endpoint: an optional second prompting pass (Server-Sent Events).

Takes a *finished* analysis (produced by ``/analyze``) and re-prompts the model to
re-render it as a single, self-contained, visual HTML infographic — so the athlete can
scan the result instead of reading a wall of text. Nothing is saved to the memory
corpus; this is a pure presentation transform over text the athlete already has.

The generated HTML is LLM-authored, so it is only ever shown inside a sandboxed iframe.
Rather than embed it client-side (``srcdoc``/``blob:`` are blocked by some embedded
webviews), the finished HTML is stashed in-process and served from a real URL
(``GET /infographic/view/{token}``) that the iframe points at. That response is locked
down with a strict CSP (only our nonced resize script runs; no network, no remote
assets), and the iframe's ``sandbox`` keeps it on an opaque origin isolated from the app.
"""

from __future__ import annotations

import re
import secrets
import threading
import time
from typing import Iterator, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from fit2json import analyzer
from fit2json.web.schemas import InfographicRequest
from fit2json.web.sse import SSE_HEADERS
from fit2json.web.sse import sse as _sse

router = APIRouter(tags=["infographic"])


# ── Ephemeral in-process stash ──────────────────────────────────────────────────
# The finished infographic HTML is held briefly so the iframe can load it from a URL.
# It is not persisted to the memory corpus; entries expire and are capped in number.

_STASH: dict = {}
_STASH_LOCK = threading.Lock()
_STASH_MAX = 24
_STASH_TTL_S = 60 * 60


def _stash_html(html: str) -> str:
    token = secrets.token_urlsafe(16)
    now = time.time()
    with _STASH_LOCK:
        _STASH[token] = (now, html)
        # Drop expired, then cap to the most-recent _STASH_MAX entries.
        for key in [k for k, (ts, _) in _STASH.items() if now - ts > _STASH_TTL_S]:
            _STASH.pop(key, None)
        if len(_STASH) > _STASH_MAX:
            for key, _ in sorted(_STASH.items(), key=lambda kv: kv[1][0])[: len(_STASH) - _STASH_MAX]:
                _STASH.pop(key, None)
    return token


def _get_stashed(token: str) -> Optional[str]:
    with _STASH_LOCK:
        item: Optional[Tuple[float, str]] = _STASH.get(token)
    if item is None:
        return None
    ts, html = item
    if time.time() - ts > _STASH_TTL_S:
        with _STASH_LOCK:
            _STASH.pop(token, None)
        return None
    return html


# ── HTML shaping ─────────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n([\s\S]*?)\n?```$")

# Reports the document's height to the parent so the iframe can be sized to fit. Injected
# server-side with a per-response nonce; the CSP only permits this nonced script to run,
# so any script the model may have emitted is refused by the browser.
_RESIZE_TEMPLATE = (
    "<script nonce=\"{nonce}\">(function(){{function p(){{try{{var d=document,b=d.body,"
    "e=d.documentElement,h=Math.max(e.scrollHeight,b?b.scrollHeight:0,e.offsetHeight,"
    "b?b.offsetHeight:0);parent.postMessage({{__fitsift_ig_height:h}},'*');}}catch(_){{}}}}"
    "window.addEventListener('load',p);window.addEventListener('resize',p);"
    "if(window.ResizeObserver){{try{{new ResizeObserver(p).observe(document.documentElement);}}"
    "catch(_){{}}}}p();setTimeout(p,120);setTimeout(p,400);setTimeout(p,1200);}})();</script>"
)

_BASE_STYLE = (
    "body{margin:0;padding:20px;font-family:Inter,system-ui,-apple-system,'Segoe UI',Roboto,"
    "sans-serif;color:#0f172a;background:#ffffff;line-height:1.5;}"
)

# Runtime compatibility rules apply to both newly generated and already-cached HTML.
# Scrolling remains available, but embedded visuals do not show nested scrollbars. The
# track/fill rule repairs a common model output bug where percentage-sized <span> fills
# stay inline and therefore render at 0x0.
_RUNTIME_STYLE = (
    "*{scrollbar-width:none;-ms-overflow-style:none;}"
    "*::-webkit-scrollbar{display:none;width:0;height:0;}"
    ".track>.fill{display:block;height:100%;min-width:0;background:#64748b;}"
    ".track>.fill.on,.track>.fill.current{background:#059669;}"
    ".track>.fill.caution{background:#d97706;}"
    ".metrics>:has(.accent),.metrics>.hero,.metric.hero{background:#ecfdf5;}"
)


def clean_html(raw: str) -> str:
    """Strip code fences / stray preamble, keeping just the HTML document."""
    s = raw.strip()
    m = _FENCE_RE.match(s)
    if m:
        s = m.group(1).strip()
    low = s.lower()
    idx = low.find("<!doctype")
    if idx == -1:
        idx = low.find("<html")
    if idx > 0:
        s = s[idx:]
    return s.strip()


def servable_doc(html: str, nonce: str) -> str:
    """Wrap fragments and inject compatibility CSS plus the nonced resize script."""
    doc = html
    if not re.search(r"<!doctype", doc, re.I) and not re.search(r"<html[\s>]", doc, re.I):
        doc = (
            '<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<style>{_BASE_STYLE}</style></head><body>{doc}</body></html>"
        )
    runtime_style = f'<style id="fitsift-runtime">{_RUNTIME_STYLE}</style>'
    if re.search(r"</head>", doc, re.I):
        doc = re.sub(r"</head>", runtime_style + "</head>", doc, count=1, flags=re.I)
    elif re.search(r"<body(?:\s[^>]*)?>", doc, re.I):
        doc = re.sub(
            r"(<body(?:\s[^>]*)?>)",
            lambda match: match.group(1) + runtime_style,
            doc,
            count=1,
            flags=re.I,
        )
    else:
        doc = runtime_style + doc
    script = _RESIZE_TEMPLATE.format(nonce=nonce)
    if re.search(r"</body>", doc, re.I):
        return re.sub(r"</body>", script + "</body>", doc, count=1, flags=re.I)
    return doc + script


def html_response(html: str) -> HTMLResponse:
    """Serve stored infographic HTML as a standalone, tightly-CSP'd page for the iframe.

    Shared by the ephemeral (chat) and persisted (saved-analysis) view endpoints so both
    get the same isolation: only the nonced resize script may run, inline styles are
    allowed for the self-contained CSS, and no network/remote assets are permitted.
    """
    nonce = secrets.token_urlsafe(16)
    resp = HTMLResponse(content=servable_doc(html, nonce))
    resp.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        f"script-src 'nonce-{nonce}'; "
        "style-src 'unsafe-inline'; "
        "img-src data:; "
        "base-uri 'none'; "
        "form-action 'none'"
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-store"
    return resp


def stream_html(
    resolved: str,
    analysis: str,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
) -> Iterator[str]:
    """Stream raw HTML chunks from the resolved backend for the infographic prompt."""
    user_prompt = analyzer.build_infographic_user_prompt(analysis)

    if resolved == "copilot":
        return analyzer.stream_copilot(
            prompt=user_prompt,
            workout_paths=[],
            memory_dir=None,
            model=model,
            silent=True,
            reasoning_effort=reasoning_effort or None,
            system_prompt=analyzer.INFOGRAPHIC_SYSTEM_PROMPT,
            final_instruction=analyzer.INFOGRAPHIC_FINAL_INSTRUCTION,
        )
    if resolved in analyzer.LOCAL_BACKENDS:
        url, key = analyzer.LOCAL_BACKENDS[resolved]
        return analyzer.stream_openai_compatible(
            prompt=user_prompt,
            workout_json="",
            base_url=url,
            api_key=key,
            memory_digest=None,
            model=model,
            system_prompt=analyzer.INFOGRAPHIC_SYSTEM_PROMPT,
        )
    raise ValueError(f"Unsupported analysis backend: {resolved}")


# ── Endpoints ─────────────────────────────────────────────────────────────────────


@router.post("/infographic")
def infographic(req: InfographicRequest):
    analysis = (req.analysis or "").strip()
    if not analysis:
        raise HTTPException(status_code=422, detail="Analysis text is required.")

    resolved = analyzer.resolve_backend(req.backend, None)
    return StreamingResponse(
        _event_gen(req, resolved, analysis),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/infographic/view/{token}")
def view(token: str):
    """Serve a stashed (ephemeral, chat) infographic as a CSP'd HTML page for the iframe."""
    html = _get_stashed(token)
    if html is None:
        raise HTTPException(status_code=404, detail="Infographic not found or expired.")
    return html_response(html)


def _event_gen(req: InfographicRequest, resolved: str, analysis: str) -> Iterator[str]:
    yield _sse("start", {"backend": resolved})
    chunks: List[str] = []
    try:
        for chunk in stream_html(resolved, analysis, req.model, req.reasoning_effort):
            chunks.append(chunk)
            yield _sse("delta", {"text": chunk})
    except Exception as exc:  # analyzer raises click.ClickException on failure
        yield _sse("error", {"message": getattr(exc, "message", None) or str(exc)})
        return

    html = clean_html("".join(chunks))
    if not html:
        yield _sse("error", {"message": "The model returned no HTML."})
        return
    token = _stash_html(html)
    yield _sse("done", {"chars": len(html), "backend": resolved, "id": token})
