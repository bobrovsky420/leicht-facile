"""The settings (config.py, audit B1): every environment variable through `Settings`
or `Paths`, so `.env` is honoured everywhere, and a wrong `LOG_LEVEL` is refused at
start instead of crashing the first log call."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from leichtfacile.config import Paths, Settings

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
    assert str(settings.data_dir) == "data"


def test_a_wrong_log_level_or_format_is_refused_at_start(clean_env) -> None:
    base = {"llm_base_url": "http://llm.test/v1", "llm_api_key": "k", "llm_name": "m"}
    with pytest.raises(ValidationError, match="log_level"):
        Settings(_env_file=None, log_level="verbose", **base)  # type: ignore[call-arg]
    with pytest.raises(ValidationError, match="log_format"):
        Settings(_env_file=None, log_format="xml", **base)  # type: ignore[call-arg]
    assert Settings(_env_file=None, log_level=" warning ", **base).log_level == "WARNING"  # type: ignore[call-arg]  # fmt: skip
