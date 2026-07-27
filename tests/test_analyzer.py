"""Tests for the analysis backend harness."""

import json

import pytest

from fit2json import analyzer


class TestResolveBackend:
    def test_base_url_wins(self):
        assert analyzer.resolve_backend(None, "http://x/v1") == "openai-compatible"

    def test_explicit_backend(self):
        assert analyzer.resolve_backend("lmstudio", None) == "lmstudio"

    def test_auto_prefers_copilot(self, monkeypatch):
        monkeypatch.setattr(analyzer, "copilot_available", lambda: True)
        assert analyzer.resolve_backend(None, None) == "copilot"

    def test_auto_falls_back_to_ollama(self, monkeypatch):
        monkeypatch.setattr(analyzer, "copilot_available", lambda: False)
        assert analyzer.resolve_backend(None, None) == "ollama"


class TestCompaction:
    def _big_doc(self, n=5000):
        records = [{"timestamp": i, "heart_rate": 120, "speed": 3.0} for i in range(n)]
        return json.dumps({"activities": [{"messages": {"record": records, "session": [{"sport": "running"}]}}]})

    def test_short_input_untouched(self):
        data = json.dumps({"activities": []})
        assert analyzer.compact_workout_json(data, 10_000) == data

    def test_thins_records_to_fit(self):
        data = self._big_doc()
        out = analyzer.compact_workout_json(data, 20_000)
        assert len(out) <= 20_000
        parsed = json.loads(out)
        # session preserved even after thinning/dropping records
        assert parsed["activities"][0]["messages"]["session"][0]["sport"] == "running"

    def test_drops_records_when_tiny_budget(self):
        data = self._big_doc()
        out = analyzer.compact_workout_json(data, 500)
        assert len(out) <= 600  # truncation fallback bounds size


class _FakePopen:
    def __init__(self, cmd, **kwargs):
        _FakePopen.last_cmd = cmd
        self.returncode = 0
        self.stdout = iter(["Analysis part 1\n", "Analysis part 2\n"])

        class _Err:
            def read(self_inner):
                return ""

        self.stderr = _Err()

    def wait(self):
        return 0


class TestRunCopilot:
    def test_builds_command_and_returns_output(self, monkeypatch, tmp_path):
        monkeypatch.setattr(analyzer.shutil, "which", lambda name: "/usr/bin/copilot")
        monkeypatch.setattr(analyzer.subprocess, "Popen", _FakePopen)

        workout = tmp_path / "w.json"
        workout.write_text("{}")
        mem = tmp_path / "mem"
        mem.mkdir()

        out = analyzer.run_copilot(
            prompt="How did I do?",
            workout_paths=[workout],
            memory_dir=mem,
            model=None,
            stream=False,
        )
        assert "Analysis part 1" in out and "Analysis part 2" in out
        cmd = _FakePopen.last_cmd
        assert cmd[0] == "copilot"
        assert "--allow-all-tools" in cmd
        assert "--add-dir" in cmd
        # prompt (right after -p) references the workout file and the memory dir
        prompt_text = cmd[cmd.index("-p") + 1]
        assert str(workout) in prompt_text
        assert str(mem) in prompt_text

    def test_missing_copilot_raises(self, monkeypatch):
        monkeypatch.setattr(analyzer.shutil, "which", lambda name: None)
        import click

        with pytest.raises(click.ClickException):
            analyzer.run_copilot("p", [], None)

    def test_no_model_flag_when_unset(self, monkeypatch, tmp_path):
        """Omitting --model lets the CLI use the user's configured default (e.g. Opus).

        Forcing --model auto here overrides that default with the terse auto-router
        pick — the root cause of the "too brief for opus 4.8" report.
        """
        monkeypatch.setattr(analyzer.shutil, "which", lambda name: "/usr/bin/copilot")
        monkeypatch.setattr(analyzer.subprocess, "Popen", _FakePopen)
        analyzer.run_copilot(prompt="p", workout_paths=[], memory_dir=None, model=None, stream=False)
        assert "--model" not in _FakePopen.last_cmd

    def test_model_and_effort_passed_through(self, monkeypatch):
        monkeypatch.setattr(analyzer.shutil, "which", lambda name: "/usr/bin/copilot")
        monkeypatch.setattr(analyzer.subprocess, "Popen", _FakePopen)
        analyzer.run_copilot(
            prompt="p", workout_paths=[], memory_dir=None,
            model="claude-opus-4.8", stream=False, reasoning_effort="max",
        )
        cmd = _FakePopen.last_cmd
        assert cmd[cmd.index("--model") + 1] == "claude-opus-4.8"
        assert cmd[cmd.index("--reasoning-effort") + 1] == "max"

    def test_auto_with_effort_raises(self, monkeypatch):
        """'auto' + reasoning effort is rejected by the CLI, so fail fast with a clear error."""
        monkeypatch.setattr(analyzer.shutil, "which", lambda name: "/usr/bin/copilot")
        monkeypatch.setattr(analyzer.subprocess, "Popen", _FakePopen)
        import click

        with pytest.raises(click.ClickException):
            analyzer.run_copilot(
                prompt="p", workout_paths=[], memory_dir=None,
                model="auto", stream=False, reasoning_effort="max",
            )


class _FakeMessage:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _FakeChoiceDelta:
    def __init__(self, content):
        self.delta = type("D", (), {"content": content})()


class _FakeClient:
    class chat:
        class completions:
            @staticmethod
            def create(model, messages, stream=False):
                if stream:
                    return iter([
                        type("C", (), {"choices": [_FakeChoiceDelta("Hello ")]})(),
                        type("C", (), {"choices": [_FakeChoiceDelta("world")]})(),
                    ])
                return type("R", (), {"choices": [_FakeMessage("Full answer")]})()

    class models:
        @staticmethod
        def list():
            return type("L", (), {"data": [type("M", (), {"id": "mock-model"})()]})()


class TestRunOpenAICompatible:
    def test_non_stream(self, monkeypatch, capsys):
        monkeypatch.setattr(analyzer, "_make_client", lambda base_url, api_key: _FakeClient())
        out = analyzer.run_openai_compatible(
            prompt="p", workout_json="{}", base_url="http://x/v1", api_key="k",
            stream=False,
        )
        assert out == "Full answer"

    def test_stream_collects(self, monkeypatch):
        monkeypatch.setattr(analyzer, "_make_client", lambda base_url, api_key: _FakeClient())
        out = analyzer.run_openai_compatible(
            prompt="p", workout_json="{}", base_url="http://x/v1", api_key="k",
            stream=True,
        )
        assert out == "Hello world"
