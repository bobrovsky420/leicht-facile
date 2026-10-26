"""The settings (config.py): the TOML files, the variables and the command line in that
order, the shipped providers and presets, the user's own tables over them, the request
settings of each model, the keys from .env, and messages that name the setting and its
source."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from leichtfacile import config
from leichtfacile.config import (
    LETTERS_DIR,
    ConfigError,
    Settings,
    config_file,
    default_data_dir,
    get_settings,
    load,
    paths,
    reference_markdown,
    use_overrides,
)

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_NAMES = [
    "cscs", "publicai", "anthropic", "openai", "gemini", "openrouter", "local", "ollama",
    "vllm", "mistral", "groq", "huggingface",
]  # fmt: skip
CSCS_URL = "https://api.inference.cscs.ch/v1"


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """The user's config file in home/, the current folder work/ (leichtfacile.toml and
    .env read from there, as outside the tests). Returns the config file's path."""
    (tmp_path / "home").mkdir()
    (tmp_path / "work").mkdir()
    monkeypatch.setenv("LEICHTFACILE_CONFIG", str(tmp_path / "home" / "config.toml"))
    monkeypatch.setattr(config, "PROJECT_FILE", Path("leichtfacile.toml"))
    monkeypatch.setattr(config, "LOCAL_ENV_FILE", Path(".env"))
    monkeypatch.delenv("CSCS_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path / "work")
    return tmp_path / "home" / "config.toml"


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# A server of one's own: a provider and a preset on it.
LOCAL = """
[llm]
preset = "laptop"

[providers.laptop]
url = "http://127.0.0.1:8080/v1"
api_key = "local"
thinking = "chat-template"

[presets.laptop]
provider = "laptop"
models = { writer = "apertus-q4" }
"""


def test_each_source_overrides_the_one_before(home, monkeypatch) -> None:
    write(home, LOCAL + '\n[server]\nport = 8001\nui_lang = "de"\n\n[jobs]\nworkers = 2\n')
    write(Path("leichtfacile.toml"), '[server]\nui_lang = "fr"\nopen_browser = false\n')
    monkeypatch.setenv("LEICHTFACILE_JOBS__WORKERS", "3")
    use_overrides({"server.port": 9000})
    loaded = load()
    s = loaded.settings
    assert (s.server.port, s.server.ui_lang, s.server.open_browser, s.jobs.workers) == (
        9000, "fr", False, 3,
    )  # fmt: skip
    sources = {key: loaded.flat[key].source for key in ("server.port", "server.ui_lang",
               "jobs.workers", "llm.url", "llm.models.writer")}  # fmt: skip
    assert sources == {
        "server.port": "command line",
        "server.ui_lang": "leichtfacile.toml",
        "jobs.workers": "LEICHTFACILE_JOBS__WORKERS",
        "llm.url": str(home),
        "llm.models.writer": str(home),
    }
    assert s.pipeline.repair_rounds == 3 and "pipeline.repair_rounds" not in loaded.flat
    assert (s.llm.preset, s.llm.provider, s.llm.thinking) == ("laptop", "laptop", "chat-template")


def test_a_shipped_preset_fills_the_llm_and_the_key_comes_from_env_files(home, monkeypatch):
    write(home, '[llm]\npreset = "cscs-apertus"\n')
    write(home.parent / ".env", "CSCS_API_KEY=from-config-folder\n")
    loaded = load()
    llm = loaded.settings.llm
    assert (llm.preset, llm.provider, llm.url, llm.thinking) == (
        "cscs-apertus", "cscs", CSCS_URL, "model-suffix",
    )  # fmt: skip
    assert (llm.models.writer, llm.models.judge) == (
        "swiss-ai/Apertus-v1.5-8B", "swiss-ai/Apertus-v1.5-70B",
    )  # fmt: skip
    assert (llm.title, llm.provider_label, llm.location, llm.documents) == (
        "Apertus 8B, checked by Apertus 70B", "CSCS inference API, Lugano", "ch", "any",
    )  # fmt: skip
    assert loaded.flat["llm.url"].source == "provider cscs"
    assert loaded.flat["llm.models.writer"].source == "preset cscs-apertus"
    assert llm.api_key.get_secret_value() == "from-config-folder"
    write(Path(".env"), "CSCS_API_KEY='a$b c'\n")  # the current folder's wins, taken literally
    loaded = load()
    assert loaded.settings.llm.api_key.get_secret_value() == "a$b c"
    assert loaded.flat["llm.api_key"].source == "CSCS_API_KEY from .env"
    monkeypatch.setenv("CSCS_API_KEY", "from-shell")  # the environment wins over both
    assert load().settings.llm.api_key.get_secret_value() == "from-shell"


def test_the_shipped_catalog_is_complete_and_in_order() -> None:
    assert list(config.PROVIDERS) == PROVIDER_NAMES
    assert config.DEFAULT_PRESET == "cscs-apertus" and list(config.PRESETS)[0] == "cscs-apertus"
    for table in config.PROVIDERS.values():
        provider = config.Provider.model_validate(table)  # no unknown key, no wrong value
        assert provider.label and provider.url
        # A server of one's own names its own models (discover); every other provider
        # takes a key from a variable, and says where the text goes.
        assert provider.discover == (provider.location == "local")
        assert bool(provider.api_key_env) != provider.discover
    for table in config.PRESETS.values():
        preset = config.Preset.model_validate(table)
        assert preset.provider in config.PROVIDERS and preset.label and preset.models.writer
        assert preset.models.writer != preset.models.judge  # the judge is the writer by default
    # Every shipped preset resolves and prices its models, but for CSCS, which charged
    # nothing for the reported runs (the evaluation prices Apertus at Public AI's list).
    for item in config.available(config.collect()):
        assert item.provider and item.writer
        assert (item.cost_per_page is None) == (item.provider == "cscs")
    assert config.model_price("swiss-ai/Apertus-v1.5-8B-thinking") == (0.10, 0.20)


def test_the_catalog_file_is_checked_when_read(tmp_path) -> None:
    good = ('default = "a"\n\n[providers.p]\nlabel = "P"\nurl = "https://p.example/v1"\n\n'
            '[providers.p.models."m*"]\nthinking = "off"\n\n'
            '[presets.a]\nprovider = "p"\nlabel = "A"\nmodels = { writer = "m1" }\n')  # fmt: skip
    path = write(tmp_path / "presets.toml", good)
    catalog = config.read_catalog(path)
    assert list(catalog.presets) == ["a"] and catalog.default == "a"
    assert catalog.providers["p"]["models"] == {"m*": {"thinking": "off"}}
    cases = (
        (good.replace('url = "https://p.example/v1"\n', ""), r"\[providers\.p\] needs a label"),
        (good.replace('provider = "p"', 'provider = "q"'), r"\[presets\.a\] names no known"),
        (good.replace('models = { writer = "m1" }', ""), r"\[presets\.a\] needs a label and"),
        (good.replace('default = "a"', 'default = "b"'), "default names no preset"),
        (good.replace("[providers.p]", "[providers.P]"), "lowercase letters"),
        (good.replace('thinking = "off"', 'thinking = "maybe"'), r"\[providers\.p\]: Input"),
        (good + "[presets.a]\nurl = 'x'\n", "Cannot declare"),
    )
    for text, message in cases:
        with pytest.raises(ConfigError, match=message):
            config.read_catalog(write(path, text))


def test_a_models_table_and_the_preset_set_what_a_model_takes(home, monkeypatch) -> None:
    """Provider, then the tables whose pattern or name matches, then the preset."""
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    llm = load(preset="gpt-5-6-luna").settings.llm
    luna = llm.for_model("gpt-5.6-luna")  # the gpt-5* table and its own, over the provider
    assert (luna.thinking, luna.thinking_stages) == ("reasoning-effort", ["understand"])
    assert (luna.max_tokens_key, luna.send_temperature) == ("max_completion_tokens", False)
    assert llm.price("gpt-5.6-luna") == (0.20, 1.20) and llm.price("gpt-5.7-sol") is None
    old = llm.for_model("gpt-4.1")  # the gpt-4* table takes the old fields back
    assert (old.max_tokens_key, old.send_temperature, old.thinking) == ("max_tokens", True, "off")
    assert llm.model_table("other") == {} and llm.for_model("other").send_temperature is False
    # A preset's request settings win over the tables of every model it calls.
    write(home, '[presets.nano-quiet]\nprovider = "openai"\n'
                'models = { writer = "gpt-5.4-nano" }\nthinking_stages = []\n')  # fmt: skip
    quiet = load(preset="nano-quiet").settings.llm
    nano = quiet.for_model("gpt-5.4-nano")
    assert (nano.thinking, nano.thinking_stages, nano.input_usd) == ("reasoning-effort", [], 0.2)
    assert quiet.title == "nano-quiet"  # no label: the name
    # Anthropic: each model's table carries its own thinking switch.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    mixed = load(preset="claude-haiku-5-5-sonnet").settings.llm
    assert mixed.for_model("claude-haiku-5-5").extra_body == {"thinking": {"type": "disabled"}}
    assert mixed.for_model(mixed.judge_model).extra_body == {"thinking": {"type": "between_tools"}}
    assert mixed.for_model("claude-opus-5-5").extra_body == {}


def test_a_users_table_extends_a_shipped_preset_or_provider(home, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    write(home, '[llm]\npreset = "claude-haiku-5-5"\n\n'
                '[providers.anthropic]\ntimeout_s = 600\n\n'
                '[providers.anthropic.models.claude-haiku-5-5]\n'
                'extra_body = { thinking = { type = "enabled" } }\n\n'
                '[presets.claude-haiku-5-5]\nlabel = "Haiku, thinking"\n'
                'thinking_stages = ["write"]\n')  # fmt: skip
    loaded = load()
    llm = loaded.settings.llm
    assert (llm.title, llm.timeout_s, llm.url) == (
        "Haiku, thinking",
        600,
        "https://api.anthropic.com/v1",
    )
    haiku = llm.for_model("claude-haiku-5-5")
    # The user's table replaces the shipped table of the same model; the shipped Sonnet
    # table stays; the preset's thinking_stages reach every model.
    assert haiku.extra_body == {"thinking": {"type": "enabled"}} and haiku.input_usd is None
    assert llm.for_model("claude-sonnet-5-5").extra_body == {"thinking": {"type": "between_tools"}}
    assert llm.for_model("claude-sonnet-5-5").thinking_stages == ["write"]
    assert loaded.flat["llm.timeout_s"].source == str(home)
    assert loaded.flat["llm.headers"].source == "provider anthropic"


def test_a_preset_of_ones_own_names_a_known_provider(home) -> None:
    write(home, '[presets.mine]\nmodels = { writer = "m" }\n')
    with pytest.raises(ConfigError, match=r"preset mine: names no provider"):
        load(preset="mine")
    write(home, '[presets.mine]\nprovider = "nowhere"\nmodels = { writer = "m" }\n')
    with pytest.raises(ConfigError, match=r"presets.mine.provider = 'nowhere' \(.*\): no such"):
        load(preset="mine")
    write(home, '[presets.mine]\nprovider = "cscs"\nurl = "x"\n')  # the address is the provider's
    with pytest.raises(ConfigError, match=r"presets.mine.url \(.*\): Extra inputs"):
        load(strict=False)


def test_a_model_is_listed_with_or_without_its_provider_suffix() -> None:
    models = ["Qwen/Qwen3.5-9B", "qwen3.5:9b", "swiss-ai/Apertus-v1.5-70B"]
    assert config.listed("Qwen/Qwen3.5-9B", models)
    assert config.listed("Qwen/Qwen3.5-9B:ovhcloud", models)  # the Hugging Face router
    assert config.listed("qwen3.5:9b", models)  # an Ollama tag, listed as it is
    assert not config.listed("qwen3.5:4b", models) and not config.listed("other", models)
    llm = config.LLM(models=config.Models(writer="swiss-ai/Apertus-v1.5-8B:publicai"))
    assert llm.judge_for(models) == "swiss-ai/Apertus-v1.5-70B:publicai"


def test_the_cost_per_page_and_a_price_by_name_alone(home, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    haiku = load(preset="claude-haiku-5-5").settings.llm
    # 30k tokens in at 0.10 and 8k out at 0.50 per million, the judge the writer: 0.007
    assert config.cost_per_page(haiku) == 0.007
    mixed = load(preset="claude-haiku-5-5-sonnet").settings.llm
    assert config.cost_per_page(mixed) == pytest.approx(0.6 * 0.007 + 0.4 * 0.14)
    assert config.cost_per_page(config.LLM(models=config.Models(writer="x"))) is None
    # The evaluation prices a model by its name alone, from the shipped tables.
    assert config.model_price("openai/gpt-oss-20b:groq") == (0.10, 0.50)
    assert config.model_price("gpt-5.4-nano") == (0.20, 1.25)
    assert config.model_price("apertus-v1.5-8b-q4-llamacpp") is None


def test_dot_env_holds_keys_and_nothing_else(home) -> None:
    write(home, LOCAL)
    write(Path(".env"), "LEICHTFACILE_SERVER__PORT=9999\n")
    assert load().settings.server.port == 8000


def test_llm_takes_the_choice_and_the_switches_and_nothing_else(home, monkeypatch) -> None:
    write(home, '[llm]\npreset = "cscs-apertus"\ncache = true\noffer = ["cscs-apertus"]\n\n'
                '[providers.cscs]\napi_key = "k"\ntimeout_s = 600\n')  # fmt: skip
    llm = load().settings.llm
    assert (llm.preset, llm.timeout_s, llm.cache, llm.offer) == ("cscs-apertus", 600, True,
                                                                  ["cscs-apertus"])  # fmt: skip
    # A provider's or a preset's key in [llm] has one place to go: its table.
    write(home, '[llm]\ntimeout_s = 1800\n\n[providers.cscs]\napi_key = "k"\n')
    with pytest.raises(ConfigError, match=r"llm.timeout_s \(.*config.toml\): \[llm\] takes"):
        load()
    write(home, '[providers.cscs]\napi_key = "k"\n')
    monkeypatch.setenv("LEICHTFACILE_LLM__MODELS__WRITER", "other")
    with pytest.raises(ConfigError, match="LEICHTFACILE_PRESETS__<NAME>__<KEY>"):
        load()


def test_the_preset_in_use(home, monkeypatch) -> None:
    monkeypatch.setenv("CSCS_API_KEY", "k")
    lenient = load(strict=False)  # nothing named: the shipped default
    assert lenient.settings.llm.preset == "cscs-apertus"
    assert lenient.flat["llm.preset"].source == "the shipped default"
    write(home, LOCAL)
    assert load().settings.llm.preset == "laptop"
    use_overrides({"llm.preset": "cscs-apertus"})  # --preset
    assert load().settings.llm.url == CSCS_URL
    use_overrides({"llm.preset": "gone"})
    with pytest.raises(ConfigError, match="no such preset; known: cscs-apertus, .*, laptop"):
        load()
    use_overrides({})
    monkeypatch.setenv("LEICHTFACILE_LLM__PRESET", "cscs-apertus")  # a variable names one too
    assert load().settings.llm.url == CSCS_URL
    monkeypatch.delenv("LEICHTFACILE_LLM__PRESET")
    assert load(preset="cscs-apertus").settings.llm.url == CSCS_URL  # a draft's choice
    with pytest.raises(ConfigError, match="no such preset"):
        load(preset="nope")


def test_available_lists_every_preset_with_what_it_lacks(home, monkeypatch) -> None:
    write(home, LOCAL)
    found = {item.name: item for item in config.available()}
    assert list(found) == [*config.PRESETS, "laptop"]
    cscs = found["cscs-apertus"]
    assert cscs.missing == ("the variable CSCS_API_KEY is not set",) and not cscs.has_key
    assert (cscs.label, cscs.provider_label, cscs.key_variable) == (
        "Apertus 8B, checked by Apertus 70B", "CSCS inference API, Lugano", "CSCS_API_KEY",
    )  # fmt: skip
    assert (cscs.location, cscs.documents, cscs.judge) == ("ch", "any", "swiss-ai/Apertus-v1.5-70B")
    assert cscs.cost_per_page is None  # the 8B is not priced on CSCS
    assert found["laptop"].ready and found["laptop"].label == "laptop"
    assert (found["laptop"].writer, found["laptop"].judge) == ("apertus-q4", None)
    assert found["laptop"].has_key and found["laptop"].key_variable is None
    monkeypatch.setenv("CSCS_API_KEY", "k")
    cscs = next(item for item in config.available() if item.name == "cscs-apertus")
    assert cscs.ready and cscs.has_key
    # An organisation's choice: llm.offer lists what the interface offers.
    offer = 'preset = "laptop"\noffer = ["laptop", "cscs-apertus"]'
    write(home, LOCAL.replace('preset = "laptop"', offer))
    assert [item.name for item in config.available()] == ["cscs-apertus", "laptop"]
    write(home, LOCAL.replace('preset = "laptop"', 'preset = "laptop"\noffer = ["nope"]'))
    with pytest.raises(ConfigError, match=r"llm.offer \(.*\): no such preset nope"):
        config.available()


def test_the_later_source_decides_between_a_key_and_its_variable(home, monkeypatch) -> None:
    write(home, '[providers.mine]\nurl = "http://m/v1"\napi_key_env = "MINE_KEY"\n\n'
                '[presets.mine]\nprovider = "mine"\nmodels = { writer = "m" }\n')  # fmt: skip
    monkeypatch.setenv("MINE_KEY", "named")
    assert load(preset="mine").settings.llm.api_key.get_secret_value() == "named"
    monkeypatch.setenv("LEICHTFACILE_PROVIDERS__MINE__API_KEY", "given")
    assert load(preset="mine").settings.llm.api_key.get_secret_value() == "given"
    write(home, '[providers.mine]\nurl = "http://m/v1"\napi_key = "a"\napi_key_env = "B"\n')
    with pytest.raises(ConfigError, match="keep one"):
        load(preset="mine")


def test_a_preset_without_its_key_says_what_and_where(home) -> None:
    with pytest.raises(ConfigError, match="The preset cscs-apertus is not ready") as unset:
        load()
    message = str(unset.value)
    assert "CSCS_API_KEY (llm.api_key_env, provider cscs) is not set" in message
    assert "leichtfacile setup cscs-apertus" in message and str(home.parent / ".env") in message
    lenient = load(strict=False)  # `config show`, the web app and checks of a change
    assert lenient.problems and lenient.settings.llm.url == CSCS_URL


def test_typos_and_wrong_values_name_their_source(home, monkeypatch) -> None:
    write(home, LOCAL + "\n[server]\nprot = 8001\n")
    with pytest.raises(ConfigError, match=r"server.prot \(.*config.toml\): Extra inputs"):
        load()
    write(home, LOCAL)
    monkeypatch.setenv("LEICHTFACILE_SERVER__PORT", "eighty")
    with pytest.raises(ConfigError, match=r"server.port \(LEICHTFACILE_SERVER__PORT\)"):
        load()
    write(home, "[server\nport = 1\n")
    with pytest.raises(ConfigError, match="config.toml"):
        load()
    write(home, '[presets.My_Server]\nprovider = "cscs"\n')
    with pytest.raises(ConfigError, match="lowercase"):
        load()
    write(home, LOCAL.replace('thinking = "chat-template"', 'thinking = "maybe"'))
    with pytest.raises(ConfigError, match=r"llm.thinking \(.*config.toml\): Input should be"):
        load()


def test_variables_carry_values_and_comma_lists_but_no_tables(home, monkeypatch) -> None:
    write(home, LOCAL)
    monkeypatch.setenv("LEICHTFACILE_PRESETS__LAPTOP__THINKING_STAGES", "understand, write")
    monkeypatch.setenv("LEICHTFACILE_LLM__CACHE", "1")
    monkeypatch.setenv("LEICHTFACILE_LLM__OFFER", "laptop")
    monkeypatch.setenv("LEICHTFACILE_AUTH__PROXY_FROM", "127.0.0.1, 10.0.0.0/8")
    monkeypatch.setenv("LEICHTFACILE_AUTH__PROXY_HEADER", "X-Forwarded-User")
    monkeypatch.setenv("LEICHTFACILE_LOG__LEVEL", "")  # empty: not set
    s = load().settings
    assert s.llm.thinking_stages == ["understand", "write"] and s.llm.cache is True
    assert s.llm.offer == ["laptop"] and [i.name for i in config.available()] == ["laptop"]
    assert s.auth.mode == "proxy" and len(s.auth.proxy_networks) == 2
    assert s.log.level == "INFO"
    # A table is set in a file, never as JSON in a variable.
    monkeypatch.setenv("LEICHTFACILE_PRESETS__LAPTOP__EXTRA_BODY", '{"cache": {"no-cache": true}}')
    with pytest.raises(ConfigError, match=r"presets.laptop.extra_body \(LEICHTFACILE_PRESETS"):
        load()


def test_a_preset_from_variables_alone(home, monkeypatch) -> None:
    """A container or a CI job: a provider and a preset without any file."""
    monkeypatch.setenv("LEICHTFACILE_LLM__PRESET", "ci")
    monkeypatch.setenv("LEICHTFACILE_PROVIDERS__CI__URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("LEICHTFACILE_PROVIDERS__CI__API_KEY", "none")
    monkeypatch.setenv("LEICHTFACILE_PRESETS__CI__PROVIDER", "ci")
    monkeypatch.setenv("LEICHTFACILE_PRESETS__CI__MODELS__WRITER", "any-model")
    llm = load().settings.llm
    assert (llm.preset, llm.url, llm.models.writer) == ("ci", "http://127.0.0.1:9/v1", "any-model")
    assert llm.api_key.get_secret_value() == "none"


def test_relative_folders_follow_their_file_and_need_no_preset(home) -> None:
    write(home, '[data]\ndir = "store"\nexamples_dir = "letters"\n')
    assert paths().dir == home.parent / "store"
    assert paths().examples_dir == home.parent / "letters"
    write(Path("leichtfacile.toml"), '[data]\ndir = "data"\n')  # a checkout's own
    assert paths().dir == Path("data")
    write(home, "")
    assert paths().examples_dir == LETTERS_DIR


def test_get_settings_is_cached_until_the_command_line_changes(home) -> None:
    write(home, LOCAL)
    get_settings.cache_clear()
    try:
        first = get_settings()
        assert get_settings() is first
        use_overrides({"server.port": 8123})
        assert get_settings().server.port == 8123
    finally:
        get_settings.cache_clear()


def test_the_default_folders_follow_the_platform(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("LEICHTFACILE_CONFIG", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    assert config_file() == tmp_path / "config" / "leichtfacile" / "config.toml"
    assert default_data_dir() == tmp_path / "share" / "leichtfacile"
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert config_file() == tmp_path / "roaming" / "leichtfacile" / "config.toml"
    assert default_data_dir() == tmp_path / "local" / "leichtfacile"


def test_a_wrong_log_level_or_format_is_refused_at_start() -> None:
    with pytest.raises(ValidationError, match="log.level"):
        Settings.model_validate({"log": {"level": "verbose"}})
    with pytest.raises(ValidationError, match="log.format"):
        Settings.model_validate({"log": {"format": "xml"}})
    assert Settings.model_validate({"log": {"level": " warning "}}).log.level == "WARNING"


def test_the_reference_in_the_docs_is_current() -> None:
    """docs/configuration.md carries reference_markdown() between its markers;
    `python scripts/config_reference.py` writes it again."""
    doc = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    start, end = "<!-- reference:start -->\n", "<!-- reference:end -->"
    assert doc[doc.index(start) + len(start) : doc.index(end)].strip() == (
        reference_markdown().strip()
    ), "run `uv run python scripts/config_reference.py`"
