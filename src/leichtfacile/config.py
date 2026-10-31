"""Settings: one TOML file with sections, and the providers and presets of the model
endpoint (docs/configuration.md).

Each source overrides the one before:

1. the defaults below;
2. the shipped providers and presets (the tables of `presets.toml`): what is known
   about the public endpoints and the models on them, shipped with the package so that
   an upgrade fixes it for every user;
3. the user's config file (`config_file`), written by `leichtfacile setup`, the model
   page of the web app and `leichtfacile config set`;
4. `leichtfacile.toml` in the current folder, a checkout's own settings;
5. environment variables `LEICHTFACILE_<SECTION>__<KEY>` (`LEICHTFACILE_SERVER__PORT`);
6. the command line (`use_overrides`: `--preset`, `--host`, `--port`).

A provider (`[providers.<name>]`) is where models run and how to reach them; its
`models` tables hold what one model there needs; a preset (`[presets.<name>]`) is what
the user picks: a provider and the models that write, read and check. `[llm]` names the
preset in use (`llm.preset`; without it the first preset whose key is set, else the
shipped default) and holds the two switches
that apply to every preset, `cache` and `offer`; a request's settings come from the
provider, the table of the model called, the preset, and the user's tables of the same
names, in that order (`preset_layer`), extra_body's fields added up. A secret is given
in a file (`api_key`, `auth.token`) or named (`api_key_env`, `auth.token_env`): the
named variable comes from the environment, else from `.env` in the current folder, else
from `.env` next to the config file. A `.env` holds such secrets and nothing else.
"""

from __future__ import annotations

import fnmatch
import ipaddress
import json
import os
import re
import sys
import textwrap
import tomllib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

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

from leichtfacile.schemas import PipelineOptions, Region

ThinkingMode = Literal["model-suffix", "chat-template", "reasoning-effort", "off"]
ThinkingStage = Literal["understand", "write", "judge", "repair", "baseline", "recover"]
Location = Literal["ch", "eu", "us", "world", "local"]
Documents = Literal["any", "public"]
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
# Provider and preset names are TOML keys and parts of variable names.
NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
# The known providers and presets, shipped with the package so that an upgrade fixes
# them for every user.
PRESETS_FILE = Path(__file__).parent / "presets" / "presets.toml"
# A page of 250 words through the full pipeline: the order of magnitude of the runs in
# docs/model-comparison.md (30 to 47 thousand tokens, the judge's calls about 40 % of
# them), for the cost per page the interface shows next to a preset.
PAGE_TOKENS_IN = 30_000
PAGE_TOKENS_OUT = 8_000
JUDGE_SHARE = 0.4


class ConfigError(ValueError):
    """Settings that cannot be used. The message names each setting and its source."""


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
        "provider lists it, else the writer.",
    )


class ModelSettings(Section):
    """What the calls to a model take and cost. Set on a provider for all its models, in
    a provider's models table for one model (or a pattern), or on a preset; thinking is
    off unless set, since each provider switches it its own way."""

    thinking: ThinkingMode = Field(
        "off",
        description="How the provider switches thinking: model-suffix (a separate model "
        "named <model>-thinking, Apertus on CSCS), chat-template (vLLM, llama.cpp), "
        "reasoning-effort (the OpenAI field, none for the stages that do not think; a "
        "thinking model on Ollama) or off.",
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
    # OpenAI's GPT-5 models refuse `max_tokens` and any temperature but their default.
    max_tokens_key: Literal["max_tokens", "max_completion_tokens"] = Field(
        "max_tokens",
        description="The request field for the output budget: max_tokens, or "
        "max_completion_tokens (OpenAI's GPT-5 models refuse max_tokens).",
    )
    # Claude Opus 5.5 thinks whatever the request says and counts the thinking in
    # max_tokens: an Understand answer on a long document passed 12,000 (27 October 2026).
    thinking_tokens: int = Field(
        0,
        ge=0,
        description="Tokens added to every call's output budget, for a model that thinks "
        "whatever the request says and counts the thinking in that budget.",
    )
    send_temperature: bool = Field(
        True,
        description="Send each stage's temperature; false for a model that takes only its "
        "default (OpenAI's GPT-5 models, Gemini 3).",
    )
    timeout_s: float = Field(300.0, gt=0, description="Seconds one call may take.")
    # CSCS closes about one long thinking stream in four midway; 8 retries make a hard
    # failure rare (6 October 2026). The backoff stops growing at 30 seconds.
    max_retries: int = Field(8, ge=0, description="Retries of a failed call.")
    extra_body: dict[str, Any] = Field(
        default_factory=dict,
        description="Fields sent with every request: a gateway's switches, a model's "
        "thinking switch. A later table's fields add to the earlier ones.",
    )
    input_usd: float | None = Field(
        None, ge=0, description="USD per million input tokens, for the cost per page."
    )
    output_usd: float | None = Field(None, ge=0, description="USD per million output tokens.")

    _thinking_stages = field_validator("thinking_stages", mode="before")(_as_list)


MODEL_KEYS = frozenset(ModelSettings.model_fields)


class Connection(ModelSettings):
    """What reaches a provider: the address, the key and the headers, and what the
    interface says about it."""

    label: str | None = Field(None, description="The name the interface shows.")
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
    key_url: str | None = Field(
        None, description="Where a key comes from, linked by the interface."
    )
    location: Location = Field(
        "world",
        description="Where the text is processed: ch, eu, us, world (several countries) "
        "or local (this machine or the organisation's network).",
    )
    documents: Documents = Field(
        "any",
        description="Which documents may go there: any, or public (no personal data).",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Headers sent with every request (anthropic-version for Anthropic's "
        "OpenAI-compatible endpoint).",
    )


class Provider(Connection):
    """Where models run and how to reach them. Its request settings apply to every
    model there unless a models table or the preset says otherwise."""

    discover: bool = Field(
        False,
        description="Offer every model the server lists as a preset (a server of one's "
        "own, which names its own models).",
    )
    models: dict[str, ModelSettings] = Field(
        default_factory=dict,
        description='What one model there needs, by its name or a pattern ("gpt-5*"): '
        "[providers.<name>.models.<model>] tables.",
    )


class Preset(ModelSettings):
    """A provider with the models that write, read and check: what the user picks. Any
    request setting here overrides the provider's and the model's."""

    provider: str | None = Field(
        None,
        description="The provider the preset runs on. Required for a preset of your own; "
        "a table named like a shipped preset extends it.",
    )
    label: str | None = Field(
        None, description="The name the interface shows. Default: the preset's name."
    )
    models: Models = Field(default_factory=Models)


@dataclass(frozen=True)
class Catalog:
    """The shipped providers and presets as the file holds them, and the default preset."""

    providers: dict[str, dict[str, Any]]
    presets: dict[str, dict[str, Any]]
    default: str


def read_catalog(path: Path) -> Catalog:
    """The providers and presets of a file, each in the file's order (the interface's
    and setup's): the tables of `[providers.<name>]` and `[presets.<name>]`, checked like
    the user's own; every provider has a label and an address, every preset names a known
    provider and its writer, and `default` names a preset."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from None
    providers = _tables(path, data, "providers", Provider)
    presets = _tables(path, data, "presets", Preset)
    for name, table in providers.items():
        if not (table.get("label") and table.get("url")):
            raise ConfigError(f"{path}: [providers.{name}] needs a label and a url")
    for name, table in presets.items():
        if table.get("provider") not in providers:
            raise ConfigError(f"{path}: [presets.{name}] names no known provider")
        if not (table.get("label") and table.get("models", {}).get("writer")):
            raise ConfigError(f"{path}: [presets.{name}] needs a label and models.writer")
    default = data.get("default")
    if default not in presets:
        raise ConfigError(f"{path}: default names no preset of the file")
    return Catalog(providers, presets, str(default))


def _tables(path: Path, data: dict, section: str, model: type[Section]) -> dict[str, dict]:
    found = data.get(section, {})
    if not isinstance(found, dict):
        raise ConfigError(f"{path}: [{section}] holds one table per {section[:-1]}")
    for name, table in found.items():
        if not NAME.fullmatch(name) or not isinstance(table, dict):
            raise ConfigError(
                f"{path}: {section}.{name!r}: a {section[:-1]} is a table named with "
                "lowercase letters, digits, - and _"
            )
        try:
            model.model_validate(table)
        except ValidationError as exc:
            raise ConfigError(f"{path}: [{section}.{name}]: {exc.errors()[0]['msg']}") from None
    return found


SHIPPED = read_catalog(PRESETS_FILE)
PROVIDERS: dict[str, dict[str, Any]] = SHIPPED.providers
PRESETS: dict[str, dict[str, Any]] = SHIPPED.presets
DEFAULT_PRESET = SHIPPED.default


class LLMChoice(Section):
    """The preset in use, and the two switches that apply to every preset. A provider's
    keys live in its [providers.<name>] table, a preset's in its [presets.<name>] table."""

    preset: str | None = Field(
        None,
        description="The preset in use: a shipped one or one of your own. Default: the "
        "first preset, in the order of presets.toml, whose provider's key is set; with "
        f"none, {DEFAULT_PRESET}.",
    )
    cache: bool = Field(
        False,
        description="Keep the answers in data.dir and reuse them (development, evaluation), "
        "whichever preset is in use.",
    )
    offer: list[str] = Field(
        default_factory=list,
        description="The presets the interface offers (an organisation's choice); empty: "
        "every ready one.",
    )

    _offer = field_validator("offer", mode="before")(_as_list)


class LLM(Connection):
    """The preset in use with every key, as the settings resolve it: its provider's, the
    provider's table of each model, the preset's, the user's tables of the same names,
    and [llm]'s switches."""

    preset: str | None = Field(None, description="The preset in use.")
    provider: str | None = Field(None, description="Its provider.")
    provider_label: str | None = Field(None, description="The provider's name in the interface.")
    models: Models = Field(default_factory=Models)
    model_settings: dict[str, ModelSettings] = Field(
        default_factory=dict,
        description="The provider's models tables, the preset's settings folded in.",
    )
    cache: bool = Field(False, description="Keep the answers in data.dir and reuse them.")
    offer: list[str] = Field(default_factory=list, description="The presets the interface offers.")

    _offer = field_validator("offer", mode="before")(_as_list)

    @property
    def title(self) -> str:
        """What the interface calls the preset: its label, else its name, else its host."""
        return self.label or self.preset or urlsplit(self.url).hostname or self.url

    @property
    def understand_model(self) -> str:
        return self.models.understand or self.models.writer

    @property
    def judge_model(self) -> str:
        """models.judge, else the writer's model. What the provider serves can change
        that default: `judge_for`."""
        return self.models.judge or self.models.writer

    @property
    def larger_model(self) -> str | None:
        """The 70B of the writer's Apertus family, None for any other writer; a provider
        suffix (`:publicai` on the Hugging Face router) stays."""
        name, colon, suffix = self.models.writer.partition(":")
        larger = _APERTUS_8B.sub(r"\g<1>70\g<2>", name)
        return larger + colon + suffix if larger != name else None

    def judge_for(self, models: Iterable[str]) -> str:
        """The judge's model: models.judge when set; else the 70B of the writer's family
        when the provider lists it (the setup the evaluation measured); else the writer's
        model (a local server with one model)."""
        if self.models.judge:
            return self.models.judge
        larger = self.larger_model
        return larger if larger and listed(larger, models) else self.models.writer

    def model_table(self, name: str) -> dict[str, Any]:
        """The keys set for a model in the provider's models tables: those of every
        pattern that matches it, in the file's order, and the table named after it over
        them (case does not matter: CSCS lists Apertus-v1.5-8B, Public AI apertus-v1.5-8b)."""
        found: dict[str, Any] = {}
        for key in matching_tables(name, self.model_settings):
            table = self.model_settings[key]
            found = merge_tables(found, table.model_dump(include=table.model_fields_set))
        return found

    def for_model(self, name: str) -> ModelSettings:
        """The request settings of one model: the preset's over its table's over the
        provider's, extra_body's fields added up."""
        base = self.model_dump(include=MODEL_KEYS)
        return ModelSettings.model_validate(merge_tables(base, self.model_table(name)))

    def price(self, name: str) -> tuple[float, float] | None:
        """USD per million input and output tokens of a model; None without a price
        (a server of one's own, an unknown model)."""
        settings = self.for_model(name)
        if settings.input_usd is None or settings.output_usd is None:
            return None
        return settings.input_usd, settings.output_usd


def matching_tables(name: str, tables: Iterable[str]) -> list[str]:
    """The keys of a provider's models tables that match a model: the patterns, in
    their order, then the one named after it (case does not matter)."""
    lowered = name.lower()
    patterns = [
        k for k in tables if any(c in k for c in "*?[") and fnmatch.fnmatchcase(lowered, k.lower())
    ]
    return patterns + [k for k in tables if k.lower() == lowered]


def merge_tables(base: Mapping[str, Any], over: Mapping[str, Any]) -> dict[str, Any]:
    """`over` on `base` key by key, a table within a table too: a model's extra_body adds
    its fields to the provider's (OpenRouter's `provider` switch stays when a model's
    table sets `reasoning`), and a field set in both takes `over`'s value."""
    merged = dict(base)
    for key, value in over.items():
        earlier = merged.get(key)
        if isinstance(earlier, Mapping) and isinstance(value, Mapping):
            merged[key] = merge_tables(earlier, value)
        else:
            merged[key] = value
    return merged


def listed(model: str, models: Iterable[str]) -> bool:
    """Whether a provider's model list has the model: by its name, or by its name without
    a provider suffix (`Qwen/Qwen3.5-9B:ovhcloud` on the Hugging Face router, which lists
    `Qwen/Qwen3.5-9B`); an Ollama name (`qwen3.5:9b`) is listed as it is."""
    names = set(models)
    return model in names or (":" in model and model.rpartition(":")[0] in names)


def cost_per_page(llm: LLM) -> float | None:
    """USD for a page of 250 words through the full pipeline, an order of magnitude from
    the writer's and the judge's prices; None when one of them has no price per token."""
    writer = llm.price(llm.models.writer)
    judge = llm.price(llm.judge_model)
    if writer is None or judge is None:
        return None

    def cost(price: tuple[float, float]) -> float:
        return (PAGE_TOKENS_IN * price[0] + PAGE_TOKENS_OUT * price[1]) / 1e6

    return round((1 - JUDGE_SHARE) * cost(writer) + JUDGE_SHARE * cost(judge), 4)


def model_price(name: str) -> tuple[float, float] | None:
    """A model's prices by its name alone, from the shipped providers' tables (the
    evaluation's rescoring, which runs without a preset): the first table that prices
    it; none when a table of a server of one's own (`discover`) names it, since such a
    build pays for hardware, not tokens."""
    for provider in PROVIDERS.values():
        if provider.get("discover") and matching_tables(name, provider.get("models", {})):
            return None
    for provider in PROVIDERS.values():
        found = LLM(model_settings=provider.get("models", {})).price(name)
        if found is not None:
            return found
    return None


# The [pipeline] section is the model a job carries along (schemas.PipelineOptions), so
# the settings and the stored jobs describe the rounds with one set of fields.
Pipeline = PipelineOptions


class Texts(Section):
    """The texts the installation works on (docs/architecture.md section 8). Set by
    `leichtfacile setup`; a job keeps the value it was created with."""

    region: Region = Field(
        "CH",
        description="The national variety of German the drafts follow: CH (Switzerland), DE "
        "(Germany) or AT (Austria); `leichtfacile setup --region` sets it. French and Italian "
        "texts are Swiss whatever the value.",
    )

    @field_validator("region", mode="before")
    @classmethod
    def _region_code(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value


class Jobs(Section):
    """The job queue (docs/architecture.md §7)."""

    workers: int = Field(
        1,
        ge=1,
        le=16,
        description="Threads that run jobs; more than 1 needs a provider that serves "
        "parallel requests (vLLM does).",
    )
    queue_limit: int = Field(
        50, ge=1, description="Jobs that may wait; a submission beyond them is refused (429)."
    )
    # One model call alone may take timeout_s times the attempts.
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
    published_on: str | None = Field(
        None,
        description="In a container: the address the runtime publishes the port on "
        "(docker run -p <address>:8000:8000), judged instead of host for the login; "
        "127.0.0.1 needs none.",
    )
    port: int = Field(8000, ge=1, le=65535, description="The port.")
    open_browser: bool = Field(
        True,
        description="Open the browser at the start, on this machine and, on Linux, with a desktop.",
    )
    ui_lang: str = Field(
        "auto",
        description="Interface language for visitors who have not picked one: en, de, fr, it, "
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
        """True when the app is reachable from this machine alone: by `published_on` when
        that is set (a container binds every interface of its own, and the runtime
        publishes the port), else by `host` (127.0.0.1, ::1, localhost)."""
        host = (self.published_on or self.host).strip().strip("[]").lower()
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
        description="The database and the caches.",
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
    providers: dict[str, Provider] = Field(default_factory=dict)  # the user's own tables
    presets: dict[str, Preset] = Field(default_factory=dict)
    texts: Texts = Field(default_factory=Texts)
    pipeline: Pipeline = Field(default_factory=Pipeline)
    jobs: Jobs = Field(default_factory=Jobs)
    server: Server = Field(default_factory=Server)
    auth: Auth = Field(default_factory=Auth)
    data: Data = Field(default_factory=Data)
    log: Log = Field(default_factory=Log)

    @field_validator("providers", "presets")
    @classmethod
    def _names(cls, value: dict[str, Any]) -> dict[str, Any]:
        for name in value:
            if not NAME.fullmatch(name):
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
            published = self.server.published_on
            where = (
                f"server.published_on = {published!r}"
                if published
                else f"server.host = {self.server.host!r}"
            )
            raise ValueError(
                f"{where} publishes the app beyond this machine: "
                "set auth.token (a shared secret) or auth.proxy_header and auth.proxy_from "
                '(the reverse proxy\'s user header), or keep server.host = "127.0.0.1" (in a '
                "container, whose port the runtime publishes on this machine alone: "
                'server.published_on = "127.0.0.1")'
            )
        return self


# -- where the settings come from -------------------------------------------------------


@dataclass(frozen=True)
class Setting:
    """A value and where it came from: a file, a variable, a provider, a preset, the
    command line."""

    value: Any
    source: str


Flat = dict[str, Setting]  # dotted key ("server.port") -> value and source


@dataclass(frozen=True)
class Loaded:
    settings: Settings
    flat: Flat  # every key set somewhere, with its source
    problems: list[str]  # what keeps the preset from working (load(strict=False))


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
    """Settings from the command line (`--preset`, `--host`, `--port`), as dotted keys;
    None leaves a key to the other sources."""
    _overrides.clear()
    _overrides.update({key: value for key, value in values.items() if value is not None})
    _cached_settings.cache_clear()


def collect(replace: Mapping[Path, Mapping[str, Any]] | None = None) -> Flat:
    """Every source but the defaults and the shipped catalog, merged; `replace` stands in
    for a file's content (a change checked before it is written)."""
    replace = replace or {}
    layers = [_file_layer(path, replace.get(path)) for path in setting_files()]
    layers.append(_env_layer(os.environ))
    layers.append({key: Setting(value, "command line") for key, value in _overrides.items()})
    return _merge(layers)


def load(
    *,
    strict: bool = True,
    replace: Mapping[Path, Mapping[str, Any]] | None = None,
    preset: str | None = None,
) -> Loaded:
    """The settings with the preset in use resolved: `preset` for this load (a draft
    that picked one), else llm.preset, else the first preset with its key set, else the
    shipped default. `strict`: a ConfigError
    when the preset is incomplete (no key); else its problems are returned."""
    flat = _resolve_llm(collect(replace), preset)
    problems = _resolve_secrets(flat)
    for key in ("llm.url", "llm.models.writer"):
        if not _set(flat, key):
            problems.append(f"{key}: not set")
    if "llm.api_key" not in flat and "llm.api_key_env" not in flat:
        problems.append("llm.api_key: not set (or llm.api_key_env, the variable that holds it)")
    if strict and problems:
        name = flat["llm.preset"].value
        raise ConfigError(
            "\n".join(
                [
                    f"The preset {name} is not ready:",
                    *(f"- {p}" for p in problems),
                    f"`leichtfacile setup {name}` asks for what it lacks; `leichtfacile preset "
                    "list` shows every preset.",
                ]
            )
        )
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
    """[data] alone: the folders without the preset (no key is needed to read the
    examples or the dataset)."""
    return _section("data").data


def texts() -> Texts:
    """[texts] alone: the variety of the texts, for the commands that call no model
    (`check`)."""
    return _section("texts").texts


def _section(name: str) -> Settings:
    flat = {key: item for key, item in collect().items() if key.startswith(f"{name}.")}
    try:
        return Settings.model_validate(_tree(flat))
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


# A key whose table is one value, not settings of its own: a later source's table
# replaces it, except extra_body, whose fields add up (`_merge`).
_OPAQUE = {"extra_body", "headers", "model_settings"}
# A provider's models tables: one value per model, since model names hold dots.
_MODEL_TABLES = re.compile(r"providers\.[^.]+\.models")
# Folders a file may give relative to its own folder.
_PATHS = ("data.dir", "data.examples_dir")
# A secret is given or named; the later source's choice wins.
_PARTNER = {"api_key": "api_key_env", "api_key_env": "api_key", "token": "token_env",
            "token_env": "token"}  # fmt: skip


def flatten(tree: Mapping[str, Any], source: str, prefix: str = "") -> Flat:
    flat: Flat = {}
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if (
            isinstance(value, Mapping)
            and value
            and key not in _OPAQUE
            and not _MODEL_TABLES.fullmatch(path)
        ):
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
            earlier = merged.get(key)
            if (
                earlier is not None
                and isinstance(earlier.value, Mapping)
                and isinstance(item.value, Mapping)
            ):
                if _MODEL_TABLES.fullmatch(key):  # a later source adds or replaces models
                    item = Setting({**earlier.value, **item.value}, item.source)
                elif last == "extra_body":  # a later source's fields add to the earlier ones
                    item = Setting(merge_tables(earlier.value, item.value), item.source)
            merged[key] = item
    return merged


def _set(flat: Flat, key: str) -> bool:
    item = flat.get(key)
    return item is not None and item.value not in ("", None)


def _file_layer(path: Path, tree: Mapping[str, Any] | None = None) -> Flat:
    tree = read_file(path) if tree is None else tree
    for section in ("providers", "presets"):
        tables = tree.get(section)
        for name in tables if isinstance(tables, Mapping) else ():
            if not NAME.fullmatch(name):
                raise ConfigError(
                    f"{path}: {section}.{name!r}: use lowercase letters, digits, - and _ in names"
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
    (LEICHTFACILE_PROVIDERS__MINE__URL): the text, which the settings convert ("8001",
    "true", a comma-separated list); an empty variable sets nothing. A table (extra_body,
    headers, a models table) is set in a file."""
    flat: Flat = {}
    for name, raw in environ.items():
        upper = name.upper()
        if not upper.startswith(ENV_PREFIX) or "__" not in upper or not raw.strip():
            continue
        key = upper.removeprefix(ENV_PREFIX).lower().replace("__", ".")
        flat[key] = Setting(raw, name)
    return flat


# -- the presets as the interface and the commands list them -----------------------------


@dataclass(frozen=True)
class Available:
    """A preset the settings offer, shipped or the user's own, with what it lacks."""

    name: str
    label: str
    provider: str
    provider_label: str
    location: str
    documents: str
    key_url: str | None
    key_variable: str | None  # the provider's api_key_env: the model page asks for a key
    url: str
    writer: str
    judge: str | None
    has_key: bool  # given, or its variable set
    missing: tuple[str, ...]  # what keeps it from working; empty: ready
    cost_per_page: float | None  # USD, an order of magnitude; None without prices

    @property
    def ready(self) -> bool:
        return not self.missing


def available(flat: Flat | None = None) -> list[Available]:
    """Every preset with what it lacks, in the catalog's order then the user's own: for
    `leichtfacile preset list`, the model page and the New draft form. `llm.offer`
    limits them to the presets an organisation wants shown."""
    flat = collect() if flat is None else flat
    names = preset_names(flat)
    if (offer := flat.get("llm.offer")) is not None:
        wanted = [str(name) for name in _as_list(offer.value) or []]
        if unknown := [name for name in wanted if name not in names]:
            raise ConfigError(
                f"llm.offer ({offer.source}): no such preset {', '.join(unknown)}; "
                f"known: {', '.join(names)}"
            )
        names = [name for name in names if name in wanted] if wanted else names
    return [_available(flat, name) for name in names]


def _available(flat: Flat, name: str) -> Available:
    layer = preset_layer(flat, name)
    try:
        llm = LLM.model_validate(_tree({f"llm.{k}": v for k, v in layer.items()})["llm"])
    except ValidationError as exc:
        raise ConfigError(describe(exc, {f"llm.{k}": v for k, v in layer.items()})) from None
    missing = []
    if not llm.url:
        missing.append("url is not set")
    if not llm.models.writer:
        missing.append("no model yet")
    has_key = llm.api_key is not None
    if not has_key:
        if llm.api_key_env is None:
            missing.append("api_key is not set")
        elif secret_value(llm.api_key_env) is None:
            missing.append(f"the variable {llm.api_key_env} is not set")
        else:
            has_key = True
    return Available(
        name,
        label=llm.label or name,
        provider=llm.provider or "",
        provider_label=llm.provider_label or llm.provider or "",
        location=llm.location,
        documents=llm.documents,
        key_url=llm.key_url,
        key_variable=llm.api_key_env,
        url=llm.url,
        writer=llm.models.writer,
        judge=llm.models.judge,
        has_key=has_key,
        missing=tuple(missing),
        cost_per_page=cost_per_page(llm),
    )


def preset_names(flat: Flat) -> list[str]:
    """Every preset the settings offer: the shipped ones in the catalog's order, then
    the user's own, by name."""
    return [*PRESETS, *(name for name in _user_names(flat, "presets") if name not in PRESETS)]


def provider_names(flat: Flat) -> list[str]:
    return [
        *PROVIDERS,
        *(name for name in _user_names(flat, "providers") if name not in PROVIDERS),
    ]


def _user_names(flat: Flat, section: str) -> list[str]:
    prefix = f"{section}."
    return sorted({key.split(".")[1] for key in flat if key.startswith(prefix)})


# What [llm] takes: the choice of preset, and the switches that apply to every preset.
LLM_KEYS = ("llm.preset", "llm.cache", "llm.offer")


def _resolve_llm(flat: Flat, requested: str | None = None) -> Flat:
    """The preset in use as `llm.*` keys: `requested` (--preset, or a draft that picked
    one), else llm.preset, else the first preset with its key set (`first_with_key`). A
    key of a provider or a preset in [llm] itself is an error, since it belongs to that
    table."""
    for key, item in flat.items():
        if key.startswith("llm.") and key not in LLM_KEYS:
            raise ConfigError(
                f"{key} ({item.source}): [llm] takes preset, cache and offer only; a "
                "provider's keys go into its [providers.<name>] table, a preset's into its "
                "[presets.<name>] table (LEICHTFACILE_PRESETS__<NAME>__<KEY> in the environment)"
            )
    names = preset_names(flat)
    picked = Setting(requested, "requested") if requested else flat.get("llm.preset")
    if picked is None:
        picked = first_with_key(flat, names)
    name = str(picked.value)
    if name not in names:
        raise ConfigError(
            f"llm.preset = {name!r} ({picked.source}): no such preset; known: {', '.join(names)}"
        )
    layer = preset_layer(flat, name)
    layer["preset"] = picked
    for key in ("cache", "offer"):
        if (item := flat.get(f"llm.{key}")) is not None:
            layer[key] = item
    out = {key: item for key, item in flat.items() if not key.startswith("llm.")}
    out.update({f"llm.{key}": item for key, item in layer.items()})
    return out


def first_with_key(flat: Flat, names: list[str]) -> Setting:
    """The preset of a fresh install, while nothing names one: the first, in the
    catalog's order (setup's and the model page's), whose provider's key is in its
    variable (the environment or a .env), among llm.offer when set; else the shipped
    default. A preset of the user's own that is not complete yet is passed over."""
    if (offer := flat.get("llm.offer")) is not None and (wanted := _as_list(offer.value)):
        names = [name for name in names if name in wanted]
    for name in names:
        try:
            variable = preset_layer(flat, name).get("api_key_env")
        except ConfigError:
            continue
        if variable is not None and secret_value(str(variable.value)) is not None:
            return Setting(name, f"the key in {variable.value}")
    return Setting(DEFAULT_PRESET, "the shipped default")


def preset_layer(flat: Flat, name: str) -> Flat:
    """The keys of a preset as [llm] sees them: its provider's (shipped, then the user's
    table), the preset's over them (the same way), and the provider's models tables
    with the preset's request settings folded in, so that a model's calls take the
    provider's settings, then its table's, then the preset's."""
    preset = _layer(PRESETS, "presets", flat, name, f"preset {name}")
    named = preset.pop("provider", None)
    if named is None:
        raise ConfigError(f"preset {name}: names no provider ([presets.{name}] provider = ...)")
    provider_name = str(named.value)
    if provider_name not in provider_names(flat):
        raise ConfigError(
            f"presets.{name}.provider = {provider_name!r} ({named.source}): no such provider; "
            f"known: {', '.join(provider_names(flat))}"
        )
    provider = _layer(PROVIDERS, "providers", flat, provider_name, f"provider {provider_name}")
    tables = provider.pop("models", None)
    provider.pop("discover", None)
    if (label := provider.pop("label", None)) is not None:
        provider["provider_label"] = label
    overrides = {key: item.value for key, item in preset.items() if key in MODEL_KEYS}
    model_settings = {
        model: merge_tables(table, overrides)
        for model, table in (tables.value if tables is not None else {}).items()
    }
    layer = _merge([provider, preset])
    layer["provider"] = named
    layer["model_settings"] = Setting(
        model_settings, tables.source if tables is not None else f"provider {provider_name}"
    )
    return layer


def provider_table(flat: Flat, name: str) -> dict[str, Any]:
    """A provider's keys as a plain table, the shipped one and the user's merged (the
    model page's discovery of a local server's models): ConfigError for an unknown one."""
    if name not in provider_names(flat):
        raise ConfigError(f"no provider {name!r}; known: {', '.join(provider_names(flat))}")
    layer = _layer(PROVIDERS, "providers", flat, name, f"provider {name}")
    return _tree({key: item for key, item in layer.items()})


def _layer(
    shipped: Mapping[str, Mapping[str, Any]], section: str, flat: Flat, name: str, source: str
) -> Flat:
    """One provider's or preset's keys: the shipped table, the user's over it."""
    prefix = f"{section}.{name}."
    base = flatten({section: {name: shipped.get(name, {})}}, source)
    user = {key: item for key, item in flat.items() if key.startswith(prefix)}
    merged = _merge([base, user])
    return {k.removeprefix(prefix): item for k, item in merged.items() if k.startswith(prefix)}


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

PROVIDER_SECTION = "providers.<name>"
MODEL_SECTION = "providers.<name>.models.<model>"
PRESET_SECTION = "presets.<name>"
SECTIONS: dict[str, type[Section]] = {
    "llm": LLMChoice, PROVIDER_SECTION: Provider, MODEL_SECTION: ModelSettings,
    PRESET_SECTION: Preset, "texts": Texts, "pipeline": Pipeline, "jobs": Jobs,
    "server": Server, "auth": Auth, "data": Data, "log": Log,
}  # fmt: skip
# What `config show` lists: the preset in use with every key, then the other sections.
IN_USE: dict[str, type[Section]] = {
    "llm": LLM,
    **{k: v for k, v in SECTIONS.items() if "<" not in k and k != "llm"},
}
SECRETS = ("llm.api_key", "auth.token")


def fields(model: type[BaseModel], prefix: str = "") -> Iterator[tuple[str, FieldInfo]]:
    """Every setting of a section as (dotted key, field), `preset` and `provider` first."""
    first = ("preset", "provider")
    items = sorted(model.model_fields.items(), key=lambda item: item[0] not in first)
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
    if isinstance(value, BaseModel):
        value = value.model_dump(include=value.model_fields_set)
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
        # A section with a placeholder stands for one table per provider or preset.
        lines += ["", f"[{section}]" if "<" not in section else f"# [{section}]"]
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
    return "\n".join(lines) + "\n"


def reference_markdown() -> str:
    """The settings as tables, one per section (docs/configuration.md)."""
    out: list[str] = []
    for section, model in SECTIONS.items():
        out += [f"### `[{section}]`", "", _summary(model), ""]
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
