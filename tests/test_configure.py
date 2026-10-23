"""`leichtfacile setup` and the start of the command line: the questions, the presets,
the file setup writes, the message for missing settings and when the browser opens."""

from __future__ import annotations

import sys

import pytest

from leichtfacile.cli import main, settings_or_exit, wants_browser
from leichtfacile.config import Settings, get_settings
from leichtfacile.configure import run_setup

VARIABLES = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_NAME", "LLM_JUDGE_NAME", "LLM_THINKING_MODE",
             "LLM_MAX_RETRIES", "LLM_EXTRA_BODY", "DATA_DIR", "EXAMPLES_DIR")  # fmt: skip


@pytest.fixture
def config(tmp_path, monkeypatch):
    """The config file's place, an empty current folder and a shell without settings."""
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / "leichtfacile" / "config.env"
    monkeypatch.setenv("LEICHTFACILE_CONFIG", str(path))
    monkeypatch.chdir(tmp_path)
    return path


def answers(*values: str):
    given = iter(values)
    return lambda prompt: next(given)


def never(prompt: str) -> str:
    pytest.fail(f"asked: {prompt}")


def written(path) -> Settings:
    return Settings(_env_file=path)  # type: ignore[call-arg]


def test_the_cscs_preset_needs_only_the_key(config) -> None:
    said: list[str] = []
    listed = ["swiss-ai/Apertus-v1.5-70B", "swiss-ai/Apertus-v1.5-8B"]
    code = run_setup(ask=answers("1", "", "", ""), ask_secret=answers("secret-key"),
                     models=lambda url, key: listed, say=said.append)  # fmt: skip
    assert code == 0
    settings = written(config)
    assert settings.llm_base_url == "https://api.inference.cscs.ch/v1"
    assert settings.llm_api_key.get_secret_value() == "secret-key"
    assert settings.llm_name == "swiss-ai/Apertus-v1.5-8B"
    assert settings.llm_judge_name == "swiss-ai/Apertus-v1.5-70B"
    assert settings.llm_thinking_mode == "model-suffix" and settings.llm_max_retries == 8
    assert "secret-key" not in "\n".join(said)


def test_another_endpoint_offers_its_own_model_list(config) -> None:
    said: list[str] = []
    code = run_setup(ask=answers("6", "https://llm.example/v1", "model-b", ""),
                     ask_secret=answers("k"), models=lambda url, key: ["model-a", "model-b"],
                     say=said.append)  # fmt: skip
    assert code == 0 and "  - model-a" in said
    settings = written(config)
    assert (settings.llm_base_url, settings.llm_name) == ("https://llm.example/v1", "model-b")
    assert settings.llm_judge_name is None  # the same model judges
    assert settings.llm_thinking_mode == "off"


def test_a_model_list_that_cannot_be_read_still_asks_for_the_model(config) -> None:
    def unreachable(url: str, key: str) -> list[str]:
        raise OSError("refused")

    said: list[str] = []
    code = run_setup(ask=answers("6", "http://127.0.0.1:9/v1", "", "my-model", ""),
                     ask_secret=answers("k"), models=unreachable, say=said.append)  # fmt: skip
    assert code == 0 and any("could not be read" in line for line in said)
    assert written(config).llm_name == "my-model"  # asked again after the empty answer


def test_given_values_ask_nothing_and_replace_a_file_only_with_force(config) -> None:
    given = {"base_url": "http://llm.test/v1", "api_key": "k", "model": "m"}
    assert run_setup(**given, ask=never, ask_secret=never, say=lambda line: None) == 0
    first = config.read_text(encoding="utf-8")
    assert run_setup(**given, judge="j", ask=never, ask_secret=never, say=lambda line: None) == 1
    assert config.read_text(encoding="utf-8") == first
    assert run_setup(**given, judge="j", force=True, ask=never, say=lambda line: None) == 0
    assert written(config).llm_judge_name == "j"


def test_values_with_spaces_quotes_and_json_read_back_unchanged(config) -> None:
    key = "a b#c'd\"e\\f"
    code = run_setup(preset="publicai", base_url="https://api.publicai.co/v1", api_key=key,
                     model="swiss-ai/apertus-v1.5-8b", ask=never, say=print)  # fmt: skip
    assert code == 0
    settings = written(config)
    assert settings.llm_api_key.get_secret_value() == key
    assert settings.llm_extra_body == {"cache": {"no-cache": True}}
    assert settings.llm_thinking_mode == "chat-template"


def test_the_command_line_writes_the_file(config) -> None:
    argv = ["setup", "--base-url", "http://llm.test/v1", "--api-key", "k", "--model", "m"]
    assert main(argv) == 0
    assert written(config).llm_name == "m"


def test_missing_settings_name_themselves_and_the_setup(config, capsys) -> None:
    get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit) as stop:
            settings_or_exit()
    finally:
        get_settings.cache_clear()
    assert stop.value.code == 2
    error = capsys.readouterr().err
    assert "LLM_BASE_URL" in error and "LLM_NAME" in error and "leichtfacile setup" in error
    assert str(config) in error


def test_the_browser_opens_only_on_this_machine_with_a_desktop(monkeypatch) -> None:
    assert not wants_browser("0.0.0.0")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert not wants_browser("127.0.0.1")  # a server: Python would start a text browser
    monkeypatch.setenv("DISPLAY", ":0")
    assert wants_browser("127.0.0.1")
    monkeypatch.setattr(sys, "platform", "win32")
    assert wants_browser("localhost")
