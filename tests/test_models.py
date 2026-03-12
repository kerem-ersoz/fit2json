"""Tests for the models module."""

from fit2json.models import (
    Activity,
    ActivitySummary,
    HRZoneSeconds,
    Lap,
    OutputDocument,
    TimeSeriesSample,
)


class TestOutputDocument:
    def test_to_dict_strips_nones(self):
        activity = Activity(
            source_file="test.fit",
            sport="running",
            summary=ActivitySummary(
                total_distance_km=10.0,
                avg_power_w=None,  # should be stripped
            ),
        )
        doc = OutputDocument(activities=[activity], metadata={"tool_version": "0.1.0"})
        d = doc.to_dict()

        assert "avg_power_w" not in d["activities"][0]["summary"]
        assert d["activities"][0]["summary"]["total_distance_km"] == 10.0

    def test_to_json(self):
        doc = OutputDocument(
            activities=[
                Activity(source_file="test.fit", sport="running"),
            ],
            metadata={"file_count": 1},
        )
        json_str = doc.to_json()
        assert '"source_file": "test.fit"' in json_str
        assert '"sport": "running"' in json_str

    def test_empty_document(self):
        doc = OutputDocument()
        d = doc.to_dict()
        assert d["activities"] == []


class TestHRZoneSeconds:
    def test_defaults(self):
        zones = HRZoneSeconds()
        assert zones.z1 == 0
        assert zones.z5 == 0
