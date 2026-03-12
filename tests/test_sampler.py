"""Tests for the time-series sampler."""

from datetime import datetime, timedelta

from fit2json.sampler import downsample_to_1min


def _make_records(count: int, interval_s: int = 1, start: datetime = None):
    """Generate mock records for testing."""
    start = start or datetime(2024, 3, 10, 7, 0, 0)
    records = []
    for i in range(count):
        records.append({
            "timestamp": start + timedelta(seconds=i * interval_s),
            "heart_rate": 120 + (i % 30),
            "cadence": 85,
            "speed": 3.0 + (i % 10) * 0.1,
            "power": None,
        })
    return records


class TestDownsampleTo1Min:
    def test_empty_records(self):
        assert downsample_to_1min([]) == []

    def test_no_timestamps(self):
        records = [{"heart_rate": 120, "timestamp": None}]
        assert downsample_to_1min(records) == []

    def test_single_minute(self):
        records = _make_records(30)  # 30 seconds
        samples = downsample_to_1min(records)
        assert len(samples) == 1
        assert samples[0].elapsed_min == 0
        assert samples[0].heart_rate_bpm is not None

    def test_multiple_minutes(self):
        records = _make_records(180)  # 3 minutes
        samples = downsample_to_1min(records)
        assert len(samples) == 3
        assert samples[0].elapsed_min == 0
        assert samples[1].elapsed_min == 1
        assert samples[2].elapsed_min == 2

    def test_cadence_doubled(self):
        records = _make_records(60)
        samples = downsample_to_1min(records)
        # Cadence should be doubled (85 * 2 = 170)
        assert samples[0].cadence_spm == 170

    def test_speed_converted_to_kmh(self):
        start = datetime(2024, 1, 1)
        records = [
            {"timestamp": start, "heart_rate": 120, "cadence": 85, "speed": 3.0, "power": None},
        ]
        samples = downsample_to_1min(records)
        # 3.0 m/s * 3.6 = 10.8 km/h
        assert samples[0].speed_kmh == 10.8

    def test_handles_gaps(self):
        start = datetime(2024, 1, 1)
        records = [
            {"timestamp": start, "heart_rate": 120, "cadence": 85, "speed": 3.0, "power": None},
            # Gap at minute 1
            {"timestamp": start + timedelta(minutes=2, seconds=10), "heart_rate": 140, "cadence": 90, "speed": 3.5, "power": None},
        ]
        samples = downsample_to_1min(records)
        assert len(samples) == 3  # minutes 0, 1, 2
        assert samples[1].heart_rate_bpm is None  # gap minute

    def test_null_power_stays_null(self):
        records = _make_records(60)
        samples = downsample_to_1min(records)
        assert samples[0].power_w is None
