"""Tests for the CLI commands."""

import json
from pathlib import Path

from click.testing import CliRunner

from fit2json import analyzer
from fit2json.cli import cli

runner = CliRunner()
FIXTURE = str(Path(__file__).parent / "fixtures" / "sample-activity.fit")


class TestBasics:
    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.2.0" in result.output

    def test_help_lists_commands(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for cmd in ("convert", "fetch", "analyze", "memory"):
            assert cmd in result.output

    def test_convert_missing_file(self):
        result = runner.invoke(cli, ["convert", "/nonexistent/file.fit"])
        assert result.exit_code != 0

    def test_fetch_help(self):
        result = runner.invoke(cli, ["fetch", "--help"])
        assert result.exit_code == 0
        assert "garmin" in result.output
        assert "strava" in result.output


class TestConvert:
    def test_convert_to_combined_file(self, tmp_path):
        out = tmp_path / "a.json"
        result = runner.invoke(cli, ["convert", FIXTURE, "-o", str(out)])
        assert result.exit_code == 0, result.output
        doc = json.loads(out.read_text())
        assert doc["metadata"]["schema"] == "lossless-fit"
        act = doc["activities"][0]
        assert act["sport"] == "running"
        assert "messages" in act and "record" in act["messages"]

    def test_convert_to_directory(self, tmp_path):
        out_dir = tmp_path / "out"
        result = runner.invoke(cli, ["convert", FIXTURE, "-o", str(out_dir)])
        assert result.exit_code == 0, result.output
        files = list(out_dir.glob("*.json"))
        assert len(files) == 1

    def test_convert_gzip(self, tmp_path):
        out_dir = tmp_path / "gz"
        result = runner.invoke(cli, ["convert", FIXTURE, "-o", str(out_dir), "--gzip"])
        assert result.exit_code == 0, result.output
        assert list(out_dir.glob("*.json.gz"))


class TestAnalyze:
    def test_analyze_no_input(self):
        result = runner.invoke(cli, ["analyze", "-p", "test"], input="")
        assert result.exit_code != 0

    def test_analyze_wiring_and_memory(self, tmp_path, monkeypatch):
        workout = tmp_path / "w.json"
        runner.invoke(cli, ["convert", FIXTURE, "-o", str(workout)])
        monkeypatch.setattr(analyzer, "run_openai_compatible", lambda **kw: "MOCK OK")
        memdir = tmp_path / "mem"

        result = runner.invoke(
            cli,
            ["analyze", str(workout), "-p", "How was it?",
             "--base-url", "http://x/v1", "--memory", str(memdir)],
        )
        assert result.exit_code == 0, result.output
        assert (memdir / "index.jsonl").exists()
        entries = [json.loads(l) for l in (memdir / "index.jsonl").read_text().splitlines() if l.strip()]
        assert entries and entries[0]["sport"] == "running"

    def test_analyze_injects_profile(self, tmp_path, monkeypatch):
        workout = tmp_path / "w.json"
        runner.invoke(cli, ["convert", FIXTURE, "-o", str(workout)])

        captured = {}
        monkeypatch.setattr(
            analyzer, "run_openai_compatible",
            lambda **kw: captured.update(kw) or "MOCK OK",
        )

        profile = tmp_path / "profile.json"
        profile.write_text(json.dumps({"max_hr": 190, "goals": "Sub-3 marathon"}), encoding="utf-8")

        result = runner.invoke(
            cli,
            ["analyze", str(workout), "-p", "Coach me",
             "--base-url", "http://x/v1", "--memory", str(tmp_path / "m"),
             "--profile", str(profile)],
        )
        assert result.exit_code == 0, result.output
        assert captured["athlete_profile"] is not None
        assert "Max HR: 190 bpm" in captured["athlete_profile"]
        assert "Sub-3 marathon" in captured["athlete_profile"]

    def test_analyze_no_profile_flag(self, tmp_path, monkeypatch):
        workout = tmp_path / "w.json"
        runner.invoke(cli, ["convert", FIXTURE, "-o", str(workout)])

        captured = {}
        monkeypatch.setattr(
            analyzer, "run_openai_compatible",
            lambda **kw: captured.update(kw) or "MOCK OK",
        )

        profile = tmp_path / "profile.json"
        profile.write_text(json.dumps({"max_hr": 190}), encoding="utf-8")

        result = runner.invoke(
            cli,
            ["analyze", str(workout), "-p", "Coach me",
             "--base-url", "http://x/v1", "--memory", str(tmp_path / "m"),
             "--profile", str(profile), "--no-profile"],
        )
        assert result.exit_code == 0, result.output
        assert captured["athlete_profile"] is None


class TestMemoryCommands:
    def test_memory_list_empty(self, tmp_path):
        result = runner.invoke(cli, ["memory", "list", "--memory", str(tmp_path / "empty")])
        assert result.exit_code == 0
        assert "No memories" in result.output

    def test_memory_path(self, tmp_path):
        result = runner.invoke(cli, ["memory", "path", "--memory", str(tmp_path / "m")])
        assert result.exit_code == 0
        assert str(tmp_path / "m") in result.output
