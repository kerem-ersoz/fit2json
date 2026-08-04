"""Tests for the FitSift web API (read-only library endpoints + meta)."""

import importlib

import pytest
from fastapi.testclient import TestClient

from fit2json.output import write_per_activity
from fit2json.parser import decode_fit_file

FIXTURE = "tests/fixtures/sample-activity.fit"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient wired to a fresh library built from the sample fixture."""
    library = tmp_path / "json"
    activity = decode_fit_file(FIXTURE)
    write_per_activity([activity], str(library))

    monkeypatch.setenv("FITSIFT_LIBRARY", str(library))
    monkeypatch.setenv("FITSIFT_MEMORY", str(tmp_path / "memory"))
    monkeypatch.setenv("FITSIFT_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setenv("FITSIFT_CHATS", str(tmp_path / "chats"))

    # Rebuild the app + service caches against the patched environment.
    from fit2json.web import app as app_module
    from fit2json.web import services

    services._libraries.clear()
    importlib.reload(app_module)
    return TestClient(app_module.create_app())


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_config(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["brand"]["name"] == "FitSift"
    assert "copilot" in body["backends"]
    assert body["chats_dir"].endswith("chats")


def test_models_copilot(client):
    r = client.get("/api/models", params={"backend": "copilot"})
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "copilot"
    assert body["models"][0] == "auto"
    assert "gpt-5.6-sol" in body["models"]
    assert "claude-opus-5" in body["models"]
    assert body["allow_custom"] is True
    # Effort levels are exposed (from the CLI, or the known fallback when it's absent).
    assert "high" in body["efforts"] and "medium" in body["efforts"]


def test_models_copilot_ignores_invalid_memory_files(client, tmp_path, caplog):
    memory_dir = tmp_path / "memory" / "running"
    memory_dir.mkdir(parents=True)
    (memory_dir / "._analysis.md").write_bytes(b"\x00\x05\x16\x07AppleDouble\x00\xa9")
    (memory_dir / "broken.md").write_bytes(b"---\nentry_id: broken\n\xff")

    with caplog.at_level("WARNING", logger="fit2json.web.services"):
        r = client.get("/api/models", params={"backend": "copilot"})

    assert r.status_code == 200
    assert r.json()["models"][0] == "auto"
    assert "broken.md" in caplog.text
    assert "._analysis.md" not in caplog.text


def test_models_local_backend_unreachable(client):
    r = client.get("/api/models", params={"backend": "ollama"})
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "ollama"
    assert body["efforts"] == []
    assert body["reachable"] is False  # no local server running in tests
    assert body["models"] == []


def test_list_activities(client):
    r = client.get("/api/activities")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    item = items[0]
    assert item["sport"] == "running"
    assert item["has_gps"] is True
    assert item["record_count"] == 14
    assert item["start_time"].startswith("2012-04-09")


def test_activity_detail_and_404(client):
    aid = client.get("/api/activities").json()[0]["id"]

    r = client.get(f"/api/activities/{aid}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["sport"] == "running"
    assert detail["session"]["total_distance"] > 0

    assert client.get("/api/activities/does-not-exist").status_code == 404


def test_streams_downsampling_and_gps(client):
    aid = client.get("/api/activities").json()[0]["id"]

    r = client.get(f"/api/activities/{aid}/streams", params={"max_points": 5})
    assert r.status_code == 200
    streams = r.json()
    assert streams["total_records"] == 14
    assert streams["point_count"] <= 5
    assert streams["stride"] >= 3
    # GPS polyline present and converted to plausible degrees.
    assert len(streams["latlng"]) > 0
    lat, lng = streams["latlng"][0]
    assert 40 < lat < 42 and -74 < lng < -72  # somewhere near the sample's location


def test_streams_field_filter(client):
    aid = client.get("/api/activities").json()[0]["id"]
    r = client.get(f"/api/activities/{aid}/streams", params={"fields": "altitude"})
    assert r.status_code == 200
    series = r.json()["series"]
    assert "altitude" in series
    assert "speed" not in series


def test_laps_and_raw(client):
    aid = client.get("/api/activities").json()[0]["id"]

    laps = client.get(f"/api/activities/{aid}/laps").json()["laps"]
    assert len(laps) == 1

    raw = client.get(f"/api/activities/{aid}/raw").json()
    assert "messages" in raw and "record" in raw["messages"]


def test_derive_source_ref():
    from fit2json.web.services import derive_source_ref

    g = derive_source_ref("garmin", "2024-03-10_07-30-00_1234567890.fit")
    assert g and g["platform"] == "garmin" and g["id"] == "1234567890"
    assert "connect.garmin.com" in g["url"]

    s = derive_source_ref("strava", "2024-03-10T07-30-00Z_9988776.strava.json")
    assert s and s["platform"] == "strava" and s["id"] == "9988776"
    assert "strava.com/activities/9988776" in s["url"]

    # A generic local .fit with no external id → no link.
    assert derive_source_ref("local", "sample-activity.fit") is None


def test_analyze_streams_and_saves(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, athlete_profile=None, **kwargs):
        assert workout_paths and workout_paths[0].exists()
        assert silent is True  # web path uses --silent to strip the copilot tool-trace
        yield "## Analysis\n"
        yield "Looking strong!"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post("/api/analyze", json={"activity_id": aid, "prompt": "How did I do?"})
    assert r.status_code == 200
    body = r.text
    assert "event: delta" in body
    assert "Looking strong!" in body
    assert "event: done" in body

    # The finished analysis is saved to memory and surfaces on the activity.
    analyses = client.get(f"/api/activities/{aid}/analyses").json()["analyses"]
    assert len(analyses) == 1
    assert analyses[0]["prompt"] == "How did I do?"
    assert "Looking strong!" in analyses[0]["content"]

    # And in the global memory list.
    entries = client.get("/api/memory").json()["entries"]
    assert len(entries) == 1


def test_analyze_missing_activity(client):
    r = client.post("/api/analyze", json={"activity_id": "nope", "prompt": "hi"})
    assert r.status_code == 404


def test_analyze_accepts_activity_ids(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None, **kwargs):
        captured["paths"] = list(workout_paths)
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post("/api/analyze", json={"activity_ids": [aid], "prompt": "How did I do?"})
    assert r.status_code == 200
    assert "event: done" in r.text
    assert len(captured["paths"]) == 1
    # A single-activity request (via the list form) still saves to memory.
    assert len(client.get(f"/api/activities/{aid}/analyses").json()["analyses"]) == 1


def test_analyze_requires_prompt(client):
    # Missing prompt fails validation; a blank prompt is rejected by the route.
    assert client.post("/api/analyze", json={"activity_ids": ["x"]}).status_code == 422
    assert client.post("/api/analyze", json={"prompt": "   "}).status_code == 422


def test_chats_empty_then_upsert_and_resume(client):
    # A fresh corpus has no saved chats.
    assert client.get("/api/chats").json() == {"chats": []}

    # PUT upserts (create-on-first-save): the client owns the id.
    body = {
        "backend": "copilot",
        "model": "auto",
        "activity_ids": ["a1", "a2"],
        "messages": [
            {"id": "m1", "role": "user", "content": "How did my week go?"},
            {"id": "m2", "role": "assistant", "content": "Strong and consistent."},
        ],
    }
    r = client.put("/api/chats/chat-123", json=body)
    assert r.status_code == 200
    saved = r.json()
    assert saved["id"] == "chat-123"
    assert saved["title"] == "How did my week go?"  # derived from first user message
    assert saved["created_at"] and saved["updated_at"]
    assert [m["content"] for m in saved["messages"]] == ["How did my week go?", "Strong and consistent."]

    # It now shows in the history summary (no message bodies, but a count).
    listed = client.get("/api/chats").json()["chats"]
    assert len(listed) == 1
    assert listed[0]["id"] == "chat-123"
    assert listed[0]["message_count"] == 2
    assert listed[0]["activity_ids"] == ["a1", "a2"]
    assert "messages" not in listed[0]

    # And can be resumed in full.
    full = client.get("/api/chats/chat-123").json()
    assert len(full["messages"]) == 2
    assert full["activity_ids"] == ["a1", "a2"]


def test_chats_update_preserves_created_at_and_delete(client):
    first = client.put(
        "/api/chats/c1",
        json={"messages": [{"id": "m1", "role": "user", "content": "Hi"}]},
    ).json()

    # A second save keeps created_at but advances the transcript.
    second = client.put(
        "/api/chats/c1",
        json={
            "title": "My renamed chat",
            "messages": [
                {"id": "m1", "role": "user", "content": "Hi"},
                {"id": "m2", "role": "assistant", "content": "Hello!"},
            ],
        },
    ).json()
    assert second["created_at"] == first["created_at"]
    assert second["title"] == "My renamed chat"
    assert len(second["messages"]) == 2

    assert client.delete("/api/chats/c1").status_code == 200
    assert client.get("/api/chats/c1").status_code == 404
    assert client.delete("/api/chats/c1").status_code == 404


def test_chats_missing_returns_404(client):
    assert client.get("/api/chats/nope").status_code == 404


def test_chat_id_is_path_safe(client, tmp_path):
    # An id with unsafe characters is sanitized to a single plain filename inside the
    # chats dir — no subdirectories, nothing escaping the directory.
    r = client.put(
        "/api/chats/chat@2024!weird",
        json={"messages": [{"id": "m1", "role": "user", "content": "hey"}]},
    )
    assert r.status_code == 200
    assert r.json()["id"] == "chat-2024-weird"

    chats_dir = tmp_path / "chats"
    entries = list(chats_dir.iterdir())
    assert entries == [chats_dir / "chat-2024-weird.json"]  # one flat file, no nesting


def test_analyze_freeform_no_selection(client, monkeypatch):
    """With no workouts selected, the agent is handed the whole library to find them itself."""
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None, library_dir=None, **kwargs):
        captured["workout_paths"] = list(workout_paths)
        captured["library_dir"] = library_dir
        yield "Across your recent long runs…"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    r = client.post("/api/analyze", json={"prompt": "compare my last 3 long runs"})
    assert r.status_code == 200
    assert "event: delta" in r.text and "event: done" in r.text
    assert captured["workout_paths"] == []  # no specific files — the agent browses
    assert captured["library_dir"] is not None  # the library is handed to the agent
    # Freeform is exploratory; nothing is written to the corpus.
    assert client.get("/api/memory").json()["entries"] == []


def test_analyze_multi_workout_map_reduce(client, monkeypatch):
    """2+ workouts → per-workout building blocks, then a synthesis over them that isn't saved."""
    from fit2json import analyzer
    from fit2json.web import services

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    # No compatible saved analysis → force per-workout generation (mocked; no real copilot).
    monkeypatch.setattr(services, "latest_compatible_analysis", lambda *a, **k: None)
    gen = {"n": 0}

    def fake_generate(activity, path, backend, model, reasoning_effort, prompt, save=True):
        gen["n"] += 1
        return f"per-workout analysis {gen['n']}"

    monkeypatch.setattr(services, "generate_workout_analysis", fake_generate)

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None, **kwargs):
        # The synthesis reasons over the per-workout analyses, not the raw workout files.
        assert workout_paths == []
        assert "per-workout analysis 1" in prompt and "per-workout analysis 2" in prompt
        yield "## Comparison\n"
        yield "The second was harder."

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post("/api/analyze", json={"activity_ids": [aid, aid], "prompt": "compare"})
    assert r.status_code == 200
    body = r.text
    assert "event: step" in body and "event: delta" in body and "event: done" in body
    assert "The second was harder." in body
    assert gen["n"] == 2
    # The nested synthesis is not written to the corpus.
    assert client.get("/api/memory").json()["entries"] == []


def test_analyze_reuses_compatible_analysis(client, monkeypatch):
    """When a tier-compatible analysis already exists, it's reused instead of regenerated."""
    from fit2json import analyzer
    from fit2json.web import services

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    monkeypatch.setattr(services, "latest_compatible_analysis", lambda *a, **k: "REUSED BLOCK")

    def no_generate(*a, **k):
        raise AssertionError("should not regenerate when a compatible analysis exists")

    monkeypatch.setattr(services, "generate_workout_analysis", no_generate)

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None, **kwargs):
        assert "REUSED BLOCK" in prompt
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post("/api/analyze", json={"activity_ids": [aid, aid], "prompt": "compare"})
    assert r.status_code == 200 and "event: done" in r.text


def test_analyze_freeform_injects_profile(client, monkeypatch):
    """The freeform (no-selection) coach path also personalizes with the "You" profile."""
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, library_dir=None, athlete_profile=None, **kwargs):
        captured["athlete_profile"] = athlete_profile
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)
    client.put("/api/profile", json={"max_hr": 185, "goals": "Marathon PR"})

    r = client.post("/api/analyze", json={"prompt": "How is my training trending?"})
    assert r.status_code == 200
    assert captured["athlete_profile"] is not None
    assert "Max HR: 185 bpm" in captured["athlete_profile"]


def test_analyze_multi_synthesis_injects_profile(client, monkeypatch):
    """The multi-workout synthesis (REDUCE) personalizes with the "You" profile."""
    from fit2json import analyzer
    from fit2json.web import services

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    monkeypatch.setattr(services, "latest_compatible_analysis", lambda *a, **k: "BLOCK")
    monkeypatch.setattr(services, "generate_workout_analysis", lambda *a, **k: "BLOCK")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, athlete_profile=None, **kwargs):
        captured["athlete_profile"] = athlete_profile
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)
    client.put("/api/profile", json={"ftp_w": 250, "goals": "FTP boost"})

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post("/api/analyze", json={"activity_ids": [aid, aid], "prompt": "compare"})
    assert r.status_code == 200
    assert captured["athlete_profile"] is not None
    assert "FTP: 250 W" in captured["athlete_profile"]


def test_analyze_appends_chart_guidance(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, athlete_profile=None, **kwargs):
        captured["prompt"] = prompt
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post("/api/analyze", json={"activity_id": aid, "prompt": "Summarize"})
    assert r.status_code == 200
    # Chart guidance is appended to the model's prompt by default…
    assert "fitsift-chart" in captured["prompt"]
    # …but memory keeps the athlete's original prompt.
    analyses = client.get(f"/api/activities/{aid}/analyses").json()["analyses"]
    assert analyses[0]["prompt"] == "Summarize"


def test_analyze_charts_can_be_disabled(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, athlete_profile=None, **kwargs):
        captured["prompt"] = prompt
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post(
        "/api/analyze", json={"activity_id": aid, "prompt": "Summarize", "charts": False}
    )
    assert r.status_code == 200
    assert "fitsift-chart" not in captured["prompt"]


# ── infographic (optional second pass) ───────────────────────────────────────


def test_infographic_streams_html(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, system_prompt=None, final_instruction=None, **kwargs):
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        captured["final_instruction"] = final_instruction
        captured["workout_paths"] = workout_paths
        yield "<!doctype html><html><body>"
        yield "<h1>Strong run</h1></body></html>"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    r = client.post("/api/infographic", json={"analysis": "You ran 10k at threshold. Avg HR 165."})
    assert r.status_code == 200
    body = r.text
    assert "event: start" in body
    assert "event: delta" in body
    assert "<!doctype html>" in body
    assert "event: done" in body

    # The infographic pass uses its own system prompt + HTML trailer, carries no workout
    # files, and feeds the analysis text into the user prompt.
    assert captured["system_prompt"] == analyzer.INFOGRAPHIC_SYSTEM_PROMPT
    assert captured["final_instruction"] == analyzer.INFOGRAPHIC_FINAL_INSTRUCTION
    assert captured["workout_paths"] == []
    assert "You ran 10k at threshold" in captured["prompt"]


def _run_infographic(client, monkeypatch, html_chunks):
    """Drive one infographic stream and return the `done` event's data dict."""
    import json as _json

    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, system_prompt=None, final_instruction=None, **kwargs):
        yield from html_chunks

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    r = client.post("/api/infographic", json={"analysis": "ran 10k"})
    assert r.status_code == 200
    done = None
    for frame in r.text.split("\n\n"):
        if "event: done" in frame:
            data_line = [ln for ln in frame.splitlines() if ln.startswith("data:")][0]
            done = _json.loads(data_line[len("data:"):].strip())
    return done


def test_infographic_view_serves_stashed_html(client, monkeypatch):
    done = _run_infographic(
        client, monkeypatch, ["<!doctype html><html><body><h1>Nice run</h1></body></html>"]
    )
    assert done and done.get("id")

    v = client.get(f"/api/infographic/view/{done['id']}")
    assert v.status_code == 200
    assert v.headers["content-type"].startswith("text/html")
    assert "<h1>Nice run</h1>" in v.text
    # A tightly-scoped CSP is applied and a nonced resize script is injected.
    csp = v.headers.get("content-security-policy", "")
    assert "default-src 'none'" in csp
    nonce = csp.split("script-src 'nonce-")[1].split("'")[0]
    assert f'<script nonce="{nonce}">' in v.text
    assert "__fitsift_ig_height" in v.text
    assert 'id="fitsift-runtime"' in v.text
    assert "scrollbar-width:none" in v.text
    assert ".track>.fill{display:block" in v.text
    assert ".track>.fill.current{background:#059669" in v.text
    assert ".track>.fill.caution{background:#d97706" in v.text


def test_infographic_view_unknown_token_404(client):
    assert client.get("/api/infographic/view/nope-not-real").status_code == 404


def test_infographic_requires_analysis(client):
    assert client.post("/api/infographic", json={"analysis": "   "}).status_code == 422
    assert client.post("/api/infographic", json={}).status_code == 422


def test_infographic_forwards_model_and_effort(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, system_prompt=None, final_instruction=None, **kwargs):
        captured["model"] = model
        captured["reasoning_effort"] = reasoning_effort
        yield "<html></html>"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    r = client.post(
        "/api/infographic",
        json={"analysis": "a", "model": "claude-x", "reasoning_effort": "high"},
    )
    assert r.status_code == 200
    assert captured["model"] == "claude-x"
    assert captured["reasoning_effort"] == "high"


def test_infographic_reports_backend_errors(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")

    def boom(*a, **k):
        raise RuntimeError("model exploded")
        yield  # pragma: no cover - marks this a generator

    monkeypatch.setattr(analyzer, "stream_copilot", boom)

    r = client.post("/api/infographic", json={"analysis": "a"})
    assert r.status_code == 200
    assert "event: error" in r.text
    assert "model exploded" in r.text


# ── memory infographic (persisted per saved analysis) ────────────────────────


def _make_memory_entry(client, monkeypatch):
    """Run one analysis so it's saved to memory; return its entry_id. The stubbed model
    returns coach markdown for the analysis pass and HTML for the infographic pass."""
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, system_prompt=None, final_instruction=None, **kwargs):
        if system_prompt == analyzer.INFOGRAPHIC_SYSTEM_PROMPT:
            yield "<!doctype html><html><body><h1>Viz</h1></body></html>"
        else:
            yield "## Analysis\nSolid run."

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    assert client.post("/api/analyze", json={"activity_id": aid, "prompt": "How did I do?"}).status_code == 200
    entries = client.get("/api/memory").json()["entries"]
    assert entries
    return entries[0]["entry_id"]


def test_memory_infographic_generate_persist_and_serve(client, monkeypatch):
    entry_id = _make_memory_entry(client, monkeypatch)

    # Nothing cached yet.
    assert client.get(f"/api/memory/{entry_id}/infographic").json()["exists"] is False

    # Generate → streams progress and persists.
    r = client.post(f"/api/memory/{entry_id}/infographic")
    assert r.status_code == 200
    assert "event: done" in r.text and "<!doctype html>" in r.text

    # Now cached (survives via the on-disk sidecar).
    status = client.get(f"/api/memory/{entry_id}/infographic").json()
    assert status["exists"] is True and status["generated_at"]

    # View is a CSP'd page with a nonced resize script.
    v = client.get(f"/api/memory/{entry_id}/infographic/view")
    assert v.status_code == 200 and v.headers["content-type"].startswith("text/html")
    assert "<h1>Viz</h1>" in v.text
    assert "default-src 'none'" in v.headers.get("content-security-policy", "")
    assert "__fitsift_ig_height" in v.text

    # Raw is the stored HTML for copy/download — no resize shim.
    raw = client.get(f"/api/memory/{entry_id}/infographic/raw")
    assert raw.status_code == 200 and "<h1>Viz</h1>" in raw.text
    assert "__fitsift_ig_height" not in raw.text


def test_memory_infographic_unknown_entry_404(client):
    assert client.get("/api/memory/nope/infographic").status_code == 404
    assert client.get("/api/memory/nope/infographic/view").status_code == 404
    assert client.get("/api/memory/nope/infographic/raw").status_code == 404
    assert client.post("/api/memory/nope/infographic").status_code == 404


# ── athlete profile ("You" tab) ──────────────────────────────────────────────


def test_profile_defaults_empty(client):
    body = client.get("/api/profile").json()
    # Every field present but null until the athlete configures it.
    assert body["height_cm"] is None
    assert body["max_hr"] is None
    assert body["goals"] is None


def test_profile_put_and_get_roundtrip(client):
    payload = {
        "name": "Sam",
        "sex": "female",
        "birth_year": 1992,
        "height_cm": 170,
        "weight_kg": 62.5,
        "resting_hr": 46,
        "max_hr": 188,
        "lactate_threshold_hr": 170,
        "ftp_w": 240,
        "vo2max": 58.0,
        "goals": "Run a sub-40 10k",
    }
    r = client.put("/api/profile", json=payload)
    assert r.status_code == 200
    saved = r.json()
    assert saved["name"] == "Sam"
    assert saved["weight_kg"] == 62.5

    # Persisted across requests (read back from disk).
    again = client.get("/api/profile").json()
    assert again["max_hr"] == 188
    assert again["goals"] == "Run a sub-40 10k"


def test_profile_put_partial_clears_unset(client):
    client.put("/api/profile", json={"height_cm": 180, "max_hr": 190})
    # A subsequent save with only some fields does not retain the old ones.
    client.put("/api/profile", json={"weight_kg": 70})
    body = client.get("/api/profile").json()
    assert body["weight_kg"] == 70
    assert body["height_cm"] is None
    assert body["max_hr"] is None


def test_profile_rejects_out_of_range(client):
    r = client.put("/api/profile", json={"max_hr": 999})
    assert r.status_code == 422


def test_profile_get_tolerates_bad_on_disk_value(client):
    """A hand-edited profile.json with an out-of-range value must not 500 the GET."""
    import json
    import os
    from pathlib import Path

    path = Path(os.environ["FITSIFT_PROFILE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"height_cm": 400, "max_hr": 190}), encoding="utf-8")

    r = client.get("/api/profile")
    assert r.status_code == 200
    body = r.json()
    # The offending field is dropped; the valid one survives.
    assert body["height_cm"] is None
    assert body["max_hr"] == 190


def test_analyze_injects_profile(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, athlete_profile=None, **kwargs):
        captured["prompt"] = prompt
        captured["athlete_profile"] = athlete_profile
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    client.put("/api/profile", json={"max_hr": 190, "weight_kg": 72, "goals": "Sub-3 marathon"})

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post("/api/analyze", json={"activity_id": aid, "prompt": "Coach me"})
    assert r.status_code == 200
    profile_block = captured["athlete_profile"]
    assert profile_block is not None
    assert "Max HR: 190 bpm" in profile_block
    assert "Sub-3 marathon" in profile_block


def test_analyze_without_profile_passes_none(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, athlete_profile=None, **kwargs):
        captured["athlete_profile"] = athlete_profile
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post("/api/analyze", json={"activity_id": aid, "prompt": "Coach me"})
    assert r.status_code == 200
    assert captured["athlete_profile"] is None


def test_analyze_forwards_model_and_reasoning_effort(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False,
                    reasoning_effort=None, athlete_profile=None, **kwargs):
        captured["model"] = model
        captured["reasoning_effort"] = reasoning_effort
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post(
        "/api/analyze",
        json={
            "activity_id": aid,
            "prompt": "Coach me",
            "model": "claude-opus-4.8",
            "reasoning_effort": "max",
        },
    )
    assert r.status_code == 200
    # The web coach must forward the athlete's model + reasoning effort to the CLI,
    # otherwise a powerful model silently runs at default depth (the "too brief" bug).
    assert captured["model"] == "claude-opus-4.8"
    assert captured["reasoning_effort"] == "max"


@pytest.fixture()
def empty_client(tmp_path, monkeypatch):
    """A TestClient wired to an empty library (for ingest tests)."""
    library = tmp_path / "json"
    library.mkdir()
    monkeypatch.setenv("FITSIFT_LIBRARY", str(library))
    monkeypatch.setenv("FITSIFT_MEMORY", str(tmp_path / "memory"))
    monkeypatch.setenv("FITSIFT_PROFILE", str(tmp_path / "profile.json"))
    monkeypatch.setenv("FITSIFT_CHATS", str(tmp_path / "chats"))

    from fit2json.web import app as app_module
    from fit2json.web import services

    services._libraries.clear()
    importlib.reload(app_module)
    return TestClient(app_module.create_app())


def _fixture_bytes():
    with open(FIXTURE, "rb") as fh:
        return fh.read()


def test_convert_upload_and_dedup(empty_client):
    data = _fixture_bytes()

    r = empty_client.post(
        "/api/convert", files=[("files", ("sample.fit", data, "application/octet-stream"))]
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["added"]) == 1
    assert body["skipped"] == 0
    assert body["added"][0]["sport"] == "running"
    assert len(empty_client.get("/api/activities").json()) == 1

    # Re-uploading the same activity is deduped, not duplicated.
    r2 = empty_client.post(
        "/api/convert", files=[("files", ("sample.fit", data, "application/octet-stream"))]
    )
    body2 = r2.json()
    assert body2["added"] == []
    assert body2["skipped"] == 1
    assert len(empty_client.get("/api/activities").json()) == 1


def test_convert_rejects_non_fit(empty_client):
    r = empty_client.post(
        "/api/convert", files=[("files", ("notes.txt", b"hello", "text/plain"))]
    )
    assert r.status_code == 200
    body = r.json()
    assert body["added"] == []
    assert len(body["errors"]) == 1
    assert body["errors"][0]["file"] == "notes.txt"


def test_fetch_garmin_stores(empty_client, monkeypatch):
    from pathlib import Path

    from fit2json.sources import garmin as garmin_src

    monkeypatch.setattr(
        garmin_src, "fetch_garmin_activities", lambda **kwargs: [Path(FIXTURE)]
    )

    r = empty_client.post("/api/fetch/garmin", json={"days": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["fetched"] == 1
    assert len(body["added"]) == 1
    assert body["added"][0]["source"] == "garmin"


def test_fetch_unknown_platform(empty_client):
    assert empty_client.post("/api/fetch/nope", json={"days": 7}).status_code == 404


def test_metrics_unwrap_multivalue():
    """Lossless multi-value fields (e.g. enhanced_avg_speed=[5.42, None]) unwrap to a scalar."""
    from fit2json.web import services

    assert services._scalar([5.42, None]) == 5.42
    assert services._scalar([None, 3.0]) == 3.0
    assert services._scalar([None, None]) is None
    assert services._scalar(7) == 7
    cleaned = services._clean_metrics({"avg_speed_mps": [5.42, None], "avg_hr": 150})
    assert cleaned == {"avg_speed_mps": 5.42, "avg_hr": 150}


def test_legacy_0_1_format_shim():
    """fit2json 0.1 'compact' activities (summary/time_series) still populate the UI."""
    from fit2json.memory import _session_metrics
    from fit2json.web import services

    legacy = {
        "metadata": {"tool_version": "0.1.0"},
        "activities": [
            {
                "source_file": "2024-01-02_09-00-00_555444333.fit",
                "sport": "walking",
                "start_time": "2024-01-02T09:00:00+00:00",
                "summary": {
                    "total_distance_km": 4.0,
                    "total_duration_s": 2400,
                    "avg_heart_rate_bpm": 110,
                    "total_calories": 250,
                    "total_ascent_m": 30,
                },
                "laps": [
                    {"lap_number": 1, "distance_km": 4.0, "duration_s": 2400, "avg_heart_rate_bpm": 110}
                ],
                "time_series_1min": [{"elapsed_min": 0, "heart_rate_bpm": 100}],
            }
        ],
    }
    acts = services.decoded_from_obj(legacy)
    assert len(acts) == 1
    act = acts[0]
    assert act.sport == "walking"
    assert (act.start_time or "").startswith("2024-01-02")
    metrics = _session_metrics(act)
    assert metrics["distance_m"] == 4000.0
    assert metrics["duration_s"] == 2400
    assert metrics["avg_hr"] == 110
    assert round(metrics["avg_speed_mps"], 4) == round(4000.0 / 2400, 4)
    assert len(act.messages.get("lap") or []) == 1


def test_memory_reads_unindexed_md_from_filesystem(client):
    """The memory listing scans the .md corpus, not just index.jsonl."""
    import os
    from pathlib import Path

    mem = Path(os.environ["FITSIFT_MEMORY"])
    sport_dir = mem / "running"
    sport_dir.mkdir(parents=True, exist_ok=True)
    (sport_dir / "2024-05-05T0700-00Z_run_deadbeef.md").write_text(
        "---\n"
        "entry_id: e-unindexed\n"
        "activity_id: 2024-05-05T0700-00Z_run\n"
        "date: 2024-05-05T07:00:00+00:00\n"
        "sport: running\n"
        "source_file: run.fit\n"
        "backend: copilot\n"
        "model: \n"
        "created_at: 2024-05-05T07:30:00+00:00\n"
        'prompt: "How was my run?"\n'
        'metrics: {"distance_m": 5000}\n'
        "---\n\n"
        "# Running — 2024-05-05\n\n**Prompt:** How was my run?\n\nGreat run!\n",
        encoding="utf-8",
    )

    entries = client.get("/api/memory").json()["entries"]
    ids = [e["entry_id"] for e in entries]
    assert "e-unindexed" in ids

    entry = client.get("/api/memory/e-unindexed").json()
    assert "Great run!" in (entry.get("content") or "")
