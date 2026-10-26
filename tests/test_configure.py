"""`leichtfacile setup`, `endpoint` and `config` (configure.py) and the start of the
command line: the questions, the presets, what is written where, the checks before a
change is written, and when the browser opens."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

from leichtfacile import config
from leichtfacile.cli import main, settings_or_exit, wants_browser
from leichtfacile.config import ConfigError, get_settings, load
from leichtfacile.configure import (
    edit,
    list_endpoints,
    remove_endpoint,
    run_setup,
    set_value,
    show,
    unset_value,
    use_endpoint,
)

LISTED = ["swiss-ai/Apertus-v1.5-70B", "swiss-ai/Apertus-v1.5-8B"]
# the menu's "Another OpenAI-compatible endpoint", after the presets it offers
OTHER = str(sum(preset.in_menu for preset in config.PRESETS.values()) + 1)


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """The config file's place, an empty current folder and no keys in the shell."""
    path = tmp_path / "home" / "config.toml"
    monkeypatch.setenv("LEICHTFACILE_CONFIG", str(path))
    monkeypatch.setattr(config, "PROJECT_FILE", Path("leichtfacile.toml"))
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", Path(".env"))
    for name in ("CSCS_API_KEY", "LLM_API_KEY", "LOCAL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path / "work")
    return path


def answers(*values: str):
    given = iter(values)
    return lambda prompt: next(given)


def never(prompt: str) -> str:
    pytest.fail(f"asked: {prompt}")


def toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_the_cscs_preset_needs_only_the_key(home) -> None:
    said: list[str] = []
    # endpoint 1 in the menu, then the key: no address, name, model or judge question
    code = run_setup(ask=answers("1"), ask_secret=answers("secret-key"),
                     models=lambda url, key: LISTED, say=said.append)  # fmt: skip
    assert code == 0
    assert toml(home) == {"llm": {"endpoint": "cscs"}}  # the preset as it is: no table
    assert (home.parent / ".env").read_text(encoding="utf-8").endswith("CSCS_API_KEY=secret-key\n")
    llm = load().settings.llm
    assert llm.url == "https://api.inference.cscs.ch/v1" and llm.thinking == "model-suffix"
    assert [llm.models.writer, llm.models.judge] == LISTED[::-1]
    assert llm.api_key.get_secret_value() == "secret-key"
    assert "secret-key" not in "\n".join(said) and "secret-key" not in home.read_text("utf-8")
    assert "The endpoint lists 2 models." in said  # the key was tried


def test_a_preset_whose_key_is_set_asks_nothing(home, monkeypatch) -> None:
    monkeypatch.setenv("CSCS_API_KEY", "from-shell")
    said: list[str] = []
    assert run_setup(name="cscs", ask=never, ask_secret=never, say=said.append) == 0
    assert toml(home) == {"llm": {"endpoint": "cscs"}} and not (home.parent / ".env").exists()
    assert "Its key comes from the variable CSCS_API_KEY." in said
    # What differs from the preset goes into a table of the preset's name, nothing else.
    code = run_setup(name="cscs", model="swiss-ai/Apertus-v1.5-70B", force=True, ask=never,
                     ask_secret=never, say=said.append)  # fmt: skip
    assert code == 0
    assert toml(home) == {
        "endpoints": {"cscs": {"models": {"writer": "swiss-ai/Apertus-v1.5-70B"}}},
        "llm": {"endpoint": "cscs"},
    }
    assert load().settings.llm.url == "https://api.inference.cscs.ch/v1"
    # Back to the preset as it is: the table goes.
    assert run_setup(name="cscs", force=True, ask=never, ask_secret=never, say=said.append) == 0
    assert toml(home) == {"llm": {"endpoint": "cscs"}}


def test_the_menu_leaves_out_the_rarely_used_presets_which_setup_still_takes(
    home, monkeypatch
) -> None:
    said: list[str] = []
    assert run_setup(ask=answers("1"), ask_secret=answers("k"), models=lambda url, key: LISTED,
                     say=said.append) == 0  # fmt: skip
    menu = [line.split(". ", 1)[1] for line in said if re.match(r"  \d+\. ", line)]
    offered = ("cscs", "apertus", "anthropic", "openai", "gemini", "local", "ollama", "vllm")
    assert menu == [*(config.PRESETS[name].label for name in offered),
                    "Another OpenAI-compatible endpoint"]  # fmt: skip
    # Named, a preset out of the menu is set up like any other.
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    code = run_setup(name="mistral", model="mistral-small-latest", ask=answers(""),
                     ask_secret=answers("mk"), models=lambda url, key: [],
                     say=said.append)  # fmt: skip
    assert code == 0 and toml(home)["llm"] == {"endpoint": "mistral"}
    llm = load().settings.llm
    assert (llm.url, llm.models.writer) == ("https://api.mistral.ai/v1", "mistral-small-latest")


def test_a_preset_with_choices_offers_them_before_any_listed_model(home, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    listed = ["claude-haiku-5-5", "claude-opus-5-5", "claude-sonnet-5-5"]
    said: list[str] = []
    # Enter takes the first choice: Haiku, which judges itself.
    code = run_setup(name="anthropic", ask=answers(""), ask_secret=answers("ak"),
                     models=lambda url, key, headers: listed, say=said.append)  # fmt: skip
    assert code == 0
    menu = [line for line in said if re.match(r"  \d+\. ", line)]
    assert menu == [f"  {i}. {choice['label']}" for i, choice in
                    enumerate(config.PRESETS["anthropic"].choices, 1)] + [
                    "  3. Another model the endpoint lists"]  # fmt: skip
    assert toml(home)["endpoints"] == {"anthropic": {"models": {"writer": "claude-haiku-5-5"}}}
    llm = load().settings.llm
    assert (llm.models.writer, llm.judge_model) == ("claude-haiku-5-5", "claude-haiku-5-5")
    # The preset switches Haiku's thinking off: nothing of it in the user's file.
    assert llm.model_extra_body["claude-haiku-5-5"] == {"thinking": {"type": "disabled"}}
    # The last option lists the endpoint's models and takes any of them.
    code = run_setup(name="anthropic", force=True, ask=answers("3", "claude-opus-5-5"),
                     ask_secret=answers(""), models=lambda url, key, headers: listed,
                     say=said.append)  # fmt: skip
    assert code == 0 and "  - claude-opus-5-5" in said
    assert load().settings.llm.models.writer == "claude-opus-5-5"


def test_a_choice_saves_its_settings_and_another_model_drops_them(home, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    listed = ["gpt-4.1", "gpt-5.4-nano", "gpt-5.6-luna"]
    another = str(len(config.PRESETS["openai"].choices) + 1)
    assert run_setup(name="openai", ask=answers("1"), ask_secret=answers("ok"),
                     models=lambda url, key: listed, say=lambda line: None) == 0  # fmt: skip
    assert toml(home)["endpoints"]["openai"] == {
        "models": {"writer": "gpt-5.6-luna"},
        "thinking": "reasoning-effort",
        "thinking_stages": ["understand"],
    }
    llm = load().settings.llm
    assert (llm.thinking, llm.thinking_stages) == ("reasoning-effort", ["understand"])
    # Another model leaves no switch of the earlier choice behind.
    assert run_setup(name="openai", force=True, ask=answers(another, "gpt-4.1"),
                     ask_secret=answers(""), models=lambda url, key: listed,
                     say=lambda line: None) == 0  # fmt: skip
    assert toml(home)["endpoints"]["openai"] == {"models": {"writer": "gpt-4.1"}}
    # A choice's model given as a flag brings the choice's settings.
    assert run_setup(name="openai", model="gpt-5.4-nano", force=True, ask=never,
                     ask_secret=never, say=lambda line: None) == 0  # fmt: skip
    assert toml(home)["endpoints"]["openai"]["thinking_stages"] == ["understand"]


def test_gemini_flash_thinks_at_its_lowest_level_and_takes_no_temperature(
    home, monkeypatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert run_setup(name="gemini", ask=answers(""), ask_secret=answers("gk"),
                     models=lambda url, key: ["gemini-3.8-flash"],
                     say=lambda line: None) == 0  # fmt: skip
    assert toml(home)["endpoints"] == {"gemini": {"models": {"writer": "gemini-3.8-flash"}}}
    llm = load().settings.llm
    assert (llm.models.writer, llm.judge_model) == ("gemini-3.8-flash", "gemini-3.8-flash")
    # Gemini 3 cannot stop thinking: the preset asks for the lowest level, not for none.
    assert llm.model_extra_body["gemini-3.8-flash"] == {"reasoning_effort": "low"}
    assert (llm.thinking, llm.send_temperature) == ("off", False)


def test_another_endpoint_offers_its_own_model_list(home) -> None:
    said: list[str] = []
    code = run_setup(ask=answers(OTHER, "https://llm.example/v1", "", "model-b"),
                     ask_secret=answers("k"), models=lambda url, key: ["model-a", "model-b"],
                     say=said.append)  # fmt: skip
    assert code == 0 and "  - model-a" in said
    assert toml(home)["endpoints"] == {"llm": {
        "url": "https://llm.example/v1", "api_key_env": "LLM_API_KEY",
        "models": {"writer": "model-b"},
    }}  # fmt: skip
    llm = load().settings.llm
    assert (llm.models.writer, llm.judge_model, llm.thinking) == ("model-b", "model-b", "off")
    assert llm.api_key.get_secret_value() == "k"


def test_a_model_list_that_cannot_be_read_still_asks_for_the_model(home) -> None:
    def unreachable(url: str, key: str) -> list[str]:
        raise OSError("refused")

    said: list[str] = []
    code = run_setup(ask=answers(OTHER, "http://10.1.2.3:9/v1", "gpu", "", "my-model"),
                     ask_secret=answers("k"), models=unreachable, say=said.append)  # fmt: skip
    assert code == 0 and any("could not be read" in line for line in said)
    assert load().settings.llm.models.writer == "my-model"  # asked again after the empty answer
    assert "GPU_API_KEY=k" in (home.parent / ".env").read_text(encoding="utf-8")


def test_a_server_of_ones_own_takes_the_presets_key(home) -> None:
    code = run_setup(preset="local", model="apertus-q4", ask=never, ask_secret=never,
                     say=lambda line: None)  # fmt: skip
    assert code == 0 and not (home.parent / ".env").exists()
    llm = load().settings.llm
    assert (llm.url, llm.api_key.get_secret_value()) == ("http://127.0.0.1:8080/v1", "local")


def test_given_values_ask_nothing_and_update_only_with_force(home) -> None:
    given = {"base_url": "http://llm.test/v1", "api_key": "k", "model": "m", "name": "test"}
    assert run_setup(**given, ask=never, ask_secret=never, say=lambda line: None) == 0
    set_value(home, "endpoints.test.timeout_s", "1800", say=lambda line: None)
    first = home.read_text(encoding="utf-8")
    assert run_setup(**given, judge="j", ask=never, ask_secret=never, say=lambda line: None) == 1
    assert home.read_text(encoding="utf-8") == first
    assert run_setup(**given, judge="j", force=True, ask=never, say=lambda line: None) == 0
    llm = load().settings.llm
    assert (llm.models.judge, llm.timeout_s) == ("j", 1800)  # the hand-set key stays


def test_keys_with_spaces_quotes_and_dollars_read_back_unchanged(home) -> None:
    key = "a b#c'd\"e\\f$g"
    code = run_setup(preset="apertus", api_key=key, ask=never, say=lambda line: None)
    assert code == 0
    llm = load().settings.llm
    assert llm.api_key.get_secret_value() == key
    assert llm.extra_body == {"cache": {"no-cache": True}} and llm.thinking == "chat-template"


def test_saved_endpoints_are_listed_switched_and_removed(home) -> None:
    quiet = {"ask_secret": never, "say": lambda line: None}
    assert run_setup(preset="cscs", api_key="k", ask=never, **quiet) == 0
    # Interactive: a server of one's own asks for the model alone; keep cscs in use.
    assert run_setup(preset="local", ask=answers("apertus-q4", "n"), ask_secret=never,
                     models=lambda url, key: [], say=lambda line: None) == 0  # fmt: skip
    said: list[str] = []
    list_endpoints(say=said.append)
    rows = {line[2:].split()[0]: line for line in said if line[:1] in "* "}
    assert list(rows) == list(config.PRESETS)
    assert rows["cscs"].startswith("* cscs ") and rows["cscs"].endswith("  ready")
    assert rows["local"].startswith("  local ") and rows["local"].endswith("  ready")
    assert "  apertus-q4 " in rows["local"]
    assert rows["apertus"].endswith("  the variable PUBLICAI_API_KEY is not set")
    assert said[-1].startswith("In use: cscs (")
    assert use_endpoint("local", path=home, say=said.append) == 0
    assert load().settings.llm.endpoint == "local"
    assert use_endpoint("apertus", path=home, say=said.append) == 0  # a bare preset
    with pytest.raises(ConfigError, match="no such endpoint"):
        use_endpoint("nowhere", path=home, say=said.append)
    assert remove_endpoint("apertus", path=home, say=said.append) == 1
    assert said[-1].startswith("apertus is a preset that ships with the app")
    assert use_endpoint("local", path=home, say=said.append) == 0
    assert remove_endpoint("local", path=home, say=said.append) == 0
    assert said[-2].startswith("Removed the saved settings of the preset local")
    # cscs is ready (its key is in .env), but nothing picks it: nothing is guessed.
    assert said[-1] == "No endpoint is in use now: `leichtfacile endpoint use <name>`."
    assert "endpoints" not in toml(home)
    with pytest.raises(ConfigError, match="No model endpoint is in use"):
        load()


def test_config_set_checks_before_it_writes(home) -> None:
    said: list[str] = []
    set_value(home, "server.port", "8001", say=said.append)
    set_value(home, "endpoints.gpu.thinking_stages", '["understand"]', say=said.append)
    set_value(home, "endpoints.gpu.models.writer", "8", say=said.append)  # a name, not a number
    set_value(home, "llm.cache", "true", say=said.append)
    assert toml(home) == {"server": {"port": 8001}, "llm": {"cache": True}, "endpoints": {
        "gpu": {"thinking_stages": ["understand"], "models": {"writer": "8"}}}}  # fmt: skip
    before = home.read_text(encoding="utf-8")
    with pytest.raises(ConfigError, match="server.prot"):
        set_value(home, "server.prot", "1", say=said.append)
    with pytest.raises(ConfigError, match=r"llm.timeout_s .*\[llm\] takes endpoint and cache"):
        set_value(home, "llm.timeout_s", "60", say=said.append)
    with pytest.raises(ConfigError, match="publishes the app"):
        set_value(home, "server.host", "0.0.0.0", say=said.append)
    assert home.read_text(encoding="utf-8") == before
    assert unset_value(home, "server.port", say=said.append) == 0
    assert unset_value(home, "server.port", say=said.append) == 1


def test_a_project_file_wins_and_setting_the_user_file_says_so(home) -> None:
    Path("leichtfacile.toml").write_text("[server]\nport = 9000\n", encoding="utf-8")
    said: list[str] = []
    set_value(home, "server.port", "8001", say=said.append)
    assert said[-1] == f"Note: ./leichtfacile.toml sets it too and wins over {home}."


def test_config_show_names_sources_and_hides_keys(home, monkeypatch) -> None:
    run_setup(preset="cscs", api_key="secret-key-1234", ask=never, say=lambda line: None)
    monkeypatch.setenv("LEICHTFACILE_SERVER__PORT", "8001")
    said: list[str] = []
    show(say=said.append)
    rows = {line.split()[0]: line for line in said if line[:1].isalpha() and "  " in line}
    assert rows["llm.url"].endswith("preset cscs")
    assert rows["llm.endpoint"].endswith("config file")
    assert rows["server.port"].endswith("LEICHTFACILE_SERVER__PORT")
    assert rows["pipeline.repair_rounds"].endswith("default")
    assert "****1234" in rows["llm.api_key"] and "secret" not in "\n".join(said)


def test_edit_opens_the_editor_until_the_file_is_valid(home, monkeypatch) -> None:
    monkeypatch.setenv("EDITOR", "my-editor --wait")
    texts = iter(["[server]\nprot = 1\n", "[server]\nport = 8001\n"])
    opened: list[list[str]] = []

    def run(command: list[str]) -> None:
        opened.append(command)
        Path(command[-1]).write_text(next(texts), encoding="utf-8")

    said: list[str] = []
    assert edit(home, run=run, ask=answers("y"), say=said.append) == 0
    assert opened[0] == ["my-editor", "--wait", str(home)] and len(opened) == 2
    assert any("server.prot" in line for line in said) and said[-1] == f"{home}: valid."


def test_the_command_line(home, tmp_path, capsys) -> None:
    argv = ["setup", "--base-url", "http://llm.test/v1", "--api-key", "k", "--model", "m",
            "--name", "test", "--no-models"]  # fmt: skip
    assert main(argv) == 0
    assert load().settings.llm.models.writer == "m"
    other = tmp_path / "other.toml"
    assert main(["--config", str(other), "config", "set", "server.port", "8123"]) == 0
    assert toml(other) == {"server": {"port": 8123}}
    capsys.readouterr()
    assert main(["config", "show", "--defaults"]) == 0
    out = capsys.readouterr().out
    assert "\n[server]\n" in out and "\n# port = 8000\n" in out
    assert main(["config", "set", "server.port", "x"]) == 2
    assert "server.port" in capsys.readouterr().err


def test_missing_settings_name_themselves_and_the_setup(home, capsys) -> None:
    get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit) as stop:
            settings_or_exit()
    finally:
        get_settings.cache_clear()
    assert stop.value.code == 2
    error = capsys.readouterr().err
    assert "No model endpoint is in use" in error and "leichtfacile setup" in error
    assert str(home) in error


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
