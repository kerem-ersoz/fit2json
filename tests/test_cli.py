"""Tests for the CLI commands."""

from click.testing import CliRunner

from fit2json.cli import cli


runner = CliRunner()


class TestCLI:
    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "convert" in result.output
        assert "fetch" in result.output
        assert "analyze" in result.output

    def test_convert_missing_file(self):
        result = runner.invoke(cli, ["convert", "/nonexistent/file.fit"])
        assert result.exit_code != 0

    def test_fetch_help(self):
        result = runner.invoke(cli, ["fetch", "--help"])
        assert result.exit_code == 0
        assert "garmin" in result.output
        assert "strava" in result.output

    def test_analyze_no_input(self):
        result = runner.invoke(cli, ["analyze", "--prompt", "test"])
        assert result.exit_code != 0

    def test_convert_help(self):
        result = runner.invoke(cli, ["convert", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
