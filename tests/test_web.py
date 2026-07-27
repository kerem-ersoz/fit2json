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
