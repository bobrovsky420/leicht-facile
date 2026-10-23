"""Settings from the user's config file, a `.env` file in the current folder and the
environment, each overriding the one before.

The three required variables are `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_NAME`: any
OpenAI-compatible endpoint. `leichtfacile setup` writes them to the config file
(`config_file`). Everything else has a default.
"""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ThinkingMode = Literal["model-suffix", "chat-template", "off"]
AuthMode = Literal["none", "token", "proxy"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["text", "json"]
Network = ipaddress.IPv4Network | ipaddress.IPv6Network

# The 8B of an Apertus family (swiss-ai/Apertus-v1.5-8B, swiss-ai/apertus-v1.5-8b), whose
# 70B judges by default when the endpoint serves it.
_APERTUS_8B = re.compile(r"(apertus\S*-)8(b)$", re.IGNORECASE)
APP = "leichtfacile"
# The example letters shipped with the package (examples.py).
LETTERS_DIR = Path(__file__).parent / "letters"


def config_file() -> Path:
    """The user's settings file, written by `leichtfacile setup`: LEICHTFACILE_CONFIG
    when set, else config.env in the platform's folder for settings (Windows:
    %APPDATA%\\leichtfacile, macOS: ~/Library/Application Support/leichtfacile, else
    $XDG_CONFIG_HOME or ~/.config/leichtfacile)."""
    if override := os.environ.get("LEICHTFACILE_CONFIG"):
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP / "config.env"


def default_data_dir() -> Path:
    """Where the database lives unless DATA_DIR says otherwise (Windows:
    %LOCALAPPDATA%\\leichtfacile, macOS: ~/Library/Application Support/leichtfacile,
    else $XDG_DATA_HOME or ~/.local/share/leichtfacile)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP


def env_files() -> tuple[Path, ...]:
    """The files settings are read from, the later one winning: the user's config file,
    then `.env` in the current folder. The environment wins over both."""
    return (config_file(), Path(".env"))


class Paths(BaseSettings):
    """The settings that need no model endpoint. The dataset tools and the example
    loader read them as `paths()` without a key; the application reads them as part of
    `Settings`. Every environment variable goes through one of the two, so the config
    file and `.env` are honoured everywhere (audit B1)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = Field(default_factory=default_data_dir)
    # The example letters the New draft form and the empty drafts list offer: .txt or .md,
    # each with an optional .json of job settings next to it (examples.py).
    examples_dir: Path = LETTERS_DIR


class Settings(Paths):
    # Model endpoint (OpenAI-compatible). See .env.example for the supported profiles.
    llm_base_url: str
    llm_api_key: SecretStr
    llm_name: str
    llm_judge_name: str | None = None
    # The Understand stage's model, when it should differ from the writer (the hybrid:
    # the 70B reads, the 8B writes; docs/prompts.md compares the tiers). Empty: the
    # writer's model.
    llm_understand_name: str | None = None
    # Thinking, for the stages below: off by default, since each endpoint switches it its
    # own way. Apertus on CSCS serves it as models named "<name>-thinking"
    # (model-suffix); vLLM and llama.cpp take it through the chat template
    # (chat-template). .env.example has the settings per endpoint.
    llm_thinking_mode: ThinkingMode = "off"
    llm_thinking_suffix: str = "-thinking"
    # Stages that use the thinking model. Writing without thinking was faster and closer
    # to easy language in the first local tests (docs/prompts.md).
    llm_thinking_stages: str = "understand,judge"
    # Streamed responses: the endpoint sends the answer as it is generated, so a proxy in
    # front of it cannot time out a long answer (Cloudflare in front of the Public AI
    # gateway does so after about 100 seconds). Off only for a server without streaming.
    llm_stream: bool = True
    llm_timeout_s: float = Field(default=300.0, gt=0)
    # CSCS closes about one long thinking stream in four midway; 8 retries make a hard
    # failure rare (6 October 2026). The backoff stops growing at 30 seconds.
    llm_max_retries: int = Field(default=8, ge=0)
    llm_cache: bool = False
    # Extra JSON fields sent with every request, for gateway-specific switches such as
    # Public AI's `{"cache": {"no-cache": true}}` (its response cache ignores the
    # thinking switch). Set as JSON in the environment.
    llm_extra_body: dict[str, Any] = Field(default_factory=dict)

    # Pipeline
    max_repair_rounds: int = Field(default=3, ge=0)
    # Rounds that ask only for the must-keep facts still missing after the repair loop
    # has stopped (docs/architecture.md §4.6). 0 switches them off.
    max_facts_rounds: int = Field(default=1, ge=0, le=5)
    # How many missing facts one facts-only round asks for. A repair round asks for at
    # most 5 next to its flagged blocks; a facts round has nothing else to do. 10 since
    # the measured dev rerun of 7 October 2026 (docs/prompts.md): fact
    # coverage 79 against 75 percent with 5, no invented value, fewer judge findings.
    max_missing_per_facts_round: int = Field(default=10, ge=1, le=20)
    # The recover round after the facts rounds: up to this many must-keep values still
    # missing in the best version, each asked for alone with its source paragraph
    # (stages.recover_fact, the review page's "Suggest a sentence"), as one new version.
    # On by default since 9 October 2026: on the dev pairs German fact
    # coverage rose from 78 to 96 percent, no invented value added (docs/prompts.md).
    # 0 turns it off.
    max_recover_facts: int = Field(default=10, ge=0, le=20)
    # The polish round after the recover round: up to this many repair rounds on the
    # best version for the rule findings alone, its errors first, then its warnings once
    # no error is left; no fact and no judge's problem. The facts and recover rounds add
    # the source's sentences nearly verbatim, and the loop never sees them again (10 October
    # 2026; measured in docs/prompts.md). 0 turns it off.
    max_polish_rounds: int = Field(default=1, ge=0, le=3)
    # The vocabulary of hard words (rules/data/vocabulary_<lang>.toml) in the pipeline:
    # the checked explanations in the fact sheet, missing glossary entries by code, the
    # LEX-07 findings in the repair rounds and the vocabulary round, a last round for the
    # office words left (docs/architecture.md §4.6). The writer itself gets no list of
    # office words: such a list made the 8B write more of them (docs/prompts.md). Off
    # only to measure what the vocabulary brings, or if a kind of document suffers.
    use_vocabulary: bool = True

    # Jobs (docs/architecture.md §7). Worker threads that run the queued jobs:
    # one is enough for a reviewer's workload; more share one endpoint that serves
    # parallel requests (vLLM does, `--max-num-seqs`).
    job_workers: int = Field(default=1, ge=1, le=16)
    # Jobs that may wait for a worker; a submission beyond that is refused with 429.
    job_queue_limit: int = Field(default=50, ge=1)
    # Seconds a job may run before it is stopped with its finished stages kept (one
    # model call alone may take LLM_TIMEOUT_S times the attempts); 0: no budget.
    job_time_budget_s: float = Field(default=7200.0, ge=0)
    # Submissions read at once: the fetch, the PDF parse and the segmentation run in the
    # request's thread, and beyond this many at a time a submission is refused with 429
    # and asked to try again, so slow documents never fill the thread pool.
    ingest_slots: int = Field(default=4, ge=1, le=32)
    # Days after which a job nobody changed is deleted with its artifacts, calls and
    # cache rows (lifecycle.py), checked every hour. 0 keeps everything.
    data_retention_days: int = Field(default=0, ge=0)

    # Runtime. Document text is only ever logged at DEBUG (docs/architecture.md
    # §10); the level is checked at start, so a typo never crashes the first log call.
    log_level: LogLevel = "INFO"
    # One line per record as text (`LEVEL logger: message key=value`) or as JSON
    # (`{"time", "level", "logger", "message", "request_id", "job_id", ...}`) for a log
    # collector (web/observability.py).
    log_format: LogFormat = "text"
    # Interface language for visitors who have not picked one: a code with a catalog in
    # web/locales/ (en, de), or "auto" for the browser's preference. The switcher in the
    # header overrides it per browser.
    ui_lang: str = "auto"

    # Lets users submit URLs of the private network (an intranet deployment that needs
    # internal pages); the redirect hops are still walked and checked (ingest/fetch.py).
    allow_private_urls: bool = False

    # Deployment (docs/architecture.md §10, web/security.py). The interface the app is
    # published on; `leichtfacile serve --host` sets it. Published on anything but the
    # loopback interface, the app refuses to start without one of the two logins below.
    bind_host: str = "127.0.0.1"
    # A shared secret: browsers are asked for it (HTTP Basic, any user name, the token as
    # the password), scripts send `Authorization: Bearer <token>`. Empty: no login.
    auth_token: SecretStr | None = None
    # Or the header a reverse proxy fills with the user it has logged in
    # (`X-Forwarded-User`, `Remote-User`), trusted only when the request comes from one
    # of the proxy's addresses or networks in AUTH_PROXY_FROM (comma-separated).
    auth_proxy_header: str | None = None
    auth_proxy_from: str = ""
    # Writes and other costly requests (POST, PUT, PATCH, DELETE) one client address may
    # make per minute; 0 turns the limit off.
    rate_limit_per_minute: int = Field(default=120, ge=0)

    @field_validator("log_level", mode="before")
    @classmethod
    def _level_name(cls, value: object) -> object:
        """`LOG_LEVEL=info` means INFO."""
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("log_format", mode="before")
    @classmethod
    def _format_name(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _deployment_is_consistent(self) -> Settings:
        if self.auth_token_value and self.auth_proxy_header:
            raise ValueError("set AUTH_TOKEN or AUTH_PROXY_HEADER, not both")
        if self.auth_proxy_header and not self.proxy_networks:
            raise ValueError(
                "AUTH_PROXY_HEADER needs AUTH_PROXY_FROM, the proxy's addresses or networks "
                "(comma-separated), so that nobody else can send the header"
            )
        if not self.bound_to_loopback and self.auth_mode == "none":
            raise ValueError(
                f"BIND_HOST={self.bind_host!r} publishes the app beyond this machine: set "
                "AUTH_TOKEN (a shared secret) or AUTH_PROXY_HEADER and AUTH_PROXY_FROM (the "
                "reverse proxy's user header), or keep BIND_HOST=127.0.0.1"
            )
        return self

    @property
    def judge_name(self) -> str:
        """LLM_JUDGE_NAME, else the writer's model. What the endpoint serves can change
        that default: `judge_for`."""
        return self.llm_judge_name or self.llm_name

    @property
    def larger_name(self) -> str | None:
        """The 70B of the writer's Apertus family, None for any other writer."""
        larger = _APERTUS_8B.sub(r"\g<1>70\g<2>", self.llm_name)
        return larger if larger != self.llm_name else None

    def judge_for(self, models: Iterable[str]) -> str:
        """The judge's model: LLM_JUDGE_NAME when set; else the 70B of the writer's
        family when the endpoint lists it (the setup the evaluation measured, also when
        only the three required variables are set); else the writer's model (a local
        server with one model)."""
        if self.llm_judge_name:
            return self.llm_judge_name
        larger = self.larger_name
        return larger if larger and larger in set(models) else self.llm_name

    @property
    def understand_name(self) -> str:
        return self.llm_understand_name or self.llm_name

    @property
    def thinking_stages(self) -> set[str]:
        return {s.strip() for s in self.llm_thinking_stages.split(",") if s.strip()}

    @property
    def auth_token_value(self) -> str:
        """The shared secret, "" when none is set."""
        return self.auth_token.get_secret_value() if self.auth_token else ""

    @property
    def auth_mode(self) -> AuthMode:
        if self.auth_proxy_header:
            return "proxy"
        return "token" if self.auth_token_value else "none"

    @property
    def proxy_networks(self) -> list[Network]:
        """The reverse proxy's addresses from AUTH_PROXY_FROM (an address is a network
        of one). Raises ValueError for an entry that is neither."""
        return [
            ipaddress.ip_network(entry.strip(), strict=False)
            for entry in self.auth_proxy_from.split(",")
            if entry.strip()
        ]

    @property
    def bound_to_loopback(self) -> bool:
        """True when BIND_HOST reaches this machine alone (127.0.0.1, ::1, localhost)."""
        host = self.bind_host.strip().strip("[]").lower()
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # values come from the config file, .env and the environment
    return Settings(_env_file=env_files())  # type: ignore[call-arg]


def paths() -> Paths:
    """DATA_DIR and EXAMPLES_DIR without the model settings (no key needed)."""
    return Paths(_env_file=env_files())  # type: ignore[call-arg]
