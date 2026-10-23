"""Settings: one TOML file with sections and saved model endpoints
(docs/configuration.md).

Each source overrides the one before:

1. the defaults below;
2. the preset an endpoint starts from (`PRESETS`): what is known about a public endpoint,
   kept here so that an upgrade fixes it for every user;
3. the user's config file (`config_file`), written by `leichtfacile setup` and
   `leichtfacile config set`;
4. `leichtfacile.toml` in the current folder, a checkout's own settings;
5. environment variables `LEICHTFACILE_<SECTION>__<KEY>` (`LEICHTFACILE_SERVER__PORT`);
6. the command line (`use_overrides`: `--endpoint`, `--host`, `--port`).

`[llm]` is the endpoint in use: `llm.endpoint` names one of the saved
`[endpoints.<name>]`, and every other key of `[llm]` overrides that endpoint's (and its
preset's). A secret is given in a file (`api_key`, `auth.token`) or named
(`api_key_env`, `auth.token_env`): the named variable comes from the environment, else
from `.env` in the current folder, else from `.env` next to the config file. A `.env`
holds such secrets and nothing else.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import textwrap
import tomllib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from dotenv import dotenv_values
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic.fields import FieldInfo

ThinkingMode = Literal["model-suffix", "chat-template", "off"]
ThinkingStage = Literal["understand", "write", "judge", "repair", "baseline", "recover"]
AuthMode = Literal["none", "token", "proxy"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["text", "json"]
Network = ipaddress.IPv4Network | ipaddress.IPv6Network

APP = "leichtfacile"
ENV_PREFIX = "LEICHTFACILE_"
# A checkout's own settings and secrets, in the folder the command starts from.
PROJECT_FILE = Path("leichtfacile.toml")
LOCAL_ENV_FILE = Path(".env")
# The example letters shipped with the package (examples.py).
LETTERS_DIR = Path(__file__).parent / "letters"
# The 8B of an Apertus family (swiss-ai/Apertus-v1.5-8B, swiss-ai/apertus-v1.5-8b), whose
# 70B judges by default when the endpoint serves it.
_APERTUS_8B = re.compile(r"(apertus\S*-)8(b)$", re.IGNORECASE)
# Endpoint names are TOML keys and parts of variable names.
ENDPOINT_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")


@dataclass(frozen=True)
class Preset:
    label: str
    values: dict[str, Any] = field(default_factory=dict)  # keys of an endpoint


PRESETS: dict[str, Preset] = {
    # The endpoint of the reported numbers. Thinking models are separate model names
    # ending in "-thinking". CSCS closes about one long thinking stream in four midway
    # (6 October 2026); the default retries (llm.max_retries) make a hard failure rare.
    "cscs": Preset(
        "Apertus on the CSCS inference API",
        {
            "url": "https://api.inference.cscs.ch/v1",
            "api_key_env": "CSCS_API_KEY",
            "models": {"writer": "swiss-ai/Apertus-v1.5-8B", "judge": "swiss-ai/Apertus-v1.5-70B"},
            "thinking": "model-suffix",
        },
    ),
    # Public documents only: run by Metagov Inc. (US nonprofit), requests go to compute
    # partners. The 8B (Juelich, vLLM) thinks when asked through the chat template; the
    # 70B (Infomaniak) ignores the switch. The gateway caches answers without regard to
    # the switch, so the extra body turns its cache off. Its "-thinking" names serve the
    # older Apertus 1 without thinking. Checked on 6 October 2026.
    "publicai": Preset(
        "Apertus on the Public AI gateway (public documents only)",
        {
            "url": "https://api.publicai.co/v1",
            "api_key_env": "PUBLICAI_API_KEY",
            "models": {"writer": "swiss-ai/apertus-v1.5-8b", "judge": "swiss-ai/apertus-v1.5-70b"},
            "thinking": "chat-template",
            "extra_body": {"cache": {"no-cache": True}},
        },
    ),
    # A server of one's own takes any key.
    "local": Preset(
        "A server of your own (llama.cpp :8080, Ollama :11434, vLLM)",
        {"url": "http://127.0.0.1:8080/v1", "api_key": "local"},
    ),
    "openai": Preset(
        "OpenAI", {"url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"}
    ),
    "mistral": Preset(
        "Mistral AI", {"url": "https://api.mistral.ai/v1", "api_key_env": "MISTRAL_API_KEY"}
    ),
}


def _shown(text: str) -> dict[str, str]:
    """A default the reference describes instead of printing (a platform's folder)."""
    return {"shown": text}


def _as_list(value: object) -> object:
    """A list from TOML, or from a variable as JSON or comma-separated text."""
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


class Section(BaseModel):
    # A misspelt key is an error, not a setting silently ignored.
    model_config = ConfigDict(extra="forbid")


class Models(Section):
    """The models of the pipeline's stages."""

    writer: str = Field("", description="The model that reads, writes and repairs. Required.")
    # The hybrid: the 70B reads, the 8B writes (docs/prompts.md compares the tiers).
    understand: str | None = Field(
        None, description="The Understand stage's model, when it differs from the writer."
    )
    judge: str | None = Field(
        None,
        description="The judge's model. Default: the 70B of an Apertus 8B writer when the "
        "endpoint lists it, else the writer.",
    )


class Endpoint(Section):
    """A model endpoint (OpenAI-compatible). Thinking is off unless set, since each
    endpoint switches it its own way."""

    preset: str | None = Field(
        None,
        description="A known endpoint whose settings this one starts from: "
        + ", ".join(PRESETS)
        + ".",
    )
    url: str = Field(
        "", description="The endpoint's address, for most servers ending in /v1. Required."
    )
    api_key: SecretStr | None = Field(
        None, description="The key, written into the file. A server of your own takes any key."
    )
    api_key_env: str | None = Field(
        None,
        description="Or the variable that holds the key: from the environment, else from "
        ".env in the current folder, else from .env next to the config file.",
    )
    models: Models = Field(default_factory=Models)
    thinking: ThinkingMode = Field(
        "off",
        description="How the endpoint switches thinking: model-suffix (a separate model "
        "named <model>-thinking, Apertus on CSCS), chat-template (vLLM, llama.cpp) or off.",
    )
    thinking_suffix: str = Field("-thinking", description="The thinking models' suffix.")
    # Writing without thinking was faster and closer to easy language in the first tests
    # (docs/prompts.md). On a 24 GB L4 one letter took 63 minutes with these stages and 22
    # with understand alone.
    thinking_stages: list[ThinkingStage] = Field(
        default_factory=lambda: ["understand", "judge"],
        description="The stages that think, when thinking is on.",
    )
    # Cloudflare in front of the Public AI gateway cuts a silent answer after about 100 s.
    stream: bool = Field(
        True,
        description="Streamed answers, so that a proxy cannot time out a long one; false "
        "only for a server that cannot stream.",
    )
    timeout_s: float = Field(300.0, gt=0, description="Seconds one call may take.")
    # CSCS closes about one long thinking stream in four midway; 8 retries make a hard
    # failure rare (6 October 2026). The backoff stops growing at 30 seconds.
    max_retries: int = Field(8, ge=0, description="Retries of a failed call.")
    cache: bool = Field(
        False, description="Keep the answers in data.dir and reuse them (development, evaluation)."
    )
    extra_body: dict[str, Any] = Field(
        default_factory=dict,
        description="Fields sent with every request, for a gateway's switches.",
    )

    _thinking_stages = field_validator("thinking_stages", mode="before")(_as_list)

    @field_validator("extra_body", mode="before")
    @classmethod
    def _json(cls, value: object) -> object:
        return json.loads(value) if isinstance(value, str) and value.strip() else value

    @field_validator("preset")
    @classmethod
    def _known(cls, value: str | None) -> str | None:
        if value is not None and value not in PRESETS:
            raise ValueError(f"no preset {value!r}; known: {', '.join(PRESETS)}")
        return value


class LLM(Endpoint):
    """The endpoint in use: `endpoint` picks a saved one, and every other key set here
    overrides that endpoint's."""

    endpoint: str | None = Field(
        None,
        description="The saved endpoint in use ([endpoints.<name>]). Default: the only one saved.",
    )

    @property
    def understand_model(self) -> str:
        return self.models.understand or self.models.writer

    @property
    def judge_model(self) -> str:
        """models.judge, else the writer's model. What the endpoint serves can change
        that default: `judge_for`."""
        return self.models.judge or self.models.writer

    @property
    def larger_model(self) -> str | None:
        """The 70B of the writer's Apertus family, None for any other writer."""
        larger = _APERTUS_8B.sub(r"\g<1>70\g<2>", self.models.writer)
        return larger if larger != self.models.writer else None

    def judge_for(self, models: Iterable[str]) -> str:
        """The judge's model: models.judge when set; else the 70B of the writer's family
        when the endpoint lists it (the setup the evaluation measured); else the writer's
        model (a local server with one model)."""
        if self.models.judge:
            return self.models.judge
        larger = self.larger_model
        return larger if larger and larger in set(models) else self.models.writer


class Pipeline(Section):
    """The rounds after the first draft (docs/architecture.md §4.6)."""

    repair_rounds: int = Field(
        3, ge=0, le=10, description="Repair rounds on the rule findings and the judge's; 0: none."
    )
    facts_rounds: int = Field(
        1,
        ge=0,
        le=5,
        description="Rounds that ask only for the must-keep facts still missing after the "
        "repair rounds; 0: none.",
    )
    # 10 since the dev rerun of 7 October 2026 (docs/prompts.md): fact coverage 79 against
    # 75 percent with 5, no invented value, fewer judge findings.
    missing_per_facts_round: int = Field(
        10,
        ge=1,
        le=20,
        description="Missing facts one such round asks for (a repair round asks for 5).",
    )
    # On since 9 October 2026: German fact coverage on the dev pairs rose from 78 to 96
    # percent, no invented value added (docs/prompts.md).
    recover_facts: int = Field(
        10,
        ge=0,
        le=20,
        description="Must-keep values still missing then, asked for one by one with their "
        "source paragraph, as one new version; 0: none.",
    )
    # The facts and recover rounds add the source's sentences nearly verbatim, and the
    # loop never sees them again (10 October 2026; measured in docs/prompts.md).
    polish_rounds: int = Field(
        1,
        ge=0,
        le=3,
        description="Repair rounds on the best version's rule findings alone, at the end; 0: none.",
    )
    # The writer itself gets no list of office words: such a list made the 8B write more
    # of them (docs/prompts.md).
    vocabulary: bool = Field(
        True,
        description="The vocabulary of hard words in the pipeline; false only to measure "
        "what it brings.",
    )


class Jobs(Section):
    """The job queue (docs/architecture.md §7)."""

    workers: int = Field(
        1,
        ge=1,
        le=16,
        description="Threads that run jobs; more than 1 needs an endpoint that serves "
        "parallel requests (vLLM does).",
    )
    queue_limit: int = Field(
        50, ge=1, description="Jobs that may wait; a submission beyond them is refused (429)."
    )
    # One model call alone may take llm.timeout_s times the attempts.
    time_budget_s: float = Field(
        7200.0,
        ge=0,
        description="Seconds a job may run before it stops with its finished stages kept; "
        "0: no limit.",
    )
    # The fetch, the PDF parse and the segmentation run in the request's thread.
    ingest_slots: int = Field(
        4,
        ge=1,
        le=32,
        description="Submissions read (fetched, parsed, segmented) at once; one beyond them "
        "is refused (429).",
    )


class Server(Section):
    """The web application (`leichtfacile serve`)."""

    host: str = Field(
        "127.0.0.1",
        description="The interface the app is published on (0.0.0.0: every interface); "
        "anything but this machine needs a login ([auth]).",
    )
    port: int = Field(8000, ge=1, le=65535, description="The port.")
    open_browser: bool = Field(
        True,
        description="Open the browser at the start, on this machine and, on Linux, with a desktop.",
    )
    ui_lang: str = Field(
        "auto",
        description="Interface language for visitors who have not picked one: en, de, fr, "
        "or auto (the browser's).",
    )
    # The redirect hops are still walked and checked (ingest/fetch.py).
    allow_private_urls: bool = Field(
        False, description="Let users submit URLs of the internal network (an intranet)."
    )
    rate_limit_per_minute: int = Field(
        120,
        ge=0,
        description="Writes (POST, PUT, PATCH, DELETE) per client address and minute; 0: no limit.",
    )

    @property
    def bound_to_loopback(self) -> bool:
        """True when the host reaches this machine alone (127.0.0.1, ::1, localhost)."""
        host = self.host.strip().strip("[]").lower()
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False


class Auth(Section):
    """The login, needed when the app is published beyond this machine
    (docs/architecture.md §10)."""

    token: SecretStr | None = Field(
        None,
        description="A shared secret: browsers ask for it (any user name, the token as the "
        "password), scripts send Authorization: Bearer <token>.",
    )
    token_env: str | None = Field(None, description="Or the variable that holds the token.")
    proxy_header: str | None = Field(
        None,
        description="Or the header a reverse proxy fills with the logged-in user "
        "(X-Forwarded-User, Remote-User) ...",
    )
    proxy_from: list[str] = Field(
        default_factory=list,
        description="... trusted from these addresses or networks only (127.0.0.1, 172.16.0.0/12).",
    )

    _proxy_from = field_validator("proxy_from", mode="before")(_as_list)

    @field_validator("proxy_from")
    @classmethod
    def _networks(cls, value: list[str]) -> list[str]:
        for entry in value:
            ipaddress.ip_network(entry, strict=False)  # ValueError names the entry
        return value

    @property
    def token_value(self) -> str:
        """The shared secret, "" when none is set."""
        return self.token.get_secret_value() if self.token else ""

    @property
    def mode(self) -> AuthMode:
        if self.proxy_header:
            return "proxy"
        return "token" if self.token_value else "none"

    @property
    def proxy_networks(self) -> list[Network]:
        """The reverse proxy's addresses (an address is a network of one)."""
        return [ipaddress.ip_network(entry, strict=False) for entry in self.proxy_from]


class Data(Section):
    """Where the app keeps its data. A relative folder is taken from the folder of the
    file that names it."""

    dir: Path = Field(
        default_factory=lambda: default_data_dir(),
        description="The database, the caches and the spaCy models (models/).",
        json_schema_extra=_shown("the user's app-data folder"),
    )
    examples_dir: Path = Field(
        LETTERS_DIR,
        description="A folder of example letters for the New draft form (.txt or .md, a "
        ".json of job settings next to each).",
        json_schema_extra=_shown("the letters shipped with the package"),
    )
    # Checked every hour (lifecycle.py); the job's cache rows go with it.
    retention_days: int = Field(
        0,
        ge=0,
        description="Jobs nobody changed for this many days are deleted; 0 keeps everything.",
    )


class Log(Section):
    """The app's log. Document text is only ever logged at DEBUG (docs/architecture.md
    §10)."""

    level: LogLevel = Field("INFO", description="DEBUG, INFO, WARNING, ERROR or CRITICAL.")
    format: LogFormat = Field(
        "text",
        description="text, or json: one JSON object per line (time, level, logger, message, "
        "request_id, job_id) for a log collector.",
    )

    @field_validator("level", mode="before")
    @classmethod
    def _level_name(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("format", mode="before")
    @classmethod
    def _format_name(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class Settings(Section):
    llm: LLM = Field(default_factory=LLM)
    endpoints: dict[str, Endpoint] = Field(default_factory=dict)
    pipeline: Pipeline = Field(default_factory=Pipeline)
    jobs: Jobs = Field(default_factory=Jobs)
    server: Server = Field(default_factory=Server)
    auth: Auth = Field(default_factory=Auth)
    data: Data = Field(default_factory=Data)
    log: Log = Field(default_factory=Log)

    @field_validator("endpoints")
    @classmethod
    def _names(cls, value: dict[str, Endpoint]) -> dict[str, Endpoint]:
        for name in value:
            if not ENDPOINT_NAME.fullmatch(name):
                raise ValueError(f"{name!r}: use lowercase letters, digits, - and _")
        return value

    @model_validator(mode="after")
    def _deployment_is_consistent(self) -> Settings:
        auth = self.auth
        if auth.token_value and auth.proxy_header:
            raise ValueError("set auth.token or auth.proxy_header, not both")
        if auth.proxy_header and not auth.proxy_from:
            raise ValueError(
                "auth.proxy_header needs auth.proxy_from, the proxy's addresses or networks, "
                "so that nobody else can send the header"
            )
        if not self.server.bound_to_loopback and auth.mode == "none":
            raise ValueError(
                f"server.host = {self.server.host!r} publishes the app beyond this machine: "
                "set auth.token (a shared secret) or auth.proxy_header and auth.proxy_from "
                '(the reverse proxy\'s user header), or keep server.host = "127.0.0.1"'
            )
        return self


# -- where the settings come from -------------------------------------------------------


class ConfigError(ValueError):
    """Settings that cannot be used. The message names each setting and its source."""


@dataclass(frozen=True)
class Setting:
    """A value and where it came from: a file, a variable, a preset, the command line."""

    value: Any
    source: str


Flat = dict[str, Setting]  # dotted key ("server.port") -> value and source


@dataclass(frozen=True)
class Loaded:
    settings: Settings
    flat: Flat  # every key set somewhere, with its source
    problems: list[str]  # what keeps the endpoint from working (load(strict=False))


def config_file() -> Path:
    """The user's settings file: LEICHTFACILE_CONFIG (or `--config`) when set, else
    config.toml in the platform's folder for settings (Windows: %APPDATA%\\leichtfacile,
    macOS: ~/Library/Application Support/leichtfacile, else $XDG_CONFIG_HOME or
    ~/.config/leichtfacile)."""
    if override := os.environ.get("LEICHTFACILE_CONFIG"):
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP / "config.toml"


def default_data_dir() -> Path:
    """Where the data lives unless data.dir says otherwise (Windows:
    %LOCALAPPDATA%\\leichtfacile, macOS: ~/Library/Application Support/leichtfacile,
    else $XDG_DATA_HOME or ~/.local/share/leichtfacile)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP


def setting_files() -> tuple[Path, ...]:
    """The TOML files, the later one winning: the user's, then the current folder's."""
    user = config_file()
    if user.resolve() == PROJECT_FILE.resolve():
        return (user,)
    return (user, PROJECT_FILE)


def env_files() -> tuple[Path, ...]:
    """The .env files the named secrets are read from, the first one winning; the
    environment wins over both."""
    return (LOCAL_ENV_FILE, config_file().parent / ".env")


def read_file(path: Path) -> dict[str, Any]:
    """A settings file as a dict, {} when there is none."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ConfigError(f"{path}: {exc.strerror or exc}") from None
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from None


def secret_value(name: str) -> tuple[str, str] | None:
    """A named secret and where it was found: the environment, else a .env file."""
    if value := os.environ.get(name):
        return value, "the environment"
    for path in env_files():
        # Taken literally: a key may contain a "$".
        if path.is_file() and (value := dotenv_values(path, interpolate=False).get(name)):
            return value, str(path)
    return None


# The command line's settings (`use_overrides`), the last source.
_overrides: dict[str, Any] = {}


def use_overrides(values: Mapping[str, Any]) -> None:
    """Settings from the command line (`--endpoint`, `--host`, `--port`), as dotted keys;
    None leaves a key to the other sources."""
    _overrides.clear()
    _overrides.update({key: value for key, value in values.items() if value is not None})
    _cached_settings.cache_clear()


def collect(replace: Mapping[Path, Mapping[str, Any]] | None = None) -> Flat:
    """Every source but the defaults and the presets, merged; `replace` stands in for a
    file's content (a change checked before it is written)."""
    replace = replace or {}
    layers = [_file_layer(path, replace.get(path)) for path in setting_files()]
    layers.append(_env_layer(os.environ))
    layers.append({key: Setting(value, "command line") for key, value in _overrides.items()})
    return _merge(layers)


def load(*, strict: bool = True, replace: Mapping[Path, Mapping[str, Any]] | None = None) -> Loaded:
    """The settings with the endpoint in use resolved. `strict`: a ConfigError when the
    endpoint is missing or incomplete; else its problems are returned."""
    flat = _resolve_endpoint(collect(replace))
    problems = _resolve_secrets(flat)
    for key in ("llm.url", "llm.models.writer"):
        if not _set(flat, key):
            problems.append(f"{key}: not set")
    if "llm.api_key" not in flat and "llm.api_key_env" not in flat:
        problems.append("llm.api_key: not set (or llm.api_key_env, the variable that holds it)")
    if strict and problems:
        if not _set(flat, "llm.url") and not any(key.startswith("endpoints.") for key in flat):
            raise ConfigError(
                "No model endpoint is set up: run `leichtfacile setup` "
                f"(settings: {config_file()})."
            )
        raise ConfigError("\n".join(["Settings are missing:", *(f"- {p}" for p in problems)]))
    try:
        settings = Settings.model_validate(_tree(flat))
    except ValidationError as exc:
        raise ConfigError(describe(exc, flat)) from None
    return Loaded(settings, flat, problems)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The settings of a command that calls the model. Raises ConfigError."""
    return load().settings


# The cache `use_overrides` clears, also while a test stands in for get_settings.
_cached_settings = get_settings


def paths() -> Data:
    """[data] alone: the folders without the endpoint (no key is needed to read the
    examples or the dataset)."""
    flat = {key: item for key, item in collect().items() if key.startswith("data.")}
    try:
        return Settings.model_validate(_tree(flat)).data
    except ValidationError as exc:
        raise ConfigError(describe(exc, flat)) from None


def describe(exc: ValidationError, flat: Flat) -> str:
    """The errors with their settings' sources."""
    lines = ["The settings are not valid:"]
    for error in exc.errors():
        key = ".".join(str(part) for part in error["loc"])
        message = error["msg"].removeprefix("Value error, ")
        source = source_of(flat, key)
        where = f" ({source})" if source else ""
        lines.append(f"- {key}{where}: {message}" if key else f"- {message}")
    return "\n".join(lines)


def source_of(flat: Flat, key: str) -> str | None:
    """The source of a key, or of the nearest table above it that has one."""
    while key:
        if key in flat:
            return flat[key].source
        key = key.rpartition(".")[0]
    return None


# A key that takes a whole table, never merged key by key.
_OPAQUE = {"extra_body"}
# Folders a file may give relative to its own folder.
_PATHS = ("data.dir", "data.examples_dir")
# A secret is given or named; the later source's choice wins.
_PARTNER = {"api_key": "api_key_env", "api_key_env": "api_key", "token": "token_env",
            "token_env": "token"}  # fmt: skip


def flatten(tree: Mapping[str, Any], source: str, prefix: str = "") -> Flat:
    flat: Flat = {}
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, Mapping) and value and key not in _OPAQUE:
            flat.update(flatten(value, source, path + "."))
        else:
            flat[path] = Setting(value, source)
    return flat


def _tree(flat: Flat) -> dict[str, Any]:
    root: dict[str, Any] = {}
    for key, item in flat.items():
        *heads, last = key.split(".")
        node = root
        for head in heads:
            if not isinstance(node.get(head), dict):
                node[head] = {}
            node = node[head]
        if item.value == {} and isinstance(node.get(last), dict):
            continue  # an empty table adds nothing to a filled one
        node[last] = {} if item.value == {} else item.value
    return root


def _merge(layers: Iterable[Flat]) -> Flat:
    merged: Flat = {}
    for layer in layers:
        for key, item in layer.items():
            head, _, last = key.rpartition(".")
            if last in _PARTNER:
                partner = f"{head}.{_PARTNER[last]}" if head else _PARTNER[last]
                if partner in layer:
                    raise ConfigError(f"{key} and {partner} are both set ({item.source}): keep one")
                merged.pop(partner, None)
            merged[key] = item
    return merged


def _set(flat: Flat, key: str) -> bool:
    item = flat.get(key)
    return item is not None and item.value not in ("", None)


def _file_layer(path: Path, tree: Mapping[str, Any] | None = None) -> Flat:
    tree = read_file(path) if tree is None else tree
    endpoints = tree.get("endpoints")
    for name in endpoints if isinstance(endpoints, Mapping) else ():
        if not ENDPOINT_NAME.fullmatch(name):
            raise ConfigError(
                f"{path}: endpoint {name!r}: use lowercase letters, digits, - and _ in names"
            )
    flat = flatten(tree, str(path))
    for key in _PATHS:
        item = flat.get(key)
        if item is not None and isinstance(item.value, str):
            folder = Path(item.value).expanduser()
            folder = folder if folder.is_absolute() else path.parent / folder
            flat[key] = Setting(folder, item.source)
    return flat


def _env_layer(environ: Mapping[str, str]) -> Flat:
    """LEICHTFACILE_<SECTION>__<KEY>, the parts joined by two underscores
    (LEICHTFACILE_ENDPOINTS__LOCAL__URL); an empty variable sets nothing."""
    flat: Flat = {}
    for name, raw in environ.items():
        upper = name.upper()
        if not upper.startswith(ENV_PREFIX) or "__" not in upper or not raw.strip():
            continue
        key = upper.removeprefix(ENV_PREFIX).lower().replace("__", ".")
        value = _env_value(raw)
        if isinstance(value, dict) and value and key.rpartition(".")[2] not in _OPAQUE:
            flat.update(flatten(value, name, key + "."))
        else:
            flat[key] = Setting(value, name)
    return flat


def _env_value(raw: str) -> Any:
    """JSON for a list or a table (`["understand"]`, `{"cache": ...}`), else the text,
    which the settings convert ("8001", "true")."""
    text = raw.strip()
    if text.startswith(("[", "{")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return raw


def _resolve_endpoint(flat: Flat) -> Flat:
    """The endpoint in use as `llm.*` keys: its preset's settings, then the saved
    endpoint's, then [llm]'s own."""
    names = sorted({key.split(".")[1] for key in flat if key.startswith("endpoints.")})
    chosen = flat.get("llm.endpoint")
    if chosen is not None:
        name: str | None = str(chosen.value)
        if name not in names:
            saved = f"saved: {', '.join(names)}" if names else "none is saved"
            raise ConfigError(
                f"llm.endpoint = {name!r} ({chosen.source}): no [endpoints.{name}]; {saved}"
            )
    elif len(names) > 1:
        raise ConfigError(
            f"Several endpoints are saved ({', '.join(names)}) and llm.endpoint picks none: "
            "`leichtfacile endpoint use <name>`."
        )
    else:
        name = names[0] if names else None
    prefix = f"endpoints.{name}."
    saved_keys = {
        k.removeprefix(prefix): v for k, v in flat.items() if name and k.startswith(prefix)
    }
    own = {k.removeprefix("llm."): v for k, v in flat.items() if k.startswith("llm.")}
    preset: Flat = {}
    named = own.get("preset") or saved_keys.get("preset")
    if named is not None and named.value in PRESETS:  # an unknown one fails validation
        preset = flatten(PRESETS[named.value].values, f"preset {named.value}")
    resolved = _merge([preset, saved_keys, own])
    if name is not None:
        resolved["endpoint"] = chosen or Setting(name, "the only saved endpoint")
    out = {key: item for key, item in flat.items() if not key.startswith("llm.")}
    out.update({f"llm.{key}": item for key, item in resolved.items()})
    return out


def _resolve_secrets(flat: Flat) -> list[str]:
    """Fill llm.api_key and auth.token from the variables they name; the problems."""
    problems = []
    for key in ("llm.api_key", "auth.token"):
        named = flat.get(f"{key}_env")
        if named is None or key in flat:
            continue
        found = secret_value(str(named.value))
        if found is None:
            files = " or ".join(str(path) for path in env_files())
            problems.append(
                f"{key}: the variable {named.value} ({key}_env, {named.source}) is not set; "
                f"set it in the environment or in {files}"
            )
        else:
            flat[key] = Setting(found[0], f"{named.value} from {found[1]}")
    return problems


# -- the reference (docs/configuration.md, `leichtfacile config show --defaults`) --------

SECTIONS: dict[str, type[Section]] = {
    "llm": LLM, "pipeline": Pipeline, "jobs": Jobs, "server": Server, "auth": Auth,
    "data": Data, "log": Log,
}  # fmt: skip
SECRETS = ("llm.api_key", "auth.token")


def fields(model: type[BaseModel], prefix: str = "") -> Iterator[tuple[str, FieldInfo]]:
    """Every setting of a section as (dotted key, field), `endpoint` first."""
    items = sorted(model.model_fields.items(), key=lambda item: item[0] != "endpoint")
    for name, info in items:
        annotation = info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield from fields(annotation, f"{prefix}{name}.")
        else:
            yield f"{prefix}{name}", info


def toml_value(value: Any) -> str:
    """A value as TOML writes it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, dict):
        inner = ", ".join(f"{json.dumps(k)} = {toml_value(v)}" for k, v in value.items())
        return "{" + (f" {inner} " if inner else "") + "}"
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def default_text(info: FieldInfo) -> str | None:
    """The default as the reference shows it; None for none."""
    extra = info.json_schema_extra
    if isinstance(extra, dict) and "shown" in extra:
        return str(extra["shown"])
    value = info.get_default(call_default_factory=True)
    return None if value in (None, "") else toml_value(value)


def _summary(model: type[BaseModel]) -> str:
    return " ".join((model.__doc__ or "").split())


def reference_toml() -> str:
    """Every setting with its default and meaning, commented out, as a config file."""
    lines = [
        "# Every Leicht·Facile setting with its default (docs/configuration.md).",
        "# Uncomment and change what you need; `leichtfacile config show` lists the values in use.",
    ]
    for section, model in SECTIONS.items():
        lines += ["", f"[{section}]"]
        lines += [f"# {line}" for line in textwrap.wrap(_summary(model), 86)]
        for key, info in fields(model):
            lines += [f"# {line}" for line in textwrap.wrap(info.description or "", 86)]
            default = default_text(info)
            if isinstance(info.json_schema_extra, dict):
                lines += [f"# Default: {default}.", f"# {key} ="]
            elif default is None:
                lines.append(f"# {key} =")
            else:
                lines.append(f"# {key} = {default}")
        if section == "llm":
            lines += [
                "",
                "# [endpoints.<name>]",
                "# A saved endpoint: the keys of [llm] but `endpoint`; llm.endpoint picks one.",
            ]
    return "\n".join(lines) + "\n"


def reference_markdown() -> str:
    """The settings as tables, one per section (docs/configuration.md)."""
    out: list[str] = []
    for section, model in SECTIONS.items():
        out += [f"### `[{section}]`", "", _summary(model), ""]
        if section == "llm":
            out += [
                "A saved `[endpoints.<name>]` takes the same keys but `endpoint`.",
                "",
            ]
        out += ["| Key | Default | Meaning |", "|-----|---------|---------|"]
        for key, info in fields(model):
            default = default_text(info)
            shown = "" if default is None else f"`{default}`"
            if isinstance(info.json_schema_extra, dict):
                shown = default or ""
            meaning = (info.description or "").replace("|", "\\|").replace("<", "&lt;")
            out.append(f"| `{key}` | {shown} | {meaning} |")
        out.append("")
    return "\n".join(out)
