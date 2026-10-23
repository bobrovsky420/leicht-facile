"""The settings (config.py): the TOML files, the variables and the command line in that
order, the saved endpoints with their presets, the keys from .env, and messages that
name the setting and its source."""

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


LOCAL = """
[llm]
endpoint = "laptop"

[endpoints.laptop]
url = "http://127.0.0.1:8080/v1"
api_key = "local"
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
               "jobs.workers", "llm.url")}  # fmt: skip
    assert sources == {
        "server.port": "command line",
        "server.ui_lang": "leichtfacile.toml",
        "jobs.workers": "LEICHTFACILE_JOBS__WORKERS",
        "llm.url": str(home),
    }
    assert s.pipeline.repair_rounds == 3 and "pipeline.repair_rounds" not in loaded.flat
    assert s.llm.thinking == "off"  # each endpoint switches it its own way


def test_a_preset_fills_the_endpoint_and_the_key_comes_from_env_files(home, monkeypatch) -> None:
    write(home, '[endpoints.cscs]\npreset = "cscs"\n')
    write(home.parent / ".env", "CSCS_API_KEY=from-config-folder\n")
    llm = load().settings.llm
    assert (llm.endpoint, llm.url, llm.thinking) == (
        "cscs", "https://api.inference.cscs.ch/v1", "model-suffix",
    )  # fmt: skip
    assert (llm.models.writer, llm.models.judge) == (
        "swiss-ai/Apertus-v1.5-8B", "swiss-ai/Apertus-v1.5-70B",
    )  # fmt: skip
    assert llm.api_key.get_secret_value() == "from-config-folder"
    write(Path(".env"), "CSCS_API_KEY='a$b c'\n")  # the current folder's wins, taken literally
    loaded = load()
    assert loaded.settings.llm.api_key.get_secret_value() == "a$b c"
    assert loaded.flat["llm.api_key"].source == "CSCS_API_KEY from .env"
    monkeypatch.setenv("CSCS_API_KEY", "from-shell")  # the environment wins over both
    assert load().settings.llm.api_key.get_secret_value() == "from-shell"


def test_dot_env_holds_keys_and_nothing_else(home) -> None:
    write(home, LOCAL)
    write(Path(".env"), "LEICHTFACILE_SERVER__PORT=9999\n")
    assert load().settings.server.port == 8000


def test_llm_overrides_the_endpoint_in_use_and_its_preset(home) -> None:
    write(home, "[llm]\ntimeout_s = 1800\nmodels = { judge = \"j\" }\n\n"
                "[endpoints.cscs]\npreset = \"cscs\"\napi_key = \"k\"\ntimeout_s = 600\n"
                "thinking_stages = [\"understand\"]\n")  # fmt: skip
    llm = load().settings.llm
    assert (llm.timeout_s, llm.thinking_stages) == (1800, ["understand"])
    assert (llm.models.writer, llm.models.judge) == ("swiss-ai/Apertus-v1.5-8B", "j")


def test_the_endpoint_in_use(home, monkeypatch) -> None:
    write(home, LOCAL + '\n[endpoints.cscs]\npreset = "cscs"\napi_key = "k"\n')
    assert load().settings.llm.endpoint == "laptop"
    use_overrides({"llm.endpoint": "cscs"})  # --endpoint
    assert load().settings.llm.url == "https://api.inference.cscs.ch/v1"
    use_overrides({"llm.endpoint": "gone"})
    with pytest.raises(ConfigError, match=r"no \[endpoints.gone\]; saved: cscs, laptop"):
        load()
    use_overrides({})
    write(home, LOCAL.replace('endpoint = "laptop"', "") + '\n[endpoints.cscs]\napi_key = "k"\n')
    with pytest.raises(ConfigError, match="llm.endpoint picks none"):
        load()
    write(home, LOCAL.replace('endpoint = "laptop"', ""))
    assert load().settings.llm.endpoint == "laptop"  # the only one saved


def test_the_later_source_decides_between_a_key_and_its_variable(home, monkeypatch) -> None:
    write(home, '[endpoints.mine]\npreset = "local"\napi_key_env = "MINE_KEY"\n'
                'models = { writer = "m" }\n')  # fmt: skip
    monkeypatch.setenv("MINE_KEY", "named")
    assert load().settings.llm.api_key.get_secret_value() == "named"  # not the preset's
    monkeypatch.setenv("LEICHTFACILE_LLM__API_KEY", "given")
    assert load().settings.llm.api_key.get_secret_value() == "given"
    write(home, '[llm]\napi_key = "a"\napi_key_env = "B"\n')
    with pytest.raises(ConfigError, match="keep one"):
        load()


def test_missing_settings_say_what_and_where(home) -> None:
    with pytest.raises(ConfigError, match="No model endpoint is set up") as nothing:
        load()
    assert "leichtfacile setup" in str(nothing.value) and str(home) in str(nothing.value)
    write(home, '[endpoints.cscs]\npreset = "cscs"\n')
    with pytest.raises(ConfigError, match="CSCS_API_KEY") as unset:
        load()
    assert "llm.api_key_env, preset cscs" in str(unset.value)
    lenient = load(strict=False)  # `config show` and checks of a change
    assert lenient.problems and lenient.settings.llm.url


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
    write(home, '[endpoints.My_Server]\nurl = "x"\n')
    with pytest.raises(ConfigError, match="lowercase"):
        load()


def test_variables_carry_lists_tables_and_switches(home, monkeypatch) -> None:
    write(home, LOCAL)
    monkeypatch.setenv("LEICHTFACILE_LLM__THINKING_STAGES", "understand, write")
    monkeypatch.setenv("LEICHTFACILE_LLM__EXTRA_BODY", '{"cache": {"no-cache": true}}')
    monkeypatch.setenv("LEICHTFACILE_LLM__CACHE", "1")
    monkeypatch.setenv("LEICHTFACILE_AUTH__PROXY_FROM", '["127.0.0.1", "10.0.0.0/8"]')
    monkeypatch.setenv("LEICHTFACILE_AUTH__PROXY_HEADER", "X-Forwarded-User")
    monkeypatch.setenv("LEICHTFACILE_LOG__LEVEL", "")  # empty: not set
    s = load().settings
    assert s.llm.thinking_stages == ["understand", "write"] and s.llm.cache is True
    assert s.llm.extra_body == {"cache": {"no-cache": True}}
    assert s.auth.mode == "proxy" and len(s.auth.proxy_networks) == 2
    assert s.log.level == "INFO"


def test_relative_folders_follow_their_file_and_need_no_endpoint(home) -> None:
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
