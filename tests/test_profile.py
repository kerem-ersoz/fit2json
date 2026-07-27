"""Tests for the athlete-profile module (load / save / prompt formatting)."""

from datetime import datetime, timezone

from fit2json.profile import (
    default_profile_path,
    format_profile_prompt,
    load_profile,
    save_profile,
)


def test_save_strips_empty_and_unknown_fields(tmp_path):
    path = tmp_path / "profile.json"
    saved = save_profile(
        path,
        {
            "height_cm": 180,
            "weight_kg": None,   # dropped (None)
            "goals": "",         # dropped (empty)
            "junk": "nope",      # dropped (unknown)
            "max_hr": 190,
        },
    )
    assert saved == {"height_cm": 180, "max_hr": 190}
    assert load_profile(path) == {"height_cm": 180, "max_hr": 190}


def test_load_missing_file_is_empty(tmp_path):
    assert load_profile(tmp_path / "nope.json") == {}


def test_load_corrupt_file_is_empty(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load_profile(path) == {}


def test_format_prompt_empty():
    assert format_profile_prompt({}) == ""


def test_format_prompt_includes_set_fields_with_units():
    year = datetime.now(timezone.utc).year
    block = format_profile_prompt(
        {
            "sex": "male",
            "birth_year": year - 30,
            "height_cm": 180,
            "weight_kg": 72,
            "resting_hr": 48,
            "max_hr": 190,
            "lactate_threshold_hr": 168,
            "ftp_w": 260,
            "vo2max": 55,
            "goals": "Sub-3 marathon",
        }
    )
    assert "Height: 180 cm" in block
    assert "Weight: 72 kg" in block
    assert "Max HR: 190 bpm" in block
    assert "FTP: 260 W" in block
    assert "Age: 30" in block
    assert "Sub-3 marathon" in block


def test_format_prompt_ignores_unspecified_sex_and_bad_birth_year():
    block = format_profile_prompt({"sex": "unspecified", "birth_year": 1700, "max_hr": 200})
    assert "Sex" not in block
    assert "Age" not in block
    assert "Max HR: 200 bpm" in block


def test_default_profile_path_is_under_fit2json():
    p = default_profile_path()
    assert p.name == "profile.json"
    assert ".fit2json" in p.parts
