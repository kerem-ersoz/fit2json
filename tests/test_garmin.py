"""Tests for the Garmin source (token-store auth + skip-existing dedup).

All Garmin network access is mocked by injecting a fake ``garminconnect`` module
into ``sys.modules`` — the import in ``fit2json.sources.garmin`` is function-local,
so the fake is picked up at call time. No network is touched.
"""

import os
import sys
import types

import click
import pytest
from click.testing import CliRunner

from fit2json.cli import cli
from fit2json.sources.garmin import fetch_garmin_activities

# ── Fakes ──────────────────────────────────────────────────────────────────────


class _AuthError(Exception):
    pass


class _ConnError(Exception):
    pass


class _RateError(Exception):
    pass


class _Fmt:
    ORIGINAL = "ORIGINAL"


class FakeGarmin:
    """Configurable stand-in for garminconnect.Garmin."""

    # Per-test knobs (reset by the fixture).
    resume_should_fail = True
    resume_exc = FileNotFoundError("no cached tokens")
    activities: list = []
    fit_bytes = b"FITDATA"
    instances: list = []

    def __init__(self, email=None, password=None, is_cn=False, **kwargs):
        self.email = email
        self.password = password
        self.login_calls = []
        self.downloaded_ids = []
        self.dumped = []
        self.ActivityDownloadFormat = _Fmt
        self.garth = types.SimpleNamespace(dump=lambda path: self.dumped.append(path))
        FakeGarmin.instances.append(self)

    def login(self, tokenstore=None):
        self.login_calls.append(tokenstore)
        # Capture what GARMINTOKENS looked like at login time (the credential path
        # must clear it so login() doesn't try to resume from the env var).
        self.login_env_tokens = os.environ.get("GARMINTOKENS")
        # Resume path: constructed via Garmin() (no email) with a tokenstore.
        if self.email is None:
            if FakeGarmin.resume_should_fail:
                raise FakeGarmin.resume_exc
            return True
        # Credential path.
        return True

    def get_activities_by_date(self, start, end):
        return list(FakeGarmin.activities)

    def download_activity(self, activity_id, dl_fmt=None):
        self.downloaded_ids.append(activity_id)
        return FakeGarmin.fit_bytes


@pytest.fixture
def fake_garmin(monkeypatch):
    FakeGarmin.instances = []
    FakeGarmin.resume_should_fail = True
    FakeGarmin.resume_exc = FileNotFoundError("no cached tokens")
    FakeGarmin.activities = []
    FakeGarmin.fit_bytes = b"FITDATA"

    for var in ("GARMIN_EMAIL", "GARMIN_PASSWORD", "GARMINTOKENS"):
        monkeypatch.delenv(var, raising=False)

    module = types.ModuleType("garminconnect")
    module.Garmin = FakeGarmin
    module.GarminConnectAuthenticationError = _AuthError
    module.GarminConnectConnectionError = _ConnError
    module.GarminConnectTooManyRequestsError = _RateError
    monkeypatch.setitem(sys.modules, "garminconnect", module)
    return FakeGarmin


# ── Auth: token-store resume + fallback ─────────────────────────────────────────


class TestGarminAuth:
    def test_resume_uses_cached_session_without_credentials(self, fake_garmin, tmp_path):
        fake_garmin.resume_should_fail = False
        token_dir = tmp_path / "tokens"

        result = fetch_garmin_activities(
            days=1,
            output_dir=str(tmp_path / "fit"),
            token_dir=str(token_dir),
            interactive=False,
        )

        assert result == []
        # Only the resume client is created (no credential fallback).
        assert len(fake_garmin.instances) == 1
        resumed = fake_garmin.instances[0]
        assert resumed.email is None
        assert resumed.login_calls == [str(token_dir)]

    def test_fallback_to_credentials_and_persist_tokens(self, fake_garmin, tmp_path, monkeypatch):
        # Mirror the Docker wrapper: GARMINTOKENS set in the env, no explicit --token-dir.
        fake_garmin.resume_should_fail = True
        token_dir = tmp_path / "tokens"
        monkeypatch.setenv("GARMINTOKENS", str(token_dir))

        result = fetch_garmin_activities(
            days=1,
            output_dir=str(tmp_path / "fit"),
            email="rider@example.com",
            password="secret",
            interactive=False,
        )

        assert result == []
        # First instance = failed resume, second = credential login.
        assert len(fake_garmin.instances) == 2
        resume_client, cred_client = fake_garmin.instances
        assert resume_client.email is None
        assert cred_client.email == "rider@example.com"
        # The credential login must NOT see GARMINTOKENS (else it would try to resume
        # instead of doing a fresh login).
        assert cred_client.login_env_tokens is None
        # Tokens were persisted to the resolved token dir for future runs.
        assert cred_client.dumped == [str(token_dir)]
        # ...and the env var is restored afterwards.
        assert os.environ["GARMINTOKENS"] == str(token_dir)

    def test_missing_credentials_when_resume_fails_raises(self, fake_garmin, tmp_path):
        fake_garmin.resume_should_fail = True

        with pytest.raises(click.ClickException) as exc:
            fetch_garmin_activities(
                days=1,
                output_dir=str(tmp_path / "fit"),
                token_dir=str(tmp_path / "tokens"),
                interactive=False,
            )

        assert "credentials" in str(exc.value).lower()


# ── Dedup: skip already-downloaded ──────────────────────────────────────────────


class TestGarminDedup:
    def test_skips_existing_and_downloads_only_new(self, fake_garmin, tmp_path):
        fake_garmin.resume_should_fail = False
        raw_dir = tmp_path / "fit"
        raw_dir.mkdir()
        # Pre-existing archive for activity 111 (matches *_111.fit).
        (raw_dir / "2024-01-01_07-00-00_111.fit").write_bytes(b"OLD")

        fake_garmin.activities = [
            {"activityId": 111, "activityName": "old run", "startTimeLocal": "2024-01-01 07:00:00"},
            {"activityId": 222, "activityName": "new run", "startTimeLocal": "2024-01-02 08:00:00"},
        ]

        result = fetch_garmin_activities(
            days=2,
            output_dir=str(raw_dir),
            token_dir=str(tmp_path / "tokens"),
            interactive=False,
        )

        # Only the new activity is downloaded and returned.
        assert len(result) == 1
        new_file = raw_dir / "2024-01-02_08-00-00_222.fit"
        assert result[0] == new_file
        assert new_file.read_bytes() == b"FITDATA"

        client = fake_garmin.instances[0]
        assert client.downloaded_ids == [222]

        # The pre-existing file is untouched.
        assert (raw_dir / "2024-01-01_07-00-00_111.fit").read_bytes() == b"OLD"


# ── Token persistence (version tolerance) ───────────────────────────────────────


class TestPersistTokens:
    def _client_with(self, attr, dumped):
        holder = types.SimpleNamespace(dump=lambda path: dumped.append(path))
        return types.SimpleNamespace(**{attr: holder})

    def test_uses_garth_attr_on_old_library(self, tmp_path):
        from fit2json.sources.garmin import _persist_tokens

        dumped = []
        client = self._client_with("garth", dumped)  # garminconnect <= 0.2.x
        assert _persist_tokens(client, str(tmp_path / "tok")) is True
        assert dumped == [str(tmp_path / "tok")]

    def test_uses_client_attr_on_new_library(self, tmp_path):
        from fit2json.sources.garmin import _persist_tokens

        dumped = []
        client = self._client_with("client", dumped)  # garminconnect >= 0.3.x
        assert _persist_tokens(client, str(tmp_path / "tok")) is True
        assert dumped == [str(tmp_path / "tok")]

    def test_returns_false_when_no_garth_client(self, tmp_path):
        from fit2json.sources.garmin import _persist_tokens

        assert _persist_tokens(types.SimpleNamespace(), str(tmp_path / "tok")) is False


# ── CLI wiring ──────────────────────────────────────────────────────────────────


class TestGarminCLI:
    def test_fetch_garmin_help_lists_new_options(self):
        result = CliRunner().invoke(cli, ["fetch", "garmin", "--help"])
        assert result.exit_code == 0
        assert "--token-dir" in result.output
        assert "--raw-dir" in result.output
