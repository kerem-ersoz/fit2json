"""Tests for the lossless FIT parser."""

import datetime
import json
from pathlib import Path

from fit2json.parser import _coerce, _decode_message, _field_key, decode_fit_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample-activity.fit"


class _FakeField:
    """Lightweight stand-in for fitdecode.types.FieldData."""

    def __init__(self, name, value, units=None, def_num=0, is_named=True):
        self.name = name
        self.value = value
        self.units = units
        self.def_num = def_num
        self.is_named = is_named


class _FakeFrame:
    def __init__(self, fields):
        self.fields = fields


class TestCoerce:
    def test_datetime_to_iso_utc(self):
        dt = datetime.datetime(2024, 3, 10, 7, 30, 0)
        assert _coerce(dt) == "2024-03-10T07:30:00+00:00"

    def test_bytes_to_hex(self):
        assert _coerce(b"\x01\xff") == "01ff"

    def test_tuple_to_list_recursive(self):
        assert _coerce((1, b"\x00", (2, 3))) == [1, "00", [2, 3]]

    def test_passthrough_scalars(self):
        assert _coerce(5) == 5
        assert _coerce(1.5) == 1.5
        assert _coerce("x") == "x"
        assert _coerce(None) is None


class TestFieldKeyAndMessage:
    def test_unnamed_field_key(self):
        assert _field_key(_FakeField(None, 1, def_num=22, is_named=False)) == "unknown_22"

    def test_named_field_key(self):
        assert _field_key(_FakeField("heart_rate", 120)) == "heart_rate"

    def test_duplicate_field_names_become_list(self):
        frame = _FakeFrame([
            _FakeField("x", 1),
            _FakeField("x", 2),
            _FakeField("x", 3),
        ])
        rec = _decode_message(frame, {})
        assert rec["x"] == [1, 2, 3]

    def test_units_legend_populated(self):
        units = {}
        _decode_message(_FakeFrame([_FakeField("distance", 10, units="m")]), units)
        assert units["distance"] == "m"


class TestDecodeFitFile:
    def test_decodes_known_message_types(self):
        act = decode_fit_file(FIXTURE)
        assert "record" in act.messages
        assert "session" in act.messages
        assert act.message_counts["record"] >= 1

    def test_metadata_derived(self):
        act = decode_fit_file(FIXTURE)
        assert act.sport == "running"
        assert act.start_time and act.start_time.startswith("2012-")

    def test_units_and_timestamp_serialization(self):
        act = decode_fit_file(FIXTURE)
        assert act.field_units.get("distance") == "m"
        first = act.messages["record"][0]
        assert isinstance(first["timestamp"], str)  # datetime -> ISO string

    def test_fully_json_serializable(self):
        act = decode_fit_file(FIXTURE)
        # Must not raise
        json.dumps(act.to_dict())

    def test_missing_file_raises(self):
        import pytest

        with pytest.raises(FileNotFoundError):
            decode_fit_file("/nonexistent/file.fit")
