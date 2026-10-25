"""Phase 0: the one settings module (Architecture section 12, NFR-SEC-004)."""

from __future__ import annotations

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith("VERIDOC_"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_defaults_are_safe(clean_env):
    from apps.api.settings import Settings

    s = Settings(_env_file=None)
    assert s.host == "127.0.0.1"
    assert s.safe_mode is False
    assert s.model_mode == "fake"
    assert s.anchor_enabled is False
    assert list(s.feature_flags) == []
    assert s.max_import_mb > 0


def test_environment_overrides(clean_env):
    from apps.api.settings import Settings

    clean_env.setenv("VERIDOC_SAFE_MODE", "1")
    clean_env.setenv("VERIDOC_MODEL_MODE", "local")
    clean_env.setenv("VERIDOC_MAX_IMPORT_MB", "5")
    s = Settings(_env_file=None)
    assert s.safe_mode is True
    assert s.model_mode == "local"
    assert s.max_import_mb == 5


def test_feature_flags_parse_comma_list(clean_env):
    from apps.api.settings import Settings

    clean_env.setenv("VERIDOC_FEATURE_FLAGS", "use_fixtures, voice ,")
    s = Settings(_env_file=None)
    assert set(s.feature_flags) == {"use_fixtures", "voice"}


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5", "example.com", "::"])
def test_host_must_be_loopback(clean_env, host):
    from apps.api.settings import Settings, SettingsError

    clean_env.setenv("VERIDOC_HOST", host)
    with pytest.raises((SettingsError, ValueError)):
        Settings(_env_file=None)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_loopback_hosts_accepted(clean_env, host):
    from apps.api.settings import Settings

    clean_env.setenv("VERIDOC_HOST", host)
    assert Settings(_env_file=None).host == host


def test_model_mode_rejects_unknown_value(clean_env):
    from apps.api.settings import Settings

    clean_env.setenv("VERIDOC_MODEL_MODE", "cloud")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_no_secret_has_a_default(clean_env):
    from apps.api.settings import Settings

    s = Settings(_env_file=None)
    for name, value in s.model_dump().items():
        if any(word in name for word in ("key", "secret", "token", "passphrase", "password")):
            assert value in (None, "", [], {}), f"{name} must not have a default value"
