"""`leichtfacile setup`, `preset` and `config` (configure.py) and the start of the
command line: the questions, the providers and presets, what is written where, the
checks before a change is written, and when the browser opens."""

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
    ANOTHER_MODEL,
    ANOTHER_SERVER,
    edit,
    list_presets,
    remove_preset,
    run_setup,
    save_preset,
    set_value,
    show,
    unset_value,
    use_preset,
)

LISTED = ["swiss-ai/Apertus-v1.5-70B", "swiss-ai/Apertus-v1.5-8B"]
# the menu's "Another OpenAI-compatible server", after the providers
OTHER = str(len(config.PROVIDERS) + 1)
ANTHROPIC = str(list(config.PROVIDERS).index("anthropic") + 1)


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


def menus(said: list[str]) -> list[list[str]]:
    """The numbered lists setup printed, one per question."""
    found: list[list[str]] = []
    for line in said:
        if re.match(r"  1\. ", line):
            found.append([])
        if re.match(r"  \d+\. ", line):
            found[-1].append(line.split(". ", 1)[1])
    return found


def test_a_shipped_preset_needs_only_the_key(home) -> None:
    said: list[str] = []
    # provider 1 (CSCS) in the menu, the key, then its one preset: no address, name,
    # model or judge question
    code = run_setup(ask=answers("1", "1"), ask_secret=answers("secret-key"),
                     models=lambda url, key, headers: LISTED, say=said.append)  # fmt: skip
    assert code == 0
    assert toml(home) == {"llm": {"preset": "cscs-apertus"}}  # the preset as it is: no table
    assert (home.parent / ".env").read_text(encoding="utf-8").endswith("CSCS_API_KEY=secret-key\n")
    providers, presets = menus(said)
    assert providers == [str(t["label"]) for t in config.PROVIDERS.values()] + [ANOTHER_SERVER]
    assert presets == ["Apertus 8B, checked by Apertus 70B", ANOTHER_MODEL]
    llm = load().settings.llm
    assert llm.url == "https://api.inference.cscs.ch/v1" and llm.thinking == "model-suffix"
    assert [llm.models.writer, llm.models.judge] == LISTED[::-1]
    assert llm.api_key.get_secret_value() == "secret-key"
    assert "secret-key" not in "\n".join(said) and "secret-key" not in home.read_text("utf-8")
    assert "CSCS inference API, Lugano lists 2 models." in said  # the key was tried


def test_a_preset_whose_key_is_set_asks_nothing(home, monkeypatch) -> None:
    monkeypatch.setenv("CSCS_API_KEY", "from-shell")
    said: list[str] = []
    assert run_setup(preset="cscs-apertus", ask=never, ask_secret=never, say=said.append) == 0
    assert toml(home) == {"llm": {"preset": "cscs-apertus"}} and not (home.parent / ".env").exists()
    assert "Its key comes from the variable CSCS_API_KEY." in said
    # A model of the provider becomes a preset of the user's own, named after both.
    code = run_setup(provider="cscs", model="swiss-ai/Apertus-v1.5-70B", ask=never,
                     ask_secret=never, say=said.append)  # fmt: skip
    assert code == 0
    assert toml(home) == {
        "presets": {"cscs-swiss-ai-apertus-v1-5-70b": {
            "provider": "cscs", "models": {"writer": "swiss-ai/Apertus-v1.5-70B"},
        }},
        "llm": {"preset": "cscs-swiss-ai-apertus-v1-5-70b"},
    }  # fmt: skip
    llm = load().settings.llm
    assert llm.url == "https://api.inference.cscs.ch/v1"
    assert llm.judge_model == "swiss-ai/Apertus-v1.5-70B"  # the writer judges by default


def test_a_providers_presets_are_offered_then_any_listed_model(home, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    listed = ["claude-haiku-5-5", "claude-opus-5-5", "claude-sonnet-5-5"]
    said: list[str] = []
    # Anthropic, the key, Enter: the first preset (Haiku, which judges itself).
    code = run_setup(ask=answers(ANTHROPIC, ""), ask_secret=answers("ak"),
                     models=lambda url, key, headers: listed, say=said.append)  # fmt: skip
    assert code == 0
    assert menus(said)[1] == [
        "Claude Haiku 5.5", "Claude Haiku 5.5, checked by Sonnet 5.5", "Claude Sonnet 5.5",
        ANOTHER_MODEL,
    ]  # fmt: skip
    assert toml(home) == {"llm": {"preset": "claude-haiku-5-5"}}
    llm = load().settings.llm
    assert (llm.models.writer, llm.judge_model) == ("claude-haiku-5-5", "claude-haiku-5-5")
    assert llm.for_model("claude-haiku-5-5").extra_body == {"thinking": {"type": "disabled"}}
    # The last option lists the provider's models and takes any of them, as a preset of
    # the user's own.
    code = run_setup(provider="anthropic", ask=answers("4", "claude-opus-5-5", ""),
                     ask_secret=answers(""), models=lambda url, key, headers: listed,
                     say=said.append)  # fmt: skip
    assert code == 0 and "  - claude-opus-5-5" in said
    assert toml(home)["presets"] == {"anthropic-claude-opus-5-5": {
        "provider": "anthropic", "models": {"writer": "claude-opus-5-5"},
    }}  # fmt: skip
    assert load().settings.llm.models.writer == "claude-opus-5-5"


def test_a_server_of_ones_own_becomes_a_provider_and_a_preset(home) -> None:
    said: list[str] = []
    listed = ["model-a", "model-b"]
    code = run_setup(ask=answers(OTHER, "https://llm.example/v1", "", "model-b"),
                     ask_secret=answers("k"), models=lambda url, key, headers: listed,
                     say=said.append)  # fmt: skip
    assert code == 0 and "  - model-a" in said
    assert toml(home) == {
        "providers": {"llm": {"url": "https://llm.example/v1", "api_key_env": "LLM_API_KEY"}},
        "presets": {"llm": {"provider": "llm", "models": {"writer": "model-b"}}},
        "llm": {"preset": "llm"},
    }
    llm = load().settings.llm
    assert (llm.models.writer, llm.judge_model, llm.thinking) == ("model-b", "model-b", "off")
    assert llm.api_key.get_secret_value() == "k" and llm.location == "world"


def test_a_model_list_that_cannot_be_read_still_asks_for_the_model(home) -> None:
    def unreachable(url: str, key: str, headers=None) -> list[str]:
        raise OSError("refused")

    said: list[str] = []
    code = run_setup(ask=answers(OTHER, "http://10.1.2.3:9/v1", "gpu", "", "my-model"),
                     ask_secret=answers("k"), models=unreachable, say=said.append)  # fmt: skip
    assert code == 0 and any("could not be read" in line for line in said)
    assert load().settings.llm.models.writer == "my-model"  # asked again after the empty answer
    assert "GPU_API_KEY=k" in (home.parent / ".env").read_text(encoding="utf-8")
    assert load().settings.llm.preset == "gpu"


def test_a_local_server_takes_the_providers_key_and_lists_its_models(home) -> None:
    said: list[str] = []
    # Interactive: no key question, the server's models, Enter takes the only one.
    code = run_setup(provider="local", ask=answers(""), ask_secret=never,
                     models=lambda url, key, headers: ["apertus-q4"], say=said.append)  # fmt: skip
    assert code == 0 and not (home.parent / ".env").exists()
    assert toml(home)["presets"] == {"local-apertus-q4": {
        "provider": "local", "models": {"writer": "apertus-q4"},
    }}  # fmt: skip
    llm = load().settings.llm
    assert (llm.url, llm.api_key.get_secret_value()) == ("http://127.0.0.1:8080/v1", "local")
    assert (llm.thinking, llm.timeout_s) == ("chat-template", 1800)


def test_given_values_ask_nothing_and_update_only_with_force(home) -> None:
    given = {"base_url": "http://llm.test/v1", "api_key": "k", "model": "m", "name": "test"}
    assert run_setup(**given, ask=never, ask_secret=never, say=lambda line: None) == 0
    set_value(home, "presets.test.timeout_s", "1800", say=lambda line: None)
    first = home.read_text(encoding="utf-8")
    assert run_setup(**given, judge="j", ask=never, ask_secret=never, say=lambda line: None) == 1
    assert home.read_text(encoding="utf-8") == first
    assert run_setup(**given, judge="j", force=True, ask=never, say=lambda line: None) == 0
    llm = load().settings.llm
    assert (llm.models.judge, llm.timeout_s) == ("j", 1800)  # the hand-set key stays


def test_keys_with_spaces_quotes_and_dollars_read_back_unchanged(home) -> None:
    key = "a b#c'd\"e\\f$g"
    code = run_setup(preset="publicai-apertus", api_key=key, ask=never, say=lambda line: None)
    assert code == 0
    llm = load().settings.llm
    assert llm.api_key.get_secret_value() == key
    assert llm.extra_body == {"cache": {"no-cache": True}} and llm.thinking == "chat-template"


def test_presets_are_listed_switched_and_removed(home) -> None:
    quiet = {"ask_secret": never, "say": lambda line: None}
    assert run_setup(preset="cscs-apertus", api_key="k", ask=never, **quiet) == 0
    # A server of one's own, in the file; keep cscs-apertus in use.
    assert run_setup(provider="local", ask=answers("apertus-q4", "n"), ask_secret=never,
                     models=lambda url, key, headers: [], say=lambda line: None) == 0  # fmt: skip
    said: list[str] = []
    list_presets(say=said.append)
    rows = {line[2:].split()[0]: line for line in said if line[:1] in "* "}
    assert list(rows) == [*config.PRESETS, "local-apertus-q4"]
    assert rows["cscs-apertus"].startswith("* cscs-apertus ") and rows["cscs-apertus"].endswith(
        "  ready"
    )
    assert (
        rows["local-apertus-q4"].endswith("  ready") and "  apertus-q4 " in rows["local-apertus-q4"]
    )
    assert rows["publicai-apertus"].endswith("  the variable PUBLICAI_API_KEY is not set")
    assert said[-1].startswith("In use: cscs-apertus (")
    assert use_preset("local-apertus-q4", path=home, say=said.append) == 0
    assert load().settings.llm.preset == "local-apertus-q4"
    with pytest.raises(ConfigError, match="no such preset"):
        use_preset("nowhere", path=home, say=said.append)
    assert remove_preset("publicai-apertus", path=home, say=said.append) == 1
    assert said[-1].startswith("publicai-apertus is a preset that ships with the app")
    assert remove_preset("local-apertus-q4", path=home, say=said.append) == 0
    assert said[-2].startswith("Removed the preset local-apertus-q4")
    assert said[-1] == "In use now: cscs-apertus."  # the shipped default, which is ready
    assert "presets" not in toml(home) and "preset" not in toml(home).get("llm", {})


def test_save_preset_writes_a_table_of_ones_own(home) -> None:
    said: list[str] = []
    table = {"provider": "ollama", "label": "Mine", "models": {"writer": "qwen3.5:9b"},
             "thinking_stages": ["understand"], "timeout_s": 600.0}  # fmt: skip
    save_preset(home, "mine", table, say=said.append)
    assert toml(home) == {"presets": {"mine": table}, "llm": {"preset": "mine"}}
    llm = load().settings.llm
    assert (llm.title, llm.url, llm.timeout_s) == ("Mine", "http://127.0.0.1:11434/v1", 600)
    assert llm.for_model("qwen3.5:9b").thinking_stages == ["understand"]  # over the qwen3* table
    with pytest.raises(ConfigError, match="use lowercase"):
        save_preset(home, "Mine", table)


def test_config_set_checks_before_it_writes(home) -> None:
    said: list[str] = []
    set_value(home, "server.port", "8001", say=said.append)
    set_value(home, "presets.gpu.thinking_stages", '["understand"]', say=said.append)
    set_value(home, "presets.gpu.models.writer", "8", say=said.append)  # a name, not a number
    set_value(home, "llm.cache", "true", say=said.append)
    assert toml(home) == {"server": {"port": 8001}, "llm": {"cache": True}, "presets": {
        "gpu": {"thinking_stages": ["understand"], "models": {"writer": "8"}}}}  # fmt: skip
    before = home.read_text(encoding="utf-8")
    with pytest.raises(ConfigError, match="server.prot"):
        set_value(home, "server.prot", "1", say=said.append)
    with pytest.raises(ConfigError, match=r"llm.timeout_s .*\[llm\] takes preset, cache and offer"):
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
    run_setup(preset="cscs-apertus", api_key="secret-key-1234", ask=never, say=lambda line: None)
    monkeypatch.setenv("LEICHTFACILE_SERVER__PORT", "8001")
    said: list[str] = []
    show(say=said.append)
    rows = {line.split()[0]: line for line in said if line[:1].isalpha() and "  " in line}
    assert rows["llm.url"].endswith("provider cscs")
    assert rows["llm.models.writer"].endswith("preset cscs-apertus")
    assert rows["llm.preset"].endswith("config file")
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
    argv = ["setup", "test", "--base-url", "http://llm.test/v1", "--api-key", "k", "--model", "m",
            "--no-models"]  # fmt: skip
    assert main(argv) == 0
    assert load().settings.llm.models.writer == "m" and load().settings.llm.preset == "test"
    assert main(["preset", "use", "cscs-apertus"]) == 0
    assert load(strict=False).settings.llm.preset == "cscs-apertus"
    other = tmp_path / "other.toml"
    assert main(["--config", str(other), "config", "set", "server.port", "8123"]) == 0
    assert toml(other) == {"server": {"port": 8123}}
    capsys.readouterr()
    assert main(["config", "show", "--defaults"]) == 0
    out = capsys.readouterr().out
    assert "\n[server]\n" in out and "\n# port = 8000\n" in out
    assert "\n# [providers.<name>]\n" in out and "\n# [presets.<name>]\n" in out
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
    assert "The preset cscs-apertus is not ready" in error and "leichtfacile setup" in error
    assert str(home.parent / ".env") in error
    assert settings_or_exit(strict=False).llm.preset == "cscs-apertus"  # `serve` starts anyway


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
