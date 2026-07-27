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


def test_models_copilot(client):
    r = client.get("/api/models", params={"backend": "copilot"})
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "copilot"
    assert body["models"][0] == "auto"  # always offered; fresh corpus has no others yet
    assert body["allow_custom"] is True
    # Effort levels are exposed (from the CLI, or the known fallback when it's absent).
    assert "high" in body["efforts"] and "medium" in body["efforts"]


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

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None):
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

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None):
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


def test_analyze_freeform_no_selection(client, monkeypatch):
    """With no workouts selected, the agent is handed the whole library to find them itself."""
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None, library_dir=None):
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

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None):
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

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None):
        assert "REUSED BLOCK" in prompt
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post("/api/analyze", json={"activity_ids": [aid, aid], "prompt": "compare"})
    assert r.status_code == 200 and "event: done" in r.text


def test_analyze_appends_chart_guidance(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None):
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

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None):
        captured["prompt"] = prompt
        yield "ok"

    monkeypatch.setattr(analyzer, "stream_copilot", fake_stream)

    aid = client.get("/api/activities").json()[0]["id"]
    r = client.post(
        "/api/analyze", json={"activity_id": aid, "prompt": "Summarize", "charts": False}
    )
    assert r.status_code == 200
    assert "fitsift-chart" not in captured["prompt"]


def test_analyze_forwards_model_and_reasoning_effort(client, monkeypatch):
    from fit2json import analyzer

    monkeypatch.setattr(analyzer, "resolve_backend", lambda backend, base_url: "copilot")
    captured: dict = {}

    def fake_stream(prompt, workout_paths, memory_dir=None, model=None, silent=False, reasoning_effort=None):
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
