"""The settings (config.py, audit B1): every environment variable through `Settings`
or `Paths`, so `.env` is honoured everywhere, and a wrong `LOG_LEVEL` is refused at
start instead of crashing the first log call."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from leichtfacile.config import (
    LETTERS_DIR,
    Paths,
    Settings,
    config_file,
    default_data_dir,
    env_files,
    get_settings,
    paths,
)

VARIABLES = (
    "LLM_BASE_URL", "LLM_API_KEY", "LLM_NAME", "DATA_DIR", "EXAMPLES_DIR",
    "ALLOW_PRIVATE_URLS", "LOG_LEVEL", "LOG_FORMAT",
)  # fmt: skip


@pytest.fixture
def clean_env(monkeypatch):
    """The shell must not decide these tests."""
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_the_flags_and_folders_come_from_the_env_file(tmp_path, clean_env) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "LLM_BASE_URL=http://llm.test/v1\nLLM_API_KEY=k\nLLM_NAME=m\n"
        f"DATA_DIR={tmp_path / 'data'}\nEXAMPLES_DIR={tmp_path / 'examples'}\n"
        "ALLOW_PRIVATE_URLS=1\nLOG_LEVEL=debug\nLOG_FORMAT=JSON\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=env)  # type: ignore[call-arg]
    assert settings.allow_private_urls is True
    assert settings.log_level == "DEBUG" and settings.log_format == "json"
    assert settings.data_dir == tmp_path / "data"
    assert settings.examples_dir == tmp_path / "examples"
    # The dataset tools and the example loader read the folders without a key.
    paths = Paths(_env_file=env)  # type: ignore[call-arg]
    assert (paths.data_dir, paths.examples_dir) == (tmp_path / "data", tmp_path / "examples")


def test_the_shell_wins_over_the_env_file_and_defaults_hold(tmp_path, clean_env, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("EXAMPLES_DIR=from-file\n", encoding="utf-8")
    monkeypatch.setenv("EXAMPLES_DIR", "from-shell")
    assert str(Paths(_env_file=env).examples_dir) == "from-shell"  # type: ignore[call-arg]
    settings = Settings(
        _env_file=None, llm_base_url="http://llm.test/v1", llm_api_key="k", llm_name="m"
    )  # type: ignore[call-arg]
    assert settings.allow_private_urls is False
    assert (settings.log_level, settings.log_format) == ("INFO", "text")
    assert settings.data_dir == default_data_dir()
    monkeypatch.delenv("EXAMPLES_DIR")
    assert Paths(_env_file=None).examples_dir == LETTERS_DIR  # type: ignore[call-arg]
    assert settings.llm_thinking_mode == "off"  # each endpoint switches it its own way


def test_the_config_file_then_the_env_file_then_the_shell(tmp_path, clean_env, monkeypatch):
    """`leichtfacile setup` writes the config file; a .env in the current folder and the
    shell override it, in that order."""
    config = tmp_path / "config.env"
    config.write_text(
        "LLM_BASE_URL=http://config/v1\nLLM_API_KEY=k\nLLM_NAME=from-config\n"
        "DATA_DIR=from-config\nEXAMPLES_DIR=from-config\n",
        encoding="utf-8",
    )
    work = tmp_path / "work"
    work.mkdir()
    (work / ".env").write_text("LLM_NAME=from-env\nEXAMPLES_DIR=from-env\n", encoding="utf-8")
    monkeypatch.setenv("LEICHTFACILE_CONFIG", str(config))
    monkeypatch.setenv("EXAMPLES_DIR", "from-shell")
    monkeypatch.chdir(work)
    assert config_file() == config and env_files() == (config, Path(".env"))
    get_settings.cache_clear()
    try:
        settings = get_settings()
    finally:
        get_settings.cache_clear()
    assert settings.llm_base_url == "http://config/v1" and settings.llm_name == "from-env"
    assert str(settings.examples_dir) == "from-shell"
    assert str(paths().data_dir) == "from-config"


def test_the_default_folders_follow_the_platform(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("LEICHTFACILE_CONFIG", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    assert config_file() == tmp_path / "config" / "leichtfacile" / "config.env"
    assert default_data_dir() == tmp_path / "share" / "leichtfacile"
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert config_file() == tmp_path / "roaming" / "leichtfacile" / "config.env"
    assert default_data_dir() == tmp_path / "local" / "leichtfacile"


def test_a_wrong_log_level_or_format_is_refused_at_start(clean_env) -> None:
    base = {"llm_base_url": "http://llm.test/v1", "llm_api_key": "k", "llm_name": "m"}
    with pytest.raises(ValidationError, match="log_level"):
        Settings(_env_file=None, log_level="verbose", **base)  # type: ignore[call-arg]
    with pytest.raises(ValidationError, match="log_format"):
        Settings(_env_file=None, log_format="xml", **base)  # type: ignore[call-arg]
    assert Settings(_env_file=None, log_level=" warning ", **base).log_level == "WARNING"  # type: ignore[call-arg]  # fmt: skip
