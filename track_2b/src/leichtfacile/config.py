"""Settings from environment variables (and a local `.env` file during development).

The three variables required by the hackathon template are `LLM_BASE_URL`,
`LLM_API_KEY` and `LLM_NAME`. Everything else has a default.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ThinkingMode = Literal["model-suffix", "chat-template", "off"]
AuthMode = Literal["none", "token", "proxy"]
Network = ipaddress.IPv4Network | ipaddress.IPv6Network

# The 8B of an Apertus family (swiss-ai/Apertus-v1.5-8B, swiss-ai/apertus-v1.5-8b), whose
# 70B judges by default when the endpoint serves it.
_APERTUS_8B = re.compile(r"(apertus\S*-)8(b)$", re.IGNORECASE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Model endpoint (OpenAI-compatible). See .env.example for the supported profiles.
    llm_base_url: str
    llm_api_key: SecretStr
    llm_name: str
    llm_judge_name: str | None = None
    # The Understand stage's model, when it should differ from the writer (the hybrid:
    # the 70B reads, the 8B writes; track_2b/docs/prompts.md compares the tiers). Empty: the
    # writer's model.
    llm_understand_name: str | None = None
    llm_thinking_mode: ThinkingMode = "model-suffix"
    llm_thinking_suffix: str = "-thinking"
    # Stages that use the thinking model. Writing without thinking was faster and closer
    # to easy language in the first local tests (track_2b/docs/prompts.md); the day-1 checks
    # on the CSCS endpoint decide the final setting.
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
    # has stopped (track_2b/docs/architecture.md §4.6). 0 switches them off.
    max_facts_rounds: int = Field(default=1, ge=0, le=5)
    # How many missing facts one facts-only round asks for. A repair round asks for at
    # most 5 next to its flagged blocks; a facts round has nothing else to do. 10 since
    # the measured dev rerun of 7 October 2026 (PLAN.md D-Z, track_2b/docs/prompts.md): fact
    # coverage 79 against 75 percent with 5, no invented value, fewer judge findings.
    max_missing_per_facts_round: int = Field(default=10, ge=1, le=20)
    # The recover round after the facts rounds: up to this many must-keep values still
    # missing in the best version, each asked for alone with its source paragraph
    # (stages.recover_fact, the review page's "Suggest a sentence"), as one new version.
    # On by default since 9 October 2026 (PLAN.md D-AC): on the dev pairs German fact
    # coverage rose from 78 to 96 percent, no invented value added (track_2b/docs/prompts.md).
    # 0 turns it off.
    max_recover_facts: int = Field(default=10, ge=0, le=20)
    # The polish round after the recover round: up to this many repair rounds on the
    # best version for the rule findings alone, its errors first, then its warnings once
    # no error is left; no fact and no judge's problem. The facts and recover rounds add
    # the source's sentences nearly verbatim, and the loop never sees them again (PLAN.md
    # D-AF, 10 October 2026; measured in track_2b/docs/prompts.md). 0 turns it off.
    max_polish_rounds: int = Field(default=1, ge=0, le=3)
    # The vocabulary of hard words (rules/data/vocabulary_<lang>.toml) in the pipeline:
    # the checked explanations in the fact sheet, missing glossary entries by code, the
    # LEX-07 findings in the repair rounds and the vocabulary round, a last round for the
    # office words left (track_2b/docs/architecture.md §4.6). The writer itself gets no list of
    # office words: such a list made the 8B write more of them (track_2b/docs/prompts.md). Off
    # only to measure what the vocabulary brings, or if a kind of document suffers.
    use_vocabulary: bool = True

    # Runtime
    data_dir: Path = Path("track_2b/data")
    log_level: str = "INFO"
    # Interface language for visitors who have not picked one: a code with a catalog in
    # web/locales/ (en, de), or "auto" for the browser's preference. The switcher in the
    # header overrides it per browser.
    ui_lang: str = "auto"

    # Deployment (track_2b/docs/architecture.md §10, web/security.py). The interface the
    # port is published on: docker-compose.yml reads the same variable, so one line in
    # .env publishes the app and tells it so. Published on anything but the loopback
    # interface, the app refuses to start without one of the two logins below.
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
    return Settings()  # type: ignore[call-arg]  # values come from the environment
